import { useEffect, useState } from "react";

const STEPS = [
  { phase: "upload", label: "Tải tệp lên" },
  { phase: "analyze", label: "AI đọc điều khoản và đối chiếu pháp luật" },
];

function formatElapsed(seconds) {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m} phút ${String(s).padStart(2, "0")} giây` : `${s} giây`;
}

/** Overlay shown while a contract is uploaded and analysed: which step, and how long it has run. */
export default function AnalysisProgress({ phase }) {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const current = Math.max(
    0,
    STEPS.findIndex((s) => s.phase === phase),
  );

  return (
    <div
      role="status"
      aria-live="polite"
      className="absolute inset-0 bg-paper-raised/95 rounded-md flex flex-col items-center justify-center z-20 px-4"
    >
      <div className="w-full max-w-[16rem] h-1 bg-rule overflow-hidden rounded-full">
        <div className="h-full w-1/3 bg-quiet animate-progress-sweep" />
      </div>
      <ol className="mt-4 space-y-1.5 text-[0.75rem]">
        {STEPS.map((step, i) => (
          <li
            key={step.phase}
            className={`flex items-center gap-2 ${
              i < current ? "text-ok" : i === current ? "text-ink font-medium" : "text-ink-faint"
            }`}
          >
            <span className="material-symbols-outlined !text-[1rem]">
              {i < current ? "check_circle" : i === current ? "progress_activity" : "radio_button_unchecked"}
            </span>
            {step.label}
          </li>
        ))}
      </ol>
      <p className="mt-3 text-[0.6875rem] text-ink-muted text-center">
        Đã chạy {formatElapsed(elapsed)}. Thường mất 30–90 giây, vui lòng giữ trang này mở.
      </p>
    </div>
  );
}
