/** Normalize + parse risk payloads for Legal Consultant Report UI. */

export function severityLabel(severity) {
  if (severity === "critical") return "Nghiêm trọng";
  if (severity === "warning") return "Cần chú ý";
  return "Ổn";
}

export function cleanText(s) {
  return String(s || "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/^[-•*]+\s+/, "")
    .replace(/^\d+[.)]\s+/, "")
    .trim();
}

/** Strip internal chunk_ref / DB ids from legal_basis strings. */
export function formatLegalBasis(raw) {
  const text = String(raw || "").trim();
  if (!text) return null;

  let s = text.replace(/\[\s*([^\]|]+?)\s*\|\s*[^\]]+\]/g, (_, doc) => doc.trim());
  s = s.replace(/\b\d{3,}:[A-Za-z0-9.]+/g, "");
  s = s
    .replace(/\s*[|]\s*/g, " ")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([,.;:])/g, "$1")
    .replace(/:\s*:/g, ":")
    .trim();
  return s || null;
}

const LABEL_RE =
  /^(Kết\s*luận|Vi\s*phạm\s*pháp\s*luật|Lý\s*do|Rủi\s*ro(?:\s*hợp\s*đồng)?|Khuyến\s*nghị)\s*:\s*(.*)$/i;

function isDraftLabel(cleaned) {
  return /^(Đề xuất câu thay thế|Đề xuất sửa(?: điều khoản)?|Câu thay thế(?: đề xuất)?)\s*:?\s*$/i.test(
    cleaned,
  );
}

export function parseIssue(issue) {
  const text = (issue || "").trim();
  if (!text) {
    return { conclusion: "Chưa có mô tả vấn đề.", reasons: [] };
  }

  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => l.replace(/^[-•*]+\s+/, "").trim());

  let conclusion = "";
  const reasons = [];
  let mode = "start";

  for (const line of lines) {
    const labeled = line.match(LABEL_RE);
    if (labeled) {
      const label = labeled[1].toLowerCase().replace(/\s+/g, " ");
      const rest = labeled[2].trim();
      if (/kết luận|vi phạm/.test(label)) {
        if (!conclusion && rest) conclusion = rest;
        else if (rest) reasons.push(rest);
        mode = "after-conclusion";
      } else if (/lý do|rủi ro/.test(label)) {
        mode = "reasons";
        if (rest) reasons.push(rest);
      }
      continue;
    }

    if (/^Lý\s*do\s*:?\s*$/i.test(line)) {
      mode = "reasons";
      continue;
    }

    if (!conclusion && mode === "start") {
      conclusion = line;
      mode = "after-conclusion";
      continue;
    }

    reasons.push(line);
  }

  if (!conclusion) conclusion = lines[0] || "";

  const cleanConclusion = cleanText(conclusion);
  const cleanReasons = reasons
    .map(cleanText)
    .filter(Boolean)
    .filter((r) => r !== cleanConclusion);

  return {
    conclusion: cleanConclusion || "Chưa có mô tả vấn đề.",
    reasons: cleanReasons,
  };
}

export function parseRecommendation(recommendation) {
  const text = (recommendation || "").trim();
  if (!text) {
    return { sections: [], draft: null };
  }

  const draftMatch = text.match(/«([^»]+)»/);
  const draft = draftMatch ? draftMatch[1].trim() : null;
  const withoutDraft = draft
    ? text.replace(/«[^»]+»/g, "").replace(/\n{2,}/g, "\n").trim()
    : text;

  const lines = withoutDraft
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const sections = [];
  let current = { title: null, items: [] };

  const flush = () => {
    if (current.title || current.items.length) {
      sections.push(current);
      current = { title: null, items: [] };
    }
  };

  for (const line of lines) {
    let raw = line.replace(/^[-•*]+\s+/, "").replace(/^\d+[.)]\s+/, "").trim();
    const cleaned = cleanText(raw);
    if (!cleaned || isDraftLabel(cleaned)) continue;

    const isHeading =
      (/^Đối với\b/i.test(cleaned) || /^Về\b/i.test(cleaned)) && cleaned.length < 140;

    if (
      isHeading ||
      (/:\s*$/.test(cleaned) && cleaned.length < 100 && !/[.!?…]/.test(cleaned.slice(0, -1)))
    ) {
      flush();
      current.title = cleaned.replace(/:$/, "");
      continue;
    }
    current.items.push(cleaned);
  }
  flush();

  const pruned = sections.filter((s) => s.items.length > 0);

  if (!pruned.length && withoutDraft) {
    const fallback = cleanText(withoutDraft.replace(/«[^»]+»/g, ""));
    if (fallback && !isDraftLabel(fallback)) {
      pruned.push({ title: null, items: [fallback] });
    }
  }

  return { sections: pruned, draft };
}

function shortenTitle(text, max = 72) {
  const t = cleanText(text);
  if (!t) return "Vấn đề cần xử lý";
  if (t.length <= max) return t;
  const cut = t.slice(0, max);
  const at = Math.max(cut.lastIndexOf(" "), cut.lastIndexOf(","));
  return `${(at > 40 ? cut.slice(0, at) : cut).trim()}…`;
}

function deriveTopics(reasons, conclusion) {
  const src = [...reasons, conclusion].join(" ").toLowerCase();
  const catalog = [
    { topic: "Làm thêm giờ", keys: ["làm thêm", "overtime", "thêm giờ"] },
    { topic: "Tiền lương OT", keys: ["lương làm thêm", "tiền lương", "ot", "overtime pay"] },
    { topic: "Giới hạn OT", keys: ["giới hạn", "không quá", "vượt quá"] },
    { topic: "Bảo hiểm", keys: ["bảo hiểm", "bhxh", "bhyt"] },
    { topic: "Chấm dứt HĐLĐ", keys: ["chấm dứt", "sa thải", "đơn phương"] },
    { topic: "Thai sản / kết hôn", keys: ["mang thai", "thai sản", "kết hôn"] },
    { topic: "Kỷ luật / phạt tiền", keys: ["kỷ luật", "phạt tiền", "khấu trừ"] },
    { topic: "Tranh chấp", keys: ["tranh chấp", "tòa án", "trọng tài"] },
  ];
  const hit = catalog.filter((c) => c.keys.some((k) => src.includes(k))).map((c) => c.topic);
  return hit.slice(0, 5);
}

/**
 * Unified view-model for IssueCard — works with new structured risks and legacy text.
 */
export function normalizeRiskView(risk, clauseFallback) {
  const parsedIssue = parseIssue(risk.issue);
  const parsedRec = parseRecommendation(risk.recommendation);

  const title =
    (risk.title && String(risk.title).trim()) ||
    shortenTitle(parsedIssue.conclusion, 64);

  const description = parsedIssue.conclusion;

  const reasons =
    (Array.isArray(risk.reasons) && risk.reasons.length
      ? risk.reasons.map(cleanText).filter(Boolean)
      : null) || parsedIssue.reasons;

  const summaryTopics =
    (Array.isArray(risk.summary_topics) && risk.summary_topics.length
      ? risk.summary_topics.map(cleanText).filter(Boolean)
      : null) || deriveTopics(reasons, description);

  const impact = Array.isArray(risk.impact)
    ? risk.impact.map(cleanText).filter(Boolean)
    : [];

  let citations = [];
  if (Array.isArray(risk.legal_citations) && risk.legal_citations.length) {
    // Structured from backend/LLM only — never re-split titles on / or -
    citations = risk.legal_citations
      .map((c) => {
        const title = cleanText(c.title || c.label || "");
        const summary =
          cleanText(c.summary || "") ||
          (Array.isArray(c.points) ? c.points.map(cleanText).filter(Boolean).join(" ") : "");
        return title
          ? {
              title,
              summary,
              docNumber: cleanText(c.doc_number || "") || null,
              location: cleanText(c.location || "") || null,
              article: cleanText(c.article || "") || null,
              clause: cleanText(c.clause || "") || null,
              point: cleanText(c.point || "") || null,
              quote: c.quote ? String(c.quote).trim() : null,
              sourceUrl: c.source_url || c.url || null,
              deepLink: c.deep_link || null,
              sourceElementId: c.source_element_id || null,
              status: cleanText(c.status || c.eff_flag || "") || null,
              evidencePath: c.evidence_path || c.path || null,
            }
          : null;
      })
      .filter(Boolean);
  } else if (risk.legal_basis) {
    // Legacy blob: show as one intact block (no client-side doc-number parsing)
    const text = formatLegalBasis(risk.legal_basis);
    if (text) {
      citations = [
        {
          title: "Căn cứ pháp lý",
          summary: text,
          docNumber: null,
          location: null,
          quote: null,
          sourceUrl: null,
          deepLink: null,
          status: null,
        },
      ];
    }
  }

  const actionsFromStruct = Array.isArray(risk.actions)
    ? risk.actions.map(cleanText).filter(Boolean)
    : [];
  const actionsFromRec = parsedRec.sections.flatMap((s) => s.items);
  const actions = actionsFromStruct.length ? actionsFromStruct : actionsFromRec;

  const revisedClause =
    (risk.revised_clause && String(risk.revised_clause).trim()) ||
    parsedRec.draft ||
    null;

  const originalClause =
    (risk.original_clause && String(risk.original_clause).trim()) ||
    (clauseFallback?.text && String(clauseFallback.text).trim()) ||
    (clauseFallback?.summary && String(clauseFallback.summary).trim()) ||
    null;

  let confidence = null;
  if (typeof risk.confidence === "number" && !Number.isNaN(risk.confidence)) {
    confidence = risk.confidence > 1 ? risk.confidence / 100 : risk.confidence;
    confidence = Math.max(0, Math.min(1, confidence));
  }

  return {
    title,
    description,
    summaryTopics,
    reasons,
    impact,
    citations,
    actions,
    originalClause,
    revisedClause,
    confidence,
  };
}

/** Highlight topic keywords inside a reason string (simple mark tags as parts). */
export function highlightKeywords(text, topics = []) {
  const raw = String(text || "");
  if (!topics.length) return [{ t: "text", v: raw }];

  const keys = topics
    .flatMap((t) => {
      const base = String(t).trim();
      if (!base) return [];
      // also try significant words ≥4 chars
      const words = base.split(/\s+/).filter((w) => w.length >= 4);
      return [base, ...words];
    })
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);

  if (!keys.length) return [{ t: "text", v: raw }];

  const escaped = keys.map((k) => k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`(${escaped.join("|")})`, "gi");
  const parts = [];
  let last = 0;
  let m;
  while ((m = re.exec(raw)) !== null) {
    if (m.index > last) parts.push({ t: "text", v: raw.slice(last, m.index) });
    parts.push({ t: "mark", v: m[1] });
    last = m.index + m[0].length;
  }
  if (last < raw.length) parts.push({ t: "text", v: raw.slice(last) });
  if (!parts.length) parts.push({ t: "text", v: raw });
  return parts;
}

/** Very light token mark: words in revised not in original (case-insensitive). */
export function markChangedTokens(original, revised) {
  const rev = String(revised || "");
  if (!rev) return [{ t: "text", v: "" }];
  if (!original) return [{ t: "text", v: rev }];

  const origSet = new Set(
    String(original)
      .toLowerCase()
      .split(/(\s+)/)
      .filter((t) => t.trim())
      .map((t) => t.replace(/[«»""''.,;:!?()]/g, "")),
  );

  const tokens = rev.split(/(\s+)/);
  return tokens.map((tok) => {
    if (!tok.trim()) return { t: "text", v: tok };
    const bare = tok.replace(/[«»""''.,;:!?()]/g, "").toLowerCase();
    if (bare.length >= 3 && !origSet.has(bare)) return { t: "add", v: tok };
    return { t: "text", v: tok };
  });
}

export function sortRisks(risks) {
  const rank = { critical: 0, warning: 1, ok: 2 };
  return [...(risks || [])].sort((a, b) => {
    const sr = (rank[a.severity] ?? 9) - (rank[b.severity] ?? 9);
    if (sr !== 0) return sr;
    const na = parseInt(String(a.clause_ref || "").replace(/\D/g, ""), 10) || 0;
    const nb = parseInt(String(b.clause_ref || "").replace(/\D/g, ""), 10) || 0;
    return na - nb;
  });
}

export function riskKey(risk, idx) {
  return `${risk.clause_ref || "clause"}-${risk.severity || "x"}-${idx}`;
}
