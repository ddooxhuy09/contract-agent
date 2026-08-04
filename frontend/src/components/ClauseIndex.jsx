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
    <section className="mb-section-gap border border-rule rounded-md bg-paper-raised shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-3.5 sm:px-4 py-2.5 text-left hover:bg-quiet-soft/30 transition-colors"
        aria-expanded={open}
      >
        <span className="section-title flex items-baseline gap-1.5">
          Mục lục điều khoản
          <span className="text-[0.75rem] font-normal text-ink-faint">({rows.length})</span>
        </span>
        <span className="material-symbols-outlined text-ink-faint !text-[1.125rem]">
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
                <div key={num} className="px-3.5 sm:px-4 py-2.5">
                  <div className="flex items-start gap-2">
                    <button
                      type="button"
                      className="flex-1 text-left min-w-0"
                      onClick={() => setExpanded(isOpen ? null : num)}
                    >
                      <div className="flex flex-wrap items-center gap-1.5">
                        <span className="text-[0.8125rem] font-medium text-ink-faint tabular-nums w-6 shrink-0">
                          {clause.clause_number}
                        </span>
                        <span className="text-[0.8125rem] font-medium text-ink">
                          {clause.title || `Điều ${clause.clause_number}`}
                        </span>
                        {top && (
                          <span
                            className={`text-[0.625rem] font-medium uppercase tracking-wide px-1 py-0.5 rounded-sm ${
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
                        <p className="mt-1.5 ui-text text-ink-muted pl-6">{clause.summary}</p>
                      )}
                    </button>
                    {top && (
                      <button
                        type="button"
                        onClick={() => onOpenIssueKey?.(top.key)}
                        className="text-[0.6875rem] font-medium text-quiet shrink-0 hover:text-ink pt-0.5"
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
