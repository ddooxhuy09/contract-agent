import { useState } from "react";

function Field({ label, value, icon }) {
  return (
    <div className="min-w-0 flex gap-2.5">
      <span className="material-symbols-outlined text-ink-faint !text-[1.25rem] mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0">
        <dt className="text-[0.75rem] text-ink-faint">{label}</dt>
        <dd
          className={`text-[0.9375rem] font-medium line-clamp-2 break-words ${value ? "text-ink" : "text-ink-faint"}`}
          title={value || undefined}
        >
          {value || "Không xác định"}
        </dd>
      </div>
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
    <section className="mb-section-gap card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-4 sm:px-5 py-3.5 text-left hover:bg-quiet-soft/40 transition-colors"
        aria-expanded={open}
      >
        <span className="material-symbols-outlined text-quiet">description</span>
        <span className="section-title">Hồ sơ hợp đồng</span>
        {!open && (
          <span className="hidden md:flex flex-1 min-w-0 items-center gap-2 text-[0.8125rem] text-ink-muted truncate">
            {[analysis.contract_type, duration].filter(Boolean).join("  ·  ")}
          </span>
        )}
        <span className="material-symbols-outlined text-ink-faint ml-auto">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>

      {open && (
        <div className="px-4 sm:px-5 pb-5 pt-4 space-y-5 border-t border-rule">
          <dl className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-4">
            <Field icon="gavel" label="Loại hợp đồng" value={analysis.contract_type} />
            <Field icon="payments" label="Giá trị" value={analysis.contract_value} />
            <Field icon="schedule" label="Thời hạn" value={duration} />
            <Field icon="balance" label="Luật áp dụng" value={analysis.governing_law} />
            <Field icon="forum" label="Giải quyết tranh chấp" value={analysis.dispute_resolution} />
            <Field icon="event" label="Ngày ký" value={analysis.execution_date} />
          </dl>

          <div>
            <p className="text-[0.75rem] font-medium text-ink-faint uppercase tracking-wide mb-2">Các bên tham gia</p>
            {analysis.parties?.length ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {analysis.parties.map((party, idx) => (
                  <div key={idx} className="rounded-xl border border-rule p-3 bg-paper/60">
                    <p className="text-[0.75rem] font-semibold uppercase tracking-wide text-quiet mb-1 line-clamp-2">
                      {party.role || `Bên ${idx + 1}`}
                    </p>
                    <p className="text-[0.9375rem] font-semibold text-ink break-words">{party.name}</p>
                    <div className="mt-1.5 space-y-0.5 text-[0.8125rem] text-ink-muted">
                      {party.id_number && <p>CCCD/CMND: {party.id_number}</p>}
                      {party.tax_id && <p>MST: {party.tax_id}</p>}
                      {party.representative && <p>Đại diện: {party.representative}</p>}
                      {party.address && <p>{party.address}</p>}
                    </div>
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
