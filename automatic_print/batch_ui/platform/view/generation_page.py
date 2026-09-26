"""One production-platform tab for batch previews and generation."""

from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout,
    QLabel, QPushButton, QTabWidget, QVBoxLayout, QWidget,
)

from ..completed import CompletedErpPage
from .pages import build_generation_page, table_widget
from .route_view import build_route_page
from ..s2b.preview import S2BPreviewPage


def build_accepted_page(owner) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    intro = QLabel(
        "显示已经接单但尚未进入生产中的订单。"
        "批次生成功能只在这个区域。"
    )
    intro.setWordWrap(True)
    owner.accepted_summary = QLabel("尚未读取待生产订单数量。")
    owner.accepted_table = table_widget(
        ["订单号", "物流", "项目", "件数", "接单时间", "操作"]
    )
    layout.addWidget(intro)
    layout.addWidget(owner.accepted_summary)
    layout.addWidget(owner.accepted_table)
    layout.addWidget(QLabel("批次生成"))
    layout.addWidget(build_generation_page(owner))
    return page


def build_batch_generation_page(owner, platform_name: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    owner.open_playwright_button = QPushButton(
        f"打开 {platform_name} Playwright 浏览器"
    )
    owner.open_playwright_button.setToolTip(
        f"立即启动或显示 {platform_name} 自动化 Chrome；登录后再读取批次预览。"
    )
    owner.open_playwright_button.clicked.connect(owner.open_playwright_browser)
    layout.addWidget(owner.open_playwright_button)
    sections = QTabWidget()
    received = QWidget()
    received_layout = QVBoxLayout(received)
    if platform_name == "隆丰":
        received_layout.addWidget(build_route_page(owner))
    received_layout.addWidget(build_generation_page(owner))
    received_layout.addStretch()
    sections.addTab(received, "已接单筛选预览")
    owner.completed_page = CompletedErpPage(owner, platform_name)
    sections.addTab(owner.completed_page, "生产中批次策略")
    layout.addWidget(sections)
    owner.generation_sections = sections
    return page


def build_s2b_strategy_page(owner) -> QWidget:
    page = S2BPreviewPage(owner)
    owner.s2b_preview_page = page
    owner.s2b_strategy_editor = page.strategy_editor
    return page


def ask_generation_rule(owner, plan) -> str | None:
    details = "\n".join(
        f"{item.shipping_method} / {item.order_composition}："
        f"{item.item_count} 项、{item.piece_count} 件"
        for item in plan.nonempty_items
    )
    dialog = QDialog(owner)
    dialog.setWindowTitle("最终确认：生成后无法撤销")
    description = QLabel(
        f"平台：{plan.platform_name}\n\n{details}\n\n"
        f"生成：{plan.total_items} 项"
    )
    rule = QComboBox()
    rule.addItems(["按有面单生成批次规则", "按无面单生成批次规则"])
    form = QFormLayout()
    form.addRow("批次生成规则", rule)
    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setText("确认并生成（不可撤销）")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout = QVBoxLayout(dialog)
    layout.addWidget(description)
    layout.addLayout(form)
    layout.addWidget(buttons)
    return rule.currentText() if dialog.exec() == QDialog.Accepted else None
