"""Readable two-surface layout for fleet state and low-frequency controls."""

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget


def build_machine_status_layout(page, title, description, overview):
    sections = QTabWidget(page)
    status_page = QWidget()
    status_layout = QVBoxLayout(status_page)
    status_layout.setContentsMargins(0, 8, 0, 0)
    status_layout.addWidget(overview)
    status_layout.addWidget(page.table, 1)

    control_page = QWidget()
    control_layout = QVBoxLayout(control_page)
    control_layout.setContentsMargins(0, 8, 0, 0)
    control_layout.addWidget(page.availability_control)
    control_layout.addWidget(page.control_panel)
    control_layout.addWidget(page.command_panel)
    control_layout.addStretch()

    sections.addTab(status_page, "11 台机器状态")
    sections.addTab(control_page, "控制与任务")
    layout = QVBoxLayout(page)
    layout.addWidget(title)
    layout.addWidget(description)
    layout.addWidget(sections, 1)
    page.sections = sections
    page.status_section = status_page
    page.control_section = control_page
