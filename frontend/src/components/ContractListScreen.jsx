const STATUS_STYLES = {
  analyzed: { label: "Đã phân tích", className: "bg-ok-soft text-ok" },
  parsed: { label: "Chờ phân tích", className: "bg-caution-soft text-caution" },
  uploaded: { label: "Lỗi xử lý", className: "bg-stamp-soft text-stamp" },
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
      className="w-full text-left grid grid-cols-[1fr_auto] md:grid-cols-[1fr_9rem_6.5rem_1.25rem] items-center gap-2 md:gap-3 px-3 sm:px-3.5 py-2.5 hover:bg-quiet-soft/50 transition-colors"
    >
      <div className="min-w-0">
        <p className="ui-text font-medium text-ink truncate">{contract.filename}</p>
        <p className="text-[0.6875rem] text-ink-faint mt-0.5 md:hidden">{formatDate(contract.created_at)}</p>
      </div>
      <span className="hidden md:block text-[0.75rem] text-ink-muted tabular-nums">
        {formatDate(contract.created_at)}
      </span>
      <span
        className={`justify-self-end text-[0.625rem] font-medium px-1.5 py-0.5 rounded-sm ${style.className}`}
      >
        {style.label}
      </span>
      <span className="material-symbols-outlined text-ink-faint !text-[1rem] hidden md:block">
        chevron_right
      </span>
    </button>
  );
}

export default function ContractListScreen({
  contracts,
  loading,
  statusText,
  error,
  onOpenContract,
  mainClassName,
}) {
  return (
    <main className={mainClassName}>
      <div className="page-pad max-w-content mx-auto w-full animate-fade-in">
        <div className="mb-4 sm:mb-5">
          <h1 className="page-title">Hợp đồng của bạn</h1>
          <p className="ui-text text-ink-muted mt-1">
            Mở kết quả đã phân tích. Tải hợp đồng mới từ thanh bên.
          </p>
        </div>

        {error && <p className="mb-3 text-stamp text-[0.75rem] font-medium">{error}</p>}

        {statusText && (
          <div className="mb-3 flex items-center gap-2 px-3 py-2 rounded-md border border-rule bg-paper-raised">
            <span className="w-1.5 h-1.5 rounded-full bg-quiet animate-pulse" />
            <span className="text-[0.75rem] font-medium text-ink">{statusText}</span>
          </div>
        )}

        {loading ? (
          <p className="text-ink-muted text-center py-12 ui-text">Đang tải danh sách...</p>
        ) : contracts.length === 0 ? (
          <div className="border border-dashed border-rule-strong rounded-md p-8 sm:p-10 flex flex-col items-center justify-center text-center bg-paper-raised">
            <span className="material-symbols-outlined text-ink-faint !text-[1.75rem] mb-2">folder_open</span>
            <h2 className="section-title mb-1">Chưa có hợp đồng nào</h2>
            <p className="ui-text text-ink-muted max-w-xs">
              Bấm <span className="font-medium text-ink">Tải hợp đồng mới</span> trên thanh bên để bắt đầu.
            </p>
          </div>
        ) : (
          <div className="bg-paper-raised border border-rule rounded-md shadow-sm overflow-hidden">
            <div className="hidden md:grid grid-cols-[1fr_9rem_6.5rem_1.25rem] gap-3 px-3.5 py-2 border-b border-rule bg-paper meta-text uppercase text-ink-faint">
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
