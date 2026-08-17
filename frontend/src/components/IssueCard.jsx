import { useMemo, useState } from "react";
import {
  highlightKeywords,
  markChangedTokens,
  normalizeRiskView,
  severityLabel,
} from "../lib/riskDisplay";

function Section({ icon, tone, title, hint, children }) {
  const tones = {
    stamp: "border-stamp/20 bg-stamp-soft/30 text-stamp",
    caution: "border-caution/25 bg-caution-soft/40 text-caution",
    quiet: "border-quiet/20 bg-quiet-soft/50 text-quiet",
    ok: "border-ok/25 bg-ok-soft/40 text-ok",
    ink: "border-rule bg-paper text-ink-muted",
  };
  const t = tones[tone] || tones.ink;

  return (
    <div className="rounded-md border border-rule overflow-hidden">
      <div className={`flex items-center gap-2 px-3 py-2 border-b border-rule ${t}`}>
        <span className="material-symbols-outlined !text-[1rem]">{icon}</span>
        <div className="min-w-0">
          <p className="text-[0.6875rem] font-medium uppercase tracking-wide text-ink">{title}</p>
          {hint && <p className="text-[0.625rem] text-ink-muted leading-snug">{hint}</p>}
        </div>
      </div>
      <div className="px-3 py-2.5 bg-paper-raised">{children}</div>
    </div>
  );
}

function MarkedText({ parts }) {
  return (
    <>
      {parts.map((p, i) => {
        if (p.t === "mark") {
          return (
            <mark key={i} className="bg-caution-soft text-ink rounded-sm px-0.5">
              {p.v}
            </mark>
          );
        }
        if (p.t === "add") {
          return (
            <span key={i} className="bg-ok-soft text-ink rounded-sm px-0.5">
              {p.v}
            </span>
          );
        }
        return <span key={i}>{p.v}</span>;
      })}
    </>
  );
}

export default function IssueCard({ risk, open, onToggle, cardId, clauseFallback }) {
  const view = useMemo(
    () => normalizeRiskView(risk, clauseFallback),
    [risk, clauseFallback],
  );
  const [copied, setCopied] = useState(false);
  const [reasonsExpanded, setReasonsExpanded] = useState(false);

  const isCritical = risk.severity === "critical";
  const rail = isCritical ? "border-l-stamp" : "border-l-caution";
  const badge = isCritical
    ? "bg-stamp text-paper-raised"
    : "bg-caution text-paper-raised";

  const visibleReasons = reasonsExpanded ? view.reasons : view.reasons.slice(0, 2);
  const hasMoreReasons = view.reasons.length > 2;

  const revisedParts = useMemo(
    () => markChangedTokens(view.originalClause, view.revisedClause),
    [view.originalClause, view.revisedClause],
  );

  const copyRevised = async () => {
    if (!view.revisedClause) return;
    try {
      await navigator.clipboard.writeText(view.revisedClause);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  return (
    <article id={cardId} className={`border-l-[3px] ${rail} scroll-mt-20`}>
      <button
        type="button"
        onClick={onToggle}
        className="w-full text-left px-3 sm:px-4 py-3 flex items-start gap-3 hover:bg-quiet-soft/30 transition-colors"
        aria-expanded={open}
      >
        <div className="flex-1 min-w-0 grid grid-cols-1 sm:grid-cols-[7rem_1fr] gap-2 sm:gap-4 items-start">
          <div className="flex flex-wrap items-center gap-1.5 sm:flex-col sm:items-start sm:gap-1.5">
            <h3 className="text-[0.8125rem] font-medium text-ink">
              {risk.clause_ref || "Điều khoản"}
            </h3>
            <span
              className={`inline-flex items-center gap-1 px-1.5 py-1 text-[0.625rem] font-semibold uppercase tracking-wide rounded-sm ${badge}`}
            >
              <span className="material-symbols-outlined !text-[0.75rem]" style={{ fontVariationSettings: "'FILL' 1" }}>
                {isCritical ? "error" : "warning"}
              </span>
              {severityLabel(risk.severity)}
            </span>
            {typeof view.confidence === "number" && (
              <span className="text-[0.625rem] text-ink-faint tabular-nums">
                Tin cậy {Math.round(view.confidence * 100)}%
              </span>
            )}
          </div>
          <div className="min-w-0">
            <p className="text-[0.875rem] font-medium text-ink leading-snug">{view.title}</p>
            {view.description && view.description !== view.title && (
              <p className="mt-1 text-[0.75rem] text-ink-muted leading-relaxed line-clamp-2">
                {view.description}
              </p>
            )}
          </div>
        </div>
        <span className="material-symbols-outlined text-ink-faint shrink-0 !text-[1.125rem]">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>

      {open && (
        <div className="px-3 sm:px-4 pb-4 sm:pl-[calc(7rem+1rem+1rem)] space-y-3 border-t border-rule pt-3">
          {view.summaryTopics.length > 0 && (
            <Section icon="bolt" tone={isCritical ? "stamp" : "caution"} title="Tóm tắt" hint="Scan trong vài giây">
              <p className="text-[0.75rem] text-ink-muted mb-2">Điều khoản này liên quan / vi phạm về:</p>
              <div className="flex flex-wrap gap-1.5">
                {view.summaryTopics.map((t) => (
                  <span
                    key={t}
                    className="inline-flex items-center px-2 py-1 rounded-sm bg-paper border border-rule text-[0.6875rem] font-medium text-ink"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </Section>
          )}

          {view.reasons.length > 0 && (
            <Section icon="help" tone="ink" title="Vì sao sai" hint="Lý do chính">
              <ul className="space-y-2 ui-text text-ink-muted">
                {visibleReasons.map((r, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="shrink-0 mt-1.5 w-1 h-1 rounded-full bg-rule-strong" />
                    <span>
                      <MarkedText parts={highlightKeywords(r, view.summaryTopics)} />
                    </span>
                  </li>
                ))}
              </ul>
              {hasMoreReasons && (
                <button
                  type="button"
                  className="mt-2 text-[0.6875rem] font-medium text-quiet hover:text-ink"
                  onClick={() => setReasonsExpanded((v) => !v)}
                >
                  {reasonsExpanded ? "Thu gọn" : `Xem thêm (${view.reasons.length - 2})`}
                </button>
              )}
            </Section>
          )}

          {view.impact.length > 0 && (
            <Section icon="gavel" tone="stamp" title="Ảnh hưởng" hint="Nếu giữ nguyên điều khoản này">
              <ul className="space-y-2 ui-text text-ink">
                {view.impact.map((item, i) => (
                  <li key={i} className="flex gap-2">
                    <span className="material-symbols-outlined text-stamp !text-[0.875rem] shrink-0 mt-0.5">
                      report
                    </span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {view.citations.length > 0 && (
            <Section icon="menu_book" tone="quiet" title="Căn cứ pháp luật" hint="Nguồn đối chiếu">
              <ul className="space-y-2.5">
                {view.citations.map((c, i) => (
                  <li key={i} className="rounded-md border border-rule bg-paper px-2.5 py-2">
                    <p className="text-[0.75rem] font-medium text-quiet flex items-start gap-1.5">
                      <span className="material-symbols-outlined !text-[0.875rem] mt-0.5">book_2</span>
                      <span>{c.title}</span>
                    </p>
                    {c.summary ? (
                      <p className="mt-1.5 text-[0.75rem] text-ink-muted pl-5">{c.summary}</p>
                    ) : null}
                    {(c.docNumber || c.location || c.status) && (
                      <p className="mt-2 pl-5 text-[0.6875rem] text-ink-faint">
                        {[c.docNumber, c.location, c.status].filter(Boolean).join(" · ")}
                      </p>
                    )}
                    {c.quote ? (
                      <blockquote className="mt-2 pl-5 border-l-2 border-quiet/30 text-[0.75rem] leading-relaxed text-ink whitespace-pre-wrap">
                        {c.quote}
                      </blockquote>
                    ) : null}
                    {c.deepLink || c.sourceUrl ? (
                      <a
                        href={c.deepLink || c.sourceUrl}
                        target="_blank"
                        rel="noreferrer"
                        className="mt-2 pl-5 inline-flex items-center gap-1 text-[0.6875rem] font-medium text-quiet hover:text-ink"
                      >
                        <span className="material-symbols-outlined !text-[0.875rem]">open_in_new</span>
                        {c.deepLink ? "Mở đúng vị trí trên VBPL" : "Mở văn bản nguồn"}
                      </a>
                    ) : null}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {view.actions.length > 0 && (
            <Section icon="checklist" tone="ok" title="Việc cần làm" hint="Checklist chỉnh sửa">
              <ul className="space-y-1.5">
                {view.actions.map((a, i) => (
                  <li key={i} className="flex gap-2 ui-text text-ink">
                    <span className="material-symbols-outlined text-ok !text-[1rem] shrink-0">
                      check_circle
                    </span>
                    <span>{a}</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {(view.originalClause || view.revisedClause) && (
            <Section
              icon="edit_note"
              tone="ok"
              title="AI đã sửa điều khoản"
              hint="So sánh gốc ↔ bản chỉnh; có thể copy bản mới"
            >
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-2.5">
                {view.originalClause && (
                  <div className="rounded-md border border-rule bg-paper p-2.5">
                    <p className="meta-text text-ink-faint uppercase mb-1.5">Điều khoản gốc</p>
                    <p className="ui-text text-ink-muted whitespace-pre-wrap">{view.originalClause}</p>
                  </div>
                )}
                {view.revisedClause && (
                  <div className="rounded-md border border-ok/30 bg-ok-soft/40 p-2.5">
                    <p className="meta-text text-ok uppercase mb-1.5">Điều khoản sau chỉnh sửa</p>
                    <p className="ui-text text-ink whitespace-pre-wrap">
                      <MarkedText parts={revisedParts} />
                    </p>
                  </div>
                )}
              </div>
              {view.revisedClause && (
                <button
                  type="button"
                  onClick={copyRevised}
                  className="mt-2.5 inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-ink text-paper-raised text-[0.75rem] font-medium hover:bg-ink/90 transition-colors"
                >
                  <span className="material-symbols-outlined !text-[1rem]">content_copy</span>
                  {copied ? "Đã sao chép điều khoản đã sửa" : "Sao chép điều khoản đã sửa"}
                </button>
              )}
            </Section>
          )}
        </div>
      )}
    </article>
  );
}
