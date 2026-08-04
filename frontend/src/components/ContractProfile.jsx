import { useState } from "react";

function Field({ label, value }) {
  return (
    <div className="min-w-0">
      <dt className="meta-text text-ink-faint uppercase mb-0.5">{label}</dt>
      <dd className="ui-text text-ink font-medium truncate" title={value || undefined}>
        {value || "Không xác định"}
      </dd>
    </div>
  );
}

export default function ContractProfile({ analysis, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  const duration =
    analysis.start_date && analysis.end_date
      ? `${analysis.start_date} – ${analysis.end_date}`
      : analysis.duration;

  return (
    <section className="mb-section-gap border border-rule rounded-md bg-paper-raised shadow-sm overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between gap-3 px-3.5 sm:px-4 py-2.5 text-left hover:bg-quiet-soft/30 transition-colors"
        aria-expanded={open}
      >
        <span className="section-title">Hồ sơ hợp đồng</span>
        <span className="material-symbols-outlined text-ink-faint !text-[1.125rem]">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>

      {open && (
        <div className="px-3.5 sm:px-4 pb-3.5 space-y-4 border-t border-rule pt-3">
          <dl className="grid grid-cols-1 xs:grid-cols-2 lg:grid-cols-3 gap-x-4 gap-y-3">
            <Field label="Loại hợp đồng" value={analysis.contract_type} />
            <Field label="Giá trị" value={analysis.contract_value} />
            <Field label="Thời hạn" value={duration} />
            <Field label="Luật áp dụng" value={analysis.governing_law} />
            <Field label="Giải quyết tranh chấp" value={analysis.dispute_resolution} />
            <Field label="Ngày ký" value={analysis.execution_date} />
          </dl>

          <div>
            <p className="meta-text text-ink-faint uppercase mb-2">Các bên tham gia</p>
            {analysis.parties?.length ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {analysis.parties.map((party, idx) => (
                  <div key={idx} className="rounded-md border border-rule p-2.5 bg-paper/50">
                    <p className="meta-text uppercase text-quiet mb-0.5">
                      {party.role || `Bên ${idx + 1}`}
                    </p>
                    <p className="ui-text font-medium text-ink">{party.name}</p>
                    {party.tax_id && (
                      <p className="text-[0.6875rem] text-ink-muted mt-1">MST/CCCD: {party.tax_id}</p>
                    )}
                    {party.representative && (
                      <p className="text-[0.6875rem] text-ink-muted">Đại diện: {party.representative}</p>
                    )}
                    {party.address && (
                      <p className="text-[0.6875rem] text-ink-muted">{party.address}</p>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="ui-text text-ink-muted">Không trích xuất được thông tin các bên.</p>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
