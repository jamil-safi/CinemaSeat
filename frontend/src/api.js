const API_BASE = "/api/v1";

export async function apiRequest(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const payload = await response.json();
      message = payload.detail || message;
    } catch {
      // Preserve the HTTP fallback for non-JSON proxy errors.
    }
    throw new Error(message);
  }

  return response.status === 204 ? null : response.json();
}
