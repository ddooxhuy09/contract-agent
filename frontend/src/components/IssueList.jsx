import { useMemo, useState } from "react";
import IssueCard from "./IssueCard";
import { dedupeRisks, sortRisks } from "../lib/riskDisplay";

const FILTERS = [
  { key: "all", label: "Tất cả" },
  { key: "critical", label: "Nghiêm trọng" },
  { key: "warning", label: "Cần chú ý" },
];

export default function IssueList({ risks, openKey, onOpenKeyChange, clausesByNumber }) {
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    const list = dedupeRisks(sortRisks(risks));
    if (filter === "all") return list;
    return list.filter((r) => r.severity === filter);
  }, [risks, filter]);

  return (
    <section className="mb-section-gap animate-fade-in" aria-labelledby="issues-title">
      <div className="flex flex-col xs:flex-row xs:items-end xs:justify-between gap-2.5 mb-3">
        <div>
          <h2 id="issues-title" className="section-title">
            Vấn đề cần xử lý
          </h2>
          <p className="text-ink-muted text-[0.75rem] mt-0.5">{filtered.length} mục</p>
        </div>
        <div
          className="flex rounded-md border border-rule bg-paper-raised overflow-x-auto self-stretch xs:self-start"
          role="tablist"
        >
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              role="tab"
              aria-selected={filter === f.key}
              onClick={() => setFilter(f.key)}
              className={`px-2.5 py-1.5 text-[0.6875rem] font-medium whitespace-nowrap transition-colors ${
                filter === f.key
                  ? "bg-ink text-paper-raised"
                  : "text-ink-muted hover:text-ink hover:bg-quiet-soft/50"
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {filtered.length === 0 ? (
        <div className="border border-dashed border-rule rounded-md h-24 flex items-center justify-center bg-paper-raised px-4">
          <p className="ui-text text-ink-muted text-center">
            {risks?.length
              ? "Không có mục nào trong bộ lọc này."
              : "Không phát hiện vấn đề cần xử lý trong phạm vi đã rà soát."}
          </p>
        </div>
      ) : (
        <div className="border border-rule rounded-md divide-y divide-rule bg-paper-raised shadow-sm overflow-hidden">
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
