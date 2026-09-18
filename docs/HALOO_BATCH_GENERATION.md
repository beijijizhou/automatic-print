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
- 单项单件先按`style_id`选择快照内数量最多的底款，再分黑色/白色、正面/反面/双面、
  `S/M/L/XL`与`XXL(2XL)/3XL/4XL/5XL`两档。单项多件和多项多件先按物流，
  再按订单组成和整单面别分组。

## 生成方法与副作用门禁

- 页面“生成批次”的筛选模式调用
  `POST /production/v1/production/batch/global_generate_batch`；筛选请求使用
  `batch_creat_type: 1`。
- 精确选择生产项时同一接口使用`production_order_item_ids`、`batch_creat_type: 2`和
  `batch_rule_id`。当前接口没有`dry_run`、`preview`或“不改变状态”参数。
- 已生产记录均带原`production_batch_code`。重新提交必然形成重复批次关系；页面代码和响应契约
  没有证明状态`9`不会回到生产中、不会改变队列或原批次关系。因此
  `completed_batch_request()`默认拒绝构造可提交请求，只有外部已证明非重开语义时才能显式解锁。
- 防重顺序：固定状态`9`；读取实际面别；保留来源批次号；按整单分组；提交前重新读取状态、
  来源批次和项目集合；任何变化均停止。API结果不确定时不得自动重试，先查批次页。

## 当前验证

只读读取最新30个已生产项并逐项查询生产图详情，成功形成11个候选组，覆盖`USPS`、`GOFO`、
`SWIF`、`SPEE`、`YANW`、正面、反面、混合面别、黑白、两档尺码和多项多件。所有候选均已有
来源批次号，因此未调用写接口，也没有新批次号。

## 界面入口与当前限制

开发者模式 → 生产平台下载 → Haloo → 已生产分类预览。默认读取30项，可选择1–200项；读取由后台任务执行，显示实际面别、来源批次、生产项ID及未纳入数量。改变样本范围会清空旧结果。

当前快照只读第一页，不能保证跨页订单完整。界面不提供生成提交按钮；候选分组不等于可提交批次。仅含多件的快照不再要求存在单件底款。未识别面别或物流缺失在预览中明确展示，不能视为已验证分类。
