export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function apiUrl(path, base = import.meta.env?.VITE_API_URL || "/api") {
  return `${base.replace(/\/+$/, "")}/${path.replace(/^\/+/, "")}`;
}

function errorMessage(detail, status) {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail
      .map((item) => item.msg)
      .filter(Boolean)
      .join(". ");
  return status === 401
    ? "Tu sesión ha caducado. Inicia sesión de nuevo."
    : `Error del servidor (${status}).`;
}

export async function apiRequest(path, { body, headers, ...options } = {}) {
  const response = await fetch(apiUrl(path), {
    ...options,
    credentials: "include",
    headers: {
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      errorMessage(data?.detail, response.status),
      response.status,
    );
  return data;
}

export async function apiCollection(path, options) {
  const data = await apiRequest(path, options);
  if (!Array.isArray(data))
    throw new ApiError("El servidor devolvió una lista no válida.", 502);
  return data;
}
