"""Build production-platform batch pages and shared table controls."""

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
def editable_batch_combo(placeholder: str) -> QComboBox:
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.NoInsert)
    combo.lineEdit().setPlaceholderText(placeholder)
    combo.setToolTip("可从已读取的批次中选择，也可粘贴或复制批次号。")
    return combo
def table_widget(headers: list[str], stretch: int | None = None):
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeToContents
    )
    if stretch is not None:
        table.horizontalHeader().setSectionResizeMode(
            stretch, QHeaderView.Stretch
        )
    return table


def build_generation_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "从已接单、尚未进入生产中的订单生成生产批次。"
        "最终确认后才生成，批次生成后无法撤销。"
    )
    intro.setWordWrap(True)
    owner.batch_rule_summary = QLabel()
    owner.batch_rule_summary.setWordWrap(True)
    owner.batch_rule_summary.setStyleSheet(
        "padding:8px;background:#eef4ff;border:1px solid #9bbcff;"
        "font-weight:600;"
    )
    owner.generation_table = table_widget(
        ["物流分类", "项目", "件数", "订单组成", "操作状态"]
    )
    owner.preview_rules_button = QPushButton("读取分类数量")
    owner.preview_rules_button.clicked.connect(
        owner.preview_generation_rules
    )
    owner.generate_rules_button = QPushButton("确认并生成批次")
    owner.generate_rules_button.setEnabled(False)
    owner.generate_rules_button.clicked.connect(
        owner.confirm_generate_rules
    )
    actions = QHBoxLayout()
    actions.addWidget(owner.preview_rules_button)
    actions.addWidget(owner.generate_rules_button)
    owner.generation_warning = QLabel(
        "安全保护：生成前显示平台、物流和订单组成数量，并最终确认。"
    )
    owner.generation_warning.setWordWrap(True)
    for widget in (
        intro,
        owner.batch_rule_summary,
        owner.generation_table,
    ):
        layout.addWidget(widget)
    layout.addLayout(actions)
    layout.addWidget(owner.generation_warning)
    return page


def build_production_page(owner, output_row: QHBoxLayout) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "选择已经生成的生产批次，可在本机继续排版并由RIIN生成PRN，"
        "或发送到指定在线机器完成下载、排版和PRN。不会启动物理打印。"
        if getattr(owner, "download_only", False)
        else "查看已经生成且正在生产的批次，并下载生产图。"
             "下载完成后仅解压；请手动启动排版。"
    )
    intro.setWordWrap(True)
    owner.summary = QLabel("尚未读取已生成批次。")
    owner.range_start = editable_batch_combo("选择或粘贴起始批次号")
    owner.range_end = editable_batch_combo("选择或粘贴结束批次号")
    owner.range_button = QPushButton("读取并选择范围")
    owner.range_button.clicked.connect(owner.load_batch_range)
    range_row = QHBoxLayout()
    range_row.addWidget(owner.range_start)
    owner.range_separator = QLabel("至")
    range_row.addWidget(owner.range_separator)
    range_row.addWidget(owner.range_end)
    range_row.addWidget(owner.range_button)
    owner.table = table_widget(
        ["选择", "批次号", "项目", "件数", "类型", "生成批次时间", "生产图"],
        5,
    )
    owner.refresh_button = QPushButton("刷新批次")
    owner.refresh_button.clicked.connect(owner.refresh_batches)
    owner.select_button = QPushButton("全选可下载批次")
    owner.select_button.clicked.connect(owner.select_all_ready)
    owner.download_button = QPushButton("下载并解压")
    owner.download_button.clicked.connect(owner.download_selected)
    owner.automated_print_button = QPushButton("下载、排版并生成打印文件")
    owner.automated_print_button.clicked.connect(owner.download_and_print_selected)
    owner.automated_print_button.setToolTip(
        "按当前打印参数生成最终PNG，再逐批交给RIIN生成PRN并加入PrinterExp；"
        "不会启动物理打印。"
    )
    owner.remote_dispatch_button = QPushButton("发送到指定机器生成 PRN")
    owner.remote_dispatch_button.clicked.connect(owner.dispatch_selected_to_machine)
    owner.remote_dispatch_button.setToolTip(
        "把当前勾选批次和当前排版参数发送给指定在线机器；目标机负责下载、"
        "排版、生成PRN并加载PrintExp，不会启动物理打印。"
    )
    owner.remote_dispatch_status = QLabel(
        "可将当前勾选批次发送到指定在线机器，从下载连续执行到 PRN。"
    )
    owner.remote_dispatch_status.setWordWrap(True)
    from ..remote_dispatch import RemoteBatchDispatcher
    owner.remote_batch_dispatcher = RemoteBatchDispatcher(owner)
    owner.open_download_folder = QCheckBox("下载完成后打开文件夹")
    owner.open_download_folder.setChecked(True)
    owner.process_button = QPushButton("重新排版已下载批次")
    owner.process_button.clicked.connect(owner.process_batches)
    actions = QHBoxLayout()
    action_buttons = [owner.refresh_button]
    if not getattr(owner, "download_only", False):
        action_buttons.extend((owner.select_button, owner.download_button))
    action_buttons.extend((owner.automated_print_button, owner.remote_dispatch_button))
    if not getattr(owner, "download_only", False):
        action_buttons.append(owner.process_button)
    for button in action_buttons:
        actions.addWidget(button)
    owner.test_mode = QCheckBox(
        "快速测试：普通模式首批 5 张；合并模式每批 5 张"
    )
    owner.test_mode.setChecked(not getattr(owner, "download_only", False))
    owner.test_mode.setEnabled(not getattr(owner, "download_only", False))
    owner.download_preview_only = QCheckBox(
        "仅计算排版数据，不生成最终大图"
    )
    owner.download_preview_only.setChecked(
        bool(getattr(owner, "download_only", False))
    )
    owner.download_preview_only.setEnabled(
        not getattr(owner, "download_only", False)
    )
    owner.merge_batches = QCheckBox("合并选中的批次为一个排版文件")
    if tuple(getattr(owner, "platform_names", ())) == ("S2B",):
        for control in (owner.range_start, owner.range_separator,
                        owner.range_end, owner.range_button):
            control.hide()
    if getattr(owner, "download_only", False):
        for control in (
            owner.select_button,
            owner.download_button,
            owner.open_download_folder,
            owner.process_button,
            owner.test_mode,
            owner.download_preview_only,
            owner.merge_batches,
        ):
            control.hide()
    else:
        owner.automated_print_button.hide()
    if not hasattr(owner, "log"):
        owner.log = QPlainTextEdit()
        owner.log.setReadOnly(True)
    layout.addWidget(intro)
    if not getattr(owner, "local_only", False):
        layout.addWidget(QLabel("下载保存位置"))
        layout.addLayout(output_row)
    layout.addWidget(owner.summary)
    layout.addLayout(range_row)
    layout.addWidget(owner.table)
    layout.addWidget(owner.test_mode)
    layout.addWidget(owner.download_preview_only)
    layout.addWidget(owner.merge_batches)
    layout.addLayout(actions)
    layout.addWidget(owner.remote_dispatch_status)
    if not getattr(owner, "local_only", False):
        layout.addWidget(owner.log)
    return page
