from pathlib import Path
from automatic_print.layout_engine.error_context import error_context


def test_named_file_identifies_whole_order_and_both_faces():
    paths=[Path('/source/A00001-B123-1-T-Black-M-NO1-1.png'),
           Path('/source/A00002-B123-1-T-Black-M-NO1-2.png'),
           Path('/source/B456-1-T-White-M-NO1-1.png')]
    text=error_context(paths[0].name+'：膜宽不足',paths,'/source','刀位计算')
    assert '订单 B123 · 2 张' in text
    assert paths[1].name in text
    assert 'B456' not in text
    assert '失败步骤：刀位计算' in text


def test_global_failure_does_not_blame_arbitrary_order():
    paths=[Path('/source/B123-1.png'),Path('/source/B456-1.png')]
    text=error_context('整批刀位不存在',paths,'/source')
    assert '无法归因于单一订单' in text
    assert '订单 B123' in text and '订单 B456' in text
    assert error_context(text,paths)==text


def test_dialog_copy_is_complete_and_does_not_close(monkeypatch):
    from test_developer_mode import APP
    from PySide6.QtWidgets import QDialog,QPushButton,QPlainTextEdit
    from automatic_print.ui.failure_dialog import show_failure_dialog
    message='失败原因：膜宽不足\n订单 B123\n文件：test.png'
    def execute(dialog):
        assert dialog.findChild(QPlainTextEdit).toPlainText()==message
        button=next(b for b in dialog.findChildren(QPushButton) if '复制' in b.text())
        button.click()
        assert APP.clipboard().text()==message
        return 0
    monkeypatch.setattr(QDialog,'exec',execute)
    show_failure_dialog(None,message)


def test_error_contains_header_pixels_dpi_and_limits(tmp_path):
    from PIL import Image
    from automatic_print.layout import LayoutSettings
    path=tmp_path/'B123-1-T-Black-M-NO1-1.png'
    with Image.new('RGBA',(1000,500)) as image:
        image.save(path,dpi=(100,100))
    text=error_context('膜宽不足',[path],tmp_path,settings=LayoutSettings(media_width_mm=430,dpi=150))
    assert '1000×500 像素' in text
    assert '原DPI' in text and '原画布打印尺寸 254.' in text
    assert '膜宽 450 毫米' in text and '可打印宽度 430 毫米' in text


def test_actual_choice_width_failure_is_quantified(tmp_path):
    from PIL import Image
    from automatic_print.layout import LayoutSettings,generate_layout
    import pytest
    path=tmp_path/'B123-1-T-Black-M-NO1-1.png'
    with Image.new('RGBA',(200,100)) as image:
        image.save(path,dpi=(25.4,25.4))
    with pytest.raises(ValueError) as error:
        generate_layout([path],tmp_path/'out',LayoutSettings(dpi=25.4,media_width_mm=150,
            allow_rotation=False,number_images=False,color_block_enabled=False))
    text=str(error.value)
    assert '需要宽度 200.00 毫米，允许 150.00 毫米，超出 50.00 毫米' in text
    assert '实际输出DPI 25.4' in text
