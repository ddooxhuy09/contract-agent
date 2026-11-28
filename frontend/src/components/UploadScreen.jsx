import { useCallback, useEffect, useRef, useState } from "react";
import { fetchModels } from "../api";
import AiDisclaimer from "./AiDisclaimer";
import AnalysisProgress from "./AnalysisProgress";
import TermsModal from "./TermsModal";

const ACCEPTED_EXTENSIONS = [".docx", ".pdf", ".png", ".jpg", ".jpeg"];

function isAccepted(file) {
  const name = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((ext) => name.endsWith(ext));
}

export default function UploadScreen({ onSubmit, statusText, phase, error, mainClassName }) {
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
      setLocalError("Chỉ hỗ trợ tệp .DOCX, .PDF hoặc ảnh (.PNG, .JPG, .JPEG). Tệp .DOC cần chuyển sang .DOCX.");
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
      <div className="page-pad max-w-content mx-auto w-full animate-fade-in">
        <div className="mb-5 max-w-2xl">
          <h1 className="page-title">Tải hợp đồng lên</h1>
          <p className="ui-text text-ink-muted mt-1">
            Trích xuất điều khoản và nhận ý kiến rủi ro pháp lý.
          </p>
        </div>
        <AiDisclaimer className="mb-4 max-w-2xl" />

        <div
          className={`upload-zone relative px-4 py-10 sm:p-14 border-2 border-dashed rounded-2xl flex flex-col items-center justify-center transition-colors cursor-pointer bg-paper-raised max-w-2xl ${
            dragActive ? "border-quiet bg-quiet-soft/60" : "border-rule-strong"
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
            accept=".docx,.pdf,.png,.jpg,.jpeg"
            className="hidden"
            onChange={(e) => pickFile(e.target.files?.[0])}
          />
          <span
            className={`w-14 h-14 rounded-2xl flex items-center justify-center mb-3 ${
              selectedFile ? "bg-ok-soft text-ok" : "bg-quiet-soft text-quiet"
            }`}
          >
            <span className="material-symbols-outlined !text-[1.75rem]">
              {selectedFile ? "task" : "cloud_upload"}
            </span>
          </span>
          {selectedFile ? (
            <>
              <h2 className="text-[1rem] font-semibold text-ink mb-0.5 text-center break-all px-2">
                {selectedFile.name}
              </h2>
              <p className="text-[0.8125rem] text-ink-muted">Nhấn để chọn tệp khác</p>
            </>
          ) : (
            <>
              <h2 className="text-[1rem] font-semibold text-ink mb-0.5">Kéo thả hoặc chọn tệp</h2>
              <p className="text-[0.8125rem] text-ink-muted">DOCX, PDF hoặc ảnh (OCR)</p>
            </>
          )}

          {busy && <AnalysisProgress phase={phase} />}
        </div>

        {(localError || error) && (
          <p role="alert" className="mt-3 max-w-2xl px-3.5 py-2.5 rounded-xl bg-stamp-soft text-stamp text-[0.875rem] font-medium">
            {localError || error}
          </p>
        )}

        <div className="mt-5 max-w-2xl space-y-4">
          <div className="flex items-start gap-2.5">
            <input
              id="accept-terms"
              type="checkbox"
              checked={acceptedTerms}
              disabled={busy}
              onChange={(e) => setAcceptedTerms(e.target.checked)}
              className="mt-1 w-4 h-4 rounded border-rule accent-quiet shrink-0 cursor-pointer disabled:cursor-not-allowed"
            />
            <div className="min-w-0">
              <label htmlFor="accept-terms" className="text-[0.875rem] text-ink leading-relaxed cursor-pointer">
                Đã đọc và chấp nhận các điều khoản
              </label>
              <p className="text-[0.8125rem] text-ink-faint leading-relaxed mt-0.5">
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
              <div className="flex items-center gap-2.5 min-w-0">
                <span id="model-label" className="text-[0.8125rem] font-medium text-ink-muted shrink-0">
                  Chế độ
                </span>
                <div role="radiogroup" aria-labelledby="model-label" className="flex flex-wrap gap-1.5 p-1 rounded-xl bg-surface-container">
                  {models.map((m) => {
                    const active = provider === m.provider;
                    return (
                      <button
                        key={m.provider}
                        type="button"
                        role="radio"
                        aria-checked={active}
                        disabled={busy}
                        onClick={() => setProvider(m.provider)}
                        className={`px-3.5 py-1.5 rounded-lg text-[0.875rem] font-medium transition-colors disabled:cursor-not-allowed ${
                          active
                            ? "bg-paper-raised text-quiet shadow-sm"
                            : "text-ink-muted hover:text-ink"
                        }`}
                      >
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            <button
              type="button"
              className="xs:ml-auto px-5 py-2.5 bg-quiet text-white text-[0.875rem] font-semibold rounded-lg shadow-sm hover:bg-quiet/90 transition-colors flex items-center justify-center gap-2 disabled:opacity-40 disabled:cursor-not-allowed"
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
              <span className="material-symbols-outlined">arrow_forward</span>
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
