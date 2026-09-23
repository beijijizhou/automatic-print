import { createClient } from "https://esm.sh/@supabase/supabase-js@2";
import { handleProductionAction } from "./production.ts";

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "content-type, x-automatic-print-key, authorization, apikey",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const ORDER_URL =
  "https://overseasfactory.s2bdiy.com/req/factory/orderProductOrder/getOrderList";
const ACCOUNTS = new Set(["DTF", "UV", "3D"]);
const CACHE_MS = 24 * 60 * 60 * 1000;

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  try {
    await requireClientKey(request);
    const input = await request.json();
    const action = String(input.action || "batch_info").trim();
    const account = String(input.account || "DTF").trim().toUpperCase();
    if (!ACCOUNTS.has(account)) throw new ClientError("Unsupported S2B account", 400);

    const url = requiredEnv("SUPABASE_URL");
    const serviceKey = requiredEnv("SUPABASE_SERVICE_ROLE_KEY");
    const db = createClient(url, serviceKey);
    const secret = Deno.env.get("ERP_TOKEN_ENCRYPTION_KEY") || serviceKey;
    const batch = String(input.batch_number || "").trim().toUpperCase();
    if (action === "batch_info") {
      if (!/^[A-Z0-9]{12}$/.test(batch)) {
        throw new ClientError("Invalid batch number", 400);
      }
      const cached = await loadCache(db, account, batch);
      if (cached && new Date(cached.expires_at).getTime() > Date.now()) {
        return json(responseBody(cached, "hit"));
      }
    }

    const platform = `S2B:${account}`;
    if (action === "refresh_login") {
      const result = await refreshLogin(db, platform, input, secret);
      return json({ account, ...result });
    }
    const { data: credential, error: credentialError } = await db
      .from("erp_api_credentials")
      .select("encrypted_token,status")
      .eq("platform", platform)
      .maybeSingle();
    if (credentialError) throw credentialError;
    if (!credential) throw new ClientError(`${platform} shared login is not configured`, 503);
    if (credential.status === "expired") {
      throw new ClientError(`${platform} shared login has expired`, 503);
    }
    const token = await decryptToken(String(credential.encrypted_token), secret);
    if (action !== "batch_info") {
      const result = await handleProductionAction(token, action, input);
      await db.from("erp_api_credentials").update({
        last_used_at: new Date().toISOString(), last_error: null,
      }).eq("platform", platform);
      return json({ account, ...result });
    }
    const records = await fetchAll(token, batch);
    const normalized = records.map(normalizeRecord);
    const now = new Date();
    const row = {
      account,
      batch_number: batch,
      source_total: normalized.length,
      records: normalized,
      summary: summarize(normalized),
      fetched_at: now.toISOString(),
      expires_at: new Date(now.getTime() + CACHE_MS).toISOString(),
      last_error: null,
    };
    const { error: cacheError } = await db
      .from("s2b_batch_metadata")
      .upsert(row, { onConflict: "account,batch_number" });
    if (cacheError) throw cacheError;
    await db.from("erp_api_credentials").update({
      last_used_at: now.toISOString(), last_error: null,
    }).eq("platform", platform);
    return json(responseBody(row, "miss"));
  } catch (error) {
    const status = error instanceof ClientError
      ? error.status
      : Number((error as { status?: number })?.status || 500);
    return json({ error: error instanceof Error ? error.message : String(error) }, status);
  }
});

class ClientError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function requireClientKey(request: Request) {
  const expectedClient = requiredEnv("AUTOMATIC_PRINT_API_KEY");
  const sharedClient = Deno.env.get("YDWX_SHARE_API_KEY")?.trim() || "";
  const suppliedClient = request.headers.get("x-automatic-print-key") || "";
  const suppliedAdmin = (request.headers.get("authorization") || "")
    .replace(/^Bearer\s+/i, "");
  const [client, shared, suppliedClientDigest] = await Promise.all([
    digest(expectedClient), digest(sharedClient), digest(suppliedClient),
  ]);
  if (client === suppliedClientDigest ||
      (sharedClient && shared === suppliedClientDigest)) return;
  if (suppliedAdmin && await isSupabaseAdminCredential(suppliedAdmin)) return;
  throw new ClientError("Unauthorized", 401);
}

async function isSupabaseAdminCredential(credential: string) {
  const response = await fetch(
    `${requiredEnv("SUPABASE_URL")}/auth/v1/admin/users?page=1&per_page=1`,
    {
      headers: {
        "apikey": credential,
        "Authorization": `Bearer ${credential}`,
      },
    },
  );
  return response.ok;
}

async function loadCache(db: ReturnType<typeof createClient>, account: string, batch: string) {
  const { data, error } = await db.from("s2b_batch_metadata").select(
    "account,batch_number,source_total,records,summary,fetched_at,expires_at",
  ).eq("account", account).eq("batch_number", batch).maybeSingle();
  if (error) throw error;
  return data;
}

async function fetchAll(token: string, batch: string) {
  const rows: Record<string, unknown>[] = [];
  let page = 1;
  let lastPage = 1;
  do {
    const response = await fetch(ORDER_URL, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`,
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json;charset=UTF-8",
        "Origin": "https://overseasfactory.s2bdiy.com",
        "Referer": "https://overseasfactory.s2bdiy.com/factory/orderManage",
      },
      body: JSON.stringify({
        batch_numbers: [batch], status: -3, page, per_page: 500,
      }),
    });
    if (response.status === 401 || response.status === 403) {
      throw new ClientError("S2B shared login has expired", 503);
    }
    if (!response.ok) throw new Error(`S2B returned HTTP ${response.status}`);
    const body = await response.json();
    if (body.status !== "success") {
      throw new Error(String(body.msg || "S2B batch query failed"));
    }
    const data = body.data || {};
    rows.push(...(Array.isArray(data.data) ? data.data : []));
    lastPage = Number(data.last_page || page);
    page += 1;
  } while (page <= lastPage);
  return rows;
}

function normalizeRecord(row: Record<string, any>) {
  const order = row.order_data || {};
  const item = row.order_item_data || {};
  return {
    order_code: String(order.order_code || ""),
    order_item_code: String(item.order_item_code || ""),
    item_position: String(item.order_item_pos || ""),
    item_count: Number(item.order_item_total_count || 0),
    color: String(item.stock_sku_color_text || "").trim(),
    size: String(item.stock_sku_size_text || "").trim(),
    material: String(item.stock_sku_product_material_text || "").trim(),
    product_name: String(item.basic_product_name || "").trim(),
  };
}

function summarize(records: ReturnType<typeof normalizeRecord>[]) {
  const colors: Record<string, number> = {};
  const sizes: Record<string, number> = {};
  const colorSizes: Record<string, number> = {};
  for (const row of records) {
    colors[row.color || "未识别颜色"] = (colors[row.color || "未识别颜色"] || 0) + 1;
    sizes[row.size || "未识别尺码"] = (sizes[row.size || "未识别尺码"] || 0) + 1;
    const key = `${row.color || "未识别颜色"}|${row.size || "未识别尺码"}`;
    colorSizes[key] = (colorSizes[key] || 0) + 1;
  }
  return { colors, sizes, color_sizes: colorSizes };
}

function responseBody(row: Record<string, any>, cache: string) {
  return {
    account: row.account, batch_number: row.batch_number,
    source_total: row.source_total, records: row.records,
    summary: row.summary, fetched_at: row.fetched_at,
    expires_at: row.expires_at, cache,
  };
}

async function decryptToken(value: string, secret: string) {
  if (!value.startsWith("aesgcm:v1:")) {
    throw new ClientError("S2B credential must be refreshed in the shared AES format", 503);
  }
  const [, , nonce, ciphertext] = value.split(":", 4);
  const key = await crypto.subtle.importKey(
    "raw", await sha256(`after-sales:erp-api-token:${secret}`),
    { name: "AES-GCM" }, false, ["decrypt"],
  );
  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: decode(nonce) }, key, decode(ciphertext),
  );
  return new TextDecoder().decode(plain);
}

async function refreshLogin(
  db: ReturnType<typeof createClient>,
  platform: string,
  input: Record<string, unknown>,
  secret: string,
) {
  const token = String(input.token || "").trim();
  if (token.length < 32 || token.length > 8192) {
    throw new ClientError("Invalid S2B login token", 400);
  }
  const verified = await handleProductionAction(token, "production_batches", {
    page: 1, per_page: 1,
  }) as Record<string, unknown>;
  const encryptedToken = await encryptToken(token, secret);
  const now = new Date().toISOString();
  const { data, error } = await db.from("erp_api_credentials").update({
    encrypted_token: encryptedToken,
    status: "active",
    last_used_at: now,
    last_error: null,
  }).eq("platform", platform).select("platform").maybeSingle();
  if (error) throw error;
  if (!data) throw new ClientError(`${platform} shared login is not configured`, 503);
  const records = Array.isArray(verified.records)
    ? verified.records as Record<string, unknown>[] : [];
  return {
    action: "refresh_login",
    refreshed: true,
    total: Number(verified.total || records.length),
    latest_created_at: String(records[0]?.created_at || ""),
  };
}

async function encryptToken(value: string, secret: string) {
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const key = await crypto.subtle.importKey(
    "raw", await sha256(`after-sales:erp-api-token:${secret}`),
    { name: "AES-GCM" }, false, ["encrypt"],
  );
  const ciphertext = new Uint8Array(await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce }, key, new TextEncoder().encode(value),
  ));
  return `aesgcm:v1:${encode(nonce)}:${encode(ciphertext)}`;
}

async function digest(value: string) {
  return [...await sha256(value)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}
async function sha256(value: string) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value)));
}
function decode(value: string) {
  const padded = value.replaceAll("-", "+").replaceAll("_", "/").padEnd(
    value.length + ((4 - value.length % 4) % 4), "=",
  );
  return Uint8Array.from(atob(padded), (character) => character.charCodeAt(0));
}
function encode(value: Uint8Array) {
  let binary = "";
  for (const byte of value) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replace(/=+$/, "");
}
function requiredEnv(name: string) {
  const value = Deno.env.get(name);
  if (!value) throw new Error(`Missing ${name}`);
  return value;
}
function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status, headers: { ...CORS, "Content-Type": "application/json" },
  });
}
