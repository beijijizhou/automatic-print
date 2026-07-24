from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)


def _table(headers: list[str], stretch: int | None = None):
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
    owner.generation_table = _table(
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


def build_accepted_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "显示已经接单但尚未进入生产中的订单。"
        "批次生成功能只在这个区域。"
    )
    intro.setWordWrap(True)
    owner.accepted_summary = QLabel("尚未读取待生产订单数量。")
    owner.accepted_table = _table(
        ["订单号", "物流", "项目", "件数", "接单时间", "操作"]
    )
    layout.addWidget(intro)
    layout.addWidget(owner.accepted_summary)
    layout.addWidget(owner.accepted_table)
    layout.addWidget(QLabel("批次生成"))
    layout.addWidget(build_generation_page(owner))
    return page


def build_production_page(owner, output_row: QHBoxLayout) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "查看已经生成且正在生产的批次，并下载生产图。"
        "下载完成后自动解压和排版。"
    )
    intro.setWordWrap(True)
    owner.summary = QLabel("尚未读取已生成批次。")
    owner.range_start = QLineEdit()
    owner.range_start.setPlaceholderText("起始批次号")
    owner.range_end = QLineEdit()
    owner.range_end.setPlaceholderText("结束批次号")
    owner.range_button = QPushButton("读取并选择范围")
    owner.range_button.clicked.connect(owner.load_batch_range)
    range_row = QHBoxLayout()
    range_row.addWidget(owner.range_start)
    range_row.addWidget(QLabel("至"))
    range_row.addWidget(owner.range_end)
    range_row.addWidget(owner.range_button)
    owner.table = _table(
        ["选择", "批次号", "项目", "件数", "类型", "创建时间", "生产图"],
        5,
    )
    owner.refresh_button = QPushButton("刷新批次")
    owner.refresh_button.clicked.connect(owner.refresh_current_section)
    owner.select_button = QPushButton("全选可下载批次")
    owner.select_button.clicked.connect(owner.select_all_ready)
    owner.download_button = QPushButton("一键下载并自动排版")
    owner.download_button.clicked.connect(owner.download_selected)
    owner.process_button = QPushButton("重新排版已下载批次")
    owner.process_button.clicked.connect(owner.process_batches)
    actions = QHBoxLayout()
    for button in (
        owner.refresh_button,
        owner.select_button,
        owner.download_button,
        owner.process_button,
    ):
        actions.addWidget(button)
    owner.test_mode = QCheckBox("快速测试：第一个批次只处理前 5 张")
    owner.test_mode.setChecked(True)
    owner.log = QPlainTextEdit()
    owner.log.setReadOnly(True)
    layout.addWidget(intro)
    layout.addWidget(QLabel("下载保存位置"))
    layout.addLayout(output_row)
    layout.addWidget(owner.summary)
    layout.addLayout(range_row)
    layout.addWidget(owner.table)
    layout.addWidget(owner.test_mode)
    layout.addLayout(actions)
    layout.addWidget(owner.log)
    return page


def build_cleared_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel("该平台所有生产项目均已完成的订单会显示在这里。")
    intro.setWordWrap(True)
    owner.cleared_summary = QLabel("尚未读取生产中数量。")
    owner.cleared_table = _table(
        ["订单号", "物流", "项目", "件数", "完成时间", "状态"]
    )
    layout.addWidget(intro)
    layout.addWidget(owner.cleared_summary)
    layout.addWidget(owner.cleared_table)
    return page


def build_local_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "显示已经下载并解压到本机的生产批次。"
        "刷新和排版只读取本地硬盘，不访问生产平台。"
    )
    intro.setWordWrap(True)
    owner.local_summary = QLabel("尚未读取本地生产批次。")
    owner.local_table = _table(
        ["选择", "平台", "批次号", "图片数", "本地更新时间", "文件夹"],
        5,
    )
    owner.local_refresh_button = QPushButton("刷新本地文件")
    owner.local_refresh_button.clicked.connect(owner.refresh_local_batches)
    owner.local_select_button = QPushButton("全选本地批次")
    owner.local_select_button.clicked.connect(owner.select_all_local)
    owner.local_process_button = QPushButton("排版选中的本地批次")
    owner.local_process_button.clicked.connect(
        owner.process_selected_local_batches
    )
    owner.local_open_button = QPushButton("打开本地文件夹")
    owner.local_open_button.clicked.connect(owner.open_local_folder)
    actions = QHBoxLayout()
    for button in (
        owner.local_refresh_button,
        owner.local_select_button,
        owner.local_process_button,
        owner.local_open_button,
    ):
        actions.addWidget(button)
    owner.local_test_mode = QCheckBox("快速测试：第一个批次只处理前 5 张")
    owner.local_test_mode.setChecked(True)
    layout.addWidget(intro)
    layout.addWidget(owner.local_summary)
    layout.addWidget(owner.local_table)
    layout.addWidget(owner.local_test_mode)
    layout.addLayout(actions)
    return page
