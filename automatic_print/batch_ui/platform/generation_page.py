"""One production-platform tab for batch previews and generation."""

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

from .completed import CompletedErpPage
from .pages import build_generation_page
from .route_view import build_route_page


def build_batch_generation_page(owner, platform_name: str) -> QWidget:
    page = QWidget()
    layout = QVBoxLayout(page)
    sections = QTabWidget()
    received = QWidget()
    received_layout = QVBoxLayout(received)
    if platform_name == "隆丰":
        received_layout.addWidget(build_route_page(owner))
    received_layout.addWidget(build_generation_page(owner))
    received_layout.addStretch()
    sections.addTab(received, "已接单筛选预览")
    owner.completed_page = CompletedErpPage(owner, platform_name)
    sections.addTab(owner.completed_page, "已生产补单计划")
    layout.addWidget(sections)
    owner.generation_sections = sections
    return page
