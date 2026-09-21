// SDS factory credentials stay in Edge Function secrets, never in the desktop app.
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-automatic-print-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const API = "https://factory-api.sdspod.com";

class ClientError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function requiredEnv(name: string): string {
  const value = Deno.env.get(name)?.trim();
  if (!value) throw new ClientError(`${name} is not configured`, 503);
  return value;
}

async function digest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });
}

async function factoryToken(): Promise<string> {
  const credentials = JSON.parse(requiredEnv("YDWX_FACTORY_LOGIN_JSON"));
  for (const field of ["contact_tel", "factory_code", "password", "extraInfo"]) {
    if (typeof credentials[field] !== "string" || !credentials[field]) {
      throw new ClientError(`Factory login is missing ${field}`, 503);
    }
  }
  const response = await fetch(`${API}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Accept": "application/json" },
    body: JSON.stringify(credentials),
  });
  if (!response.ok) throw new ClientError(`Factory login failed (${response.status})`, 503);
  const body = await response.json();
  const token = body?.data?.access_token || body?.data?.token;
  if (typeof token !== "string" || !token) throw new ClientError("Factory login returned no token", 503);
  return token;
}

async function batchList(token: string): Promise<Response> {
  const response = await fetch(`${API}/factoryTask/producing?onlyShowProducing=0`, {
    headers: { "Access-Token": token, "Accept": "application/json",
      "Origin": "https://factory.sdsdiy.com", "Referer": "https://factory.sdsdiy.com/" },
  });
  if (!response.ok) throw new ClientError(`Factory batch list failed (${response.status})`, 502);
  const body = await response.json();
  if (!Array.isArray(body?.dateList)) throw new ClientError("Factory batch response is invalid", 502);
  return json(body);
}

async function manuscript(token: string, input: Record<string, unknown>): Promise<Response> {
  const taskId = Number(input.task_id);
  const mode = input.mode;
  if (!Number.isSafeInteger(taskId) || taskId <= 0 || !["down", "redown"].includes(String(mode))) {
    throw new ClientError("Invalid task or download mode", 400);
  }
  const query = new URLSearchParams({ taskId: String(taskId), access_token: token, type: String(mode) });
  const upstream = await fetch(`${API}/factory_orders/downloadManuscriptsByTaskId?${query}`, {
    headers: { "Referer": "https://factory.sdsdiy.com/" },
  });
  if (!upstream.ok || !upstream.body) throw new ClientError(`Factory download failed (${upstream.status})`, 502);
  return new Response(upstream.body, {
    status: 200,
    headers: { ...CORS, "Content-Type": "application/zip", "Cache-Control": "no-store" },
  });
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  try {
    const supplied = request.headers.get("x-automatic-print-key") || "";
    const installerKey = requiredEnv("AUTOMATIC_PRINT_API_KEY");
    const shareKey = Deno.env.get("YDWX_SHARE_API_KEY")?.trim() || "";
    const authorized = supplied && (
      await digest(supplied) === await digest(installerKey) ||
      (shareKey && await digest(supplied) === await digest(shareKey))
    );
    if (!authorized) {
      throw new ClientError("Unauthorized", 401);
    }
    const input = await request.json();
    const token = await factoryToken();
    if (input?.action === "list") return await batchList(token);
    if (input?.action === "download") return await manuscript(token, input);
    throw new ClientError("Unsupported action", 400);
  } catch (error) {
    return json({ error: error instanceof Error ? error.message : "Unknown error" },
      error instanceof ClientError ? error.status : 500);
  }
});
