import { useCallback, useEffect, useRef, useState } from "react";
import { fetchModels } from "../api";
import AiDisclaimer from "./AiDisclaimer";
import TermsModal from "./TermsModal";

const ACCEPTED_EXTENSIONS = [".docx", ".doc", ".pdf", ".png", ".jpg", ".jpeg"];

function isAccepted(file) {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export default function UploadScreen({ onSubmit, statusText, error, mainClassName }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [localError, setLocalError] = useState(null);
  const [models, setModels] = useState([]);
  const [provider, setProvider] = useState("");
  const [acceptedTerms, setAcceptedTerms] = useState(false);
  const [termsOpen, setTermsOpen] = useState(false);
  const inputRef = useRef(null);
  const busy = Boolean(statusText);
  const canSubmit = Boolean(selectedFile) && acceptedTerms && !busy;

  useEffect(() => {
    fetchModels()
      .then((list) => {
        setModels(list);
        if (list.length) setProvider(list[0].provider);
      })
      .catch(() => setModels([]));
  }, []);

  const pickFile = useCallback((file) => {
    if (!file) return;
    if (!isAccepted(file)) {
      setLocalError("Chỉ hỗ trợ tệp .DOCX, .DOC, .PDF hoặc ảnh (.PNG, .JPG, .JPEG)");
      return;
    }
    setLocalError(null);
    setSelectedFile(file);
  }, []);

  const handleDrop = useCallback(
    (e) => {
      e.preventDefault();
      setDragActive(false);
      if (busy) return;
      pickFile(e.dataTransfer.files?.[0]);
    },
    [busy, pickFile],
  );

  const openTerms = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setTermsOpen(true);
  };

  return (
    <main className={mainClassName}>
      <header className="sticky top-11 md:top-0 z-30 border-b border-rule">
        <AiDisclaimer flush />
      </header>
      <div className="page-pad max-w-content mx-auto w-full animate-fade-in">
        <div className="mb-4 max-w-xl">
          <h1 className="page-title">Tải hợp đồng lên</h1>
          <p className="ui-text text-ink-muted mt-1">
            Trích xuất điều khoản và nhận ý kiến rủi ro pháp lý.
          </p>
        </div>

        <div
          className={`upload-zone relative px-4 py-8 sm:p-10 border border-dashed rounded-md flex flex-col items-center justify-center transition-colors cursor-pointer bg-paper-raised max-w-xl ${
            dragActive ? "border-quiet bg-quiet-soft/40" : "border-rule-strong"
          }`}
          onDragOver={(e) => {
            e.preventDefault();
            if (!busy) setDragActive(true);
          }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => !busy && inputRef.current?.click()}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".doc,.docx,.pdf,.png,.jpg,.jpeg"
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          <span className="material-symbols-outlined text-ink-faint !text-[1.75rem] mb-2">cloud_upload</span>
          {selectedFile ? (
            <>
              <h2 className="ui-text font-medium text-ink mb-0.5 text-center break-all px-2">
                {selectedFile.name}
              </h2>
              <p className="text-[0.75rem] text-ink-muted">Nhấn để chọn tệp khác</p>
            </>
          ) : (
            <>
              <h2 className="ui-text font-medium text-ink mb-0.5">Kéo thả hoặc chọn tệp</h2>
              <p className="text-[0.75rem] text-ink-muted">DOCX, DOC, PDF hoặc ảnh (OCR)</p>
            </>
          )}

          {busy && (
            <div className="absolute inset-0 bg-paper-raised/95 rounded-md flex flex-col items-center justify-center z-20 px-4">
              <div className="w-full max-w-[14rem] h-1 bg-rule overflow-hidden rounded-full">
                <div className="h-full w-1/3 bg-quiet animate-progress-sweep" />
              </div>
              <p className="mt-3 text-[0.75rem] font-medium text-ink text-center">{statusText}</p>
            </div>
          )}
        </div>

        {(localError || error) && (
          <p className="mt-3 text-stamp text-[0.75rem] font-medium">{localError || error}</p>
        )}

        <div className="mt-4 max-w-xl space-y-3">
          <div className="flex items-start gap-2">
            <input
              id="accept-terms"
              type="checkbox"
              checked={acceptedTerms}
              disabled={busy}
              onChange={(e) => setAcceptedTerms(e.target.checked)}
              className="mt-0.5 w-3.5 h-3.5 rounded-sm border-rule text-ink accent-ink shrink-0 cursor-pointer disabled:cursor-not-allowed"
            />
            <div className="min-w-0">
              <label htmlFor="accept-terms" className="text-[0.75rem] text-ink leading-relaxed cursor-pointer">
                Đã đọc và chấp nhận các điều khoản
              </label>
              <p className="text-[0.6875rem] text-ink-faint leading-relaxed mt-0.5">
                <button
                  type="button"
                  onClick={openTerms}
                  className="text-quiet underline underline-offset-2 hover:text-ink transition-colors"
                >
                  Chính sách sử dụng dịch vụ và bảo vệ thông tin
                </button>
              </p>
            </div>
          </div>

          <div className="flex flex-col xs:flex-row xs:flex-wrap xs:items-center gap-2.5">
            {models.length > 0 && (
              <div className="flex items-center gap-2 min-w-0">
                <label className="text-[0.75rem] font-medium text-ink-muted shrink-0" htmlFor="model-select">
                  Chế độ
                </label>
                <select
                  id="model-select"
                  value={provider}
                  onChange={(e) => setProvider(e.target.value)}
                  disabled={busy}
                  className="px-2.5 py-1.5 rounded-md border border-rule bg-paper-raised text-ink text-[0.75rem] font-medium focus:outline-none focus:border-quiet min-w-0"
                >
                  {models.map((m) => (
                    <option key={m.provider} value={m.provider}>
                      {m.label}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <button
              type="button"
              className="xs:ml-auto px-4 py-2 bg-ink text-paper-raised text-[0.75rem] font-medium rounded-md hover:bg-ink/90 transition-colors flex items-center justify-center gap-1.5 disabled:opacity-40 disabled:cursor-not-allowed"
              disabled={!canSubmit}
              title={
                !selectedFile
                  ? "Chọn tệp hợp đồng trước"
                  : !acceptedTerms
                    ? "Cần chấp nhận điều khoản trước khi phân tích"
                    : undefined
              }
              onClick={() => onSubmit(selectedFile, provider)}
            >
              Phân tích ngay
              <span className="material-symbols-outlined !text-[1rem]">arrow_forward</span>
            </button>
          </div>
        </div>
      </div>

      <TermsModal
        open={termsOpen}
        onClose={() => setTermsOpen(false)}
        onAccept={() => {
          setAcceptedTerms(true);
          setTermsOpen(false);
        }}
      />
    </main>
  );
}
