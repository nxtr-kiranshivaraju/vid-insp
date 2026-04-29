export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(status: number, message: string, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function request<T>(input: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  if (!headers.has("Accept")) headers.set("Accept", "application/json");

  const res = await fetch(input, { ...init, headers, credentials: "include" });
  const ct = res.headers.get("content-type") ?? "";
  const isJson = ct.includes("application/json");
  const body = isJson ? await res.json().catch(() => null) : await res.text();
  if (!res.ok) {
    const message =
      (body && typeof body === "object" && "error" in body && String((body as { error: unknown }).error)) ||
      `HTTP ${res.status}`;
    throw new ApiError(res.status, message, body);
  }
  return body as T;
}

export async function requestText(input: string, init: RequestInit = {}): Promise<string> {
  const headers = new Headers(init.headers);
  const res = await fetch(input, { ...init, headers, credentials: "include" });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new ApiError(res.status, `HTTP ${res.status}`, text);
  }
  return res.text();
}
