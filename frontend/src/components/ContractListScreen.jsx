const STATUS_STYLES = {
  analyzed: { label: "Đã phân tích", bg: "bg-success-green/10", text: "text-success-green", icon: "check_circle" },
  parsed: { label: "Chờ phân tích", bg: "bg-secondary-fixed", text: "text-on-secondary-fixed", icon: "hourglass_top" },
  uploaded: { label: "Lỗi xử lý tệp", bg: "bg-error-container", text: "text-on-error-container", icon: "error" },
};

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString("vi-VN", { dateStyle: "medium", timeStyle: "short" });
  } catch {
    return iso;
  }
}

function ContractCard({ contract, onOpen }) {
  const style = STATUS_STYLES[contract.status] || STATUS_STYLES.uploaded;
  return (
    <button
      onClick={() => onOpen(contract)}
      className="w-full text-left bg-surface-container-lowest border border-border-subtle rounded-xl p-card-padding flex items-center gap-4 hover:shadow-md hover:border-primary-container transition-all"
    >
      <div className="w-12 h-12 rounded-lg bg-primary-fixed flex items-center justify-center shrink-0">
        <span className="material-symbols-outlined text-primary">description</span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-label-bold text-label-bold text-primary truncate">{contract.filename}</p>
        <p className="text-label-sm text-on-surface-variant">{formatDate(contract.created_at)}</p>
      </div>
      <span className={`inline-flex items-center gap-1 ${style.bg} ${style.text} px-3 py-1 rounded-full text-label-sm font-label-bold shrink-0`}>
        <span className="material-symbols-outlined text-[16px]">{style.icon}</span>
        {style.label}
      </span>
      <span className="material-symbols-outlined text-on-surface-variant shrink-0">chevron_right</span>
    </button>
  );
}

export default function ContractListScreen({ contracts, loading, statusText, error, onOpenContract, onNewUpload, onSignOut }) {
  return (
    <div className="min-h-screen bg-background text-on-surface">
      <nav className="flex justify-between items-center px-container-padding h-16 w-full fixed top-0 z-50 bg-surface-container-lowest border-b border-border-subtle">
        <span className="font-display-lg text-display-lg text-primary">ContractLens</span>
        <button
          className="flex items-center gap-2 font-label-bold text-label-bold text-on-surface-variant hover:text-primary transition-colors"
          onClick={onSignOut}
        >
          <span className="material-symbols-outlined text-[20px]">logout</span>
          Đăng xuất
        </button>
      </nav>

      <main className="pt-24 pb-16 max-w-[900px] mx-auto px-container-padding">
        <div className="flex items-center justify-between mb-section-gap flex-wrap gap-4">
          <div>
            <h1 className="font-display-lg text-display-lg text-primary mb-1">Hợp đồng của bạn</h1>
            <p className="text-on-surface-variant font-body-md text-body-md">
              Xem lại kết quả phân tích cũ hoặc tải lên hợp đồng mới.
            </p>
          </div>
          <button
            className="px-5 py-3 bg-primary text-on-primary font-label-bold text-label-bold rounded-lg hover:opacity-90 transition-all flex items-center gap-2 shrink-0"
            onClick={onNewUpload}
          >
            <span className="material-symbols-outlined">upload_file</span>
            Tải hợp đồng mới
          </button>
        </div>

        {error && <p className="mb-4 text-error font-label-bold text-label-bold">{error}</p>}

        {statusText && (
          <div className="mb-6 flex items-center gap-3 px-4 py-3 bg-surface-container rounded-lg">
            <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
            <span className="font-label-bold text-label-bold text-primary">{statusText}</span>
          </div>
        )}

        {loading ? (
          <p className="text-on-surface-variant text-center py-16">Đang tải danh sách hợp đồng...</p>
        ) : contracts.length === 0 ? (
          <div
            className="upload-zone border-2 border-dashed border-outline-variant rounded-xl p-16 flex flex-col items-center justify-center text-center cursor-pointer bg-surface-container-lowest"
            onClick={onNewUpload}
          >
            <div className="glow-cloud w-20 h-20 bg-primary-fixed rounded-full flex items-center justify-center mb-6">
              <span className="material-symbols-outlined text-[40px] text-primary">cloud_upload</span>
            </div>
            <h2 className="font-headline-sm text-headline-sm text-primary mb-2">Chưa có hợp đồng nào</h2>
            <p className="font-body-md text-body-md text-on-surface-variant">
              Tải lên hợp đồng đầu tiên để AI bắt đầu phân tích rủi ro pháp lý.
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {contracts.map((c) => (
              <ContractCard key={c.contract_id} contract={c} onOpen={onOpenContract} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
