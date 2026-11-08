import { useState } from "react";
import { downloadReport } from "../api";

/** Header actions of a result: download the shareable report, re-run the analysis. */
export default function ReportActions({ contractId, onReanalyze, disabled }) {
  const [downloading, setDownloading] = useState(null);
  const [error, setError] = useState(null);

  const download = async (format) => {
    setError(null);
    setDownloading(format);
    try {
      await downloadReport(contractId, format);
    } catch (err) {
      setError(err.message || "Không tải được báo cáo.");
    } finally {
      setDownloading(null);
    }
  };

  const reanalyze = () => {
    if (window.confirm("Phân tích lại sẽ gọi AI lần nữa (khoảng 30–90 giây) và thay thế kết quả hiện tại. Tiếp tục?")) {
      onReanalyze();
    }
  };

  const btn =
    "inline-flex items-center gap-1 px-2 py-1 rounded-md border border-rule bg-paper-raised text-[0.6875rem] font-medium text-ink hover:bg-quiet-soft/50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed";

  return (
    <div className="ml-auto flex items-center gap-1.5 shrink-0">
      {error && <span className="text-[0.6875rem] text-stamp hidden sm:inline">{error}</span>}
      <button type="button" className={btn} disabled={disabled || downloading} onClick={() => download("md")}
        title="Báo cáo dễ đọc (Markdown), gồm kết luận và mức sử dụng AI">
        <span className="material-symbols-outlined !text-[0.875rem]">description</span>
        {downloading === "md" ? "Đang tải..." : "Báo cáo"}
      </button>
      <button type="button" className={btn} disabled={disabled || downloading} onClick={() => download("json")}
        title="Dữ liệu đầy đủ (JSON) để lưu hoặc gửi đi đánh giá">
        <span className="material-symbols-outlined !text-[0.875rem]">data_object</span>
        {downloading === "json" ? "Đang tải..." : "JSON"}
      </button>
      <button type="button" className={btn} disabled={disabled} onClick={reanalyze}>
        <span className="material-symbols-outlined !text-[0.875rem]">refresh</span>
        <span className="hidden sm:inline">Phân tích lại</span>
      </button>
    </div>
  );
}
