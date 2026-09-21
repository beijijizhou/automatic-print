"""Run ERP batch generation reads and writes in the worker thread."""

from ...automation.batches.rules import (
    generate_rule_batches, preview_rule_batch_plan,
)
from ...automation.batches.routes import (
    generate_route_batch, preview_route_batch,
)


GENERATION_ACTIONS = {
    "preview_rules", "generate_rules", "preview_route", "generate_route",
}


def run_generation_action(worker) -> None:
    if worker.action == "preview_rules":
        worker._deliver(worker.plan_loaded, preview_rule_batch_plan(
            worker.platform_name, worker._report,
        ))
    elif worker.action == "generate_rules":
        if worker.batch_plan is None:
            raise RuntimeError("请先读取并确认批次分类数量。")
        count = generate_rule_batches(
            worker.batch_plan, worker.generation_rule, worker._report,
        )
        worker._deliver(worker.completed, {
            "type": "batches_generated",
            "platform": worker.platform_name,
            "generated": count,
        })
    elif worker.action == "preview_route":
        worker._report(f"正在读取工艺路线与 {worker.route_label} 的项目数…")
        worker._deliver(worker.plan_loaded, preview_route_batch(worker.route_label))
    elif worker.action == "generate_route":
        if worker.route_plan is None:
            raise RuntimeError("请先读取并确认工艺路线。")
        result = generate_route_batch(worker.route_plan, worker._report)
        worker._deliver(worker.completed, {
            "type": "route_batches_generated",
            "platform": worker.platform_name,
            "route": result.plan.selected_route,
            "items": result.plan.item_count,
            "codes": result.batch_codes,
            "status": result.batch_status,
        })
