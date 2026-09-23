"""Run ERP batch generation reads and writes in the worker thread."""

from ...automation.batches.received.rules import (
    generate_rule_batches, preview_rule_batch_plan,
)
from ...automation.batches.received.routes import (
    generate_route_batch, preview_route_batch,
)
from ...automation.batches.received.default_multi import (
    generate_default_multi, preview_default_multi,
)


GENERATION_ACTIONS = {
    "preview_rules", "generate_rules", "preview_route", "generate_route",
    "preview_default_multi", "generate_default_multi",
}


def run_generation_action(worker) -> None:
    if worker.action == "preview_rules":
        worker._report("正在连接 ERP 并读取全部已接单生产项…")
        plan = preview_rule_batch_plan(
            worker.platform_name, worker._report,
        )
        worker._report("规则预览计算完成；正在更新界面…")
        worker._deliver(worker.plan_loaded, plan)
    elif worker.action == "generate_rules":
        if worker.batch_plan is None:
            raise RuntimeError("请先读取并确认批次分类数量。")
        count = generate_rule_batches(
            worker.batch_plan, worker.generation_rule, worker._report,
        )
        worker._report(f"批次生成完成：平台确认 {count} 个批次。")
        worker._deliver(worker.completed, {
            "type": "batches_generated",
            "platform": worker.platform_name,
            "generated": count,
        })
    elif worker.action == "preview_route":
        worker._report(f"正在读取工艺路线与 {worker.route_label} 的项目数…")
        plan = preview_route_batch(worker.route_label)
        worker._report("工艺路线预览计算完成；正在更新界面…")
        worker._deliver(worker.plan_loaded, plan)
    elif worker.action == "preview_default_multi":
        worker._report("正在读取默认工艺路线的多项多件…")
        plan = preview_default_multi()
        worker._report("默认工艺预览计算完成；正在更新界面…")
        worker._deliver(worker.plan_loaded, plan)
    elif worker.action == "generate_default_multi":
        if worker.route_plan is None:
            raise RuntimeError("请先读取并确认默认路线多项多件。")
        result = generate_default_multi(worker.route_plan, worker._report)
        worker._report(
            f"默认工艺批次生成完成：平台确认 {len(result.batch_codes)} 个批次。"
        )
        worker._deliver(worker.completed, {
            "type": "default_multi_generated",
            "platform": worker.platform_name,
            "items": result.plan.item_count,
            "pieces": result.plan.piece_count,
            "codes": result.batch_codes,
            "status": result.batch_status,
        })
    elif worker.action == "generate_route":
        if worker.route_plan is None:
            raise RuntimeError("请先读取并确认工艺路线。")
        result = generate_route_batch(worker.route_plan, worker._report)
        worker._report(
            f"工艺路线批次生成完成：平台确认 {len(result.batch_codes)} 个批次。"
        )
        worker._deliver(worker.completed, {
            "type": "route_batches_generated",
            "platform": worker.platform_name,
            "route": result.plan.selected_route,
            "items": result.plan.item_count,
            "codes": result.batch_codes,
            "status": result.batch_status,
        })
