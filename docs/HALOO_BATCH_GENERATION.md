# Haloo 生产批次生成接口与安全边界

本文记录从已登录 Haloo 生产管理当前页面和已加载前端模块核实的接口事实；不记录
Cookie、Token、用户资料或订单标识。

## 页面与状态

- 生产项页：`/factory/fnsz-sale/produceManage/produceItemsManage`。
- 生产批次页：`/factory/fnsz-sale/produceManage/produceChainManage/productionBatch/index`。
- `GET /production/v1/production/order/item/status` 当前返回：`-1`待接单、`1`已接单、
  `5`生产中、`9`已生产、`-3`已取消。测试数据只允许状态`9`。
- `POST /production/v1/production/order/item/page` 使用JSON请求；主要筛选字段为`status`、
  `order_compositions`、`logistics_sorting_code_list`、`styles.style_sku_ids`、`print_type`、
  `view_count`、分页和排序。响应包含`total`、`page`、`page_size`、`list`、`total_qty`。

## 分类事实

- 订单组成当前枚举：`1`单项单件、`2`单项多件、`3`多项多件；生成计划按`order_id`
  保持整单，不按单个生产项拆散多项订单。
- 物流使用接口实际码，如`USPS`、`GOFO`、`SWIF`、`SPEE`、`YANW`；显示名称不作为请求值。
- `view_count`只能表示设计面数量，不能区分单面的正面与反面。
- `POST /production/v1/production/order/item/production_image`，参数
  `{"production_order_item_id": "..."}`，响应的`production_images[].name`才是规范面别：
  仅`A面`为正面，仅`B面`为反面，同时有`A面`和`B面`为双面；其他值禁止猜测。
- 单项单件先按物流，再按底款`style_id`、颜色、实际面别及尺码档分别分类；
  同底款黑色与白色也生成不同分组。`S/M/L/XL`与`XXL(2XL)/3XL/4XL/5XL`为两档。
  单项多件和多项多件只按物流、订单组成及整单面别分组；不按底款或颜色拆单。

## 生成方法与提交核验

- 页面“生成批次”的筛选模式调用
  `POST /production/v1/production/batch/global_generate_batch`；筛选请求使用
  `batch_creat_type: 1`。
- 精确选择尚未入批次的生产项时，同一接口使用`production_order_item_ids`、
  `batch_creat_type: 2`和`batch_rule_id`；前端会排除已有`production_batch_id`的项目。
- 已经入过批次的已完成订单必须调用
  `POST /production/v1/production/batch/supplement/generate_batch`，请求为
  `item_list: [{item_id, qty}]`与`batch_rule_id`。该补单操作不会改变原订单完成状态。
- 防重顺序：固定状态`9`；读取实际面别；保留来源批次号；按整单分组；提交前重新读取状态、
  来源批次和项目集合；使用`order_id`过滤精确读取整单（复核返回总数），不可只依赖首页快照；
  任何变化均停止。API结果不确定时不得自动重试，先查批次页和项目补单明细。

## 当前验证

真实已完成数据覆盖`USPS`、`GOFO`、`SWIF`、`SPEE`、`YANW`等物流、两种底款、黑白、
正反/双面及多项多件。补单测试验证了同底款黑色件按`GOFO`与`USPS`分别生成、
同订单的黑白两项目共同生成2项2件、另一底款双面件独立生成1项1件、白色单件独立生成。
五组的原订单均保持状态`9`及原批次号，平台补单明细分别指向唯一新批次；下载的图片数
分别为1、1、2、2、1，其中混色整单同订单，双面图片为同一件的两面。五组45厘米本地排版、
RIIN PRN及PrintExp加载均完成，未物理打印。普通精确选择接口对已有批次项目无操作。

## 界面入口与当前限制

开发者模式 → 生产平台下载 → Haloo → 已生产底款分类。默认读取30项，可选择1–200项；读取由后台任务执行，显示底款名称与ID、颜色、实际面别、来源批次、生产项ID及未纳入数量。勾选分组时，下方“待生成清单”立即逐组展示真实底款名称、ID、颜色、物流、面别及件数；确认窗口再次完整列出，确认后才提交。按每组单独生成补单批次；已有补单的组不可勾选。改变样本范围会清空旧结果。

当前快照只读第一页，不能保证跨页订单完整；提交前按订单ID重新读取并校验完整性和来源批次。仅含多件的快照不要求存在单件底款。未识别面别或物流缺失不能视为已验证分类。
