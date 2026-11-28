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
    "inline-flex items-center gap-1.5 px-3 py-2 rounded-lg border border-rule bg-paper-raised text-[0.8125rem] font-medium text-ink hover:bg-quiet-soft hover:border-quiet/30 hover:text-quiet transition-colors disabled:opacity-40 disabled:cursor-not-allowed";
  const icon = "material-symbols-outlined !text-[1.125rem]";

  return (
    <div className="ml-auto flex items-center gap-2 shrink-0">
      {error && <span className="text-[0.75rem] text-stamp hidden sm:inline">{error}</span>}
      <button type="button" className={btn} disabled={disabled || downloading} onClick={() => download("md")}
        aria-label="Tải báo cáo" title="Báo cáo dễ đọc (Markdown), gồm kết luận và mức sử dụng AI">
        <span className={icon}>description</span>
        <span className="hidden sm:inline">{downloading === "md" ? "Đang tải..." : "Báo cáo"}</span>
      </button>
      <button type="button" className={btn} disabled={disabled || downloading} onClick={() => download("json")}
        aria-label="Tải JSON" title="Dữ liệu đầy đủ (JSON) để lưu hoặc gửi đi đánh giá">
        <span className={icon}>data_object</span>
        <span className="hidden sm:inline">{downloading === "json" ? "Đang tải..." : "JSON"}</span>
      </button>
      <button type="button" className={btn} disabled={disabled} onClick={reanalyze}
        aria-label="Phân tích lại" title="Chạy lại AI trên hợp đồng này">
        <span className={icon}>refresh</span>
        <span className="hidden sm:inline">Phân tích lại</span>
      </button>
    </div>
  );
}
