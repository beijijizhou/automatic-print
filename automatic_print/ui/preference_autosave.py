from PySide6.QtCore import QObject, QTimer


class PreferenceAutosave(QObject):
    """Persist edits without dialogs; flush pending edits before window close."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(300)
        self.timer.timeout.connect(self.flush)
        label, block, cutter = window.label_settings, window.color_block_settings, window.cutter_settings
        signals = [label.settings_changed, block.settings_changed]
        signals += [control.valueChanged for control in (
            window.width, window.spacing, window.margin, window.dpi,
            window.worker_threads, cutter.knife, cutter.safety, cutter.marker_offset,
            cutter.printable.left, cutter.printable.right,
        )]
        signals += [control.currentIndexChanged for control in (
            window.rotation_direction, window.png_compression, window.png_engine,
            cutter.film, cutter.mode,
        )]
        signals += [window.allow_rotation.toggled, cutter.auto_knife.toggled, cutter.rotation_zone.toggled]
        signals += [window.folder.textChanged, window.output_location.textChanged]
        signals += [window.output_beside_source.toggled]
        signals += [cutter.quick_mode.toggled]
        home = window.automation_home
        signals += [home.output.textChanged, home.local_test_mode.toggled, home.local_merge_batches.toggled]
        for signal in signals:
            signal.connect(self.schedule)

    def schedule(self, *_args):
        if not getattr(self.window, 'settings_reset_pending', False):
            self.timer.start()

    def flush(self):
        self.timer.stop()
        if not getattr(self.window, 'settings_reset_pending', False):
            self.window.save_layout_preferences(notify=False)
