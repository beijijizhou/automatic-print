"""Bridge the authenticated Fengniao page to its loaded API modules."""

from typing import Any

CHUNK_ROOT = "https://fe-product.hihumbird.com/static/js/chunk/"
PROCESS_BATCH_MODULE = "processBatchManage-"


def production_api_frame(page):
    frames = [frame for frame in page.frames if frame.name == "fnsz-sale"]
    if len(frames) != 1:
        raise RuntimeError("ERP 生产模块尚未加载完成，请刷新后重试。")
    return frames[0]


def production_batch_frame(page):
    """Return the visible batch table in either a direct or shell page."""
    if page.locator("tbody tr, th").count():
        return page
    frames = [
        frame
        for frame in page.frames
        if "/productionBatch/index" in frame.url
        and frame.parent_frame is not None
    ]
    for frame in reversed(frames):
        if frame.locator("tbody tr, th").count():
            return frame
    if frames:
        return frames[-1]
    raise RuntimeError("ERP 生产批次内容区域尚未加载完成，请刷新后重试。")


def module_url(page, filename_prefix: str, fallback: str | None = None) -> str:
    frame = production_api_frame(page)
    resources = frame.evaluate(
        "() => performance.getEntriesByType('resource').map(x => x.name)"
    )
    matches = [
        url
        for url in resources
        if "/static/js/chunk/" in url
        and url.rsplit("/", 1)[-1].startswith(filename_prefix)
    ]
    if matches:
        return matches[-1]
    if fallback:
        return CHUNK_ROOT + fallback
    raise RuntimeError(f"ERP 前端模块未加载：{filename_prefix}")


def call_module(
    page,
    filename_prefix: str,
    export_name: str,
    argument: Any = None,
    fallback: str | None = None,
):
    frame = production_api_frame(page)
    url = module_url(page, filename_prefix, fallback)
    return frame.evaluate(
        """async ({url, exportName, argument}) => {
            const api = await import(url);
            const fn = api[exportName];
            if (typeof fn !== "function") {
                throw new Error(`ERP API export not found: ${exportName}`);
            }
            return await fn(argument);
        }""",
        {"url": url, "exportName": export_name, "argument": argument},
    )


def call_imported_module(
    page,
    importer_prefix: str,
    call_marker: str,
    export_name: str,
    argument: Any = None,
    fallback: str | None = None,
):
    """Resolve a hashed dependency from the stable module that calls it."""
    frame = production_api_frame(page)
    return frame.evaluate(
        r"""async ({importerPrefix, marker, exportName, argument, fallback}) => {
            const importer = performance.getEntriesByType('resource')
                .map(x => x.name)
                .find(url => url.includes('/static/js/chunk/') &&
                    url.split('/').pop().startsWith(importerPrefix));
            let dependency = fallback;
            if (importer) {
                const source = await (await fetch(importer)).text();
                const markerIndex = source.indexOf(marker);
                const callArea = source.slice(Math.max(0, markerIndex - 200),
                    markerIndex + marker.length);
                const callMatch = callArea.match(/([A-Za-z_$][\w$]*)\(\{product_sale_type_list/);
                if (callMatch) {
                    const alias = callMatch[1];
                    const imports = source.matchAll(/import\{([^}]*)\}from[\"']([^\"']+)[\"']/g);
                    for (const match of imports) {
                        const declarations = match[1].replace(/\s/g, '').split(',');
                        if (declarations.includes(`${exportName}as${alias}`) ||
                            (exportName === alias && declarations.includes(exportName))) {
                            dependency = new URL(match[2], importer).href;
                            break;
                        }
                    }
                }
            }
            if (!dependency) throw new Error(`ERP API module not found: ${marker}`);
            const fn = (await import(dependency))[exportName];
            if (typeof fn !== 'function') {
                throw new Error(`ERP API export not found: ${exportName}`);
            }
            return await fn(argument);
        }""",
        {
            "importerPrefix": importer_prefix,
            "marker": call_marker,
            "exportName": export_name,
            "argument": argument,
            "fallback": CHUNK_ROOT + fallback if fallback else None,
        },
    )
