import { useEffect, useRef, useState } from "react";
import {
  TERMS_EFFECTIVE_DATE,
  TERMS_HIGHLIGHTS,
  TERMS_INTRO,
  TERMS_PRODUCT,
  TERMS_SECTIONS,
  TERMS_TITLE,
  TERMS_VERSION,
} from "../content/termsPolicy";

const TONES = {
  quiet: "bg-quiet-soft text-quiet",
  ok: "bg-ok-soft text-ok",
  caution: "bg-caution-soft text-caution",
  stamp: "bg-stamp-soft text-stamp",
};

function Paras({ items }) {
  if (!items?.length) return null;
  return items.map((text) => (
    <p key={text} className="text-[0.9375rem] text-ink-muted leading-relaxed">
      {text}
    </p>
  ));
}

function List({ items, ordered = false }) {
  if (!items?.length) return null;
  return (
    <ul className="space-y-1.5">
      {items.map((text, i) => (
        <li key={text} className="flex gap-2.5 text-[0.9375rem] text-ink-muted leading-relaxed">
          {ordered ? (
            <span className="w-5 h-5 mt-0.5 rounded-full bg-quiet-soft text-quiet text-[0.75rem] font-semibold flex items-center justify-center shrink-0">
              {i + 1}
            </span>
          ) : (
            <span className="material-symbols-outlined text-quiet !text-[1.125rem] mt-0.5 shrink-0">check</span>
          )}
          <span>{text}</span>
        </li>
      ))}
    </ul>
  );
}

function Section({ section, index, open, onToggle }) {
  return (
    <section className="rounded-xl border border-rule bg-paper-raised overflow-hidden">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="w-full flex items-center gap-3 px-3.5 py-3 text-left hover:bg-quiet-soft/40 transition-colors"
      >
        <span className="w-8 h-8 rounded-lg bg-quiet-soft text-quiet flex items-center justify-center shrink-0">
          <span className="material-symbols-outlined !text-[1.125rem]">{section.icon}</span>
        </span>
        <span className="flex-1 min-w-0 text-[0.9375rem] font-semibold text-ink leading-snug">
          <span className="text-ink-faint font-medium mr-1.5">{index + 1}.</span>
          {section.title}
        </span>
        <span className="material-symbols-outlined text-ink-faint">{open ? "expand_less" : "expand_more"}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 pt-3 space-y-3 border-t border-rule bg-paper/40">
          <Paras items={section.paragraphs} />
          <List items={section.bullets} />
          {section.subtitle && <p className="text-[0.875rem] font-semibold text-ink pt-1">{section.subtitle}</p>}
          <List items={section.numbered} ordered />
          {section.after?.length > 0 && (
            <div className="rounded-lg border border-quiet/20 bg-quiet-soft/60 px-3.5 py-3 space-y-2">
              <Paras items={section.after} />
            </div>
          )}
        </div>
      )}
    </section>
  );
}

export default function TermsModal({ open, onClose, onAccept }) {
  const closeRef = useRef(null);
  const scrollRef = useRef(null);
  const [openIds, setOpenIds] = useState(() => new Set());

  useEffect(() => {
    if (!open) return undefined;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    scrollRef.current?.scrollTo(0, 0);

    const onKey = (e) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = prev;
      window.removeEventListener("keydown", onKey);
    };
  }, [open, onClose]);

  if (!open) return null;

  const allOpen = openIds.size === TERMS_SECTIONS.length;
  const toggle = (id) =>
    setOpenIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <div className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <button type="button" className="absolute inset-0 bg-ink/50 backdrop-blur-[2px]" aria-label="Đóng chính sách" onClick={onClose} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-title"
        className="relative w-full sm:max-w-3xl max-h-[94vh] sm:max-h-[min(46rem,90vh)] flex flex-col bg-paper-raised sm:rounded-2xl rounded-t-2xl shadow-lift overflow-hidden"
      >
        <header className="shrink-0 px-4 sm:px-6 py-4 border-b border-rule">
          <div className="flex items-start gap-3.5">
            <span className="w-11 h-11 rounded-xl bg-quiet text-white flex items-center justify-center shrink-0 shadow-sm">
              <span className="material-symbols-outlined !text-[1.5rem]" style={{ fontVariationSettings: "'FILL' 1" }}>
                policy
              </span>
            </span>
            <div className="min-w-0 flex-1">
              <h2 id="terms-title" className="text-[1.125rem] font-semibold text-ink leading-snug">
                {TERMS_TITLE}
              </h2>
              <p className="text-[0.8125rem] text-ink-faint mt-0.5">
                {TERMS_PRODUCT} · Phiên bản {TERMS_VERSION} · Hiệu lực {TERMS_EFFECTIVE_DATE}
              </p>
            </div>
            <button
              ref={closeRef}
              type="button"
              aria-label="Đóng"
              onClick={onClose}
              className="w-9 h-9 rounded-lg flex items-center justify-center text-ink-muted hover:text-ink hover:bg-paper shrink-0"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 sm:px-6 py-5 space-y-6 bg-paper/50">
          <p className="text-[0.9375rem] text-ink-muted leading-relaxed">{TERMS_INTRO}</p>

          <div>
            <h3 className="text-[0.75rem] font-semibold uppercase tracking-wide text-ink-faint mb-2.5">
              4 điều quan trọng nhất
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {TERMS_HIGHLIGHTS.map((h) => (
                <div key={h.title} className="rounded-xl border border-rule bg-paper-raised p-3.5 shadow-sm">
                  <div className="flex items-center gap-2.5 mb-1.5">
                    <span className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${TONES[h.tone]}`}>
                      <span className="material-symbols-outlined !text-[1.125rem]" style={{ fontVariationSettings: "'FILL' 1" }}>
                        {h.icon}
                      </span>
                    </span>
                    <p className="text-[0.9375rem] font-semibold text-ink leading-snug">{h.title}</p>
                  </div>
                  <p className="text-[0.875rem] text-ink-muted leading-relaxed">{h.text}</p>
                </div>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-2.5">
              <h3 className="text-[0.75rem] font-semibold uppercase tracking-wide text-ink-faint">Nội dung chi tiết</h3>
              <button
                type="button"
                onClick={() => setOpenIds(allOpen ? new Set() : new Set(TERMS_SECTIONS.map((s) => s.id)))}
                className="text-[0.8125rem] font-medium text-quiet hover:underline"
              >
                {allOpen ? "Thu gọn tất cả" : "Mở rộng tất cả"}
              </button>
            </div>
            <div className="space-y-2">
              {TERMS_SECTIONS.map((section, i) => (
                <Section
                  key={section.id}
                  section={section}
                  index={i}
                  open={openIds.has(section.id)}
                  onToggle={() => toggle(section.id)}
                />
              ))}
            </div>
          </div>
        </div>

        <footer className="shrink-0 px-4 sm:px-6 py-3.5 border-t border-rule bg-paper-raised flex flex-col-reverse xs:flex-row gap-2 xs:items-center xs:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2.5 rounded-lg border border-rule bg-paper-raised text-[0.875rem] font-medium text-ink-muted hover:text-ink hover:bg-paper transition-colors"
          >
            Đóng
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="px-5 py-2.5 rounded-lg bg-quiet text-white text-[0.875rem] font-semibold shadow-sm hover:bg-quiet/90 transition-colors"
          >
            Đồng ý và tiếp tục
          </button>
        </footer>
      </div>
    </div>
  );
}
