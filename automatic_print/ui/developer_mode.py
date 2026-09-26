"""Gate diagnostic entry points without changing production parameters."""
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)
from .full_test_runner import install_full_test_control

EXPERIMENTAL_PLATFORMS = ('莆田',)

DEVELOPER_FEATURES = (
    ('诊断与记录', (
        ('完整测试', '运行完整自动测试和本机真实批次跨平台回归，不生成PRN'),
        ('排版历史', '查看历史批次的膜方案、面积、占位率和耗时'),
        ('批量分析文件夹', '比较多个批次的用膜数据，不生成打印文件'),
        ('标签位置安全短测', '用小样本验证外置标签、方向、侧别和刀位安全坐标'),
        ('DTF随机10批冷启动测试', '随机选择10个HL批次，逐批生成并记录每一步及总耗时'),
        ('算法诊断', '查看排版步骤、复杂度和实际耗时'),
        ('整单归侧双排（仅本次任务）', '从测试与诊断菜单勾选本次双列固定刀位任务的整单归侧双排策略'),
    )),
    ('标签与批次资料', (
        ('切膜刀码开关', '关闭后切换为正常排版，再次开启恢复之前的切膜模式'),
        ('平台＋尺码标签开关', '关闭新增平台尺码文字，切膜刀码和原图二维码保持不变'),
        ('批次顺序标注', '显示批次文件夹名、正序和倒序'),
        ('S2B 批次信息查询', '通过共享服务读取颜色、尺码等批次资料'),
    )),
    ('实验平台与输出', (
        ('批次下载与自动化打印', '在生产平台下载中选择批次，下载后排版并由RIIN生成PRN'),
        ('隆丰 ERP 下载', '下载已生成批次并仅计算排版数据'),
        ('S2B 生产图下载', '读取已生成导出记录并下载、校验和解压生产图'),
        ('莆田平台', '显示尚在验证中的莆田本地排版入口'),
        ('并行分块 TIFF', '允许选择实验性的 TIFF 输出格式'),
    )),
)


class DeveloperFeatureListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('开发者模式功能列表')
        self.resize(720, 470)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(('分类 / 功能', '说明', '当前状态'))
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.button(QDialogButtonBox.Close).setText('关闭')
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status)
        layout.addWidget(self.tree)
        layout.addWidget(buttons)

    def refresh(self, enabled):
        state = '已开启' if enabled else '未开启'
        self.status.setText(
            f'开发者模式当前：{state}。以下功能仅在开发者模式开启时可用；'
            '普通生产功能不列在这里。'
        )
        self.tree.clear()
        for category, features in DEVELOPER_FEATURES:
            group = QTreeWidgetItem((category, '', ''))
            self.tree.addTopLevelItem(group)
            for name, description in features:
                group.addChild(QTreeWidgetItem((name, description, state)))
        self.tree.expandAll()


def show_developer_features(window):
    dialog = window.developer_features_dialog
    dialog.refresh(getattr(window, 'developer_mode_enabled', False))
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()


def sync_experimental_platforms(window, enabled):
    canonical = window.label_settings.platform
    quick = window.automation_home.label_quick_panel.platform
    combos = (canonical, quick)
    if enabled:
        for combo in combos:
            for name in EXPERIMENTAL_PLATFORMS:
                if combo.findText(name) < 0:
                    combo.addItem(name)
        return
    if canonical.currentText().strip() in EXPERIMENTAL_PLATFORMS:
        canonical.setCurrentText('隆丰')
    for combo in combos:
        for name in EXPERIMENTAL_PLATFORMS:
            index = combo.findText(name)
            if index >= 0:
                combo.removeItem(index)


def developer_task_active(window):
    details = window.automation_home.label_quick_panel.details_dialog
    dialog = getattr(details, 'bulk_dialog', None)
    production = getattr(details, 'production_bulk_dialog', None)
    erp = getattr(window, 'longfeng_erp_dialog', None)
    benchmark = getattr(details, 'cold_benchmark_dialog', None)
    label_test = getattr(details, 'label_position_test_dialog', None)
    return bool(
        (dialog and dialog.thread is not None)
        or (production and production.thread is not None)
        or (erp and erp.thread is not None)
        or (benchmark and benchmark.is_running())
        or (label_test and label_test.is_running())
        or (getattr(window, 'full_test_controller', None) and window.full_test_controller.is_running())
    )


def bind_developer_tab_visibility(window, tabs, page, index):
    """Keep one developer-only workspace tab synchronized with the mode toggle."""
    def sync(_enabled=False):
        enabled = window.developer_mode_checkbox.isChecked()
        if not enabled and tabs.currentWidget() is page:
            tabs.setCurrentIndex(0)
        tabs.setTabVisible(index, enabled)

    window.developer_mode_checkbox.toggled.connect(sync)
    sync()


def build_developer_mode(window, menu):
    window.developer_features_dialog = DeveloperFeatureListDialog(window)
    feature_list = QPushButton('查看开发者功能')
    feature_list.setToolTip('查看开发者模式额外开放的全部功能。')
    feature_list.clicked.connect(lambda: show_developer_features(window))
    window.developer_features_button = feature_list
    menu.addWidget(feature_list)
    checkbox = QCheckBox('开发者模式')
    checkbox.setToolTip('显示算法开销、排版历史和尚未开放给普通用户的实验排版功能。')
    window.developer_mode_checkbox = checkbox
    checkbox.setChecked(window.preferences.value('developer/enabled', False, bool))
    menu.addWidget(checkbox)
    install_full_test_control(window, menu)

    def changed(enabled):
        if not enabled and developer_task_active(window):
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
            return
        from .parameter_refresh import defer_parameter_refresh
        with defer_parameter_refresh(window):
            window.developer_mode_enabled = enabled
            sync_experimental_platforms(window, enabled)
            cutting = window.cutter_settings.mode.currentData() != 'free'
            window.quick_header_gap_group.setVisible(cutting)
            window.cutter_rules_form.setRowVisible(window.membrane_gap_enabled, cutting)
            window.cutter_rules_form.setRowVisible(window.membrane_gap, cutting)
            window.layout_rules_form.setRowVisible(window.cutter_settings.two_zone, True)
            window.cutter_settings.set_developer_mode(enabled)
            if not enabled:
                window.output_format.setCurrentIndex(max(0, window.output_format.findData('png')))
            window.quick_output_format_group.setVisible(enabled)
            window.output_parallel_form.setRowVisible(window.output_format, enabled)
            panel = window.automation_home.label_quick_panel
            panel.summary.gap_loss.setVisible(True)
            panel.history_button.setVisible(enabled)
            panel.test_tools_button.setVisible(enabled)
            panel.developer_tools_label.setVisible(enabled)
            panel.source_order.setVisible(enabled)
            panel.source_order_control.setVisible(enabled)
            panel.reference_films_label.setVisible(enabled and cutting)
            window.automation_home.batch_tools.setVisible(enabled)
            window.full_test_button.setVisible(enabled)
            window.full_test_result.setVisible(enabled)
            panel.summary.film_table.set_reference_mode(enabled)
            window.label_settings.form.setRowVisible(window.label_settings.source_order, enabled)
            window.cutter_settings.compare_films.setText('比较45/60厘米：常规与旋转（不自动切换）')
            details = panel.details_dialog
            for page in ('algorithm_page', 'history_page'):
                widget = getattr(details, page, None)
                if widget is not None:
                    if not enabled and details.tabs.currentWidget() is widget:
                        details.tabs.setCurrentIndex(0)
                    details.tabs.setTabVisible(details.tabs.indexOf(widget), enabled)
            if not enabled and hasattr(details, 'bulk_dialog'):
                details.bulk_dialog.hide()
            window.preferences.setValue('developer/enabled', enabled)
            window.preferences.sync()

    checkbox.toggled.connect(changed)
    changed(checkbox.isChecked())
    return checkbox
