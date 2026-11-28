import { useMemo } from "react";
import IssueCard from "./IssueCard";
import { dedupeRisks, sortRisks } from "../lib/riskDisplay";

const FILTERS = [
  { key: "all", label: "Tất cả" },
  { key: "critical", label: "Nghiêm trọng" },
  { key: "warning", label: "Cần chú ý" },
  { key: "info", label: "Góp ý" },
];

export default function IssueList({ risks, openKey, onOpenKeyChange, clausesByNumber, filter, onFilterChange }) {
  const all = useMemo(() => dedupeRisks(sortRisks(risks)), [risks]);
  const counts = useMemo(() => {
    const c = { all: all.length, critical: 0, warning: 0, info: 0 };
    for (const r of all) if (r.severity in c) c[r.severity] += 1;
    return c;
  }, [all]);
  const filtered = filter === "all" ? all : all.filter((r) => r.severity === filter);

  return (
    <section id="issues" className="mb-section-gap animate-fade-in scroll-mt-20" aria-labelledby="issues-title">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3 mb-3">
        <h2 id="issues-title" className="text-[1.125rem] font-semibold text-ink">
          Vấn đề cần xử lý
        </h2>
        <div className="flex gap-1.5 overflow-x-auto pb-0.5" role="tablist" aria-label="Lọc theo mức độ">
          {FILTERS.map((f) => {
            const active = filter === f.key;
            return (
              <button
                key={f.key}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => onFilterChange(f.key)}
                className={`inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full border text-[0.8125rem] font-medium whitespace-nowrap transition-colors ${
                  active
                    ? "bg-quiet border-quiet text-white shadow-sm"
                    : "bg-paper-raised border-rule text-ink-muted hover:border-quiet/40 hover:text-ink"
                }`}
              >
                {f.label}
                <span
                  className={`text-[0.75rem] tabular-nums px-1.5 rounded-full ${
                    active ? "bg-white/20 text-white" : "bg-surface-container text-ink-faint"
                  }`}
                >
                  {counts[f.key]}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="border border-dashed border-rule-strong rounded-xl py-10 flex flex-col items-center justify-center gap-1.5 bg-paper-raised px-4">
          <span className="material-symbols-outlined text-ok !text-[2rem]">task_alt</span>
          <p className="ui-text text-ink-muted text-center">
            {risks?.length
              ? "Không có mục nào trong bộ lọc này."
              : "Không phát hiện vấn đề cần xử lý trong phạm vi đã rà soát."}
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((risk) => {
            const num = String(risk.clause_ref || "").replace(/\D/g, "");
            const clause = num ? clausesByNumber?.get(num) : null;
            return (
              <IssueCard
                key={risk.key}
                cardId={`issue-${risk.key}`}
                risk={risk}
                clauseFallback={clause}
                open={openKey === risk.key}
                onToggle={() => onOpenKeyChange(openKey === risk.key ? null : risk.key)}
              />
            );
          })}
        </div>
      )}
    </section>
  );
}
