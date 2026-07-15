import { useEffect, useRef, useState } from "react";
import { chatWithContract, fetchChatHistory } from "../api";

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
    <div className="flex flex-wrap gap-2 mt-3">
      {clauses.map((c) => (
        <span
          key={c}
          className="inline-flex items-center gap-1 bg-primary-fixed text-on-primary-fixed px-2 py-0.5 rounded-full text-label-sm font-label-bold"
        >
          <span className="material-symbols-outlined text-[14px]">bookmark</span>
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
        <div className="max-w-[75%] bg-primary text-on-primary px-4 py-3 rounded-xl rounded-tr-sm font-body-md text-body-md">
          {message.text}
        </div>
      </div>
    );
  }

  const isClarification = message.needsClarification;

  return (
    <div className="flex justify-start">
      <div
        className={`max-w-[75%] px-4 py-3 rounded-xl rounded-tl-sm font-body-md text-body-md ${
          isClarification
            ? "bg-tertiary-fixed text-on-tertiary-fixed border border-warning-gold/40"
            : "bg-surface-container-lowest text-on-surface border border-border-subtle"
        }`}
      >
        {isClarification && (
          <div className="flex items-center gap-1 mb-1 text-label-sm font-label-bold uppercase tracking-wide">
            <span className="material-symbols-outlined text-[16px]">help</span>
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
  const [input, setInput] = useState("");
  const [error, setError] = useState(null);
  const scrollRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
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

    try {
      const response = await chatWithContract(contractId, question, provider);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: response.answer,
          sourceClauses: response.source_clauses || [],
          needsClarification: response.needs_clarification,
        },
      ]);
    } catch (err) {
      setError(err.message || "Đã xảy ra lỗi khi gửi câu hỏi.");
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)] max-h-[900px] bg-surface-container-lowest border border-border-subtle rounded-xl overflow-hidden shadow-sm">
      <div className="flex items-center gap-2 px-card-padding py-4 border-b border-border-subtle">
        <span className="material-symbols-outlined text-primary" style={{ fontVariationSettings: "'FILL' 1" }}>
          chat
        </span>
        <h3 className="font-headline-sm text-headline-sm text-primary">Hỏi đáp về hợp đồng & luật liên quan</h3>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto px-card-padding py-6 space-y-4">
        {loadingHistory ? (
          <p className="text-on-surface-variant text-center">Đang tải lịch sử hỏi đáp...</p>
        ) : messages.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-3">
            <div className="w-16 h-16 rounded-full bg-primary-fixed flex items-center justify-center">
              <span className="material-symbols-outlined text-[32px] text-primary">forum</span>
            </div>
            <p className="text-on-surface-variant max-w-sm">
              Hỏi bất cứ điều gì về hợp đồng này hoặc luật liên quan — câu trả lời sẽ luôn trích dẫn nguồn.
            </p>
          </div>
        ) : (
          messages.map((m, idx) => <ChatBubble key={idx} message={m} />)
        )}

        {sending && (
          <div className="flex justify-start">
            <div className="bg-surface-container-lowest border border-border-subtle px-4 py-3 rounded-xl rounded-tl-sm flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse [animation-delay:150ms]" />
              <span className="w-2 h-2 rounded-full bg-primary animate-pulse [animation-delay:300ms]" />
            </div>
          </div>
        )}
      </div>

      {error && <p className="px-card-padding text-error font-label-bold text-label-bold pb-2">{error}</p>}

      <div className="border-t border-border-subtle p-4 flex items-end gap-3">
        <textarea
          className="flex-1 resize-none rounded-lg border border-border-subtle bg-surface-container-low px-4 py-3 font-body-md text-body-md text-on-surface focus:outline-none focus:ring-2 focus:ring-secondary max-h-32"
          rows={1}
          placeholder="Nhập câu hỏi về hợp đồng hoặc luật liên quan..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={sending}
        />
        <button
          className="shrink-0 w-11 h-11 rounded-lg bg-primary text-on-primary flex items-center justify-center hover:opacity-90 transition-all disabled:opacity-40 disabled:cursor-not-allowed"
          onClick={handleSend}
          disabled={sending || !input.trim()}
        >
          <span className="material-symbols-outlined">send</span>
        </button>
      </div>
    </div>
  );
}
