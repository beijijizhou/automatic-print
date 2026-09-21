const API_ROOT = "https://overseasfactory.s2bdiy.com/req";
const BATCH_PATTERN = /^[A-Z0-9]{12}$/;

export async function handleProductionAction(
  token: string,
  action: string,
  input: Record<string, unknown>,
) {
  if (action === "production_batches") return listBatches(token, input);
  if (action === "request_export") return requestExport(token, input);
  if (action === "export_records") return exportRecords(token, input);
  if (action === "mark_downloaded") return markDownloaded(token, input);
  throw new ProductionError("Unsupported S2B action", 400);
}

class ProductionError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function listBatches(token: string, input: Record<string, unknown>) {
  const page = integer(input.page, 1, 1, 10_000);
  const perPage = integer(input.per_page, 50, 1, 100);
  const body = await request(token, "POST", "/factory/orderProductBatchNumber/index", {
    status: "", order_codes: [], third_order_ids: "", names: "",
    batch_numbers: "", order_product_line_ids: "", assign_user_id: -2,
    page, per_page: perPage,
  });
  const data = object(body.data);
  const rows = Array.isArray(data.data) ? data.data : [];
  return {
    action: "production_batches",
    page,
    per_page: perPage,
    total: Number(data.total || rows.length),
    records: rows.map(normalizeBatch),
  };
}

async function requestExport(token: string, input: Record<string, unknown>) {
  const batches = batchNumbers(input.batch_numbers);
  const path = batches.length === 1
    ? "/factory/orderProductBatchNumber/exportProductionImage"
    : "/factory/orderProductBatchNumber/batchExportProductionImage";
  await request(token, "POST", path, {
    batch_number: batches.join(","), type: 1,
  });
  return { action: "request_export", batch_numbers: batches, accepted: true };
}

async function exportRecords(token: string, input: Record<string, unknown>) {
  const page = integer(input.page, 1, 1, 10_000);
  const perPage = integer(input.per_page, 100, 1, 100);
  const query = new URLSearchParams({
    page: String(page), per_page: String(perPage), type: "4",
    is_download: "", status: "", batch_number: "",
    created_at_before: "", created_at_after: "",
  });
  const body = await request(token, "GET", `/factory/userExportRecord?${query}`);
  const data = object(body.data);
  const rows = Array.isArray(data.data) ? data.data : [];
  return {
    action: "export_records", page, per_page: perPage,
    total: Number(data.total || rows.length),
    records: rows.map(normalizeExport).filter((row) => row.batch_number),
  };
}

async function markDownloaded(token: string, input: Record<string, unknown>) {
  const id = integer(input.record_id, 0, 1, Number.MAX_SAFE_INTEGER);
  await request(token, "POST", "/factory/userExportRecord/downloadRecord", { id });
  return { action: "mark_downloaded", record_id: id, marked: true };
}

async function request(
  token: string,
  method: string,
  path: string,
  payload?: Record<string, unknown>,
) {
  const response = await fetch(API_ROOT + path, {
    method,
    headers: {
      "Authorization": `Bearer ${token}`,
      "Accept": "application/json, text/plain, */*",
      "Content-Type": "application/json;charset=UTF-8",
      "Origin": "https://overseasfactory.s2bdiy.com",
      "Referer": "https://overseasfactory.s2bdiy.com/factory/orderProduction",
    },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (response.status === 401 || response.status === 403) {
    throw new ProductionError("S2B shared login has expired", 503);
  }
  if (!response.ok) throw new ProductionError(`S2B returned HTTP ${response.status}`, 502);
  const body = await response.json();
  const failed =
    (body.status_code !== undefined && Number(body.status_code) !== 200) ||
    (body.status !== undefined && body.status !== "success");
  if (failed) {
    throw new ProductionError(String(body.msg || "S2B production request failed"), 502);
  }
  return body;
}

function normalizeBatch(row: Record<string, any>) {
  const progress = object(row.progress);
  const assignee = object(row.assign_user || row.assign_user_data || row.assign_user_info);
  return {
    batch_number: String(row.batch_number || "").trim(),
    item_count: number(progress.total_print_num, row.item_num, progress.total_num),
    piece_count: number(progress.total_num, row.total_num, row.num),
    name: String(row.name || "S2B生产批次"),
    personnel_label: String(
      row.assign_user_name || row.assignee_name || assignee.name ||
      assignee.nickname || assignee.real_name || "",
    ).trim(),
    created_at: String(row.created_at || row.created_date || ""),
  };
}

function normalizeExport(row: Record<string, any>) {
  const params = object(row.params);
  const file = object(row.oss_file);
  return {
    record_id: Number(row.id || 0),
    batch_number: String(params["批次号"] || "").trim(),
    image_count: Number(row.export_success_num || row.export_num || 0),
    created_at: String(row.created_at || ""),
    ready: Number(row.status || 0) === 2 && Boolean(row.download_url),
    download_url: String(row.download_url || ""),
    archive_name: String(file.origin_name || ""),
  };
}

function batchNumbers(value: unknown) {
  const rows = Array.isArray(value) ? value : [];
  const batches = [...new Set(rows.map((row) => String(row).trim().toUpperCase()))];
  if (!batches.length || batches.length > 100 || batches.some((row) => !BATCH_PATTERN.test(row))) {
    throw new ProductionError("Invalid S2B batch numbers", 400);
  }
  return batches;
}

function integer(value: unknown, fallback: number, minimum: number, maximum: number) {
  const parsed = Number(value === undefined ? fallback : value);
  if (!Number.isInteger(parsed) || parsed < minimum || parsed > maximum) {
    throw new ProductionError("Invalid numeric parameter", 400);
  }
  return parsed;
}

function object(value: unknown): Record<string, any> {
  return value && typeof value === "object" ? value as Record<string, any> : {};
}

function number(...values: unknown[]) {
  for (const value of values) {
    const parsed = Number(value);
    if (Number.isFinite(parsed) && value !== "" && value !== null) return parsed;
  }
  return 0;
}
