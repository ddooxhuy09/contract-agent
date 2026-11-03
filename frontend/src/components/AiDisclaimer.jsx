export default function AiDisclaimer({ className = "", flush = false }) {
  return (
    <aside
      role="note"
      className={`relative overflow-hidden bg-caution-soft/70 ${
        flush ? "" : "rounded-md border border-caution/20"
      } ${className}`}
    >
      <p
        className={`text-center text-[0.75rem] leading-relaxed text-ink-faint ${
          flush
            ? "px-3 py-2 sm:px-4 md:px-5 lg:px-6"
            : "px-4 py-2.5 sm:px-5"
        }`}
      >
        <span className="font-medium text-caution/70">Lưu ý:</span> Kết quả phân
        tích và khuyến nghị của AI chỉ mang tính tham khảo, không phải tư vấn pháp
        lý chính thức. Vui lòng kiểm tra quy định pháp luật hiện hành và tham khảo
        ý kiến chuyên gia trước khi đưa ra quyết định.
      </p>
    </aside>
  );
}
