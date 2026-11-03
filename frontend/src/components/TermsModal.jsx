import { useEffect, useRef } from "react";
import {
  TERMS_EFFECTIVE_DATE,
  TERMS_INTRO,
  TERMS_PRODUCT,
  TERMS_SECTIONS,
  TERMS_SUMMARY,
  TERMS_TITLE,
  TERMS_VERSION,
} from "../content/termsPolicy";

function Paras({ items }) {
  if (!items?.length) return null;
  return items.map((text) => (
    <p key={text} className="ui-text text-ink-muted leading-relaxed">
      {text}
    </p>
  ));
}

function List({ items, ordered = false }) {
  if (!items?.length) return null;
  const Tag = ordered ? "ol" : "ul";
  return (
    <Tag className={`space-y-1 ${ordered ? "list-decimal" : "list-disc"} pl-4`}>
      {items.map((text) => (
        <li key={text} className="ui-text text-ink-muted leading-relaxed pl-0.5">
          {text}
        </li>
      ))}
    </Tag>
  );
}

export default function TermsModal({ open, onClose, onAccept }) {
  const closeRef = useRef(null);
  const scrollRef = useRef(null);

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

  return (
    <div className="fixed inset-0 z-[80] flex items-end sm:items-center justify-center p-0 sm:p-4">
      <button
        type="button"
        className="absolute inset-0 bg-ink/45"
        aria-label="Đóng chính sách"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="terms-title"
        className="relative w-full sm:max-w-2xl max-h-[92vh] sm:max-h-[min(40rem,86vh)] flex flex-col bg-paper-raised border border-rule sm:rounded-md shadow-lift overflow-hidden"
      >
        <header className="shrink-0 px-4 sm:px-5 py-3 border-b border-rule bg-paper">
          <div className="flex items-start gap-3">
            <div className="min-w-0 flex-1">
              <p className="meta-text uppercase text-ink-faint">
                {TERMS_PRODUCT} · Phiên bản {TERMS_VERSION}
              </p>
              <h2 id="terms-title" className="section-title mt-0.5 leading-snug">
                {TERMS_TITLE}
              </h2>
              <p className="text-[0.6875rem] text-ink-faint mt-0.5">
                Ngày hiệu lực: {TERMS_EFFECTIVE_DATE}
              </p>
            </div>
            <button
              ref={closeRef}
              type="button"
              aria-label="Đóng"
              onClick={onClose}
              className="w-8 h-8 rounded-md flex items-center justify-center text-ink-muted hover:text-ink hover:bg-paper shrink-0"
            >
              <span className="material-symbols-outlined !text-[1.25rem]">close</span>
            </button>
          </div>
        </header>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 sm:px-5 py-4 space-y-5">
          <div className="space-y-2">
            <Paras items={TERMS_INTRO} />
          </div>

          {TERMS_SECTIONS.map((section) => (
            <section key={section.id} className="space-y-2 border-t border-rule pt-4">
              <h3 className="text-[0.8125rem] font-medium text-ink tracking-tight">
                {section.title}
              </h3>
              <Paras items={section.paragraphs} />
              {section.callouts?.map((item) => (
                <div
                  key={item.heading}
                  className="rounded-md border border-rule bg-paper px-3 py-2.5 space-y-1.5"
                >
                  <p className="text-[0.75rem] font-medium text-ink">{item.heading}</p>
                  <Paras items={item.body} />
                </div>
              ))}
              <List items={section.bullets} />
              <List items={section.numbered} ordered />
              {section.subtitle && (
                <p className="text-[0.75rem] font-medium text-ink pt-1">{section.subtitle}</p>
              )}
              <Paras items={section.after} />
            </section>
          ))}

          <section className="border-t border-rule pt-4 space-y-2">
            <h3 className="text-[0.8125rem] font-medium text-ink tracking-tight">
              {TERMS_SUMMARY.title}
            </h3>
            <blockquote className="rounded-md border border-quiet/20 bg-quiet-soft/50 px-3 py-2.5 ui-text text-ink leading-relaxed">
              {TERMS_SUMMARY.quote}
            </blockquote>
            <p className="ui-text text-ink-muted leading-relaxed">
              <span className="font-medium text-ink">Lưu ý quan trọng: </span>
              {TERMS_SUMMARY.note}
            </p>
          </section>
        </div>

        <footer className="shrink-0 px-4 sm:px-5 py-3 border-t border-rule bg-paper flex flex-col-reverse xs:flex-row gap-2 xs:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="px-3.5 py-2 rounded-md border border-rule bg-paper-raised text-[0.75rem] font-medium text-ink-muted hover:text-ink hover:bg-paper transition-colors"
          >
            Đóng
          </button>
          <button
            type="button"
            onClick={onAccept}
            className="px-3.5 py-2 rounded-md bg-ink text-paper-raised text-[0.75rem] font-medium hover:bg-ink/90 transition-colors"
          >
            Đồng ý và tiếp tục
          </button>
        </footer>
      </div>
    </div>
  );
}
