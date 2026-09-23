import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-automatic-print-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const STATES = new Set(["idle", "running", "completed", "failed", "stopped"]);
const DEPARTMENTS = new Set(["DTF", "UV", "3D"]);
const STALE_SECONDS = 90;
const COMMAND_STATES = new Set(["running", "succeeded", "failed"]);
const COMMAND_PLATFORMS = new Set(["Haloo", "莆田", "隆丰"]);
const COMMAND_ACTIONS = new Set(["download_layout", "pause_print", "clean_resume"]);

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
    if (action === "enqueue_command") return json(await enqueueCommand(db, input));
    if (action === "send_control") return json(await sendControl(db, input));
    if (action === "list_commands") return json(await listCommands(db));
    if (action === "claim_command") return json(await claimCommand(db, input));
    if (action === "claim_control") return json(await claimControl(db, input));
    if (action === "get_command") return json(await getCommand(db, input));
    if (action === "update_command") return json(await updateCommand(db, input));
    if (action === "cancel_command") return json(await cancelCommand(db, input));
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

async function enqueueCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  if (COMMAND_ACTIONS.has(String(input.command_action || "")) &&
      String(input.command_action) !== "download_layout") {
    return sendControl(db, input);
  }
  const target = machineId(input.target_machine_id);
  const requester = machineId(input.machine_id);
  const action = "download_layout";
  const payload = commandPayload(input.payload);
  const { data: machine, error: machineError } = await db.from("machine_status_current")
    .select("machine_id, heartbeat_at, source_online").eq("machine_id", target).maybeSingle();
  if (machineError) throw machineError;
  if (!machine) throw new ClientError("Target machine not found", 404);
  const age = (Date.now() - new Date(String(machine.heartbeat_at)).getTime()) / 1000;
  if (age > STALE_SECONDS) throw new ClientError("Target monitor is offline", 409);
  if (payload.generate_prn && machine.source_online === false) {
    throw new ClientError("Target PrintExp is offline", 409);
  }
  const expiry = optionalInteger(input.expires_minutes, 5, 120) ?? 30;
  const { data, error } = await db.from("machine_commands").insert({
    target_machine_id: target,
    requested_by_machine_id: requester,
    requested_by_name: text(input.machine_name, "machine_name", 100),
    action,
    payload,
    expires_at: new Date(Date.now() + expiry * 60_000).toISOString(),
  }).select().single();
  if (error) throw error;
  return { command: data };
}

async function sendControl(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const target = machineId(input.target_machine_id);
  const requester = machineId(input.machine_id);
  const action = String(input.command_action || "");
  if (action !== "pause_print" && action !== "clean_resume") {
    throw new ClientError("Unsupported control action", 400);
  }
  const { data: machine, error: machineError } = await db.from("machine_status_current")
    .select("machine_id, heartbeat_at, source_online").eq("machine_id", target).maybeSingle();
  if (machineError) throw machineError;
  if (!machine) throw new ClientError("Target machine not found", 404);
  const age = (Date.now() - new Date(String(machine.heartbeat_at)).getTime()) / 1000;
  if (age > STALE_SECONDS) throw new ClientError("Target monitor is offline", 409);
  if (machine.source_online === false) throw new ClientError("Target PrintExp is offline", 409);
  const now = new Date().toISOString();
  const { error: cancelError } = await db.from("machine_commands").update({
    status: "cancelled", phase: "由更新的实时控制指令替代",
    finished_at: now, updated_at: now,
  }).eq("target_machine_id", target).eq("status", "queued")
    .in("action", ["pause_print", "clean_resume"]);
  if (cancelError) throw cancelError;
  const expiry = optionalInteger(input.expires_minutes, 1, 5) ?? 2;
  const { data, error } = await db.from("machine_commands").insert({
    target_machine_id: target,
    requested_by_machine_id: requester,
    requested_by_name: text(input.machine_name, "machine_name", 100),
    action, payload: {}, phase: "实时控制信号已发送",
    expires_at: new Date(Date.now() + expiry * 60_000).toISOString(),
  }).select().single();
  if (error) throw error;
  return { command: data };
}

async function listCommands(db: ReturnType<typeof createClient>) {
  const { data, error } = await db.from("machine_commands").select("*")
    .order("created_at", { ascending: false }).limit(50);
  if (error) throw error;
  return { commands: data || [] };
}

async function claimCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const id = machineId(input.machine_id);
  const { data, error } = await db.rpc("claim_machine_command", { target_id: id }).maybeSingle();
  if (error) throw error;
  return { command: data || null };
}

async function claimControl(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const id = machineId(input.machine_id);
  const { data, error } = await db.rpc("claim_machine_control", { target_id: id }).maybeSingle();
  if (error) throw error;
  return { command: data || null };
}

async function getCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const target = machineId(input.machine_id);
  const id = uuid(input.command_id, "command_id");
  const { data, error } = await db.from("machine_commands").select("*")
    .eq("id", id).eq("target_machine_id", target).maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError("Command not found", 404);
  return { command: data };
}

async function updateCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const target = machineId(input.machine_id);
  const id = uuid(input.command_id, "command_id");
  const status = text(input.status, "status", 20);
  if (!COMMAND_STATES.has(status)) throw new ClientError("Invalid command status", 400);
  const now = new Date().toISOString();
  const changes: Record<string, unknown> = {
    status,
    phase: String(input.phase || "").slice(0, 300),
    progress_percent: optionalInteger(input.progress_percent, 0, 100),
    result: object(input.result),
    error_message: optionalText(input.error_message, 2000),
    updated_at: now,
  };
  if (status === "succeeded" || status === "failed") changes.finished_at = now;
  const { data: current, error: readError } = await db.from("machine_commands")
    .select("revision, status").eq("id", id).eq("target_machine_id", target).maybeSingle();
  if (readError) throw readError;
  if (!current) throw new ClientError("Command not found", 404);
  if (["succeeded", "failed", "cancelled", "expired"].includes(current.status)) {
    throw new ClientError("Command is already terminal", 409);
  }
  if (status === "running" && current.status !== "running") changes.started_at = now;
  changes.revision = Number(current.revision || 0) + 1;
  const { data, error } = await db.from("machine_commands").update(changes)
    .eq("id", id).eq("target_machine_id", target).select().single();
  if (error) throw error;
  return { command: data };
}

async function cancelCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const id = uuid(input.command_id, "command_id");
  const now = new Date().toISOString();
  const { data, error } = await db.from("machine_commands").update({
    status: "cancelled", phase: "由控制端取消", finished_at: now, updated_at: now,
  }).eq("id", id).eq("status", "queued").select().maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError("Only queued commands can be cancelled", 409);
  return { command: data };
}

function commandPayload(value: unknown) {
  const payload = object(value);
  const platform = text(payload.platform, "platform", 20);
  if (!COMMAND_PLATFORMS.has(platform)) throw new ClientError("Unsupported platform", 400);
  if (!Array.isArray(payload.batch_numbers) || !payload.batch_numbers.length || payload.batch_numbers.length > 20) {
    throw new ClientError("Invalid batch_numbers", 400);
  }
  const batches = payload.batch_numbers.map(item => String(item).trim());
  if (batches.some(item => !/^\d{12}$/.test(item)) || new Set(batches).size !== batches.length) {
    throw new ClientError("Invalid batch number", 400);
  }
  const layout = object(payload.layout_settings);
  if (JSON.stringify(layout).length > 20_000) throw new ClientError("Layout settings too large", 400);
  return { platform, batch_numbers: batches, layout_settings: layout,
    generate_prn: optionalBoolean(payload.generate_prn, true) };
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
function uuid(value: unknown, name: string) {
  const id = String(value || "").toLowerCase();
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/.test(id)) {
    throw new ClientError(`Invalid ${name}`, 400);
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
function object(value: unknown): Record<string, unknown> {
  if (value == null) return {};
  if (typeof value !== "object" || Array.isArray(value)) throw new ClientError("Invalid batch_info", 400);
  return value as Record<string, unknown>;
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
