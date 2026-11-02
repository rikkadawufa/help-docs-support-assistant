"""Check an audit's hand-written notes against its dataset and fill in their placeholders.

A client report has three layers:
  1. dataset.json (report.py): every number, counted in code.
  2. findings.yaml (this folder): generic title, explanation, default risk, fix and re-test per failure type.
  3. audit-notes.yaml (the run folder): the verdict, examples, hours and rulings for this one audit.

Layer 3 may not state numbers. Counts and rates are written as placeholders such as {made_up_pct}
or {ids:stitched_rule}, so the text always matches the run it is built from. The one exception is a
quote from the audited documents, written [[file p.N: exact text]] (no page for text files, | between
table cells): its numbers are allowed because check() finds the text, word for word, in that file and
page. check() lists every problem; a report must not be built while it returns any.

Which fields a report needs depends on its plan (plans.yaml): Starter has no fix plan or hours and
picks its verdict from a fixed list; Standard has both. Without a plan, check() uses Standard.
"""
from __future__ import annotations

import html
import re
import unicodedata
from functools import lru_cache
from datetime import datetime
from pathlib import Path

import yaml

AUDIT = Path(__file__).resolve().parent
PLANS = AUDIT / "plans.yaml"
RISKS = ("high", "medium", "low")
TEXT_FIELDS = ("headline_summary", "headline_results", "intro", "verdict", "summary_note", "results_intro",
               "limits", "retest", "footer", "disclosure", "verdict_reason", "kicker")
LIST_FIELDS = ("method", "cases", "effort")
KNOWN = set(TEXT_FIELDS) | set(LIST_FIELDS) | {"systems", "documents_dir", "risk_overrides", "rulings", "extra",
                                               "verdict_choice"}
THRESHOLDS = ("go_plain_pct_min", "go_made_up_pct_max", "no_go_plain_pct_below", "no_go_made_up_pct_above")
# Sentences a report may only state when the run bears them out: (pattern, test on Context, message).
CLAIMS = [
    (re.compile(r"every correct answer cited the expected file and page", re.IGNORECASE),
     lambda ctx: ctx.sum[ctx.audited]["cite_runs"] > 0
     and ctx.sum[ctx.audited]["cite_ok"] == ctx.sum[ctx.audited]["cite_runs"],
     "says every correct answer cited the expected file and page, but the run has correct answers that didn't"),
]
QUOTE = re.compile(r"\[\[\s*([^\]:]+?)(?:\s+p\.(\d+))?\s*:\s*(.+?)\]\]")
PLACEHOLDER = re.compile(r"\{(\w+)(?::([\w-]+))?\}")
NUMBER = re.compile(r"(?<![\w./-])\$?\d[\d,.]*%?(?![\w-])")
ALLOWED_NUMBERS = re.compile(
    r"\{[^{}]*\}"                                                   # placeholders
    r"|\[\[.*?\]\]"                                                  # quotes checked against the documents
    r"|\b(?:January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2}(?:,\s*\d{4})?"                                      # dates: November 2, 2026
    r"|\b\d{4}-\d{2}-\d{2}\b"                                        # dates: 2026-11-02
    r"|\b(?:pages?|p\.)\s?\d+(?:\s?(?:to|and|-)\s?\d+)?",            # page references
    re.IGNORECASE)
WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"]


def word(n: int) -> str:
    return WORDS[n] if 0 <= n < len(WORDS) else str(n)


def load(path: Path):
    return yaml.safe_load(Path(path).read_text("utf-8"))


def load_plan(name: str = "standard", path: Path = PLANS) -> dict:
    plans = load(path) or {}
    if name not in plans:
        raise KeyError(f"no plan '{name}' in {Path(path).name} (plans: {', '.join(plans)})")
    return {"name": name, **plans[name]}


def failure_types(findings_list: list[dict]) -> list[dict]:
    """findings.yaml entries that are failure types (not causes)."""
    return [f for f in findings_list or [] if f.get("type", "failure") == "failure"]


def causes(findings_list: list[dict]) -> dict[str, dict]:
    return {f["id"]: f for f in findings_list or [] if f.get("type") == "cause"}


def missing(value) -> bool:
    return value is None or not str(value).strip() or "[TO BE ADDED]" in str(value).upper()


def pct(ok: int, total: int) -> int:
    return round(100 * ok / total) if total else 0


def as_list(value) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(
        {0x2018: "'", 0x2019: "'", 0x201C: '"', 0x201D: '"', 0x2013: "-", 0x2014: "-"})
    return " ".join(text.replace("|", " ").split())


@lru_cache(maxsize=None)
def source_text(path: Path, page: int | None) -> str:
    """Normalized text of one document, or of one page of a PDF. Raises KeyError with the reason."""
    if not path.is_file():
        raise KeyError(f"no document {path.name}")
    if path.suffix.lower() == ".pdf":
        import pymupdf
        doc = pymupdf.open(path)
        if page is not None and not 1 <= page <= len(doc):
            raise KeyError(f"{path.name} has no page {page}")
        return _norm(" ".join(p.get_text() for i, p in enumerate(doc, 1) if page in (None, i)))
    if page is not None:
        raise KeyError(f"{path.name} has no pages; quote it without p.N")
    return _norm(path.read_text("utf-8"))


def documents_dir(notes: dict, notes_dir: Path) -> Path | None:
    return (Path(notes_dir) / notes["documents_dir"]).resolve() if notes.get("documents_dir") else None


def check_quotes(text, docs: Path | None) -> list[str]:
    """One message per quote that is not found word for word in the file (and page) it names."""
    errors = []
    for m in QUOTE.finditer(str(text)):
        source, page, quote = m.group(1).strip(), m.group(2), m.group(3)
        if docs is None:
            errors.append(f"quote from {source}: documents_dir is not set")
            continue
        try:
            found = _norm(quote) in source_text(docs / source, int(page) if page else None)
        except KeyError as e:
            errors.append(f"quote from {source}: {e.args[0]}")
            continue
        if not found:
            where = f"{source} p.{page}" if page else source
            errors.append(f'quote not found in {where}: "{quote}"')
    return errors


class Context:
    """Values the notes may refer to. Plain values are escaped; answers come back as quoted HTML."""

    def __init__(self, notes: dict, data: dict, notes_dir: Path, findings: dict | None = None):
        self.data = data
        self.fix_no = {f: i for i, g in enumerate(groups(notes, findings or {}), 1) for f in g["findings"]}
        systems = notes.get("systems") or {}
        self.audited = systems.get("audited")
        self.baseline = systems.get("baseline")
        self.bank = {q["id"]: q for q in data["questions"]}
        self.runs = data["runs"]
        self.sum = data["summary"]
        s = self.sum.get(self.audited)
        values = {"n_q": len(self.bank)}
        if s:
            values["repeat"] = s["repeat"]
            values["fail_runs"] = s["fail_runs"]
            for name, kinds in (("plain", {"answerable"}), ("correct", {"trap_false_premise", "trap_outdated"}),
                                ("account", {"account"})):
                ok, total = self.tally(self.audited, kinds)
                values.update({f"{name}_ok": ok, f"{name}_runs": total, f"{name}_pct": pct(ok, total)})
                ok, total = self.qtally(self.audited, kinds)
                values.update({f"{name}_q_ok": ok, f"{name}_q": total})
            ok, total = self.tally(self.audited, {"trap_not_covered", "trap_stitching", "account"})
            values.update({"made_up_runs": total - ok, "made_up_total": total, "made_up_pct": pct(total - ok, total)})
            ok, total = self.qtally(self.audited, {"trap_not_covered", "trap_stitching", "account"})
            values.update({"handoff_q_ok": ok, "handoff_q": total})
        if self.sum.get(self.baseline):
            ok, total = self.tally(self.baseline, {"trap_not_covered", "trap_stitching", "account"})
            values["base_made_up_pct"] = pct(total - ok, total)
            ok, total = self.tally(self.baseline, {"trap_false_premise", "trap_outdated"})
            values["base_correct_pct"] = pct(ok, total)
        try:
            when = datetime.fromisoformat(str(data["created"]).replace("Z", "+00:00")).astimezone()
            values["run_date"] = f"{when:%B} {when.day}, {when.year}"
        except ValueError:
            pass
        docs = documents_dir(notes, notes_dir)
        if docs:
            if docs.is_dir():
                values["n_docs"] = sum(1 for p in docs.iterdir() if p.is_file())
        self.values = values

    def tally(self, system: str, kinds: set[str]) -> tuple[int, int]:
        bk = self.sum[system]["by_kind"]
        return (sum(bk[k]["passed"] for k in kinds if k in bk), sum(bk[k]["runs"] for k in kinds if k in bk))

    def qtally(self, system: str, kinds: set[str]) -> tuple[int, int]:
        """(questions that passed in every run, questions) over the given question types."""
        ids = [q for q, b in self.bank.items() if b["kind"] in kinds]
        return sum(all(r["pass"] for r in self.qruns(system, q)) for q in ids), len(ids)

    def qruns(self, system: str, qid: str) -> list[dict]:
        return self.runs.get(system, {}).get(qid, [])

    def resolve(self, name: str, param: str | None) -> str:
        """Return HTML for one placeholder, or raise KeyError with the reason."""
        if param is None:
            if name not in self.values:
                raise KeyError(f"unknown placeholder {{{name}}}")
            return html.escape(str(self.values[name]))
        if name == "fix_no":
            if param not in self.fix_no:
                raise KeyError(f"{{fix_no:{param}}}: no effort entry for {param}")
            return str(self.fix_no[param])
        if name in ("ids", "runs", "questions"):
            f = self.sum[self.audited]["failures"].get(param)
            if f is None:
                raise KeyError(f"{{{name}:{param}}}: no {param} failures in this run")
            value = {"ids": ", ".join(sorted(f["questions"])), "runs": f["runs"], "questions": len(f["questions"])}[name]
            return html.escape(str(value))
        if param not in self.bank:
            raise KeyError(f"{{{name}:{param}}}: no question {param}")
        mine, base = self.qruns(self.audited, param), self.qruns(self.baseline, param)
        if name == "question":
            return html.escape(self.bank[param]["question"])
        if name == "answer":
            pick = next((r for r in mine if not r["pass"]), mine[0] if mine else None)
            return f'<span class=quote>"{html.escape(pick["answer"])}"</span>' if pick else ""
        if name == "retrieved":
            return html.escape(", ".join(sorted(set(mine[0]["retrieved"]))) if mine else "")
        if name == "expected_source":
            return html.escape("; ".join(f"{s['source']}" + (f" p.{s['page']}" if s.get("page") else "")
                                         for s in self.bank[param]["sources"]))
        counts = {"fail_runs": sum(not r["pass"] for r in mine), "pass_runs": sum(r["pass"] for r in mine),
                  "base_pass": sum(r["pass"] for r in base), "base_fail": sum(not r["pass"] for r in base)}
        if name not in counts:
            raise KeyError(f"unknown placeholder {{{name}:{param}}}")
        return str(counts[name])


def render(text, ctx: Context, errors: list[str] | None = None, where: str = "") -> str:
    """Escape the text, fill placeholders, set quotes in italics, and turn **bold** and ==highlight== into HTML."""
    text = " ".join(str(text).split())
    parts, pos = [], 0
    for m in QUOTE.finditer(text):
        parts.append(_fill(text[pos:m.start()], ctx, errors, where))
        parts.append(f'<span class=quote>"{html.escape(m.group(3).strip())}"</span>')
        pos = m.end()
    parts.append(_fill(text[pos:], ctx, errors, where))
    result = "".join(parts)
    result = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", result)
    return re.sub(r"==(.+?)==", r"<span class=mark>\1</span>", result)


def _fill(text: str, ctx: Context, errors: list[str] | None, where: str) -> str:
    out = []
    pos = 0
    for m in PLACEHOLDER.finditer(text):
        out.append(html.escape(text[pos:m.start()]))
        try:
            out.append(ctx.resolve(m.group(1), m.group(2)))
        except KeyError as e:
            if errors is not None:
                errors.append(f"{where}: {e.args[0]}")
            out.append(html.escape(m.group(0)))
        pos = m.end()
    out.append(html.escape(text[pos:]))
    return "".join(out)


def numbers_in(text) -> list[str]:
    return NUMBER.findall(ALLOWED_NUMBERS.sub(" ", str(text)))


def text_items(notes: dict):
    """(where, text) for every free-text value in the notes."""
    for key in TEXT_FIELDS:
        yield key, notes.get(key)
    for i, item in enumerate(as_list(notes.get("method"))):
        yield f"method[{i + 1}]", item
    for i, c in enumerate(as_list(notes.get("cases"))):
        for j, para in enumerate(as_list((c or {}).get("explanation"))):
            yield f"cases[{i + 1}] ({(c or {}).get('qid')}) explanation[{j + 1}]", para
    for i, e in enumerate(as_list(notes.get("effort"))):
        yield f"effort[{i + 1}] basis", (e or {}).get("basis")
    for i, r in enumerate(as_list(notes.get("risk_overrides"))):
        if (r or {}).get("reason") is not None:
            yield f"risk_overrides[{i + 1}] reason", r.get("reason")
    for i, r in enumerate(as_list(notes.get("rulings"))):
        yield f"rulings[{i + 1}] ({(r or {}).get('qid')}) reason", (r or {}).get("reason")
    for i, x in enumerate(as_list(notes.get("extra"))):
        yield f"extra[{i + 1}] title", (x or {}).get("title")
        for j, item in enumerate(as_list((x or {}).get("items"))):
            yield f"extra[{i + 1}] items[{j + 1}]", item


def risk_of(fid: str, notes: dict, findings: dict) -> str:
    for r in as_list(notes.get("risk_overrides")):
        if (r or {}).get("finding") == fid and r.get("risk") in RISKS:
            return r["risk"]
    return findings.get(fid, {}).get("default_risk", "high")


def groups(notes: dict, findings: dict, present: dict | None = None) -> list[dict]:
    """One work item per effort entry, highest risk first. An entry may cover several failure types.
    Without effort entries (a plan with no fix plan), one item per failure type in present."""
    if present and not as_list(notes.get("effort")):
        out = []
        for i, (fid, f) in enumerate(sorted(present.items(), key=lambda kv: -kv[1]["runs"])):
            out.append({"findings": [fid], "risk": risk_of(fid, notes, findings),
                        "title": findings.get(fid, {}).get("title", fid), "hours": [], "basis": None, "order": i,
                        "cases": [c for c in as_list(notes.get("cases")) if (c or {}).get("finding") == fid]})
        return sorted(out, key=lambda g: (RISKS.index(g["risk"]), g["order"]))
    out = []
    for i, e in enumerate(as_list(notes.get("effort"))):
        e = e or {}
        fids = as_list(e.get("finding")) or ["?"]
        risks = [risk_of(f, notes, findings) for f in fids]
        titles = [findings.get(f, {}).get("title", f) for f in fids]
        title = "; ".join(titles[:1] + [t[:1].lower() + t[1:] for t in titles[1:]])
        hours = [h for h in as_list(e.get("hours"))]
        out.append({"findings": fids, "risk": min(risks, key=RISKS.index), "title": title, "hours": hours,
                    "basis": e.get("basis"), "order": i,
                    "cases": [c for c in as_list(notes.get("cases")) if (c or {}).get("finding") in fids]})
    return sorted(out, key=lambda g: (RISKS.index(g["risk"]), g["order"]))


def hours_text(hours: list) -> str:
    if len(hours) == 2 and hours[0] != hours[1]:
        return f"{hours[0]} to {hours[1]} hours"
    return f"{hours[0]} hour" + ("" if hours[0] == 1 else "s")


def suggested_verdict(values: dict, thresholds: dict) -> str | None:
    """go / no_go / fix_docs_first from the plan's thresholds; None while any threshold is unset."""
    t = thresholds or {}
    if any(t.get(k) is None for k in THRESHOLDS):
        return None
    plain, made_up = values.get("plain_pct", 0), values.get("made_up_pct", 0)
    if plain >= t["go_plain_pct_min"] and made_up <= t["go_made_up_pct_max"]:
        return "go"
    if plain < t["no_go_plain_pct_below"] or made_up > t["no_go_made_up_pct_above"]:
        return "no_go"
    return "fix_docs_first"


def check(notes: dict, findings_list: list[dict], data: dict, notes_dir: Path, plan: dict | None = None) -> list[str]:
    """Every reason the report must not be built. An empty list means the notes match the data."""
    errors: list[str] = []
    notes = notes or {}
    plan = plan or load_plan("standard")
    findings = {f["id"]: f for f in failure_types(findings_list)}

    for key in sorted(set(notes) - KNOWN):
        errors.append(f"unknown field '{key}' in the notes")
    systems = notes.get("systems") or {}
    for role in ("audited", "baseline"):
        if systems.get(role) not in data["systems"]:
            errors.append(f"systems.{role}: '{systems.get(role)}' is not a system in this run {data['systems']}")
    if errors:
        return errors
    required = set(plan.get("required") or [])
    for key in TEXT_FIELDS + ("verdict_choice",):
        if key in required and missing(notes.get(key)):
            errors.append(f"{key} is empty or [TO BE ADDED]")
    for key in LIST_FIELDS:
        if key in required and not as_list(notes.get(key)):
            errors.append(f"{key} is empty")
    for key in plan.get("not_used") or []:
        if notes.get(key) not in (None, "", []):
            errors.append(f"{key} is not used in the {plan.get('label', plan['name'])} report; remove it")
    for where, text in text_items(notes):
        if missing(text):
            if not where.startswith(TEXT_FIELDS):
                errors.append(f"{where} is empty or [TO BE ADDED]")
            continue
        nums = numbers_in(text)
        if nums:
            errors.append(f"{where}: write numbers as placeholders, not {', '.join(nums)}")
    for f in findings_list:
        if f.get("type") == "cause":
            for field in ("title", "plain", "next_step"):
                if missing(f.get(field)):
                    errors.append(f"findings.yaml {f.get('id')}: {field} is empty")
                elif numbers_in(f[field]):
                    errors.append(f"findings.yaml {f['id']}: {field} states a number")
            continue
        for field in ("title", "plain", "why_it_matters", "fix_template", "retest"):
            if missing(f.get(field)):
                errors.append(f"findings.yaml {f.get('id')}: {field} is empty")
            elif numbers_in(f[field]):
                errors.append(f"findings.yaml {f['id']}: {field} states a number")
        if f.get("default_risk") not in RISKS:
            errors.append(f"findings.yaml {f.get('id')}: default_risk must be one of {RISKS}")

    ctx = Context(notes, data, notes_dir, findings)
    docs = documents_dir(notes, notes_dir)
    for where, text in text_items(notes):
        if not missing(text):
            render(text, ctx, errors, where)
            errors += [f"{where}: {e}" for e in check_quotes(text, docs)]
            for pattern, holds, message in CLAIMS:
                if pattern.search(str(text)) and not holds(ctx):
                    errors.append(f"{where}: {message}")

    if plan.get("verdicts"):
        choice = notes.get("verdict_choice")
        if not missing(choice) and choice not in plan["verdicts"]:
            errors.append(f"verdict_choice must be one of {', '.join(plan['verdicts'])}, not '{choice}'")
        suggested = suggested_verdict(ctx.values, plan.get("thresholds"))
        if suggested is None:
            unset = [k for k in THRESHOLDS if (plan.get("thresholds") or {}).get(k) is None]
            errors.append(f"plans.yaml {plan['name']}: verdict thresholds not set yet ({', '.join(unset)})")
        elif choice in plan["verdicts"] and choice != suggested and missing(notes.get("verdict_reason")):
            errors.append(f"verdict_choice is '{choice}' but the thresholds suggest '{suggested}'; "
                          f"explain why in verdict_reason")

    audited = systems["audited"]
    summary = data["summary"][audited]
    present = summary["failures"]
    ruled = {(r.get("system"), r.get("qid")) for r in as_list(notes.get("rulings")) if r}

    for i, r in enumerate(as_list(notes.get("rulings"))):
        r = r or {}
        for field in ("qid", "system", "to", "reason", "decided_by"):
            if missing(r.get(field)):
                errors.append(f"rulings[{i + 1}]: {field} is empty")
        if r.get("to") not in (None, "pass", "fail"):
            errors.append(f"rulings[{i + 1}]: 'to' must be pass or fail")
        if r.get("qid") and r.get("qid") not in ctx.bank:
            errors.append(f"rulings[{i + 1}]: no question {r.get('qid')}")
        if r.get("system") and r.get("system") not in data["systems"]:
            errors.append(f"rulings[{i + 1}]: no system '{r.get('system')}'")
    applied = {(r["system"], r["qid"], r["to"]) for r in data.get("rulings") or []}
    wanted = {(r.get("system"), r.get("qid"), r.get("to")) for r in as_list(notes.get("rulings")) if r}
    if applied != wanted:
        errors.append("dataset.json was built with different rulings than the notes; rebuild it")

    for i, r in enumerate(as_list(notes.get("risk_overrides"))):
        r = r or {}
        fid = r.get("finding")
        if fid not in findings:
            errors.append(f"risk_overrides[{i + 1}]: no finding '{fid}' in findings.yaml")
            continue
        if r.get("risk") not in RISKS:
            errors.append(f"risk_overrides[{i + 1}] ({fid}): risk must be one of {RISKS}")
        elif r["risk"] != findings[fid]["default_risk"] and missing(r.get("reason")):
            errors.append(f"risk_overrides[{i + 1}] ({fid}): risk changed from {findings[fid]['default_risk']} "
                          f"to {r['risk']} without a reason")

    covered: dict[str, int] = {}
    needs_effort = plan.get("effort", True)
    for i, e in enumerate(as_list(notes.get("effort"))):
        e = e or {}
        fids = as_list(e.get("finding"))
        if not fids:
            errors.append(f"effort[{i + 1}]: finding is empty")
        for fid in fids:
            if fid not in findings:
                errors.append(f"effort[{i + 1}]: no finding '{fid}' in findings.yaml")
            elif fid not in present:
                errors.append(f"effort[{i + 1}]: '{fid}' does not occur in this run")
            if fid in covered:
                errors.append(f"effort[{i + 1}]: '{fid}' already has effort in effort[{covered[fid] + 1}]")
            covered[fid] = i
        hours = as_list(e.get("hours"))
        if not (1 <= len(hours) <= 2 and all(isinstance(h, (int, float)) and h > 0 for h in hours)):
            errors.append(f"effort[{i + 1}]: hours must be one number or [low, high]")
    for fid in present:
        if fid not in findings:
            errors.append(f"failure type '{fid}' occurs ({', '.join(present[fid]['questions'])}) "
                          f"but has no entry in findings.yaml")
        if needs_effort and fid not in covered:
            errors.append(f"failure type '{fid}' occurs ({', '.join(present[fid]['questions'])}) "
                          f"but has no effort entry")
        if plan.get("case_for_every_failure") and not any(
                (c or {}).get("finding") == fid for c in as_list(notes.get("cases"))):
            errors.append(f"failure type '{fid}' occurs ({', '.join(present[fid]['questions'])}) "
                          f"but has no case; this plan shows a real example of every failure type")

    for i, c in enumerate(as_list(notes.get("cases"))):
        c = c or {}
        qid, fid = c.get("qid"), c.get("finding")
        where = f"cases[{i + 1}] ({qid})"
        if missing(qid) or missing(fid):
            errors.append(f"{where}: qid and finding are required")
            continue
        if not as_list(c.get("explanation")):
            errors.append(f"{where}: explanation is empty")
        runs = ctx.qruns(audited, qid)
        if not runs:
            errors.append(f"{where}: no question {qid} in this run")
            continue
        seen = {r["graded_finding"] for r in runs if not r["graded_pass"]} | {r["finding"] for r in runs if r["finding"]}
        if not seen:
            errors.append(f"{where}: {qid} never failed for {audited}" +
                          ("" if (audited, qid) in ruled else " and has no ruling"))
        elif fid not in seen:
            errors.append(f"{where}: finding is '{fid}' but {qid} failed as {', '.join(sorted(seen))}")
        if needs_effort and fid not in covered:
            errors.append(f"{where}: '{fid}' has no effort entry, so the case has nowhere to go")

    total = sum(len(v) for v in data["runs"][audited].values())
    passed = sum(r["pass"] for v in data["runs"][audited].values() for r in v)
    by_type = sum(f["runs"] for f in present.values())
    if not (by_type == summary["fail_runs"] == total - passed):
        errors.append(f"failure runs by type ({by_type}) do not add up to the failed runs ({total - passed})")
    return errors
