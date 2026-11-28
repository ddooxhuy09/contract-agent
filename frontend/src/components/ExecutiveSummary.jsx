import { severityLabel } from "../lib/riskDisplay";

const TONES = {
  stamp: { card: "border-stamp/25 bg-stamp-soft/40", icon: "bg-stamp text-white", name: "error" },
  caution: { card: "border-caution/30 bg-caution-soft/50", icon: "bg-caution text-white", name: "warning" },
  ok: { card: "border-ok/25 bg-ok-soft/40", icon: "bg-ok text-white", name: "check_circle" },
};

export default function ExecutiveSummary({
  criticalCount,
  warningCount,
  okClauseCount,
  uncheckedCount = 0,
  clauseCount = 0,
  topIssues,
  onOpenIssue,
  onFilter,
}) {
  const hasProblems = criticalCount + warningCount > 0;

  let tone = TONES.ok;
  let verdict = "Không phát hiện vấn đề trọng yếu";
  let detail = "Trong phạm vi các điều khoản đã rà soát.";
  if (criticalCount > 0) {
    tone = TONES.stamp;
    verdict = `Có ${criticalCount} vấn đề nghiêm trọng`;
    detail = "Nên xử lý trước khi ký hoặc thực hiện hợp đồng.";
  } else if (warningCount > 0) {
    tone = TONES.caution;
    verdict = "Chưa thấy vi phạm nghiêm trọng";
    detail = `Còn ${warningCount} điểm cần chú ý trước khi chốt.`;
  } else if (uncheckedCount > 0) {
    tone = TONES.caution;
    verdict = "Chưa thể kết luận";
    detail = `${uncheckedCount}/${clauseCount} điều khoản chưa kiểm được, hãy bấm "Phân tích lại".`;
  }

  const stats = [
    { label: "Nghiêm trọng", value: criticalCount, text: "text-stamp", chip: "bg-stamp-soft text-stamp", icon: "error", filter: "critical" },
    { label: "Cần chú ý", value: warningCount, text: "text-caution", chip: "bg-caution-soft text-caution", icon: "warning", filter: "warning" },
    { label: "Ổn", value: okClauseCount, text: "text-ok", chip: "bg-ok-soft text-ok", icon: "check_circle" },
    ...(uncheckedCount > 0
      ? [{ label: "Chưa kiểm", value: uncheckedCount, text: "text-ink-muted", chip: "bg-surface-container text-ink-muted", icon: "help" }]
      : []),
  ];

  return (
    <section className="mb-section-gap animate-fade-in" aria-labelledby="exec-summary-title">
      <div className={`rounded-xl border shadow-[0_1px_2px_rgba(22,27,38,0.05),0_4px_14px_-6px_rgba(22,27,38,0.10)] ${tone.card}`}>
        <div className="p-4 sm:p-5">
          <div className="flex items-start gap-3.5">
            <span className={`w-11 h-11 rounded-xl flex items-center justify-center shrink-0 ${tone.icon}`}>
              <span className="material-symbols-outlined !text-[1.5rem]" style={{ fontVariationSettings: "'FILL' 1" }}>
                {tone.name}
              </span>
            </span>
            <div className="min-w-0">
              <p className="meta-text text-ink-faint uppercase">Kết luận nhanh</p>
              <h2 id="exec-summary-title" className="text-[1.25rem] sm:text-[1.375rem] font-semibold text-ink leading-snug">
                {verdict}
              </h2>
              <p className="text-[0.9375rem] text-ink-muted mt-0.5">{detail}</p>
            </div>
          </div>

          <div className={`mt-4 grid gap-2.5 sm:gap-3 grid-cols-2 ${stats.length > 3 ? "sm:grid-cols-4" : "sm:grid-cols-3"}`}>
            {stats.map((s) => {
              const body = (
                <>
                  <span className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 ${s.chip}`}>
                    <span className="material-symbols-outlined !text-[1.25rem]" style={{ fontVariationSettings: "'FILL' 1" }}>
                      {s.icon}
                    </span>
                  </span>
                  <span className="min-w-0 text-left">
                    <span className={`block text-[1.5rem] font-semibold tabular-nums leading-none ${s.text}`}>{s.value}</span>
                    <span className="block text-[0.8125rem] text-ink-muted mt-1 leading-tight">{s.label}</span>
                  </span>
                </>
              );
              const base = "flex items-center gap-3 rounded-xl bg-paper-raised border border-rule px-3.5 py-3";
              return s.filter && s.value > 0 ? (
                <button
                  key={s.label}
                  type="button"
                  onClick={() => onFilter?.(s.filter)}
                  title="Xem các mục này"
                  className={`${base} hover:border-quiet/40 hover:shadow-sm transition`}
                >
                  {body}
                </button>
              ) : (
                <div key={s.label} className={base}>
                  {body}
                </div>
              );
            })}
          </div>

          {hasProblems && topIssues.length > 0 && (
            <div className="mt-5">
              <p className="meta-text text-ink-faint uppercase mb-2">Ưu tiên xử lý</p>
              <ol className="rounded-xl border border-rule bg-paper-raised divide-y divide-rule overflow-hidden">
                {topIssues.map((item, i) => (
                  <li key={item.key}>
                    <button
                      type="button"
                      onClick={() => onOpenIssue?.(item.key)}
                      className="group w-full text-left flex items-center gap-3 px-3.5 py-3 hover:bg-quiet-soft/50 transition-colors"
                    >
                      <span
                        className={`w-6 h-6 rounded-full text-[0.75rem] font-semibold flex items-center justify-center shrink-0 tabular-nums ${
                          item.severity === "critical" ? "bg-stamp-soft text-stamp" : "bg-caution-soft text-caution"
                        }`}
                      >
                        {i + 1}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="flex flex-wrap items-center gap-2">
                          <span className="text-[0.9375rem] font-semibold text-ink">{item.clauseRef}</span>
                          <span
                            className={`text-[0.6875rem] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded-full ${
                              item.severity === "critical" ? "bg-stamp-soft text-stamp" : "bg-caution-soft text-caution"
                            }`}
                          >
                            {severityLabel(item.severity)}
                          </span>
                        </span>
                        <span className="block text-[0.875rem] text-ink-muted line-clamp-2 mt-0.5">{item.conclusion}</span>
                      </span>
                      <span className="material-symbols-outlined text-ink-faint group-hover:text-quiet group-hover:translate-x-0.5 transition shrink-0">
                        arrow_forward
                      </span>
                    </button>
                  </li>
                ))}
              </ol>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
