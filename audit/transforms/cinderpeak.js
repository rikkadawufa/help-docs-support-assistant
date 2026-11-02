// Turns a reply from this demo's POST /ask into the shape audit/grade.py reads.
// Every target gets its own transform like this one; only this file changes per client.
//   answered:  true / false, or null when the API only returns free text
//   citations: sources the answer itself points to, or null when the API never returns any
//   retrieved: passages the retriever returned (empty if the API doesn't expose them)

function parseLabel(label) {
  // "warranty.pdf p.2" or "faq.md > Shipping" (Markdown has no pages -> page 0)
  const m = /^(.+?) p\.(\d+)$/.exec(label || '');
  if (m) return { source: m[1], page: Number(m[2]) };
  return { source: String(label || '').split(' > ')[0], page: 0 };
}

module.exports = (json) => {
  const status = json.status;
  const freeText = status === 'baseline'; // the simple RAG returns text only: no status, no citations
  return JSON.stringify({
    answered: freeText ? null : status === 'answered',
    answer: json.answer || '',
    citations: freeText ? null : (json.citations || []).map((c) => ({ source: c.source, page: Number(c.page || 0) })),
    retrieved: (json.retrieved || []).map((r) => parseLabel(r.label)),
  });
};
