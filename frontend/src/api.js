// All calls to the backend go through these functions.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "/api";

async function readResponse(response) {
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    // The backend always sends errors as {"error": {"code", "message", "request_id"}}.
    const message = body?.error?.message || `Request failed (${response.status})`;
    throw new Error(message);
  }
  return body;
}

export async function uploadCase(file) {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/cases`, { method: "POST", body: formData });
  return readResponse(response);
}

export async function getCase(caseId) {
  return readResponse(await fetch(`${API_BASE_URL}/cases/${caseId}`));
}

export async function listCases() {
  return readResponse(await fetch(`${API_BASE_URL}/cases`));
}

export async function reviewCase(caseId, review) {
  const response = await fetch(`${API_BASE_URL}/cases/${caseId}/review`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(review),
  });
  return readResponse(response);
}

export async function getDashboardSummary() {
  return readResponse(await fetch(`${API_BASE_URL}/dashboard/summary`));
}
