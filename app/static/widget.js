// Shared helpers for the chat widget and the compare page. No dependencies.

async function postJSON(url, body) {
  const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function el(tag, cls, text) {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text !== undefined) node.textContent = text;
  return node;
}

const STATUS = {
  answered: { cls: "ok", text: "Answered from our help docs" },
  handoff: { cls: "warn", text: "Passed to a person" },
  degraded: { cls: "bad", text: "AI unavailable, passed to a person" },
  baseline: { cls: "", text: "Simple RAG answer (no checks)" },
};

function badge(status) {
  const s = STATUS[status] || { cls: "", text: status };
  const b = el("div", `badge ${s.cls}`);
  b.append(el("span", "dot"), document.createTextNode(s.text));
  return b;
}

// Highlight the cited quote inside the full passage, keeping its line breaks.
// Words must match in order; spaces, line breaks and table pipes between them may differ.
function highlight(container, text, quote) {
  const words = quote.toLowerCase().match(/[a-z0-9$'.\-]+/g) || [];
  const escaped = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const m = escaped.length ? new RegExp(escaped.join("[\\s|:,;\"]+"), "i").exec(text) : null;
  if (!m) { container.textContent = text; return; }
  container.append(document.createTextNode(text.slice(0, m.index)), el("mark", "", m[0]),
    document.createTextNode(text.slice(m.index + m[0].length)));
}

function sourceList(citations) {
  const wrap = el("div", "sources");
  for (const c of citations) {
    const btn = el("button", "src");
    btn.type = "button";
    btn.append(el("span", "label", "\u{1F4C4} " + c.label), el("span", "quote", `“${c.quote}”`));
    const full = el("div", "full");
    btn.append(full);
    btn.addEventListener("click", async () => {
      btn.classList.toggle("open");
      if (!full.dataset.loaded) {
        full.dataset.loaded = "1";
        full.textContent = "Loading passage…";
        try {
          const res = await fetch(`/source/${encodeURIComponent(c.chunk_id)}`);
          const data = await res.json();
          full.textContent = "";
          highlight(full, data.text, c.quote);
          const mark = full.querySelector("mark");
          if (mark) mark.scrollIntoView({ block: "center" });
        } catch { full.textContent = "Could not load this passage."; }
      }
    });
    wrap.append(btn);
  }
  return wrap;
}

function renderReply(reply) {
  const box = el("div", `msg bot ${reply.status}`);
  box.append(badge(reply.status), el("div", "text", reply.answer));
  if (reply.citations && reply.citations.length) box.append(sourceList(reply.citations));
  return box;
}
