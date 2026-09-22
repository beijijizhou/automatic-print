// DTF platform credentials stay in Supabase secrets; clients see status only.
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "content-type, x-automatic-print-key",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};
const PLATFORMS = [
  "Haloo", "隆丰", "莆田", "S2B", "汉森", "七创",
  "一朵云", "方果", "SDS1", "SDS2",
] as const;
type Platform = typeof PLATFORMS[number];
type Profile = Record<string, string>;

class ClientError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status, headers: { ...CORS, "Content-Type": "application/json; charset=utf-8" },
  });
}

async function digest(value: string): Promise<string> {
  const bytes = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
  return Array.from(new Uint8Array(bytes), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function authorize(request: Request): Promise<void> {
  const supplied = request.headers.get("x-automatic-print-key") || "";
  const installer = Deno.env.get("AUTOMATIC_PRINT_API_KEY")?.trim() || "";
  const shared = Deno.env.get("YDWX_SHARE_API_KEY")?.trim() || "";
  if (!supplied || (!installer && !shared)) throw new ClientError("Unauthorized", 401);
  const candidate = await digest(supplied);
  if ((installer && candidate === await digest(installer)) ||
      (shared && candidate === await digest(shared))) return;
  throw new ClientError("Unauthorized", 401);
}

function profiles(): Record<string, Profile> {
  const raw = Deno.env.get("DTF_PLATFORM_CREDENTIALS_JSON") || "{}";
  const parsed = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new ClientError("DTF credential store is invalid", 503);
  }
  return parsed as Record<string, Profile>;
}

function requiredFields(platform: Platform): string[] {
  if (["一朵云", "七创"].includes(platform)) return ["username", "password"];
  if (platform === "汉森") return ["username", "password", "client_id"];
  if (platform === "方果") return ["username", "password", "tenant_id"];
  if (["SDS1", "SDS2"].includes(platform)) {
    return ["contact_tel", "password", "factory_code", "extraInfo"];
  }
  if (["Haloo", "隆丰", "莆田"].includes(platform)) {
    return ["token"];
  }
  return [];
}

function status(platform: Platform, stored: Record<string, Profile>) {
  if (platform === "S2B") {
    return { platform, configured: true, mode: "dedicated_gateway",
      detail: "由 S2B 服务端账号独立管理" };
  }
  const profile = stored[platform] || {};
  const missing = requiredFields(platform).filter((field) =>
    typeof profile[field] !== "string" || !profile[field].trim()
  );
  const mode = ["Haloo", "隆丰", "莆田"].includes(platform)
    ? "browser_token" : "server_login";
  return { platform, configured: missing.length === 0, mode,
    detail: missing.length ? "缺少账号配置" : "账号已存于服务端",
    missing_fields: missing };
}

async function probe(platform: Platform, profile: Profile): Promise<object> {
  let response: Response;
  if (["一朵云", "七创"].includes(platform)) {
    const base = platform === "七创"
      ? "http://us.qcpod.19diy.com" : "http://usf.19diy.com";
    response = await fetch(`${base}/AdminUser/Login?lang=zh_chs`, {
      method: "POST", signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "X-Requested-With": "XMLHttpRequest" },
      body: new URLSearchParams({ languageKind: "zh_chs",
        loginID: profile.username, password: profile.password, captchaCode: "" }),
    });
    const body = await response.json();
    if (!response.ok || body?.Code !== 200) throw new ClientError(
      `${platform} 登录未通过：${body?.Message || response.status}`, 502);
  } else if (platform === "汉森") {
    response = await fetch("https://tshirt.riin.com/auth/api/auth/login", {
      method: "POST", signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: profile.username, password: profile.password,
        clientId: profile.client_id }),
    });
    const body = await response.json();
    if (!response.ok || !(body?.data?.token || body?.data?.accessToken)) {
      throw new ClientError("汉森登录未返回 token", 502);
    }
  } else if (platform === "方果") {
    const headers: Record<string, string> = {
      "Content-Type": "application/json", "Tenant-Id": profile.tenant_id,
      "From-Client": "0", "Authorization": "Bearer null",
      "X-Timezone-Offset": "America/New_York",
    };
    if (profile.fingerprint) headers.Fingerprint = profile.fingerprint;
    response = await fetch("https://fangguo.com/fgapp/basic/system/auth/login", {
      method: "POST", signal: AbortSignal.timeout(30000), headers,
      body: JSON.stringify({ loginSource: 0, username: profile.username,
        password: profile.password }),
    });
    const body = await response.json();
    const data = body?.data;
    const token = typeof data === "string" ? data :
      data?.access_token || data?.accessToken || data?.token ||
      body?.access_token || body?.accessToken || body?.token;
    if (!response.ok || !token) throw new ClientError("方果登录未返回 token", 502);
  } else if (["SDS1", "SDS2"].includes(platform)) {
    response = await fetch("https://factory-api.sdspod.com/login", {
      method: "POST", signal: AbortSignal.timeout(30000),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ contact_tel: profile.contact_tel,
        extraInfo: profile.extraInfo, factory_code: profile.factory_code,
        password: profile.password }),
    });
    const body = await response.json();
    if (!response.ok || !(body?.data?.access_token || body?.data?.token) ||
        !(body?.data?.factory_id || body?.data?.factoryId)) {
      throw new ClientError(`${platform} 登录未返回有效工厂 token`, 502);
    }
  } else {
    throw new ClientError(`${platform} 需要浏览器页面验证，不能用服务端登录探针代替`, 422);
  }
  return { platform, verified: true, mode: "server_login" };
}

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: CORS });
  if (request.method !== "POST") return json({ error: "Method not allowed" }, 405);
  try {
    await authorize(request);
    const input = await request.json();
    const stored = profiles();
    if (input?.action === "status") {
      return json({ platforms: PLATFORMS.map((name) => status(name, stored)) });
    }
    if (input?.action === "probe") {
      const name = String(input.platform || "") as Platform;
      if (!PLATFORMS.includes(name)) throw new ClientError("Unknown platform", 400);
      if (!status(name, stored).configured) throw new ClientError("账号未配置", 503);
      return json(await probe(name, stored[name]));
    }
    throw new ClientError("Unsupported action", 400);
  } catch (error) {
    const status = error instanceof ClientError ? error.status : 500;
    return json({ error: error instanceof Error ? error.message : "Unknown error" }, status);
  }
});
