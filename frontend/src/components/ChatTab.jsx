import { useEffect, useRef, useState } from "react";
import { fetchChatHistory, streamChat } from "../api";

function historyToMessages(historyItems) {
  const messages = [];
  for (const item of historyItems) {
    messages.push({ role: "user", text: item.question });
    messages.push({
      role: "assistant",
      text: item.answer,
      sourceClauses: item.source_clauses || [],
      needsClarification: item.needs_clarification,
    });
  }
  return messages;
}

function SourceClauseBadges({ clauses }) {
  if (!clauses?.length) return null;
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {clauses.map((c) => (
        <span
          key={c}
          className="inline-flex items-center gap-0.5 bg-quiet-soft text-quiet px-1.5 py-0.5 rounded-sm text-[0.625rem] font-medium"
        >
          <span className="material-symbols-outlined !text-[0.75rem]">bookmark</span>
          Điều {c}
        </span>
      ))}
    </div>
  );
}

function ChatBubble({ message }) {
  const isUser = message.role === "user";

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] sm:max-w-[75%] bg-ink text-paper-raised px-3 py-2 rounded-md rounded-tr-sm ui-text">
          {message.text}
        </div>
      </div>
    );
  }

  const isClarification = message.needsClarification;

  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[85%] sm:max-w-[75%] px-3 py-2 rounded-md rounded-tl-sm ui-text ${
          isClarification
            ? "bg-caution-soft text-ink border border-caution/30"
            : "bg-paper text-ink border border-rule"
        }`}
      >
        {isClarification && (
          <div className="flex items-center gap-1 mb-1 text-[0.625rem] font-medium uppercase tracking-wide text-caution">
            <span className="material-symbols-outlined !text-[0.875rem]">help</span>
            Cần làm rõ thêm
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.text}</p>
        <SourceClauseBadges clauses={message.sourceClauses} />
      </div>
    </div>
  );
}

export default function ChatTab({ contractId, provider }) {
  const [messages, setMessages] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingHistory(true);
    fetchChatHistory(contractId)
      .then((res) => {
        if (!cancelled) setMessages(historyToMessages(res.messages || []));
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Không tải được lịch sử hỏi đáp.");
      })
      .finally(() => {
        if (!cancelled) setLoadingHistory(false);
      });
    return () => {
      cancelled = true;
    };
  }, [contractId]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || sending) return;

    setError(null);
    setInput("");
    setMessages((prev) => [...prev, { role: "user", text: question }]);
    setSending(true);
    setStatus("Đang xử lý...");

    let answer = "";
    let sourceClauses = [];
    let needsClarification = false;

    try {
      await streamChat(contractId, question, provider, (event, data) => {
        if (event === "step") {
          setStatus(data.label || "Đang xử lý...");
        } else if (event === "done") {
          answer = data.answer || "";
          sourceClauses = data.source_clauses || [];
          needsClarification = data.needs_clarification || false;
        }
      });
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: answer,
          sourceClauses,
          needsClarification,
        },
      ]);
    } catch (err) {
      setError(err.message || "Đã xảy ra lỗi khi gửi câu hỏi.");
    } finally {
      setSending(false);
      setStatus(null);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-7.5rem)] md:h-[calc(100vh-5.5rem)] max-h-[900px] bg-paper-raised border border-rule rounded-md overflow-hidden shadow-sm animate-fade-in">
      <div className="px-3.5 py-2.5 border-b border-rule">
        <h3 className="section-title">Hỏi đáp về hợp đồng</h3>
        <p className="text-[0.75rem] text-ink-muted mt-0.5">
          Câu trả lời trích dẫn nguồn điều khoản / luật.
        </p>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3.5 py-4 space-y-3">
        {loadingHistory ? (
          <p className="text-ink-muted text-center ui-text">Đang tải lịch sử hỏi đáp...</p>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-1.5 px-4">
            <span className="material-symbols-outlined text-ink-faint !text-[1.5rem]">forum</span>
            <p className="text-ink-muted max-w-sm ui-text">
              Hỏi về hợp đồng hoặc luật liên quan — câu trả lời sẽ trích dẫn nguồn.
            </p>
          </div>
        ) : (
          messages.map((m, idx) => <ChatBubble key={idx} message={m} />)
        )}

        {sending && (
          <div className="flex justify-start">
            <div className="bg-paper border border-rule rounded-md px-3 py-2 flex items-center gap-2 ui-text text-ink-muted">
              <span className="w-1 h-1 rounded-full bg-ink animate-pulse" />
              <span className="w-1 h-1 rounded-full bg-ink animate-pulse [animation-delay:150ms]" />
              <span className="w-1 h-1 rounded-full bg-ink animate-pulse [animation-delay:300ms]" />
              {status && <span className="text-[0.75rem]">{status}</span>}
            </div>
          </div>
        )}
      </div>

      {error && <p className="px-3.5 text-stamp text-[0.75rem] font-medium pb-1.5">{error}</p>}

      <div className="border-t border-rule p-2.5 sm:p-3 flex items-end gap-2">
        <textarea
          className="flex-1 resize-none rounded-md border border-rule bg-paper px-3 py-2 ui-text text-ink focus:outline-none focus:border-quiet max-h-28"
          rows={1}
          placeholder="Nhập câu hỏi..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button
          type="button"
          className="shrink-0 w-9 h-9 rounded-md bg-ink text-paper-raised flex items-center justify-center hover:bg-ink/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={handleSend}
          disabled={sending || !input.trim()}
          aria-label="Gửi"
        >
          <span className="material-symbols-outlined !text-[1.125rem]">send</span>
        </button>
      </div>
    </div>
  );
}
