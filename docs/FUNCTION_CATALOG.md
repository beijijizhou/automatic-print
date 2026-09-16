# Shared Function Catalog

新增代码前先查本目录，再按业务字段、中文 UI 文案、类型、报告字段和测试搜索。这里记录唯一所有者，
不是提交日志。

| 能力 | 规范所有者 | 复用规则 |
| --- | --- | --- |
| 图片发现与嵌套批次扫描 | `layout_engine/discovery.py`, `batch_discovery.py` | 单批、多批和分析功能复用，不各自遍历目录。 |
| 图片尺寸、DPI与源信息 | `layout_engine/source_metadata.py`, `images.py`, `output_dpi.py` | 一次读取形成共享事实；标签、排版和报告不得重复解码。 |
| 批次数据快照与并行测量 | `layout_engine/batch_snapshot.py`, `measurement_session.py`, `parallel_measurement.py` | 生成、仅预览和批量分析从首次读取到最终报告共享一个批次会话；保持结果原顺序，线程完成顺序不能改变生产顺序。 |
| 订单、双面、尺码归组及批次构成 | `layout_engine/order_groups.py`, `batch_analysis.py`, `size_policy.py`, `ui/batch_distribution.py` | 排版、比较、预览、报告和安全检查使用同一身份；预览上方单件显示紧凑尺码-数量，多件显示紧凑订单号-件数。 |
| 颜色与生产顺序 | `layout_engine/color_policy.py`, `single_order_sequence.py` | 颜色优先、尺码业务顺序集中维护。 |
| S2B批次元数据 | `automation/api/s2b/`, `.github/workflows/windows-release.yml` | 从文件夹尾部解析批次号，一次读取共享服务并按订单项、尺码匹配本地图片；不得在颜色排序或四种膜方案中重复访问接口。中心地址内置，受限客户端密钥只在 Windows 构建时注入。 |
| 普通行和自动多列规划 | `layout_engine/planner.py`, `cutter_planner.py`, `dynamic_columns.py`, `column_solver.py` | 膜宽与真实占位决定列数；一至八列共用同一Placement入口。 |
| 整批刀位 | `layout_engine/cutter_planner.py`, `dynamic_columns.py`, `knife_optimizer.py`, `adaptive_knife.py` | N列生成N-1条区域固定刀位；多数可并排时形成一个并排区，其余完整订单形成一个旋转区；混色订单不充当单色边界；禁止超过两个区域。 |
| 旋转区域和整批旋转 | `layout_engine/rotation_zones.py`, `rotation_compare.py`, `whole_rotation.py` | 以完整订单或尺码块评估，不复制候选算法。 |
| 单排超宽恢复 | `layout_engine/width_fit.py`, `gap_fallback.py` | 旋转区先强制横向旋转，再按当前膜宽、刀码和安全距离的动态上限等比缩小；整批候选被个别超宽图阻断时按双面同倍率生成虚拟缩小候选并重跑完整订单贪心比较；保留恢复报告。 |
| S–L并排宽度上限 | `layout_engine/pair_width.py` | 主界面默认开启；按270毫米上限生成尺寸覆盖，实际列数仍由膜宽和自动多列规划决定；不修改源图。 |
| 多刀位安全事实 | `layout_engine/knife_positions.py`, `cut_validation.py` | 输出、预览、像素检查和报告复用实际刀位列表；每条安全通道独立核验。 |
| 标签、平台文字和刀码 | `layout_engine/labels.py`, `dynamic_label.py`, `marker_stack.py`, `marker_space.py`, `platform_label.py` | 测量、预览、输出使用同一几何结果；所有新增文字必须完整处于膜标签高度带内，最终保存前再次校验；批次顺序标签使用所选批次文件夹名，不使用图片文件名；平台文字只复用二维码卡片透明空位，不得回退到外置刀码列。 |
| 二维码侧别与空白带 | `layout_engine/qr_corners.py`, `qr_placement.py`, `header_region.py` | 只测顶部有限条带的位置和可用空间，不做二维码解码或整图像素读取。 |
| 透明区域搜索 | `layout_engine/transparent_search.py`, `platform_space.py`, `marker_space.py` | 像素读取结果进入测量缓存，不在每个方案重复扫描。 |
| 轻量排版结构图 | `ui/layout_schematic.py`, `pair_preview.py` | 复用排版坐标与批次分析，不解码图片缩略图；单件显示尺码群，双面显示面别与尺码群，多件显示订单尺码群。 |
| 膜规格方案比较 | `layout_engine/film_comparison.py`, `film_specs.py` | 比较方案不自动替用户选择生产膜；当前实际输出对应的方案直接复用生产坐标，只计算另外三套几何方案。 |
| Pillow 渲染 | `layout_engine/pillow_renderer.py` | 与 vips 共享规划和安全契约，不复制排版业务。 |
| libvips 分块渲染与运行时门禁 | `layout_engine/vips_renderer.py`, `engine_info.py`, `atomic_png.py`, `save_progress.py`, `png_codecs/` | `png_codecs/row_stream.py` 按最终 Y 顺序逐行解码、合成、固定 UP 滤波、压缩并写入，每个排版行只求值一次且不生成中间图片；外层任务通过共享门禁串行进入，libvips 内部仍可多线程。完整 PNG 发布后由 `png_codecs/corridor_reader.py` 一次顺序解压，同时检查全部刀位 alpha、数据块 CRC、RGBA 尺寸和像素行完整性。 |
| 输出格式选择与并行分块 BigTIFF | `layout_engine/output_encoder.py`, `atomic_tiff.py`, `ui/output_settings.py` | 仅开发者模式可选择 TIFF；复用同一 libvips 画布，按整幅宽度的固定高度 Strip 有界生成，使用 tifffile/imagecodecs 多线程独立压缩并由单一写入器登记偏移；保留透明通道、DPI、原子发布与整批刀位复核。 |
| 分段输出 | `layout_engine/segmented_output.py`, `atomic_png.py` | 按完整行/订单切分，失败文件不可冒充可打印结果。 |
| 输出命名与完成总结 | `layout_engine/output_name.py`, `output_sizes.py`, `output_file_info.py`, `generation_result.py` | `generation_result.py` 统一构造生产输出事实；单批、多批、分段统一订单/件数命名和报告字段。 |
| 订单与刀位安全 | `layout_engine/order_validation.py`, `cut_validation.py`, `marked_pixel_validation.py` | 规划后和真实像素阶段分别核验，不能由 UI 绕过。 |
| 计划和测量缓存 | `layout_engine/plan_cache.py`, `measurement_cache.py`, `measurement_session.py`, `cutter_measurements.py`, `normal_plan_cache.py`, `cached_planner.py` | 整批计划、切膜几何与单图测量分层缓存；生产方案和膜规格比较复用同一批刀码几何，不重复进入逐图测量；单图缓存不因膜宽、组批或普通软件版本变化而失效，均使用文件指纹和24小时绝对失效策略；缓存锁冲突短等待后跳过，不阻塞生产。 |
| 仅预览报告 | `layout_engine/preview_result.py`, `output_sizes.py`, `ui/batch_summary.py` | 不渲染、不写打印图片；仍返回完整排版、刀位、单排原因和耗时报告供界面复制。 |
| 单批次后台编排 | `ui/generation_actions.py`, `ui/workers.py` | UI线程只接收不可变结果和进度信号。 |
| 多批次滚动编排 | `ui/bulk_workbench.py`, `bulk_generation_worker.py` | 外层线程池有空位立即补批次；合并批次复用内部图片线程。 |
| 主界面进度展示 | `ui/busy_spinner.py`, `operation_timing.py`, `generation_panel.py` | 未知总量用旋转指示，已知总量用真实进度条。 |
| 错误上下文与复制 | `layout_engine/error_context.py`, `error_parameters.py`, `ui/failure_panel.py` | 所有失败复用完整订单/参数诊断，不散落拼字符串。 |
| 参数持久化与模式可见性 | `ui/preferences.py`, `preference_actions.py`, `preference_autosave.py`, `layout_values.py`, `developer_mode.py` | 文件夹与设置窗口动作由 `preference_actions.py` 拥有；稳定生产控件对普通用户开放，新实验功能默认只在开发者模式显示并生效。 |
| 参数联动刷新门禁 | `ui/parameter_refresh.py` | 平台和模式一次更新多个控件时取消旧预览并抑制新批次读取；不用多个信号重复触发排版。 |
| 应用重启 | `restart_control.py` | 源码更新和恢复出厂设置共用同一安全重启入口；开发环境使用重载请求，安装环境启动新进程。 |
| 批次及膜历史 | `history/store.py`, `history/batch_queue.py`, `history/bulk_analysis.py` | 历史格式由存储模块维护，UI不直接写日志文件。 |
| ERP生产批次读取与下载 | `automation/batch_browser.py`, `automation/batch_downloads.py`, `automation/erp_api.py` | 外层工厂页面与内嵌生产模块共用一个批次内容定位入口；列表、搜索、就绪状态和下载不得各自假设表格位于顶层页面。 |
| 生产平台下载入口 | `ui/erp_download_entry.py`, `batch_ui/dialog.py`, `batch_ui/worker.py` | 多选平台后分别显示独立工作区；仅开放已生成批次下载、解压与排版预览，不得创建生产批次或生成最终大图。 |
| 源码更新 | `updates/`, `updater.py` | 检查、应用、重启为一个状态机，不要求点击两次。 |
| 协作取消 | `cancellation.py`, `ui/stop_actions.py`, `thread_lifecycle.py` | 长循环定期检查；停止不关闭应用，关闭可立即退出。 |

## 新增能力检查

1. 写清输入、输出、副作用、线程边界、缓存和生产安全要求。
2. 检查上表所有者并搜索活动调用方和相关测试。
3. 组合优先，其次扩展接口，再抽共享核心并迁移全部活跃重复。
4. 新实现必须说明与现有能力在业务语义上的差异。
5. 更新本表，并在规范所有者边界增加契约测试。

相同外观不代表相同业务；不同名称也不代表可以复制相同实现。
