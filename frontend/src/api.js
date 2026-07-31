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

export async function fetchChatHistory(contractId) {
  const res = await fetch(`${API_BASE}/api/v1/chat/${contractId}/history`, {
    headers: await authHeaders(),
  });
  return handleResponse(res);
}
