const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const STORAGE_KEY = "contractlens_auth";

async function authHeaders() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const auth = raw ? JSON.parse(raw) : null;
    const token = auth?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

async function handleResponse(res) {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return res.json();
}

export async function uploadContract(file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}/api/v1/upload`, {
    method: "POST",
    headers: await authHeaders(),
    body: formData,
  });
  return handleResponse(res);
}

export async function analyzeContract(contractId, provider, force = false) {
  const res = await fetch(`${API_BASE}/api/v1/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ contract_id: contractId, provider, force }),
  });
  return handleResponse(res);
}

export async function listContracts() {
  const res = await fetch(`${API_BASE}/api/v1/contracts`, {
    headers: await authHeaders(),
  });
  return handleResponse(res);
}

export async function fetchModels() {
  const res = await fetch(`${API_BASE}/api/v1/models`);
  return handleResponse(res);
}

export async function chatWithContract(contractId, question, provider) {
  const res = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ contract_id: contractId, question, provider }),
  });
  return handleResponse(res);
}

export async function streamChat(contractId, question, provider, onEvent) {
  const res = await fetch(`${API_BASE}/api/v1/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(await authHeaders()) },
    body: JSON.stringify({ contract_id: contractId, question, provider }),
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const event = frame.match(/^event:\s*(\S+)/m)?.[1];
      const dataLine = frame.match(/^data:\s*(.+)$/m)?.[1];
      if (event && dataLine) {
        try {
          onEvent(event, JSON.parse(dataLine));
        } catch {
          // ignore malformed frame
        }
      }
    }
  }
}

export async function fetchChatHistory(contractId) {
  const res = await fetch(`${API_BASE}/api/v1/chat/${contractId}/history`, {
    headers: await authHeaders(),
  });
  return handleResponse(res);
}
