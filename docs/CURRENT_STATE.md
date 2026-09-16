# Current System Map

本文只描述当前活动代码归属。结构调整后更新；小功能提交不追加流水记录。

## 入口与编排

- 应用入口：`automatic_print/__main__.py`、`automatic_print/app.py`。
- 主窗口：`automatic_print/ui/main_window.py`只负责应用级状态、控制器装配和窗口生命周期；
  界面上可见的工作台首页、任务状态和打印参数分别映射到`automatic_print/ui/workbench/home.py`、
  `activity.py`和`settings.py`，不再把控件树堆在主窗口入口。
- 主工作台：`automatic_print/automation_dialog.py` 为兼容门面；实际页面在
  `automatic_print/batch_ui/` 和 `automatic_print/ui/workbench/overview/`；旧的
  `ui/label_quick_panel.py`仅保留稳定兼容导入。
- 生产批次工作台目录直接对应界面和执行层级：`batch_ui/local/`拥有本地排版页，
  `platform/`拥有已接单与生产批次页，`task/`拥有后台任务生命周期，`shell/`拥有窗口外壳；
  根目录`dialog.py`只装配这些区域。`shell/view.py`只构造公共控件，`results.py`只展示任务结果，
  `batch_table.py`只映射批次表格。
- 普通模式显示生产排版规则、45/60厘米方案、批次处理记录、膜标签间距和额外损耗。补足膜间距
  由 `ui/header_gap.py` 的独立开关控制，保存的毫米数值本身不会自动启用。开发者模式显示算法
  诊断、排版历史、批量膜分析和批次顺序标注；主界面底部的功能列表按分类展示全部开发者功能
  及当前开启状态；膜规格比较固定为45/60厘米四套方案。
- `ui/batch_input_panel.py` 拥有主界面的批次操作和常用参数分组；批次、输出、排版和标签参数
  使用同一层级，并提供持久化的“打开最近生成的批次”快捷入口；批次顺序标注仍受开发者模式控制。
  `ui/workbench/overview/`按界面区域分别拥有快捷标签、批次数据、预览和信号联动；进入时默认展示
  不解码缩略图的整批订单结构图，按单件尺码群、双面尺码群和多件订单尺码群显示真实排版坐标；
  用户可切换到当前订单真实图片，刀码示意不代替真实坐标预览。
- `ui/current_film.py` 的当前膜卡片可直接修改膜规格、排版模式和自定义膜宽，修改结果与打印参数设置使用同一数据源。
- `ui/parameter_refresh.py` 统一抑制开发者模式和平台默认值联动期间的预览请求；参数更新后
  保留明确提示，只有用户重新启动排版才会读取批次。应用重启由 `restart_control.py` 统一拥有，
  源码更新和恢复出厂设置共用同一启动策略。
- 单批次生成控制：`automatic_print/controllers/layout_generation.py` 独立拥有工作线程、Worker信号接线、
  取消和释放；`controllers/generation_progress.py` 提供纯进度计算。界面启动、实时进度和最终结果分别位于
  `ui/workbench/generation/start.py`、`progress.py`和`results.py`；`ui/generation_actions.py`与
  `ui/thread_lifecycle.py`仅保留旧调用方兼容导入。
- 单批生成、仅预览及批量分析的每个批次均由 `layout_engine/measurement_session.py` 建立一份数据
  快照；DPI、尺寸、膜标签位置和各方向刀码占位在后续方案与报告中直接复用。
- 生成完成弹窗由 `layout_engine/output_file_info.py` 汇总最终生产结果；膜规格表把当前膜行替换为
  同一最终计划的真实统计，输出名由 `layout_engine/output_name.py` 同时写入订单数和件数。
- `layout_engine/output_name.py` 统一管理输出落点：生成期间写入 `排版日志/.处理中` 隔离目录，
  安全检查完成后把最终PNG扁平移入 `切膜机文件`；文本报告保存在平级 `排版日志`，不写输出JSON。
- 多批次生成控制：`automatic_print/controllers/bulk_generation.py` 管理线程、取消和释放；
  `ui/bulk_workbench.py`、`bulk_generation_worker.py`、`batch_status_board.py`分别负责展示编排、任务执行和状态视图。
  主界面以一个“开始排版”入口统一处理
  单批次目录和多批次上级目录，批次扫描结果决定实际队列数量。

## 排版核心

- 公共门面：`automatic_print/layout.py`。
- 完整生成服务：`automatic_print/layout_engine/service.py`。
- 文件发现与元数据：`discovery.py`、`batch_discovery.py`、`source_metadata.py`、
  `output_dpi.py`。`item_reader.py`只负责一次读取尺寸、DPI、旋转候选和膜标签检测，
  `item_factory.py`只把测量结果组装为单张排版对象。
- S2B 文件夹批次号解析、中心批次查询及本地图片颜色匹配位于
  `automation/api/s2b/metadata/`，生产批次列表和导出下载位于`production/`；只要识别到 S2B 批次，预览和生成都会在排版前查询一次订单颜色并按本地
  路径缓存，不依赖开发者模式或手动平台选择。服务不可用或任一图片颜色未匹配时保留本地信息继续
  排版，在预览、报告和完成确认中显示诊断，由用户选择是否采用结果；文件名不能识别订单时，以批次目录内的订单文件夹作唯一匹配回退，并把接口订单身份
  写回共享订单归组。中心地址随应用提供，正式 Windows 构建从 GitHub Secret
  `AUTOMATIC_PRINT_S2B_BATCH_INFO_KEY` 注入受限客户端密钥；源码树只保留空占位，
  Supabase service-role 和 S2B 登录凭据都不下发到生产电脑。
- 订单、双面、颜色与尺码：`order_groups.py`、`batch_analysis.py`、
  `single_order_sequence.py`、`color_policy.py`、`size_policy.py`。
- 行、刀位和区域规划：`planner.py`、`row_optimizer.py`、`cutter_planner.py`、`dynamic_columns.py`、
  `knife_optimizer.py`、`adaptive_knife.py`、`zone_optimizer.py`、`rotation_zones.py`。列数由膜宽与真实占位
  动态形成，`adaptive_knife.py` 唯一组装“并排区 + 剩余旋转区”，旋转仍超宽时复用 `width_fit.py` 缩小缓存。
  混色订单不参与单色区域边界比较，避免错误清空已经成立的多数并排区。
- 主界面默认开启的 S–L 并排宽度上限由 `layout_engine/pair_width.py` 唯一计算；通过单图尺寸覆盖交给既有
  测量、刀位、预览和渲染链路，不生成或修改源图片副本。
- 旋转与超宽恢复：`rotation_compare.py`、`whole_rotation.py`、`tail_rotation.py`、
  `single_rotation.py`、`width_fit.py`、`gap_fallback.py`。
  旋转区的竖图保持横向旋转，超出当前动态安全宽度时再等比缩小；整批旋转被个别超宽图阻断时，
  `gap_fallback.py` 用虚拟尺寸覆盖重跑完整订单局部比较，双面同倍率且整批仍最多只有并排区和旋转区两个区域。
- 标签与刀码：`labels.py`、`dynamic_label.py`、`marker_stack.py`、`left_marker.py`、
  `platform_label.py`、`header_region.py`、`transparent_search.py`。平台文字只放入原图二维码卡片的
  已验证透明空位，预览与输出复用同一坐标；普通标签和平台文字都在旋转后的膜标签高度带内搜索
  图片自身的透明空位并互相避让，外置刀码紧贴图片边缘；找不到安全范围或最终坐标越界时禁止输出，
  不能回退到刀码与二维码之间或膜标签与图案之间。
- 标签字体加载与线程内有界缓存由`layout_engine/text/fonts.py`唯一拥有；`labels.py`只负责标签内容、
  换行和徽标渲染。单图排版对象`LayoutItem`与`Placement`统一归`layout_engine/models.py`。
- 渲染与编码：`pillow_renderer.py`、`vips_renderer.py`、`png_codecs/`、
  `segmented_output.py`、`atomic_png.py`、`atomic_tiff.py`。超长 PNG 由 `png_codecs/row_stream.py`
  按排版行依次解码、合成、固定 UP 滤波、压缩和写入，每行只求值一次且不生成中间图片；PNG 保存后由
  独立读取器一次顺序解压，同时核对全部刀位的全长实际 alpha 像素、
  数据块 CRC、尺寸、RGBA 格式和像素行完整性；不再为每条刀位重复触发超长延迟画布合成，
  也不依赖 libvips 二次打开大图，
  避免超长PNG二次解码触发原生库崩溃。保存计时包含 libvips 延迟合成、编码与写入，不能解释成纯磁盘耗时。多个 Python
  工作线程的 libvips 外层延迟任务由共享门禁协调，原生库内部仍保留并行，并在正常退出时完成清理。
  开发者模式可选择并行分块 BigTIFF：画布按整幅宽度的固定高度 Strip 有界生成，tifffile/imagecodecs 多线程压缩，
  单一写入器登记块偏移；普通模式始终回到 PNG。
- 输出安全：`order_validation.py`、`cut_validation.py`、
  `marked_pixel_validation.py`、`printed_guides.py`、`output_file_info.py`。
- 膜方案与统计：`film_comparison.py` 直接复用当前实际输出行并并行计算其余方案；`film_specs.py`、`metrics.py`、
  `operation_timing.py`、`algorithm_costs.py`。
- 缓存：`plan_cache.py`、`normal_plan_cache.py`、`cached_planner.py`；单图测量由
  `measurement_cache.py` 持久化，并由 `measurement_session.py` 在任务内共享连接；
  `cutter_measurements.py` 保存本批正常/旋转刀码几何，生产方案、整批旋转和膜规格比较直接复用。
  单图缓存24小时，重新组批、膜宽变化和普通版本更新不触发源图重新测量。

## UI 与本地数据

- 设置界面的读取、保存与用户动作分别位于`ui/workbench/preferences/load.py`、`save.py`和
  `actions.py`；根目录`preferences.py`、`preference_actions.py`仅保留兼容导入，自动保存仍由
  `preference_autosave.py`节流，排版参数快照由`layout_values.py`生成。
- 批次构成：`ui/batch_distribution.py` 在单批和多批真实预览上方显示当前批次的紧凑尺码群或订单群；
  膜规格比较表不再承载该信息。
- 进度、停止和线程生命周期：`ui/busy_spinner.py`、`layout_activity.py`、
  `operation_timing.py`、`stop_actions.py`、`thread_lifecycle.py`、`worker_bridge.py`。
- 保存耗时：`layout_engine/save_progress.py`记录首批PNG数据、持续文件增长、编码收尾和原子发布；
  `atomic_png.py`与输出报告复用该事实，不把libvips重叠流水线伪装成互斥CPU步骤。流式PNG完成后，
  `cut_validation.py`把全部区域刀位映射到一个连续窄条需求图，一次从上到下复核真实输出像素；失败文件
  仍改名为“禁止打印”，同时避免保存前重复求值整幅延迟画布。
- 预览：`ui/production_preview.py`、`preview_*`、`pair_preview.py`、
  `marker_examples.py` 及 `marker_example_*`。`layout_engine/preview_result.py` 形成不落地打印图片的
  完整报告数据，`ui/batch_summary.py` 显示可复制的刀位、单排原因和耗时报告。
- 错误诊断：`ui/failure_panel.py`、`failure_dialog.py`、
  `layout_engine/error_context.py`、`error_parameters.py`。
- 历史记录：`automatic_print/history/`；最近成功输出路径由 `history/recent_output.py` 持久化，
  UI只负责按钮状态和打开目录；Qt 参数使用 `QSettings`。
- 更新：`automatic_print/updates/`、`updater.py`、`restart_control.py`。

## 外部自动化

- `automatic_print/automation/` 保存浏览器、下载和旧批次流程，目前不是主工作台优先路径；
  蜂鸟ERP页面桥接、生产项、生产批次和响应转换分别归档在`automation/api/erp/`，
  根目录`erp_api.py`只保留旧调用方兼容导入。
- ERP生产批次读取兼容顶层表格与工厂外壳中的`fnsz-sale`内嵌表格；莆田从首页“生产 / 批量生产”进入后可复用同一列表、搜索和下载通路。
- 蜂鸟ERP原始批次行到中立`BatchRecord`的转换集中在`automation/api/erp/records.py`，浏览器模块只负责页面与请求流程。
- “生产平台下载”作为主工作台独立页签，仅随开发者模式显示；支持多选已配置平台，每个平台独立显示批次、下载进度和日志。隆丰、莆田和Haloo复用蜂鸟ERP通路；S2B复用专用浏览器登录，由`automation/api/s2b/production.py`读取生产批次并在用户选择后补发生产图导出，由`downloads.py`轮询导出记录、读取`download_url`、下载到`S2B/ARCHIVES`并安全解压到`S2B/BATCHES`。下载流程不触发排版，也不自动创建生产批次。
- “莆田”本地排版入口由`ui/developer_mode.py`控制，仅在开发者模式加入平台选择；`ui/print_settings_navigation.py`集中应用40毫米膜标签间距默认值。
- 该目录仍以功能和平铺平台文件混合组织，尚未达到
  `automation/api/<provider>/` 的目标边界。新增平台代码必须进入提供商子包；迁移旧代码时保留
  公共兼容门面并删除活跃重复。

## 已知结构债务

- 以下遗留文件超过200行，测试已冻结当前上限；后续涉及其职责的修改应缩小而非增长：

| 归属 | 遗留文件 | 后续收敛方向 |
| --- | --- | --- |
| 排版核心 | `layout_engine/service.py`, `planner.py` | 服务只编排阶段；测量、候选和对象构造已有独立所有者。 |

- 部分 README 内容曾混入版本演进描述；当前规则以四份治理文档为准，README 仅保留使用和发布入口。
