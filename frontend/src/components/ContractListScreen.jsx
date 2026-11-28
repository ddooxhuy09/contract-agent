const STATUS_STYLES = {
  analyzed: { label: "Đã phân tích", icon: "check_circle", className: "bg-ok-soft text-ok" },
  parsed: { label: "Chờ phân tích", icon: "schedule", className: "bg-caution-soft text-caution" },
  uploaded: { label: "Lỗi xử lý", icon: "error", className: "bg-stamp-soft text-stamp" },
};

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("vi-VN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function ContractRow({ contract, onOpen }) {
  const style = STATUS_STYLES[contract.status] || STATUS_STYLES.uploaded;
  return (
    <button
      type="button"
      onClick={() => onOpen(contract)}
      className="group w-full text-left grid grid-cols-[auto_1fr_auto] md:grid-cols-[auto_1fr_11rem_9rem_1.5rem] items-center gap-3 md:gap-4 px-4 sm:px-5 py-3.5 hover:bg-quiet-soft/50 transition-colors"
    >
      <span className="w-10 h-10 rounded-xl bg-quiet-soft text-quiet flex items-center justify-center shrink-0">
        <span className="material-symbols-outlined">description</span>
      </span>
      <div className="min-w-0">
        <p className="text-[0.9375rem] font-semibold text-ink truncate">{contract.filename}</p>
        <p className="text-[0.8125rem] text-ink-faint mt-0.5 md:hidden">{formatDate(contract.created_at)}</p>
      </div>
      <span className="hidden md:block text-[0.8125rem] text-ink-muted tabular-nums">
        {formatDate(contract.created_at)}
      </span>
      <span
        className={`justify-self-end inline-flex items-center gap-1 text-[0.75rem] font-semibold px-2.5 py-1 rounded-full ${style.className}`}
      >
        <span className="material-symbols-outlined !text-[0.9375rem]" style={{ fontVariationSettings: "'FILL' 1" }}>
          {style.icon}
        </span>
        <span className="hidden sm:inline">{style.label}</span>
      </span>
      <span className="material-symbols-outlined text-ink-faint group-hover:text-quiet hidden md:block">
        chevron_right
      </span>
    </button>
  );
}

export default function ContractListScreen({
  contracts,
  loading,
  loadError,
  onRetry,
  onUpload,
  statusText,
  error,
  onOpenContract,
  mainClassName,
}) {
  return (
    <main className={mainClassName}>
      <div className="page-pad max-w-content mx-auto w-full animate-fade-in">
        <div className="mb-5 flex items-start justify-between gap-3">
          <div>
            <h1 className="page-title">Hợp đồng của bạn</h1>
            <p className="ui-text text-ink-muted mt-1">
              Chọn một hợp đồng để xem kết quả đã phân tích.
              {contracts.length > 0 && <span className="text-ink-faint"> · {contracts.length} hợp đồng</span>}
            </p>
          </div>
          <button
            type="button"
            onClick={onUpload}
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2.5 bg-quiet text-white text-[0.875rem] font-semibold rounded-lg shadow-sm hover:bg-quiet/90 transition-colors"
          >
            <span className="material-symbols-outlined">add</span>
            <span className="hidden xs:inline">Tải hợp đồng mới</span>
          </button>
        </div>

        {error && (
          <p role="alert" className="mb-3 px-3.5 py-2.5 rounded-xl bg-stamp-soft text-stamp text-[0.875rem] font-medium">
            {error}
          </p>
        )}

        {statusText && (
          <div role="status" className="mb-3 flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl border border-quiet/20 bg-quiet-soft">
            <span className="w-2 h-2 rounded-full bg-quiet animate-pulse" />
            <span className="text-[0.875rem] font-medium text-quiet">{statusText}</span>
          </div>
        )}

        {loading ? (
          <p className="text-ink-muted text-center py-12 ui-text">Đang tải danh sách...</p>
        ) : loadError && contracts.length === 0 ? (
          <div role="alert" className="border border-stamp/25 bg-stamp-soft/40 rounded-xl p-6 text-center">
            <p className="ui-text text-stamp font-medium">{loadError}</p>
            <button
              type="button"
              onClick={onRetry}
              className="mt-3 px-4 py-2 rounded-lg border border-rule bg-paper-raised text-[0.8125rem] font-medium text-ink hover:bg-quiet-soft transition-colors"
            >
              Thử lại
            </button>
          </div>
        ) : contracts.length === 0 ? (
          <div className="border border-dashed border-rule-strong rounded-xl p-10 sm:p-14 flex flex-col items-center justify-center text-center bg-paper-raised">
            <span className="w-14 h-14 rounded-2xl bg-quiet-soft text-quiet flex items-center justify-center mb-3">
              <span className="material-symbols-outlined !text-[1.75rem]">folder_open</span>
            </span>
            <h2 className="section-title mb-1">Chưa có hợp đồng nào</h2>
            <p className="ui-text text-ink-muted max-w-xs">
              Bấm <span className="font-semibold text-ink">Tải hợp đồng mới</span> để bắt đầu.
            </p>
          </div>
        ) : (
          <div className="card overflow-hidden">
            <div className="hidden md:grid grid-cols-[auto_1fr_11rem_9rem_1.5rem] gap-4 px-5 py-2.5 border-b border-rule bg-paper meta-text uppercase text-ink-faint">
              <span className="w-10" />
              <span>Tên tệp</span>
              <span>Ngày tạo</span>
              <span className="text-right">Trạng thái</span>
              <span />
            </div>
            <div className="divide-y divide-rule">
              {contracts.map((c) => (
                <ContractRow key={c.contract_id} contract={c} onOpen={onOpenContract} />
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
