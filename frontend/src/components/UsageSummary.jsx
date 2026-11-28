const fmt = (n) => Number(n || 0).toLocaleString("vi-VN");

/** AI usage of the run that produced this result (requests, tokens, duration). */
export default function UsageSummary({ usage }) {
  const items = usage
    ? [
        { label: "Lượt request", value: fmt(usage.requests), hint: usage.failed_requests ? `${usage.failed_requests} lỗi` : null },
        { label: "Token đầu vào", value: fmt(usage.input_tokens) },
        { label: "Token đầu ra", value: fmt(usage.output_tokens) },
        { label: "Tổng token", value: fmt(usage.total_tokens) },
        { label: "Thời gian", value: `${usage.duration_seconds ?? 0} giây` },
      ]
    : [];

  return (
    <section className="mb-section-gap card" aria-labelledby="usage-title">
      <div className="px-4 sm:px-5 py-3.5 border-b border-rule">
        <h2 id="usage-title" className="section-title">Mức sử dụng AI</h2>
        <p className="text-[0.8125rem] text-ink-muted mt-0.5">Của lần phân tích đã tạo ra kết quả này.</p>
      </div>
      {usage ? (
        <dl className="grid grid-cols-2 sm:grid-cols-5 gap-2 sm:gap-3 p-4 sm:p-5">
          {items.map((item) => (
            <div key={item.label} className="rounded-xl border border-rule px-3 py-2.5">
              <dt className="text-[0.75rem] text-ink-faint truncate">{item.label}</dt>
              <dd className="text-[1.125rem] font-semibold tabular-nums text-ink mt-0.5">{item.value}</dd>
              {item.hint && <p className="text-[0.75rem] text-stamp">{item.hint}</p>}
            </div>
          ))}
        </dl>
      ) : (
        <p className="px-4 sm:px-5 py-3.5 ui-text text-ink-muted">
          Chưa có số liệu cho lần phân tích này. Bấm <span className="font-medium text-ink">Phân tích lại</span> để ghi nhận.
        </p>
      )}
    </section>
  );
}
