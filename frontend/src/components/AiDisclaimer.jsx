/** Compact, always-visible AI notice. `flush` is kept for existing callers (full-width strip). */
export default function AiDisclaimer({ className = "", flush = false }) {
  return (
    <aside
      role="note"
      className={`flex items-start gap-2.5 bg-caution-soft/70 text-[0.8125rem] leading-snug text-ink-muted ${
        flush
          ? "px-4 py-2.5 md:px-6 lg:px-8 border-b border-caution/15"
          : "rounded-xl border border-caution/20 px-3.5 py-2.5"
      } ${className}`}
    >
      <span className="material-symbols-outlined text-caution !text-[1.125rem] shrink-0 mt-px">info</span>
      <p>
        <span className="font-semibold text-caution">Chỉ mang tính tham khảo.</span> Kết quả của AI không phải tư vấn
        pháp lý chính thức; hãy đối chiếu quy định hiện hành và hỏi chuyên gia trước khi quyết định.
      </p>
    </aside>
  );
}
