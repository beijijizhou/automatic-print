import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, apikey, content-type, x-automatic-print-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const STATES = new Set(["idle", "running", "completed", "failed", "stopped"]);
const DEPARTMENTS = new Set(["DTF", "UV", "3D"]);
const FEEDBACK_TIMEOUT_SECONDS = 20;
const COMMAND_STATES = new Set(["running", "succeeded", "failed"]);
const COMMAND_PLATFORMS = new Set(["Haloo", "莆田", "隆丰", "S2B"]);
const COMMAND_ACTIONS = new Set([
  "download_layout", "start_print", "pause_print", "clean_resume", "probe", "source_update",
  "launch_app",
]);
const PRINTER_TO_MACHINE_STATE: Record<string, string> = {
  idle: "idle", ready: "idle", printing: "running", paused: "running",
  cleaning: "running", unknown: "failed",
};
const PRINTER_CONTROL_SOURCES: Record<string, Set<string>> = {
  start_print: new Set(["ready", "paused"]),
  pause_print: new Set(["printing"]),
  clean_resume: new Set(["printing", "paused"]),
};

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
    if (action === "set_availability") return json(await setAvailability(db, input));
    if (action === "enqueue_command") return json(await enqueueCommand(db, input));
    if (action === "enqueue_update") return json(await enqueueUpdate(db, input));
    if (action === "send_control") return json(await sendControl(db, input));
    if (action === "list_commands") return json(await listCommands(db));
    if (action === "claim_command") return json(await claimCommand(db, input));
    if (action === "claim_control") return json(await claimControl(db, input));
    if (action === "get_command") return json(await getCommand(db, input));
    if (action === "update_command") return json(await updateCommand(db, input));
    if (action === "consume_command_result") return json(await consumeCommandResult(db, input));
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
  const batchInfo = object(input.batch_info);
  validateReportedPrinterState(state, batchInfo);
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
    batch_info: batchInfo,
    remaining_seconds: remaining,
    estimate_scope: remaining === null ? null : scope,
    estimated_finish_at: remaining === null
      ? null : new Date(now.getTime() + remaining * 1000).toISOString(),
    started_at: optionalDate(input.started_at),
    heartbeat_at: now.toISOString(),
    app_version: String(input.app_version || "").slice(0, 40),
    error_message: optionalText(input.error_message, 1000),
    source_online: optionalBoolean(input.source_online, true),
    auto_available: true,
    availability_reason: "",
    last_feedback_at: now.toISOString(),
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
  await markUnresponsiveMachines(db);
  const { data, error } = await db.from("machine_status_current").select("*")
    .order("machine_name", { ascending: true });
  if (error) throw error;
  return { machines: (data || []).map(decorate), feedback_timeout_seconds: FEEDBACK_TIMEOUT_SECONDS };
}

async function get(db: ReturnType<typeof createClient>, id: string) {
  const { data, error } = await db.from("machine_status_current").select("*")
    .eq("machine_id", id).maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError("Machine not found", 404);
  return { machine: decorate(data), feedback_timeout_seconds: FEEDBACK_TIMEOUT_SECONDS };
}

async function setAvailability(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const target = machineId(input.target_machine_id);
  const availability = String(input.availability || "");
  if (!new Set(["auto", "available", "unavailable"]).has(availability)) {
    throw new ClientError("Invalid availability", 400);
  }
  const { data, error } = await db.from("machine_status_current").update({
    availability_override: availability,
    updated_at: new Date().toISOString(),
  }).eq("machine_id", target).select().maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError("Target machine not found", 404);
  return { machine: decorate(data) };
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
    .select("machine_id, source_online, availability_override, auto_available")
    .eq("machine_id", target).maybeSingle();
  if (machineError) throw machineError;
  if (!machine) throw new ClientError("Target machine not found", 404);
  if (!isAvailable(machine)) throw new ClientError("Target machine is unavailable", 409);
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
  if (!new Set(["start_print", "pause_print", "clean_resume", "probe", "launch_app"]).has(action)) {
    throw new ClientError("Unsupported control action", 400);
  }
  const { data: machine, error: machineError } = await db.from("machine_status_current")
    .select("machine_id, source_online, state, progress_percent, batch_name, batch_info, availability_override, auto_available")
    .eq("machine_id", target).maybeSingle();
  if (machineError) throw machineError;
  if (!machine) throw new ClientError("Target machine not found", 404);
  const printerControl = new Set(["start_print", "pause_print", "clean_resume"]).has(action);
  if (printerControl && !isAvailable(machine)) {
    throw new ClientError("Target machine is unavailable", 409);
  }
  if (printerControl && machine.source_online === false) {
    throw new ClientError("Target PrintExp is offline", 409);
  }
  const requestedPayload = input.payload && typeof input.payload === "object"
    ? input.payload as Record<string, unknown> : {};
  const expectedBatch = String(requestedPayload.expected_batch_name || "").trim();
  const printerState = printerControl ? validatePrinterControlState(machine, action) : "";
  const probePayload = action === "probe" && requestedPayload.request === "printer_history"
    ? {
        request: "printer_history",
        limit: optionalInteger(requestedPayload.limit, 1, 500) ?? 500,
        days: optionalInteger(requestedPayload.days, 1, 31) ?? 2,
      }
    : {};
  if (action === "start_print") {
    const machineProgress = machine.progress_percent == null
      ? Number.NaN : Number(machine.progress_percent);
    const ready = printerState === "ready" && machineProgress === 0;
    const paused = printerState === "paused" && machineProgress >= 0 && machineProgress < 100;
    if (!ready && !paused) {
      throw new ClientError("Target PrintExp is not ready or paused", 409);
    }
    if ((machine.batch_info as Record<string, unknown> | null)?.task_name_verified !== true) {
      throw new ClientError("Target PRN task name is not verified", 409);
    }
    if (!expectedBatch || expectedBatch.toLocaleLowerCase() !==
        String(machine.batch_name || "").trim().toLocaleLowerCase()) {
      throw new ClientError("Target batch changed before printing", 409);
    }
  }
  const now = new Date().toISOString();
  if (printerControl) {
    const { error: cancelError } = await db.from("machine_commands").update({
      status: "cancelled", phase: "由更新的实时控制指令替代",
      finished_at: now, updated_at: now,
    }).eq("target_machine_id", target).eq("status", "queued")
      .in("action", ["start_print", "pause_print", "clean_resume"]);
    if (cancelError) throw cancelError;
  } else if (action === "launch_app") {
    const { error: cancelError } = await db.from("machine_commands").update({
      status: "cancelled", phase: "由更新的软件唤起指令替代",
      finished_at: now, updated_at: now,
    }).eq("target_machine_id", target).eq("status", "queued").eq("action", "launch_app");
    if (cancelError) throw cancelError;
  }
  const expiry = optionalInteger(input.expires_minutes, 1, 5) ?? 2;
  const { data, error } = await db.from("machine_commands").insert({
    target_machine_id: target,
    requested_by_machine_id: requester,
    requested_by_name: text(input.machine_name, "machine_name", 100),
    action, payload: action === "start_print" ? { expected_batch_name: expectedBatch } : probePayload,
    phase: action === "launch_app" ? "远程软件唤起信号已发送" : "实时控制信号已发送",
    expires_at: new Date(Date.now() + expiry * 60_000).toISOString(),
  }).select().single();
  if (error) throw error;
  return { command: data };
}

async function listCommands(db: ReturnType<typeof createClient>) {
  const { data: active, error: activeError } = await db.from("machine_commands")
    .select("*").neq("action", "probe").in("status", ["queued", "claimed", "running"])
    .order("created_at", { ascending: true }).limit(200);
  if (activeError) throw activeError;
  const { data: recent, error: recentError } = await db.from("machine_commands")
    .select("*").neq("action", "probe")
    .in("status", ["succeeded", "failed", "cancelled", "expired"])
    .order("created_at", { ascending: false }).limit(50);
  if (recentError) throw recentError;
  const rows = [...(active || []), ...(recent || [])];
  rows.sort((left, right) => String(right.created_at).localeCompare(String(left.created_at)));
  return { commands: rows };
}

async function claimCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const id = machineId(input.machine_id);
  const { data, error } = await db.rpc("claim_machine_command", { target_id: id }).maybeSingle();
  if (error) throw error;
  if (data) await markFeedback(db, id);
  return { command: data || null };
}

async function enqueueUpdate(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const target = machineId(input.target_machine_id);
  const requester = machineId(input.machine_id);
  const requested = object(input.payload);
  const revision = String(requested.target_revision || "").trim().toLowerCase();
  if (!/^[0-9a-f]{40}$/.test(revision)) {
    throw new ClientError("Invalid source revision", 400);
  }
  const version = text(requested.target_version, "target_version", 40);
  const { data: machine, error: machineError } = await db.from("machine_status_current")
    .select("machine_id").eq("machine_id", target).maybeSingle();
  if (machineError) throw machineError;
  if (!machine) throw new ClientError("Target machine not found", 404);
  const now = new Date().toISOString();
  const { error: cancelError } = await db.from("machine_commands").update({
    status: "cancelled", phase: "由更新的源码版本替代",
    finished_at: now, updated_at: now,
  }).eq("target_machine_id", target).eq("action", "source_update").eq("status", "queued");
  if (cancelError) throw cancelError;
  const expiry = optionalInteger(input.expires_minutes, 5, 1440) ?? 1440;
  const { data, error } = await db.from("machine_commands").insert({
    target_machine_id: target,
    requested_by_machine_id: requester,
    requested_by_name: text(input.machine_name, "machine_name", 100),
    action: "source_update",
    payload: { target_revision: revision, target_version: version },
    phase: "等待目标机领取源码更新",
    expires_at: new Date(Date.now() + expiry * 60_000).toISOString(),
  }).select().single();
  if (error) throw error;
  return { command: data };
}

function validateReportedPrinterState(state: string, batchInfo: Record<string, unknown>) {
  if (batchInfo.printer_state == null || batchInfo.printer_state === "") return;
  const printerState = String(batchInfo.printer_state);
  const expected = PRINTER_TO_MACHINE_STATE[printerState];
  if (!expected) throw new ClientError("Invalid PrintExp printer_state", 400);
  if (state !== expected) throw new ClientError("PrintExp state projection mismatch", 409);
}

function validatePrinterControlState(machine: Record<string, unknown>, action: string) {
  const batchInfo = machine.batch_info && typeof machine.batch_info === "object"
    ? machine.batch_info as Record<string, unknown> : {};
  const printerState = String(batchInfo.printer_state || "");
  if (!PRINTER_CONTROL_SOURCES[action]?.has(printerState)) {
    throw new ClientError(`PrintExp state ${printerState || "unknown"} rejects ${action}`, 409);
  }
  if (machine.state !== PRINTER_TO_MACHINE_STATE[printerState]) {
    throw new ClientError("Stored machine and PrintExp states are inconsistent", 409);
  }
  return printerState;
}

async function claimControl(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const id = machineId(input.machine_id);
  const { data, error } = await db.rpc("claim_machine_control", { target_id: id }).maybeSingle();
  if (error) throw error;
  if (data) await markFeedback(db, id);
  return { command: data || null };
}

async function getCommand(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const requester = machineId(input.machine_id);
  const id = uuid(input.command_id, "command_id");
  const { data, error } = await db.from("machine_commands").select("*")
    .eq("id", id)
    .or(`target_machine_id.eq.${requester},requested_by_machine_id.eq.${requester}`)
    .maybeSingle();
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
  await markFeedback(db, target);
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
  const rawDetails = payload.batch_details == null ? [] : payload.batch_details;
  if (!Array.isArray(rawDetails) || rawDetails.length > batches.length) {
    throw new ClientError("Invalid batch_details", 400);
  }
  const details = rawDetails.map((value) => {
    const detail = object(value);
    const batch = text(detail.batch_number, "batch_number", 12);
    if (!batches.includes(batch)) throw new ClientError("Unknown batch detail", 400);
    return {
      batch_number: batch,
      item_count: optionalInteger(detail.item_count, 0, 10_000_000) ?? 0,
      piece_count: optionalInteger(detail.piece_count, 0, 10_000_000) ?? 0,
    };
  });
  if (new Set(details.map(item => item.batch_number)).size !== details.length) {
    throw new ClientError("Duplicate batch detail", 400);
  }
  return { platform, batch_numbers: batches, batch_details: details, layout_settings: layout,
    generate_prn: optionalBoolean(payload.generate_prn, true) };
}

function decorate(row: Record<string, unknown>) {
  const feedbackAt = row.last_feedback_at || row.heartbeat_at;
  const age = Math.max(0, (Date.now() - new Date(String(feedbackAt)).getTime()) / 1000);
  const available = isAvailable(row);
  return {
    ...row,
    available,
    agent_online: available,
    online: available && row.source_online !== false,
    feedback_age_seconds: Math.round(age),
    heartbeat_age_seconds: Math.round(age),
  };
}

async function consumeCommandResult(db: ReturnType<typeof createClient>, input: Record<string, unknown>) {
  const requester = machineId(input.machine_id);
  const id = uuid(input.command_id, "command_id");
  const { data, error } = await db.from("machine_commands").select("status, result")
    .eq("id", id).eq("requested_by_machine_id", requester).maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError("Command not found", 404);
  if (!new Set(["succeeded", "failed"]).has(String(data.status))) {
    throw new ClientError("Command result is not ready", 409);
  }
  const result = object(data.result);
  const { error: deleteError } = await db.from("machine_commands").delete()
    .eq("id", id).eq("requested_by_machine_id", requester);
  if (deleteError) throw deleteError;
  return { result };
}

function isAvailable(row: Record<string, unknown>) {
  if (row.availability_override === "available") return true;
  if (row.availability_override === "unavailable") return false;
  return row.auto_available !== false;
}

async function markFeedback(db: ReturnType<typeof createClient>, target: string) {
  const now = new Date().toISOString();
  const { error } = await db.from("machine_status_current").update({
    auto_available: true,
    availability_reason: "",
    last_feedback_at: now,
    updated_at: now,
  }).eq("machine_id", target);
  if (error) throw error;
}

async function markUnresponsiveMachines(db: ReturnType<typeof createClient>) {
  const cutoff = new Date(Date.now() - FEEDBACK_TIMEOUT_SECONDS * 1000).toISOString();
  const { data: commands, error } = await db.from("machine_commands")
    .select("target_machine_id, created_at").eq("status", "queued")
    .lt("created_at", cutoff).order("created_at", { ascending: false }).limit(200);
  if (error) throw error;
  const checked = new Set<string>();
  for (const command of commands || []) {
    const target = String(command.target_machine_id || "");
    if (!target || checked.has(target)) continue;
    checked.add(target);
    const { data: machine, error: readError } = await db.from("machine_status_current")
      .select("last_feedback_at, availability_override").eq("machine_id", target).maybeSingle();
    if (readError) throw readError;
    if (!machine || machine.availability_override !== "auto") continue;
    if (machine.last_feedback_at &&
        new Date(String(machine.last_feedback_at)).getTime() >
        new Date(String(command.created_at)).getTime()) continue;
    const { error: updateError } = await db.from("machine_status_current").update({
      auto_available: false,
      availability_reason: `任务下发 ${FEEDBACK_TIMEOUT_SECONDS} 秒内没有反馈`,
      updated_at: new Date().toISOString(),
    }).eq("machine_id", target).eq("availability_override", "auto");
    if (updateError) throw updateError;
  }
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
