# Shared Function Catalog

新增代码前先查本目录，再按业务字段、中文 UI 文案、类型、报告字段和测试搜索。这里记录唯一所有者，
不是提交日志。

| 能力 | 规范所有者 | 复用规则 |
| --- | --- | --- |
| 图片发现与嵌套批次扫描 | `layout_engine/discovery.py`, `batch_discovery.py` | 单批、多批和分析功能复用，不各自遍历目录。 |
| 图片尺寸、DPI与源信息 | `layout_engine/source_metadata.py`, `images.py`, `output_dpi.py` | 一次读取形成共享事实；标签、排版和报告不得重复解码。 |
| 批次数据快照与并行测量 | `layout_engine/batch_snapshot.py`, `measurement_session.py`, `parallel_measurement.py` | 生成、仅预览和批量分析从首次读取到最终报告共享一个批次会话；保持结果原顺序，线程完成顺序不能改变生产顺序。 |
| 订单、双面、尺码归组及批次构成 | `layout_engine/order_groups.py`, `batch_analysis.py`, `size_policy.py` | 排版、比较、结果表、报告和安全检查使用同一身份；单件显示尺码-数量，多件显示订单号-件数。 |
| 颜色与生产顺序 | `layout_engine/color_policy.py`, `single_order_sequence.py` | 颜色优先、尺码业务顺序集中维护。 |
| 普通行和自动多列规划 | `layout_engine/planner.py`, `cutter_planner.py`, `dynamic_columns.py`, `column_solver.py` | 膜宽与真实占位决定列数；一至八列共用同一Placement入口。 |
| 整批刀位 | `layout_engine/cutter_planner.py`, `dynamic_columns.py`, `knife_optimizer.py`, `adaptive_knife.py` | N列生成N-1条区域固定刀位；多数可并排时形成一个并排区，其余完整订单形成一个旋转区；禁止超过两个区域。 |
| 旋转区域和整批旋转 | `layout_engine/rotation_zones.py`, `rotation_compare.py`, `whole_rotation.py` | 以完整订单或尺码块评估，不复制候选算法。 |
| 单排超宽恢复 | `layout_engine/width_fit.py`, `gap_fallback.py` | 先旋转、符合规则时再等比缩小；保留恢复报告。 |
| S–L并排宽度上限 | `layout_engine/pair_width.py` | 主界面默认开启；按270毫米上限生成尺寸覆盖，实际列数仍由膜宽和自动多列规划决定；不修改源图。 |
| 多刀位安全事实 | `layout_engine/knife_positions.py`, `cut_validation.py` | 输出、预览、像素检查和报告复用实际刀位列表；每条安全通道独立核验。 |
| 标签、平台文字和刀码 | `layout_engine/labels.py`, `marker_stack.py`, `platform_label.py` | 测量、预览、输出使用同一几何结果。 |
| 二维码侧别与空白带 | `layout_engine/qr_corners.py`, `qr_placement.py`, `header_region.py` | 只测顶部有限条带的位置和可用空间，不做二维码解码或整图像素读取。 |
| 透明区域搜索 | `layout_engine/transparent_search.py`, `platform_space.py`, `marker_space.py` | 像素读取结果进入测量缓存，不在每个方案重复扫描。 |
| 膜规格方案比较 | `layout_engine/film_comparison.py`, `film_specs.py` | 比较方案不自动替用户选择生产膜。 |
| Pillow 渲染 | `layout_engine/pillow_renderer.py` | 与 vips 共享规划和安全契约，不复制排版业务。 |
| libvips 分块渲染与运行时门禁 | `layout_engine/vips_renderer.py`, `engine_info.py`, `png_codecs/` | 使用浅层画布图和固定快速滤波完成合成编码；外层延迟任务通过共享门禁串行进入，libvips 内部仍可多线程，正常退出前清理缓存并关闭原生线程。 |
| 分段输出 | `layout_engine/segmented_output.py`, `atomic_png.py` | 按完整行/订单切分，失败文件不可冒充可打印结果。 |
| 输出命名与完成总结 | `layout_engine/output_name.py`, `output_sizes.py`, `output_file_info.py` | 单批、多批、分段统一订单/件数命名和报告字段；最终PNG扁平移入`切膜机文件`，文本报告进入平级`排版日志`，不生成输出JSON。 |
| 订单与刀位安全 | `layout_engine/order_validation.py`, `cut_validation.py`, `marked_pixel_validation.py` | 规划后和真实像素阶段分别核验，不能由 UI 绕过。 |
| 计划和测量缓存 | `layout_engine/plan_cache.py`, `measurement_cache.py`, `measurement_session.py`, `cutter_measurements.py`, `normal_plan_cache.py`, `cached_planner.py` | 整批计划、切膜几何与单图测量分层缓存；生产方案和膜规格比较复用同一批刀码几何，不重复进入逐图测量；单图缓存不因膜宽、组批或普通软件版本变化而失效，均使用文件指纹和24小时绝对失效策略。 |
| 仅预览报告 | `layout_engine/preview_result.py`, `output_sizes.py`, `ui/batch_summary.py` | 不渲染、不写打印图片；仍返回完整排版、刀位、单排原因和耗时报告供界面复制。 |
| 单批次后台编排 | `ui/generation_actions.py`, `ui/workers.py` | UI线程只接收不可变结果和进度信号。 |
| 多批次滚动编排 | `ui/bulk_workbench.py`, `bulk_generation_worker.py` | 外层线程池有空位立即补批次；合并批次复用内部图片线程。 |
| 主界面进度展示 | `ui/busy_spinner.py`, `operation_timing.py`, `generation_panel.py` | 未知总量用旋转指示，已知总量用真实进度条。 |
| 错误上下文与复制 | `layout_engine/error_context.py`, `error_parameters.py`, `ui/failure_panel.py` | 所有失败复用完整订单/参数诊断，不散落拼字符串。 |
| 参数持久化与模式可见性 | `ui/preferences.py`, `preference_autosave.py`, `layout_values.py`, `developer_mode.py` | 稳定生产控件对普通用户开放；新实验功能默认只在开发者模式显示并生效。控件只绑定一个当前配置键，父项变化同步清理非法子项。 |
| 批次及膜历史 | `history/store.py`, `history/batch_queue.py`, `history/bulk_analysis.py` | 历史格式由存储模块维护，UI不直接写日志文件。 |
| 源码更新 | `updates/`, `updater.py` | 检查、应用、重启为一个状态机，不要求点击两次。 |
| 协作取消 | `cancellation.py`, `ui/stop_actions.py`, `thread_lifecycle.py` | 长循环定期检查；停止不关闭应用，关闭可立即退出。 |

## 新增能力检查

1. 写清输入、输出、副作用、线程边界、缓存和生产安全要求。
2. 检查上表所有者并搜索活动调用方和相关测试。
3. 组合优先，其次扩展接口，再抽共享核心并迁移全部活跃重复。
4. 新实现必须说明与现有能力在业务语义上的差异。
5. 更新本表，并在规范所有者边界增加契约测试。

相同外观不代表相同业务；不同名称也不代表可以复制相同实现。
