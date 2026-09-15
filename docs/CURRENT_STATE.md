# Current System Map

本文只描述当前活动代码归属。结构调整后更新；小功能提交不追加流水记录。

## 入口与编排

- 应用入口：`automatic_print/__main__.py`、`automatic_print/app.py`。
- 主窗口：`automatic_print/ui/main_window.py`，负责构造应用级状态和连接各控制器。
- 主工作台：`automatic_print/automation_dialog.py` 为兼容门面；实际页面在
  `automatic_print/batch_ui/` 和 `automatic_print/ui/label_quick_panel.py`。
- 开发者模式当前仅开放45/60厘米方案；40–80厘米批量研究入口处于隐藏停用状态。补足膜间距由
  `ui/header_gap.py` 的独立开关控制，保存的毫米数值本身不会自动启用。
- 单批次生成编排：`automatic_print/ui/generation_actions.py`、`workers.py`、
  `generation_preview.py`。
- 多批次生成编排：`automatic_print/ui/bulk_workbench.py`、
  `bulk_generation_worker.py`、`batch_status_board.py`。

## 排版核心

- 公共门面：`automatic_print/layout.py`。
- 完整生成服务：`automatic_print/layout_engine/service.py`。
- 文件发现与元数据：`discovery.py`、`batch_discovery.py`、`source_metadata.py`、
  `output_dpi.py`。
- 订单、双面、颜色与尺码：`order_groups.py`、`batch_analysis.py`、
  `single_order_sequence.py`、`color_policy.py`、`size_policy.py`。
- 行、刀位和区域规划：`planner.py`、`row_optimizer.py`、`cutter_planner.py`、
  `knife_optimizer.py`、`adaptive_knife.py`、`zone_optimizer.py`、`rotation_zones.py`。多数双排路径由
  `adaptive_knife.py` 唯一组装“双排区 + 剩余旋转区”，旋转仍超宽时复用 `width_fit.py` 缩小缓存。
- 旋转与超宽恢复：`rotation_compare.py`、`whole_rotation.py`、`tail_rotation.py`、
  `single_rotation.py`、`width_fit.py`、`gap_fallback.py`。
- 标签与刀码：`labels.py`、`dynamic_label.py`、`marker_stack.py`、`left_marker.py`、
  `platform_label.py`、`header_region.py`、`transparent_search.py`。
- 渲染与编码：`pillow_renderer.py`、`vips_renderer.py`、`png_codecs/`、
  `segmented_output.py`、`atomic_png.py`。活动的大图路径使用顶部有限条带测量、平衡行画布图和固定
  UP 滤波；保存计时包含 libvips 延迟合成、编码与写入，不能解释成纯磁盘耗时。
- 输出安全：`order_validation.py`、`cut_validation.py`、
  `marked_pixel_validation.py`、`printed_guides.py`、`output_file_info.py`。
- 膜方案与统计：`film_comparison.py`、`film_specs.py`、`metrics.py`、
  `operation_timing.py`、`algorithm_costs.py`。
- 缓存：`plan_cache.py`、`normal_plan_cache.py`、`cached_planner.py`；单图测量由
  `measurement_cache.py` 持久化，并由 `measurement_session.py` 在任务内共享连接。单图缓存24小时，
  重新组批、膜宽变化和普通版本更新不触发源图重新测量。

## UI 与本地数据

- 设置和持久化：`ui/preferences.py`、`preference_autosave.py`、`layout_values.py`。
- 进度、停止和线程生命周期：`ui/busy_spinner.py`、`layout_activity.py`、
  `operation_timing.py`、`stop_actions.py`、`thread_lifecycle.py`、`worker_bridge.py`。
- 预览：`ui/production_preview.py`、`preview_*`、`pair_preview.py`、
  `marker_examples.py` 及 `marker_example_*`。`layout_engine/preview_result.py` 形成不落地打印图片的
  完整报告数据，`ui/batch_summary.py` 显示可复制的刀位、单排原因和耗时报告。
- 错误诊断：`ui/failure_panel.py`、`failure_dialog.py`、
  `layout_engine/error_context.py`、`error_parameters.py`。
- 历史记录：`automatic_print/history/`；Qt 参数使用 `QSettings`。
- 更新：`automatic_print/updates/`、`updater.py`、`restart_control.py`。

## 外部自动化

- `automatic_print/automation/` 保存 ERP、浏览器、下载和旧批次流程，目前不是主工作台优先路径。
- 该目录仍以功能和平铺平台文件混合组织，尚未达到
  `automation/api/<provider>/` 的目标边界。新增平台代码必须进入提供商子包；迁移旧代码时保留
  公共兼容门面并删除活跃重复。

## 已知结构债务

- 以下遗留文件超过200行，测试已冻结当前上限；后续涉及其职责的修改应缩小而非增长：

| 归属 | 遗留文件 | 后续收敛方向 |
| --- | --- | --- |
| 应用编排 | `ui/main_window.py`, `ui/generation_actions.py`, `ui/preferences.py` | 主窗口只装配控制器；生成状态、参数分组继续进入现有UI子模块。 |
| 工作台展示 | `ui/label_quick_panel.py`, `ui/setting_preview.py`, `ui/pair_preview.py` | 数据模型、绘制和控件构造各归现有预览功能目录。 |
| 旧批次UI | `batch_ui/batch_actions.py` | 与活动单/多批次控制器核对后组合共享动作。 |
| 排版核心 | `layout_engine/service.py`, `planner.py`, `item_factory.py` | 服务只编排阶段；测量、候选和对象构造保留单一所有者。 |
| ERP自动化 | `automation/erp_api.py`, `rule_batches.py`, `batch_browser.py` | 按提供商迁入`automation/api/<provider>/`，中立批次规则留共享层。 |

- `batch_ui/` 与 `ui/` 都包含生成和批次编排，需要逐条确认活动入口，合并重复职责，不能凭文件名删除。
- 部分 README 内容曾混入版本演进描述；当前规则以四份治理文档为准，README 仅保留使用和发布入口。
