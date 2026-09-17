# Shared Function Catalog

新增代码前先查本目录，再按业务字段、中文 UI 文案、类型、报告字段和测试搜索。这里记录唯一所有者，
不是提交日志。

| 能力 | 规范所有者 | 复用规则 |
| --- | --- | --- |
| 图片发现与嵌套批次扫描 | `layout_engine/intake/discovery/discovery.py`, `layout_engine/intake/discovery/batch_discovery.py` | 单批、多批和分析功能复用，不各自遍历目录。 |
| 图片尺寸、DPI与源信息 | `layout_engine/intake/metadata/source_metadata.py`, `layout_engine/intake/metadata/images.py`, `layout_engine/intake/metadata/output_dpi.py`, `layout_engine/domain/models.py` | 一次读取形成共享事实；`LayoutItem`与`Placement`集中在模型模块，标签、排版和报告不得重复解码。 |
| 批次数据快照与并行测量 | `layout_engine/intake/preparation/batch_snapshot.py`, `layout_engine/measurement/measurement_session.py`, `layout_engine/measurement/parallel_measurement.py`, `ui/layout_values.py`, `ui/bulk_generation_worker.py` | 生成、仅预览和批量分析从首次读取到最终报告共享一个批次会话；保持结果原顺序，线程完成顺序不能改变生产顺序；最低线程档自动给单批次最多4线程，多批次按实际并行数均分。 |
| 订单、双面、尺码归组及批次构成 | `layout_engine/orders/order_groups.py`, `layout_engine/orders/batch_analysis.py`, `layout_engine/orders/size_policy.py`, `ui/batch_distribution.py`, `ui/quick_fields.py`, `ui/batch_summary.py` | 排版、比较、预览、报告和安全检查使用同一身份；预览上方及主操作区蓝色卡片复用紧凑尺码群或订单群，蓝色卡片同时汇总订单、件数、图片数、双面和膜间距扩充数量，不得为展示重新读取源图或刀码。 |
| 颜色与生产顺序 | `layout_engine/orders/color_policy.py`, `layout_engine/orders/single_order_sequence.py` | 颜色优先、尺码业务顺序集中维护。 |
| S2B批次元数据 | `automation/api/s2b/`, `.github/workflows/windows-release.yml` | 从文件夹尾部解析批次号；识别到 S2B 后不依赖开发者模式或平台选择，排版前必须一次读取共享服务并按订单项、尺码匹配全部本地图片。文件名失效时以订单文件夹对接口订单号作唯一回退匹配。颜色缺失时带诊断继续排版并由用户确认是否采用；颜色排序和四种膜方案复用按路径、修改时间和文件大小校验的缓存，同路径文件被替换后自动失效；完整内存缓存不再访问服务配置。中心地址内置，受限客户端密钥只在 Windows 构建时注入。 |
| 普通行和自动多列规划 | `layout_engine/planning/base/planner.py`, `layout_engine/planning/columns/cutter_planner.py`, `layout_engine/planning/columns/dynamic_columns.py`, `layout_engine/planning/columns/column_solver.py` | 膜宽与真实占位决定列数；先淘汰存在无列可放或无法填满全部列的物理无解候选，再用有记忆的列匹配求解；一至八列共用同一Placement入口。 |
| 整批刀位 | `layout_engine/planning/columns/cutter_planner.py`, `layout_engine/planning/columns/dynamic_columns.py`, `layout_engine/planning/columns/knife_optimizer.py`, `layout_engine/planning/columns/adaptive_knife.py` | N列生成N-1条区域固定刀位；多数可并排时形成一个并排区，其余完整订单形成一个旋转区；混色订单不充当单色边界；禁止超过两个区域。 |
| 旋转区域和整批旋转 | `layout_engine/planning/rotation/rotation_zones.py`, `layout_engine/planning/rotation/single_rotation.py`, `layout_engine/planning/rotation/rotation_compare.py`, `layout_engine/planning/rotation/whole_rotation.py` | 以完整订单或完整尺码块评估；已有末尾旋转区时逐个比较完整尺码后缀，允许把交界前的多排尺码组整体并入旋转区，同尺码不跨区。旋转后的真实占位重新进入共享自动多列规划，同颜色同尺码的独立单件可在块内贪心重排，让膜宽决定一至八列及固定刀位，不复制候选算法。 |
| 单排超宽恢复 | `layout_engine/planning/zones/width_fit.py`, `layout_engine/planning/zones/gap_fallback.py` | 旋转区先强制横向旋转，再按当前膜宽、刀码和安全距离的动态上限等比缩小；整批候选被个别超宽图阻断时按双面同倍率生成虚拟缩小候选并重跑完整订单贪心比较；保留恢复报告。 |
| S–L并排宽度上限 | `layout_engine/planning/zones/pair_width.py` | 主界面默认开启；按270毫米上限生成尺寸覆盖，实际列数仍由膜宽和自动多列规划决定；不修改源图。 |
| 多刀位安全事实 | `layout_engine/cutting/geometry/knife_change_gap.py`, `layout_engine/cutting/validation/cut_validation.py` | 输出、预览、像素检查和报告复用实际刀位列表；每条安全通道独立核验；双排转旋转、旋转转双排及批次结束均从前一枚左侧识别刀码补足设定停止距离。该规则仅在开发者模式正数参数下调用并使用独立缓存版本，普通模式保持原算法和缓存键。 |
| 标签、平台文字和刀码 | `layout_engine/labeling/base/labels.py`, `layout_engine/labeling/text/fonts.py`, `layout_engine/labeling/text/templates.py`, `layout_engine/labeling/text/platform_badge.py`, `layout_engine/labeling/base/dynamic_label.py`, `layout_engine/labeling/markers/marker_stack.py`, `layout_engine/labeling/markers/marker_space.py`, `layout_engine/labeling/platform/platform_space.py`, `layout_engine/labeling/platform/platform_label.py`, `layout_engine/planning/zones/gap_fallback.py` | 字体加载、文本模板与平台徽标分别只有一个所有者；平台文字由平台名和原图尺码组成，以二维码卡片高度为字号上限；测量、预览、输出使用同一几何结果，旋转后整个平台尺码标签随二维码同向旋转，并只复用二维码卡片内部经像素验证的未印刷白色或透明空位，绝不放到卡片与图案之间；卡片无安全空位时仅跳过该图平台文字、记录异常并继续。外置刀码紧贴图片边缘。整批复用透明带失败时由共享回退改用外置标签真实占位并继续，报告原值、采用值、影响和修改入口。 |
| 二维码侧别与空白带 | `layout_engine/labeling/platform/qr_corners.py`, `layout_engine/labeling/markers/qr_placement.py`, `layout_engine/labeling/base/header_region.py` | 只测顶部有限条带的位置和可用空间，不做二维码解码或整图像素读取。 |
| 透明区域搜索 | `layout_engine/labeling/platform/transparent_search.py`, `layout_engine/labeling/platform/platform_space.py`, `layout_engine/labeling/markers/marker_space.py`, `layout_engine/measurement/measurement_cache.py` | 像素读取结果按文件指纹、方向和精确矩形进入持久测量缓存，不在每个方案或后续同批生成中重复扫描。 |
| 膜标签透明补距 | `layout_engine/labeling/base/header_gap.py`, `layout_engine/labeling/gap/virtual.py`, `layout_engine/labeling/gap/virtual_cache.py`, `layout_engine/labeling/gap/preparation.py`, `layout_engine/labeling/gap/cache_files.py` | 基础模块负责路径映射和批次编排；Haloo、S2B与隆丰只记录持久化的透明间距几何并在最终合成时插入，不生成中间图片；其他平台保留无损补距副本兼容路径。缓存文件模块统一处理Windows占用重试与临时文件回收，单张仍失败时保留原图继续整批，不改原图。 |
| 轻量排版结构图 | `ui/layout_schematic.py`, `pair_preview.py` | 复用排版坐标与批次分析，不解码图片缩略图；单件显示尺码群，双面显示面别与尺码群，多件显示订单尺码群。 |
| 最近成功批次入口 | `history/recent_output.py`, `ui/recent_output.py`, `batch_input_panel.py` | 持久化与按钮展示分离；单批和多批成功生成后统一记录最终批次目录，主操作区按钮跨重启恢复，目录不存在时自动禁用；仅预览和失败任务不覆盖记录。 |
| 膜规格方案比较 | `layout_engine/planning/film/film_comparison.py`, `layout_engine/planning/film/film_specs.py` | 比较方案不自动替用户选择生产膜；当前实际输出对应的方案直接复用生产坐标，只计算另外三套几何方案。 |
| 当前膜快捷编辑 | `ui/current_film.py`, `ui/cutter_settings.py` | 主界面卡片直接修改膜规格、排版模式与自定义膜宽；快捷控件和完整打印设置必须双向同步。 |
| Pillow 渲染 | `layout_engine/rendering/engines/pillow_renderer.py` | 与 vips 共享规划和安全契约，不复制排版业务。 |
| libvips 分块渲染与运行时门禁 | `layout_engine/rendering/engines/vips_renderer.py`, `layout_engine/rendering/engine_info.py`, `layout_engine/rendering/storage/atomic_png.py`, `layout_engine/rendering/storage/save_progress.py`, `layout_engine/rendering/png/` | `layout_engine/rendering/png/row_stream.py` 按最终 Y 顺序逐行解码、合成、核对刀位 alpha、固定 UP 滤波、压缩并写入，每个排版行只求值一次且不生成中间图片；外层任务通过共享门禁串行进入，libvips 内部仍可多线程。完整 PNG 发布后顺序检查全部数据块 CRC、RGBA 尺寸和文件结构，不再二次解压已核对的像素流。 |
| 排版公共入口与生成编排 | `layout_engine/__init__.py`, `layout_engine/pipeline/service.py`, `layout_engine/domain/models.py` | 包入口只导出稳定公共能力；生成流程和领域模型各有唯一所有者，不保留根目录兼容模块。 |
| 排版单元组合 | `layout_engine/planning/packing/units.py` | 单面与双面不可拆组合统一转换为规划器候选，列规划和区域优化共用。 |
| 输出格式选择与并行分块 BigTIFF | `layout_engine/output/output_sizes.py`, `layout_engine/rendering/engines/output_encoder.py`, `layout_engine/rendering/storage/atomic_tiff.py`, `ui/settings/output/format.py`, `ui/batch_input_panel.py` | 仅开发者自由排版可使用 TIFF 性能测试；RIIN单列/自动多列切膜遇到旧TIFF设置时不中断，自动采用PNG并报告降级。主界面输出参数与完整打印设置双向同步，关闭开发者模式恢复 PNG；BigTIFF复用同一libvips画布，以有界Strip并行压缩并保留透明通道、DPI和原子发布。 |
| 分段输出 | `layout_engine/rendering/storage/segmented_output.py`, `layout_engine/rendering/storage/atomic_png.py` | 按完整行/订单切分，失败文件不可冒充可打印结果。 |
| 输出命名与完成总结 | `layout_engine/output/output_name.py`, `layout_engine/output/output_sizes.py`, `layout_engine/output/output_file_info.py`, `layout_engine/output/generation_result.py` | `layout_engine/output/output_name.py`从已确定计划统一生成批次、订单、件数、尺码和区域文件名；`layout_engine/output/generation_result.py`统一构造生产输出事实，单批、多批、分段不得自行拼接命名和报告字段。 |
| 订单与刀位安全 | `layout_engine/cutting/validation/order_validation.py`, `layout_engine/cutting/validation/cut_validation.py`, `layout_engine/cutting/validation/marked_pixel_validation.py` | 规划后和真实像素阶段分别核验，不能由 UI 绕过。 |
| 计划和测量缓存 | `layout_engine/planning/cache/plan_cache.py`, `layout_engine/measurement/measurement_cache.py`, `layout_engine/measurement/measurement_session.py`, `layout_engine/measurement/cutter_measurements.py`, `layout_engine/planning/cache/normal_plan_cache.py`, `layout_engine/planning/cache/cached_planner.py` | 整批计划、切膜几何与单图测量分层缓存；PNG/TIFF及压缩参数不改变几何，跨输出格式复用同一缓存；单图占位记录首次查询时批量装入任务快照，工作线程不逐条争用SQLite；生产方案、整批旋转和膜规格比较即使重排同一批路径，也按文件身份重组并复用同一批刀码几何，不重复进入逐图测量；整批缓存使用独立排版算法版本，普通软件发布不失效；文件状态一次并发读取后由批次会话复用；缓存使用文件指纹和24小时绝对失效策略，锁冲突短等待后跳过，不阻塞生产。 |
| 单图读取与排版对象 | `layout_engine/intake/preparation/item_reader.py`, `layout_engine/intake/preparation/item_factory.py` | 读取层一次收集尺寸、DPI、旋转候选和膜标签位置；构造层只计算标签、刀码、平台文字与最终占位，不重复打开源图。 |
| 仅预览报告 | `layout_engine/reporting/preview_result.py`, `layout_engine/output/output_sizes.py`, `ui/batch_summary.py` | 不渲染、不写打印图片；仍返回完整排版、刀位、单排原因和耗时报告供界面复制。 |
| 单批次后台编排 | `controllers/layout_generation.py`, `controllers/generation_progress.py`, `ui/workbench/generation/`, `ui/workers.py` | 控制器唯一拥有工作线程生命周期和纯进度计算；UI按启动、实时进度、结果展示分离，只收集参数、构造Worker并展示不可变结果。 |
| 统一批次排版入口与滚动编排 | `ui/preference_actions.py`, `controllers/bulk_generation.py`, `ui/bulk_workbench.py`, `bulk_generation_worker.py` | 同一入口扫描单批次或多批次目录；控制器拥有任务线程和取消，UI展示状态；外层线程池有空位立即补批次，合并批次复用内部图片线程。 |
| 主界面进度展示 | `ui/busy_spinner.py`, `ui/layout_activity.py`, `ui/operation_timing.py`, `layout_engine/reporting/operation_timing.py`, `generation_panel.py` | 未知总量用旋转指示，已知总量用真实进度条；顶部活动按钮同步显示当前步骤耗时和整次总耗时，TIFF 保存显示已完成 Strip 数及真实高度进度，耗时占比仅保留在提示和耗时表。 |
| 主窗口可见页面装配 | `ui/main_window.py`, `ui/workbench/home.py`, `activity.py`, `settings.py` | 主窗口只连接应用状态和控制器；首页、任务状态与打印参数按实际UI区域各自拥有控件树，新增可见区域不得重新堆回主窗口。 |
| 主工作台批次总览 | `ui/workbench/overview/panel.py`, `label_controls.py`, `preview.py`, `bindings.py` | 目录直接对应快捷标签、批次数据、真实预览和参数联动；根目录兼容模块不拥有控件或业务逻辑。 |
| 刀码方向预览 | `ui/previews/markers/view.py`, `data.py`, `render.py`, `annotations.py` | 页签、示例数据、像素渲染和尺寸标注分别拥有唯一职责；预览复用生产排版对象和真实坐标。 |
| 真实排版预览运行时 | `ui/previews/runtime/task.py`, `loader.py`, `snapshot.py`, `viewport.py` | 后台计算、结果加载、轻量快照和视口交互分离；耗时计算不进入GUI线程。 |
| 错误上下文与复制 | `layout_engine/diagnostics/error_context.py`, `layout_engine/diagnostics/error_parameters.py`, `ui/failure_panel.py` | 所有失败复用完整订单/参数诊断，不散落拼字符串。 |
| 参数持久化与模式可见性 | `ui/workbench/preferences/`, `ui/preference_autosave.py`, `layout_values.py`, `developer_mode.py` | 读取、保存和文件夹/设置窗口动作按状态方向分离；稳定生产控件对普通用户开放，新实验功能默认只在开发者模式显示并生效。 |
| 输出参数界面 | `ui/settings/output/dpi.py`, `location.py`, `format.py`, `segmentation.py` | 设置页输出区域按用户可见参数分离，统一向工作台和生成入口提供控件与保存位置解析。 |
| 通用数值参数控件 | `ui/spinbox_style.py` | 所有毫米、尺寸和偏移浮点输入复用`double_spinbox`，不在页面内复制范围、精度和初始值构造代码。 |
| 参数联动刷新门禁 | `ui/parameter_refresh.py` | 平台和模式一次更新多个控件时取消旧预览并抑制新批次读取；不用多个信号重复触发排版。 |
| 应用重启 | `runtime/restart.py` | 源码更新和恢复出厂设置共用同一安全重启入口；仅 `dev.py` 子进程监听重载标记，普通快捷方式启动会清理过期标记，安装环境启动新进程。 |
| 批次及膜历史 | `history/store.py`, `history/batch_queue.py`, `history/bulk_analysis.py` | 历史格式由存储模块维护，UI不直接写日志文件。 |
| ERP生产批次读取与下载 | `automation/browser/batches.py`, `automation/api/erp/records.py`, `automation/transfer/downloads.py` | 浏览器流程、文件传输与响应映射分离；外层工厂页面与内嵌生产模块共用一个批次内容定位入口，列表、搜索、就绪状态和下载不得各自假设表格位于顶层页面。 |
| 生产平台下载入口 | `ui/erp_download_entry.py`, `batch_ui/dialog.py`, `batch_ui/platform/`, `batch_ui/task/`, `batch_ui/shell/results.py` | 多选平台后分别显示独立工作区；平台页面与后台任务分层，仅下载、解压已生成批次，绝不自动启动排版；默认按页面选项在完成提示后打开对应平台文件夹。 |
| ERP工作台壳层 | `batch_ui/local/`, `platform/`, `task/`, `shell/` | 目录直接对应本地排版、平台批次、任务执行和公共窗口外壳；根对话框只装配，控件构造、结果展示和批次表映射各有唯一所有者。 |
| 蜂鸟ERP接口 | `automation/api/erp/gateway.py`, `items.py`, `batches.py`, `records.py` | 页面桥接、生产项与规则、生产批次、响应转换按请求对象分离；调用方直接复用提供商接口，不保留根目录转发模块。 |
| S2B接口 | `automation/api/s2b/metadata/`, `production/` | 批次身份、共享颜色尺码元数据与本地匹配归元数据层；生产列表、人员标签、导出请求和下载归生产层；两者复用同一Supabase受限网关客户端，原始Token不进入客户端。 |
| S2B生产图下载 | `automation/api/s2b/production/gateway.py`, `downloads.py`, `archive_io.py`, `automation/browser/batches.py` | 优先由Supabase服务端代理生产批次、导出和记录查询，用户选择后按实际件数补发缺失导出，轮询真实下载地址；`archive_io.py`唯一负责下载、ZIP路径校验与解压，网关不可用才回退已登录页面，下载标记接口不承担文件传输。 |
| 自动化批次规则与本地身份 | `automation/batches/classification.py`, `local.py`, `naming.py`, `rules.py` | 分类、扫描、命名和生成规则按批次域集中；界面只调用这些共享能力，不自行解析或改名。 |
| 自动化浏览器、传输与平台 | `automation/browser/`, `automation/transfer/`, `automation/providers/`, `automation/workflows/` | 登录会话、批次页面、导出下载、平台配置和端到端流程分别归档；`automation/`根目录只公开稳定入口。 |
| 源码更新 | `updates/source.py`, `updates/release.py`, `updates/versioning.py`, `updates/worker.py` | 源码安装更新、发布包检查、版本展示和后台执行按职责分离；检查、应用和重启保持同一状态机。 |
| 协作取消与安全关闭 | `runtime/cancellation.py`, `controllers/thread_lifecycle.py`, `ui/stop_actions.py`, `ui/immediate_exit.py` | 控制器拥有线程释放，UI只路由用户停止意图；任务运行时拒绝关闭并继续处理，空闲时由 Qt 正常退出，禁止强杀进程。 |
| 应用运行时 | `runtime/branding.py`, `runtime/resources.py`, `runtime/crash_logging.py`, `runtime/restart.py`, `runtime/cancellation.py` | 品牌、资源、故障日志、重启和任务取消归运行时层；包根目录只保留启动入口。 |

## 新增能力检查

1. 写清输入、输出、副作用、线程边界、缓存和生产安全要求。
2. 检查上表所有者并搜索活动调用方和相关测试。
3. 组合优先，其次扩展接口，再抽共享核心并迁移全部活跃重复。
4. 新实现必须说明与现有能力在业务语义上的差异。
5. 更新本表，并在规范所有者边界增加契约测试。

相同外观不代表相同业务；不同名称也不代表可以复制相同实现。
