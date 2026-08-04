import { severityLabel } from "../lib/riskDisplay";

export default function ExecutiveSummary({
  criticalCount,
  warningCount,
  okClauseCount,
  topIssues,
  onOpenIssue,
}) {
  const hasProblems = criticalCount + warningCount > 0;

  let verdict;
  let bannerClass = "border-ok/30 bg-ok-soft/40";
  let accentClass = "bg-ok";
  if (criticalCount > 0) {
    verdict = `Có ${criticalCount} vấn đề nghiêm trọng — nên xử lý trước khi ký hoặc thực hiện.`;
    bannerClass = "border-stamp/25 bg-stamp-soft/50";
    accentClass = "bg-stamp";
  } else if (warningCount > 0) {
    verdict = `Không thấy vi phạm nghiêm trọng rõ ràng; còn ${warningCount} điểm cần chú ý trước khi chốt.`;
    bannerClass = "border-caution/30 bg-caution-soft/50";
    accentClass = "bg-caution";
  } else {
    verdict = "Không phát hiện vấn đề trọng yếu trong phạm vi đã rà soát.";
  }

  return (
    <section className="mb-section-gap animate-fade-in" aria-labelledby="exec-summary-title">
      <div className={`relative overflow-hidden rounded-md border ${bannerClass}`}>
        <div className={`absolute left-0 top-0 bottom-0 w-0.5 ${accentClass}`} />
        <div className="pl-4 pr-3 py-3.5 sm:pl-5 sm:pr-4 sm:py-4">
          <p className="meta-text text-ink-faint uppercase mb-1.5">Kết luận nhanh</p>
          <h2
            id="exec-summary-title"
            className="text-[0.9375rem] sm:text-[1rem] md:text-[1.0625rem] font-medium text-ink leading-snug max-w-3xl"
          >
            {verdict}
          </h2>

          <dl className="mt-3.5 grid grid-cols-3 gap-2 sm:gap-3">
            {[
              { label: "Nghiêm trọng", value: criticalCount, color: "text-stamp" },
              { label: "Cần chú ý", value: warningCount, color: "text-caution" },
              { label: "Ổn", value: okClauseCount, color: "text-ok" },
            ].map((item) => (
              <div
                key={item.label}
                className="rounded-md bg-paper-raised/80 border border-rule px-2.5 py-2 sm:px-3 sm:py-2.5"
              >
                <dt className="meta-text text-ink-faint uppercase truncate">{item.label}</dt>
                <dd className={`text-[1.125rem] sm:text-[1.25rem] font-medium tabular-nums mt-0.5 ${item.color}`}>
                  {item.value}
                </dd>
              </div>
            ))}
          </dl>

          {hasProblems && topIssues.length > 0 && (
            <div className="mt-3.5">
              <p className="meta-text text-ink-faint uppercase mb-1.5">Ưu tiên xử lý</p>
              <ol className="rounded-md border border-rule bg-paper-raised divide-y divide-rule overflow-hidden">
                {topIssues.map((item, i) => (
                  <li key={item.key}>
                    <button
                      type="button"
                      onClick={() => onOpenIssue?.(item.key)}
                      className="w-full text-left flex items-start gap-2.5 px-3 py-2.5 hover:bg-quiet-soft/40 transition-colors"
                    >
                      <span className="text-[0.75rem] font-medium text-ink-faint w-4 shrink-0 tabular-nums pt-0.5">
                        {i + 1}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="inline-flex flex-wrap items-center gap-1.5 mb-0.5">
                          <span className="text-[0.8125rem] font-medium text-ink">{item.clauseRef}</span>
                          <span
                            className={`text-[0.625rem] font-medium uppercase tracking-wide px-1 py-0.5 rounded-sm ${
                              item.severity === "critical"
                                ? "bg-stamp-soft text-stamp"
                                : "bg-caution-soft text-caution"
                            }`}
                          >
                            {severityLabel(item.severity)}
                          </span>
                        </span>
                        <p className="ui-text text-ink-muted line-clamp-2">{item.conclusion}</p>
                      </span>
                      <span className="material-symbols-outlined text-ink-faint shrink-0 !text-[1rem] mt-0.5">
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
