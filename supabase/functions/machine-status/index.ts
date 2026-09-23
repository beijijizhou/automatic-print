import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-automatic-print-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const STATES = new Set(["idle", "running", "completed", "failed", "stopped"]);
const DEPARTMENTS = new Set(["DTF", "UV", "3D"]);
const STALE_SECONDS = 90;

class ClientError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  try {
    await authorize(request);
    const input = await request.json();
    const db = createClient(requiredEnv("SUPABASE_URL"), requiredEnv("SUPABASE_SERVICE_ROLE_KEY"));
    const action = String(input?.action || "");
    if (action === "report") return json(await report(db, input));
    if (action === "list") return json(await list(db));
    if (action === "get") return json(await get(db, machineId(input.machine_id)));
    throw new ClientError("Unsupported action", 400);
  } catch (error) {
    const status = error instanceof ClientError ? error.status : 500;
    return json({ error: error instanceof Error ? error.message : String(error) }, status);
  }
});

async function report(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const id = machineId(input.machine_id);
  const state = text(input.state, "state", 20);
  if (!STATES.has(state)) throw new ClientError("Invalid state", 400);
  const department = text(input.department || "DTF", "department", 3).toUpperCase();
  if (!DEPARTMENTS.has(department)) throw new ClientError("Invalid department", 400);
  const progress = optionalInteger(input.progress_percent, 0, 100);
  const remaining = optionalInteger(input.remaining_seconds, 0, 31_536_000);
  const scope = input.estimate_scope == null ? null : String(input.estimate_scope);
  if (scope !== null && scope !== "phase" && scope !== "batch") {
    throw new ClientError("Invalid estimate_scope", 400);
  }
  const now = new Date();
  const row = {
    machine_id: id,
    machine_name: text(input.machine_name, "machine_name", 100),
    department,
    state,
    phase: String(input.phase || "").slice(0, 160),
    progress_percent: progress,
    batch_id: optionalText(input.batch_id, 160),
    batch_name: optionalText(input.batch_name, 240),
    batch_info: object(input.batch_info),
    remaining_seconds: remaining,
    estimate_scope: remaining === null ? null : scope,
    estimated_finish_at: remaining === null
      ? null : new Date(now.getTime() + remaining * 1000).toISOString(),
    started_at: optionalDate(input.started_at),
    heartbeat_at: now.toISOString(),
    app_version: String(input.app_version || "").slice(0, 40),
    error_message: optionalText(input.error_message, 1000),
    source_online: optionalBoolean(input.source_online, true),
    updated_at: now.toISOString(),
  };
  const { data: previous, error: readError } = await db.from("machine_status_current")
    .select("revision").eq("machine_id", id).maybeSingle();
  if (readError) throw readError;
  const { data, error } = await db.from("machine_status_current")
    .upsert({ ...row, revision: Number(previous?.revision || 0) + 1 })
    .select().single();
  if (error) throw error;
  return { machine: decorate(data) };
}

async function list(db: ReturnType<typeof createClient>) {
  const { data, error } = await db.from("machine_status_current").select("*")
    .order("machine_name", { ascending: true });
  if (error) throw error;
  return { machines: (data || []).map(decorate), stale_after_seconds: STALE_SECONDS };
}

async function get(db: ReturnType<typeof createClient>, id: string) {
  const { data, error } = await db.from("machine_status_current").select("*")
    .eq("machine_id", id).maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError("Machine not found", 404);
  return { machine: decorate(data), stale_after_seconds: STALE_SECONDS };
}

function decorate(row: Record<string, unknown>) {
  const age = Math.max(0, (Date.now() - new Date(String(row.heartbeat_at)).getTime()) / 1000);
  const agentOnline = age <= STALE_SECONDS;
  return {
    ...row,
    agent_online: agentOnline,
    online: agentOnline && row.source_online !== false,
    heartbeat_age_seconds: Math.round(age),
  };
}

async function authorize(request: Request) {
  const supplied = request.headers.get("x-automatic-print-key") || "";
  const allowed = [Deno.env.get("AUTOMATIC_PRINT_API_KEY") || "",
    Deno.env.get("YDWX_SHARE_API_KEY") || ""].filter(Boolean);
  if (!supplied || !allowed.length) throw new ClientError("Unauthorized", 401);
  const candidate = await digest(supplied);
  for (const value of allowed) if (candidate === await digest(value)) return;
  throw new ClientError("Unauthorized", 401);
}

function machineId(value: unknown) {
  const id = String(value || "").toLowerCase();
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)) {
    throw new ClientError("Invalid machine_id", 400);
  }
  return id;
}
function text(value: unknown, name: string, limit: number) {
  const result = String(value || "").trim();
  if (!result || result.length > limit) throw new ClientError(`Invalid ${name}`, 400);
  return result;
}
function optionalText(value: unknown, limit: number) {
  if (value == null || String(value).trim() === "") return null;
  return String(value).trim().slice(0, limit);
}
function optionalInteger(value: unknown, minimum: number, maximum: number) {
  if (value == null) return null;
  const result = Number(value);
  if (!Number.isInteger(result) || result < minimum || result > maximum) {
    throw new ClientError("Invalid numeric value", 400);
  }
  return result;
}
function optionalDate(value: unknown) {
  if (value == null || value === "") return null;
  const result = new Date(String(value));
  if (Number.isNaN(result.getTime())) throw new ClientError("Invalid started_at", 400);
  return result.toISOString();
}
function object(value: unknown) {
  if (value == null) return {};
  if (typeof value !== "object" || Array.isArray(value)) throw new ClientError("Invalid batch_info", 400);
  return value;
}
function optionalBoolean(value: unknown, fallback: boolean) {
  if (value == null) return fallback;
  if (typeof value !== "boolean") throw new ClientError("Invalid boolean value", 400);
  return value;
}
async function digest(value: string) {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), byte => byte.toString(16).padStart(2, "0")).join("");
}
function requiredEnv(name: string) {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing ${name}`);
  return value;
}
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });
}
