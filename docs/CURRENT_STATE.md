# Current System Map

本文只描述当前活动代码归属。结构调整后更新；小功能提交不追加流水记录。

## 入口与编排

- 应用入口：`automatic_print/__main__.py`、`automatic_print/app.py`。
- 主窗口：`automatic_print/ui/main_window.py`只负责应用级状态、控制器装配和窗口生命周期；
  界面上可见的工作台首页、任务状态和打印参数分别映射到`automatic_print/ui/workbench/home.py`、
  `activity.py`和`settings.py`，不再把控件树堆在主窗口入口。
- 主工作台：实际页面在`automatic_print/batch_ui/` 和
  `automatic_print/ui/workbench/overview/`；旧的
  `ui/label_quick_panel.py`仅保留稳定兼容导入。
- 生产批次工作台目录直接对应界面和执行层级：`batch_ui/local/`拥有本地排版页，
  `platform/`拥有已接单与生产批次页，`task/`拥有后台任务生命周期，`shell/`拥有窗口外壳；
  根目录`dialog.py`只装配这些区域。`shell/view.py`只构造公共控件，`results.py`只展示任务结果，
  `batch_table.py`只映射批次表格。
- 排版运行期间的当前阶段、耗时和占比只显示在顶部“开始排版”按钮；下方批次区只保留文件夹队列、
  完成结果、方案耗时与总结，不重复放置当前进度条、当前文件和状态文字。文件夹队列表仅显示
  “文件夹、图片数、尺码群/订单群”，详细阶段保留在行提示中。
- 普通模式显示生产排版规则、45/60厘米方案、批次处理记录、膜标签间距和额外损耗。补足膜间距
  由 `ui/header_gap.py` 的独立开关控制，保存的毫米数值本身不会自动启用；`layout_engine/labeling/base/header_gap.py`负责批次编排，`layout_engine/labeling/gap/virtual.py`让Haloo、S2B、莆田和隆丰持久缓存间距几何并在最终合成时插入透明像素，不创建中间大图；其他平台仍由`layout_engine/labeling/gap/preparation.py`生成兼容副本，`layout_engine/labeling/gap/cache_files.py`负责Windows占用重试和临时文件回收。补距会越过Haloo标签不属于白色卡片连通域的彩色底栏，再从真实透明分界补足40毫米。批次预览和最终报告显示总数、实际扩充、原本已满足、未能扩充及新增毫米范围。开发者模式显示算法
  诊断、排版历史、批量膜分析和批次顺序标注；主界面底部的功能列表按分类展示全部开发者功能
  及当前开启状态；膜规格比较固定为45/60厘米四套方案。
- 开发者模式主界面“刀码与标签”参数组同时提供切膜刀码和平台尺码标签开关。前者在正常排版与上次
  切膜模式之间切换，后者镜像`label_settings.platform_enabled`并只把`LayoutSettings.platform_name`
  置空；两者互不联动。
- `ui/batch_input_panel.py` 拥有主界面的批次操作和常用参数分组；最上方蓝色批次卡片先显示当前目录，
  文件名扫描完成后立即原位显示批次类型、订单/件数/图片数、尺码群和本地可识别颜色；S2B接口返回后
  在同一张卡片补全颜色和订单身份，不等待尺寸、刀码或排版计算。完整分析随后补充膜间距实际扩充数量；多批次切换时
  同步切换当前子批次，不重新读取图片或刀码。膜规格和排版方式与它并列，批次、输出、排版和标签参数
  使用同一层级，并提供持久化的“打开最近生成的批次”
  快捷入口；批次顺序标注仍受开发者模式控制。
  `ui/workbench/overview/`按界面区域分别拥有快捷标签、批次数据、预览和信号联动；进入时默认展示
  不解码缩略图的整批订单结构图，按单件尺码群、双面尺码群和多件订单尺码群显示真实排版坐标；
  用户可切换到当前订单真实图片，刀码示意不代替真实坐标预览。
- `ui/current_film.py` 的当前膜卡片可直接修改膜规格、排版模式和自定义膜宽，修改结果与打印参数设置使用同一数据源。
- `ui/parameter_refresh.py` 统一抑制开发者模式和平台默认值联动期间的预览请求；参数更新后
  保留明确提示，只有用户重新启动排版才会读取批次。应用重启由 `runtime/restart.py` 统一拥有，
  源码更新和恢复出厂设置共用同一启动策略。
- 单批次生成控制：`automatic_print/controllers/layout_generation.py` 独立拥有工作线程、Worker信号接线、
  取消和释放；`controllers/generation_progress.py` 提供纯进度计算。界面启动、实时进度和最终结果分别位于
  `ui/workbench/generation/start.py`、`progress.py`和`results.py`；`ui/generation_actions.py`与
  `ui/thread_lifecycle.py`仅保留旧调用方兼容导入。
- 单批生成、仅预览及批量分析的每个批次均由 `layout_engine/measurement/measurement_session.py` 建立一份数据
  快照；DPI、尺寸、膜标签位置和各方向刀码占位在后续方案与报告中直接复用。
- 生成完成弹窗由 `layout_engine/output/output_file_info.py` 汇总最终生产结果；膜规格表把当前膜行替换为
  同一最终计划的真实统计，输出名由 `layout_engine/output/output_name.py` 同时写入订单数和件数。
- `layout_engine/output/output_name.py` 统一管理输出落点：生成期间写入 `排版日志/.处理中` 隔离目录，
  安全检查完成后把最终PNG扁平移入 `切膜机文件`；文本报告保存在平级 `排版日志`，不写输出JSON。
- 多批次生成控制：`automatic_print/controllers/bulk_generation.py` 管理线程、取消和释放；
  `ui/bulk_workbench.py`、`bulk_generation_worker.py`、`batch_status_board.py`分别负责展示编排、任务执行和状态视图。
  主界面以一个“开始排版”入口统一处理
  单批次目录和多批次上级目录，批次扫描结果决定实际队列数量。

## 排版核心

- 公共排版入口直接由`automatic_print/layout_engine/__init__.py`导出；共享模型位于`domain/`，
  生成编排位于`pipeline/`，根目录不保留重复兼容门面。
- 完整生成服务：`automatic_print/layout_engine/pipeline/service.py`。
- `layout_engine/` 根目录只保留公共模型、单位、引擎信息、质量门禁和生成服务；实现按
  `intake/`、`orders/`、`measurement/`、`planning/`、`cutting/`、`labeling/`、
  `rendering/`、`output/`、`reporting/`和`diagnostics/`分层。每个叶子业务包最多五个
  直接实现模块，禁止再把新功能平铺回根目录。
- 文件发现与元数据：`layout_engine/intake/discovery/discovery.py`、`layout_engine/intake/discovery/batch_discovery.py`、`layout_engine/intake/metadata/source_metadata.py`、
  `layout_engine/intake/metadata/output_dpi.py`。`layout_engine/intake/preparation/item_reader.py`只负责一次读取尺寸、DPI、旋转候选和膜标签检测，
  `layout_engine/intake/preparation/item_factory.py`只把测量结果组装为单张排版对象。
- S2B 文件夹批次号解析、中心批次查询及本地图片颜色匹配位于
  `automation/api/s2b/metadata/`，生产批次列表和导出下载位于`production/`；只要识别到 S2B 批次，预览和生成都会在排版前查询一次订单颜色并按本地
  路径、修改时间和文件大小缓存，不依赖开发者模式或手动平台选择；同一路径被替换后颜色和订单缓存自动失效，完整缓存命中时不再访问服务配置。服务不可用或任一图片颜色未匹配时保留本地信息继续
  排版，在预览、报告和完成确认中显示诊断，由用户选择是否采用结果；文件名不能识别订单时，以批次目录内的订单文件夹作唯一匹配回退，并把接口订单身份
  写回共享订单归组。中心地址随应用提供，正式 Windows 构建从 GitHub Secret
  `AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY` 注入受限客户端密钥；源码树只保留空占位，
  Supabase service-role 和 S2B 登录凭据都不下发到生产电脑。
- 订单、双面、颜色与尺码：`layout_engine/orders/order_groups.py`、`layout_engine/orders/batch_analysis.py`、
  `layout_engine/orders/single_order_sequence.py`、`layout_engine/orders/color_policy.py`、`layout_engine/orders/size_policy.py`。
- 行、刀位和区域规划：`layout_engine/planning/base/planner.py`、`layout_engine/planning/base/row_optimizer.py`、`layout_engine/planning/columns/cutter_planner.py`、`layout_engine/planning/columns/dynamic_columns.py`、
  `layout_engine/planning/knife/optimizer.py`、`layout_engine/planning/columns/adaptive_knife.py`、`layout_engine/planning/zones/zone_optimizer.py`、`layout_engine/planning/rotation/rotation_zones.py`。列数由膜宽与真实占位
  动态形成；物理上无法容纳整批或无法实际使用全部列的候选在进入排版动态规划前淘汰，列分配使用有记忆匹配而非全排列。`layout_engine/planning/columns/adaptive_knife.py` 唯一组装“并排区 + 剩余旋转区”，旋转仍超宽时复用 `layout_engine/planning/zones/width_fit.py` 缩小缓存。
  混色订单不参与单色区域边界比较，避免错误清空已经成立的多数并排区。
- 主界面默认开启的 S–L 并排宽度上限由 `layout_engine/planning/zones/pair_width.py` 唯一计算；通过单图尺寸覆盖交给既有
  测量、刀位、预览和渲染链路，不生成或修改源图片副本。
- 旋转与超宽恢复：`layout_engine/planning/rotation/rotation_compare.py`、`layout_engine/planning/rotation/whole_rotation.py`、`layout_engine/planning/rotation/tail_rotation.py`、
  `layout_engine/planning/rotation/single_rotation.py`、`layout_engine/planning/zones/width_fit.py`、`layout_engine/planning/zones/gap_fallback.py`。
  单件批次以完整尺码后缀比较多排区与旋转区分界；已有末尾旋转区时，可把交界前的完整尺码组整体并入旋转区，但同尺码绝不跨区。旋转区的竖图保持横向旋转，超出当前动态安全宽度时再等比缩小；整批旋转被个别超宽图阻断时，
  `layout_engine/planning/zones/gap_fallback.py` 用虚拟尺寸覆盖重跑完整订单局部比较，双面同倍率且整批仍最多只有并排区和旋转区两个区域。
- 标签与刀码：`layout_engine/labeling/base/labels.py`、`layout_engine/labeling/base/dynamic_label.py`、`layout_engine/labeling/markers/marker_stack.py`、`layout_engine/labeling/markers/left_marker.py`、
  `layout_engine/labeling/platform/platform_label.py`、`layout_engine/labeling/base/header_region.py`、`layout_engine/labeling/platform/transparent_search.py`。平台尺码文字只放入原图二维码卡片内部
  已验证的未印刷白色或透明空位，绝不放到卡片与图案之间，使用不超过二维码卡片高度的最大字号；先在原图坐标确定位置，再与二维码一起旋转，预览与输出复用同一坐标；普通标签和平台文字都在旋转后的膜标签高度带内搜索
  图片自身的透明空位并互相避让；二维码卡片没有经过最终像素验证的安全空位时，仅跳过该图的平台尺码文字、记录异常并继续，不阻断整批。外置刀码紧贴图片边缘；整批复用透明带失败时由`layout_engine/planning/zones/gap_fallback.py`
  改用外置标签真实占位、重算刀位并记录完整恢复诊断。最终坐标越界等不可恢复安全冲突仍不得猜值绕过，
  不能回退到刀码与二维码之间或膜标签与图案之间。
- 开发者排版隔离：换刀与批次结束570毫米停止距离只有开发者模式显式传入正数时才进入规划、候选比较和独立开发者缓存版本；普通模式不调用该逻辑，使用算法缓存版本4，缓存键也不包含开发者紧凑排版与停止距离字段。
- 标签字体加载与线程内有界缓存由`layout_engine/labeling/text/fonts.py`唯一拥有；`layout_engine/labeling/base/labels.py`只负责标签内容、
  换行和徽标渲染。单图排版对象`LayoutItem`与`Placement`统一归`layout_engine/domain/models.py`。
- 渲染与编码：`layout_engine/rendering/engines/pillow_renderer.py`、`layout_engine/rendering/engines/vips_renderer.py`、`layout_engine/rendering/png/`、
  `layout_engine/rendering/storage/segmented_output.py`、`layout_engine/rendering/storage/atomic_png.py`、`layout_engine/rendering/storage/atomic_tiff.py`。超长 PNG 由 `layout_engine/rendering/png/row_stream.py`
  按排版行依次解码、合成、固定 UP 滤波、无损 RLE 压缩和写入，每行只求值一次且不生成中间图片；同一行的最终
  alpha 像素在压缩前同步核对全部刀位，PNG 发布后顺序读取数据块并核对 CRC、尺寸和 RGBA 格式，
  不再完整解压刚刚验证并编码的超长像素流；不再为每条刀位重复触发超长延迟画布合成，
  也不依赖 libvips 二次打开大图，
  避免超长PNG二次解码触发原生库崩溃。保存计时包含 libvips 延迟合成、编码与写入，不能解释成纯磁盘耗时。多个 Python
  工作线程的 libvips 外层延迟任务由共享门禁协调，原生库内部仍保留并行，并在正常退出时完成清理。
  开发者模式可在主界面“输出”参数组直接选择 PNG 或并行分块 BigTIFF，并与完整打印参数双向同步；
  BigTIFF 画布按整幅宽度和内存预算选择256至4096行 Strip 有界生成，
  tifffile/imagecodecs 多线程压缩，单一写入器登记块偏移；每个 Strip 在压缩前同步核对真实 alpha 刀位，
  不再保存后重新解压超长 TIFF；普通模式始终回到 PNG。RIIN单列/自动多列切膜即使读取到开发者旧TIFF设置，也由`layout_engine/output/output_sizes.py`继续任务并降级为PNG；TIFF仅保留给自由排版性能测试。
- 输出安全：`layout_engine/cutting/validation/order_validation.py`、`layout_engine/cutting/validation/cut_validation.py`、
  `layout_engine/cutting/validation/marked_pixel_validation.py`、`layout_engine/cutting/geometry/printed_guides.py`、`layout_engine/output/output_file_info.py`。
  `layout_engine/cutting/geometry/knife_change_gap.py`在开发者模式参数启用时，对实际刀位变化边界移动后续整行，
  并在最后一枚左侧识别刀码之后补足批次结束距离；双排转旋转、旋转转双排和批次结束均至少保留
  设定距离（机器550毫米搜索距离默认采用570毫米），最终刀位检查和输出报告复核同一距离事实。
- 膜方案与统计：`layout_engine/planning/film/film_comparison.py` 直接复用当前实际输出行并并行计算其余方案；`layout_engine/planning/film/film_specs.py`、`layout_engine/reporting/metrics.py`、
  `layout_engine/reporting/operation_timing.py`、`layout_engine/reporting/algorithm_costs.py`。
- 缓存：`layout_engine/planning/cache/plan_cache.py`、`layout_engine/planning/cache/normal_plan_cache.py`、`layout_engine/planning/cache/cached_planner.py`；单图测量由
  `layout_engine/measurement/measurement_cache.py` 持久化，并由 `layout_engine/measurement/measurement_session.py` 在任务内共享连接；PNG/TIFF及压缩参数不改变几何，跨输出格式复用同一缓存；单图占位和标签卡片区域按文件指纹持久化，后续安全复核不重新解码顶部条带；单图占位记录首次查询时一次装入任务快照，后续工作线程不再逐条争用 SQLite；
  `layout_engine/measurement/cutter_measurements.py` 保存本批正常/旋转刀码几何；后续方案即使改变路径顺序，也按文件身份重组并复用，生产方案、整批旋转和膜规格比较不再重复逐图测量。
  内置刀码和文字的透明矩形像素结论也按文件身份、方向和精确矩形持久化；单图缓存24小时，
  重新组批、膜宽变化和普通版本更新不触发源图重新测量。整批排版缓存使用独立排版算法版本而非
  软件发布版本；缓存键一次并发读取全部文件状态并写入当前测量会话，未命中后立即切换到实际测量阶段计时。
  主界面线程最低档显示为“自动（最多4线程）”：单批次取得完整线程预算，多批次按实际并行批次数均分；
  输出文件信息显示本批次有效线程数，便于直接确认测试机是否仍以单线程编码。

## UI 与本地数据

- 设置界面的读取、保存与用户动作分别位于`ui/workbench/preferences/load.py`、`save.py`和
  `actions.py`；根目录`preferences.py`、`preference_actions.py`仅保留兼容导入，自动保存仍由
  `preference_autosave.py`节流，排版参数快照由`layout_values.py`生成。设置页“输出”区域的
  分辨率、保存位置、格式和分段保存集中在`ui/settings/output/`。
- 批次构成：`ui/batch_distribution.py` 在单批和多批真实预览上方显示当前批次的紧凑尺码群或订单群；
  膜规格比较表不再承载该信息。
- 进度、停止和线程生命周期：`ui/busy_spinner.py`、`layout_activity.py`、
  `layout_engine/reporting/operation_timing.py`、`stop_actions.py`、`thread_lifecycle.py`、`worker_bridge.py`；
  顶部唯一活动状态同时显示当前步骤耗时和整次排版总耗时；TIFF 保存时另显示已完成 Strip 数及
  真实高度进度，不再把“步骤耗时占总耗时”这个非线性比例伪装成任务完成进度。
- 保存耗时：`layout_engine/rendering/storage/save_progress.py`记录首批PNG数据、持续文件增长、编码收尾和原子发布；
  `layout_engine/rendering/storage/atomic_png.py`与输出报告复用该事实，不把libvips重叠流水线伪装成互斥CPU步骤。流式PNG编码每行时，
  `layout_engine/cutting/validation/cut_validation.py`的全部区域刀位同步核对最终 alpha；发布后只顺序复核全部数据块 CRC、尺寸和格式。失败文件
  改名为“生成未完成”并保留诊断，等待用户选择后续处理，同时避免再次解压整幅超长PNG。
- 预览：异步任务、快照生成、加载和缩放控件集中在`ui/previews/runtime/`；“刀码四种情况”页签的视图、
  数据、渲染与标注集中在`ui/previews/markers/`。`layout_engine/reporting/preview_result.py` 形成不落地打印图片的
  完整报告数据，`ui/batch_summary.py` 显示可复制的刀位、单排原因和耗时报告。
- 错误诊断：`ui/failure_panel.py`、`failure_dialog.py`、
  `layout_engine/diagnostics/error_context.py`、`layout_engine/diagnostics/error_parameters.py`。
- 历史记录：`automatic_print/history/`；最近成功输出路径由 `history/recent_output.py` 持久化，
  UI只负责按钮状态和打开目录；Qt 参数使用 `QSettings`。
- 应用运行时：`automatic_print/runtime/`集中品牌、资源、崩溃日志、重启和任务取消；包根目录只保留
  `__init__.py`、`__main__.py`和`app.py`三个启动入口。
- 更新：`automatic_print/updates/`集中源码更新、发布检查、版本展示和后台执行。

## 外部自动化

- Haloo 下载工作区提供已生产分类只读预览，展示样本范围、物流、底款、颜色、面别、尺码档、来源批次及未纳入数量；不提交生成、不声称跨页整单完整。`batch_ui/task/reads.py`复用现有工作线程，`local/scanning.py`后台读取目录并按来源范围丢弃旧结果。批次排版复用界面补距开关及数值，不再强制40毫米。

- ERP批次页允许等待隐藏微前端iframe挂载，再由批次入口验证实际表格。`automation/batches/local.py`统一发现本地批次；同批次号的嵌套解压目录保留外层一次，包含其全部图片，避免重复排版；预览输出目录不参与来源发现。
- Haloo已生产测试批次由`automation/batches/completed.py`只读规划：状态9、实际生产图面别、整单、物流、订单组成、主底款、黑白和尺码档均须明确；已生产项目已有来源批次且生成接口无预演参数，当前安全门禁禁止写入，避免重开生产或扰动队列。接口证据见`docs/HALOO_BATCH_GENERATION.md`。

- `automation/api/riin/__main__.py`提供独立管理员命令入口，`elevation.py`通过Windows正常UAC授权启动一次指定操作；不要求主工作台或Codex提权。`desktop.py`拥有原生/UIA控件发现和导入文件选择框，`dialogs.py`拥有导入确认与错误对话框操作，`workflow.py`编排完整导入到PRN流程；来源目录递归读取PNG并按文件选择框容量分段。报告区分“提交导入”和实际加载完成，失败保留RIIN界面供用户继续处理；文件输出由output.py负责。旧版MFC导入按钮使用已核验的工具栏相对位置，工具栏高度不符时拒绝点击并要求重新校准。
- `automation/api/riin/output.py`新增文件输出和PrintExp加载命令，扩展上述导入入口。RIIN发送方式必须是“文件”，输出路径不可覆盖；PrintExp仅提交已有PRN，不启动物理打印。加载报告与实际预览核验分开。
- 主工作台在“本地排版”顶部开发者功能行提供“自动生成打印文件”按钮，复用本地排版的进度、预览、耗时、总结和批次记录；用户选择原始批次后，
  `ui/automated_layout.py`及`ui/automated_layout_files.py`先调用`ui/bulk_workbench.py`的统一本地排版入口并等待全部批次完成，随后只把
  本次结果记录中的最终PNG清单交给单一受限管理员任务，完成RIIN新建文档、分段导入、确认导入和
  PRN文件输出；不得把原图目录直接送入RIIN。若用户明确选择已有“切膜机文件”目录，则只枚举直接子项PNG，不解压像素也不二次排版，直接交给RIIN。
  RIIN等待期间同一区域持续显示导入文件数、已用时以及PRN已写入大小；只有非空PRN稳定落盘后才自动加入已打开的PrintExp并显示完成，但不点击开始打印；失败时保留已完成步骤和可复制诊断，由用户在RIIN中决定后续处理。
  每次RIIN任务记录本次新建的唯一MDI文档；导入完成后必须重新选中该文档再打开文件输出，避免RIIN存在多个未命名文档时把打印命令发送给任务管理中心或旧文档。
  RIIN文件输出进入其内部任务队列后，可能长时间显示“等待打印/正在打印”，并且只在任务完成时发布目标PRN；自动化最多等待两小时且仅以非空文件稳定落盘为成功，不能用三分钟无文件误判失败并重复提交同一路径。
  RIIN可能在排队时先创建48字节占位文件；完成判定必须同时满足任务管理中心精确输出路径对应行显示“打印完成”、文件不少于1KB且连续稳定，才可加入PrintExp。等待、正在打印、出错或停止均不能以文件暂时不增长替代真实任务状态。
- `automatic_print/automation/` 根目录只提供公共入口；批次分类、扫描、命名和规则位于
  `batches/`，浏览器会话与批次页面位于`browser/`，导出下载位于`transfer/`，平台配置与
  平台页面行为位于`providers/`，端到端流程位于`workflows/`。蜂鸟ERP页面桥接、生产项、
  生产批次和响应转换分别归档在`automation/api/erp/`，调用方不再经过根目录转发模块。
- ERP生产批次读取兼容顶层表格与工厂外壳中的`fnsz-sale`内嵌表格；莆田从首页“生产 / 批量生产”进入后可复用同一列表、搜索和下载通路。
- 蜂鸟ERP原始批次行到中立`BatchRecord`的转换集中在`automation/api/erp/records.py`，浏览器模块只负责页面与请求流程。
- “生产平台下载”作为主工作台独立页签，仅随开发者模式显示；支持多选已配置平台，每个平台独立显示批次、下载进度和日志。隆丰、莆田和Haloo复用蜂鸟ERP通路；S2B优先通过Supabase受限网关读取平台批次、人员标签、触发生产图导出并取得真实下载地址，原始S2B Token只在服务端解密；网关不可用时才回退专用浏览器登录。`production/downloads.py`负责编排，`production/archive_io.py`负责下载、校验及安全解压到`S2B/ARCHIVES`和`S2B/BATCHES`。下载流程不触发排版，也不自动创建生产批次。
- 蜂鸟ERP批次若已完成生产图导出但当前表格没有完整显示三个旧版下载入口，下载器复用已登录页面加载的导出记录，校验受信任HTTPS主机后流式保存同一ZIP；旧版三按钮下载继续作为兼容路径，不能因页面入口缺失拒绝已有完整导出。
- 生产平台工作台启动本地排版时，以当前工作台所选平台覆盖主界面的旧平台值；Haloo和莆田同时固定采用其40毫米默认补距，避免从下载页进入排版时因主界面残留选择而漏补。
- 冷启动时图片尺寸和DPI按用户线程上限并行预读，再一次批量查询单图测量缓存；只影响整批摆放的开发者算法开关不进入单图标签/刀码缓存键，切换开发者模式或升级该排版策略不会无故重解码原图。
- 跟随原图DPI时，批次DPI确认复用同一套有界尺寸预读并按用户线程上限并行访问源文件；结果保持原文件顺序，并向主界面报告真实完成数，避免网络批次逐张串行等待后再重复读取尺寸。
- 并行单图测量开始前尺寸已完成预读；主界面从第一张大图解压开始即显示“测量标签与刀码”及透明区域安全检查，不把首批大图像素解压误报为仍在读取轻量尺寸。
- 同一张膜标签卡片的透明/白色像素积分图在批次内只提取一次；不同字号探测及原方向、旋转方向共享该结果，不再为每个候选字号重复裁切和扫描二维码卡片。
- Haloo、S2B、莆田和隆丰启用虚拟补距时，每张源图在同一个内存快照中完成补距、尺寸/DPI、标签卡片、刀码透明区及原向/旋转候选测量；刀位计算和膜规格比较只复用测量结果，预览阶段以“每张源图完整解码一次”的自动测试锁定。
  各平台下载页默认勾选下载完成后打开对应平台文件夹，用户可在下载前关闭该行为。
- “莆田”和“Haloo”本地排版入口由`ui/developer_mode.py`控制，仅在开发者模式加入平台选择；`ui/print_settings_navigation.py`集中应用40毫米膜标签间距默认值。
- 新增外部平台接口必须进入`automation/api/<provider>/`；跨平台编排复用浏览器、批次和传输层，
  不在根目录增加平台文件或无业务含义的兼容转发层。

## 已知结构债务

- 以下遗留文件超过200行，测试已冻结当前上限；后续涉及其职责的修改应缩小而非增长：

| 归属 | 遗留文件 | 后续收敛方向 |
| --- | --- | --- |
| 排版核心 | `layout_engine/pipeline/service.py`, `layout_engine/planning/base/planner.py` | 服务只编排阶段；测量、候选和对象构造已有独立所有者。 |

- 部分 README 内容曾混入版本演进描述；当前规则以四份治理文档为准，README 仅保留使用和发布入口。
