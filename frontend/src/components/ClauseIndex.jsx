import { useMemo, useState } from "react";
import { severityLabel } from "../lib/riskDisplay";

export default function ClauseIndex({ clauses, risksByClause, onOpenIssueKey, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const [expanded, setExpanded] = useState(null);

  const rows = useMemo(() => {
    return (clauses || []).map((c) => {
      const num = String(c.clause_number);
      const linked = risksByClause.get(num) || [];
      const top = linked.find((x) => x.severity === "critical") || linked[0];
      return { clause: c, linked, top };
    });
  }, [clauses, risksByClause]);

  return (
    <section className="mb-section-gap card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-4 sm:px-5 py-3.5 text-left hover:bg-quiet-soft/40 transition-colors"
        aria-expanded={open}
      >
        <span className="section-title flex items-center gap-2.5">
          <span className="material-symbols-outlined text-quiet">list_alt</span>
          Mục lục điều khoản
          <span className="text-[0.8125rem] font-normal text-ink-faint">({rows.length})</span>
        </span>
        <span className="material-symbols-outlined text-ink-faint">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>

      {open && (
        <div className="border-t border-rule divide-y divide-rule max-h-[min(28rem,50vh)] overflow-y-auto">
          {rows.length === 0 ? (
            <p className="px-3.5 py-3 ui-text text-ink-muted">Không trích xuất được điều khoản nào.</p>
          ) : (
            rows.map(({ clause, linked, top }) => {
              const num = String(clause.clause_number);
              const isOpen = expanded === num;
              return (
                <div key={num} className="px-4 sm:px-5 py-3">
                  <div className="flex items-start gap-2">
                    <button
                      type="button"
                      className="flex-1 text-left min-w-0"
                      onClick={() => setExpanded(isOpen ? null : num)}
                    >
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[0.875rem] font-medium text-ink-faint tabular-nums w-7 shrink-0">
                          {clause.clause_number}
                        </span>
                        <span className="text-[0.875rem] font-medium text-ink">
                          {clause.title || `Điều ${clause.clause_number}`}
                        </span>
                        {top && (
                          <span
                            className={`text-[0.6875rem] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full ${
                              top.severity === "critical"
                                ? "bg-stamp-soft text-stamp"
                                : "bg-caution-soft text-caution"
                            }`}
                          >
                            {severityLabel(top.severity)}
                            {linked.length > 1 ? ` · ${linked.length}` : ""}
                          </span>
                        )}
                      </div>
                      {isOpen && (
                        <p className="mt-1.5 ui-text text-ink-muted pl-7">{clause.summary}</p>
                      )}
                    </button>
                    {top && (
                      <button
                        type="button"
                        onClick={() => onOpenIssueKey?.(top.key)}
                        className="text-[0.8125rem] font-medium text-quiet shrink-0 hover:underline pt-0.5"
                      >
                        Xem lỗi
                      </button>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}
    </section>
  );
}
