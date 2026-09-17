from PIL import Image

from automatic_print.layout_engine import LayoutSettings, generate_layout


def test_s2b_metadata_warning_does_not_block_segmented_output(tmp_path, monkeypatch):
    from automatic_print.automation.api.s2b.metadata import prepare

    calls = []
    def gateway_config():
        calls.append('metadata')
        return '', ''
    monkeypatch.setattr(prepare, 'gateway_config', gateway_config)
    batch = tmp_path/'AS2B_TEST_4_ABCDEFGHIJKL_20260917_010101_test'
    paths = []
    for index, size in enumerate(('S', 'S', 'M', 'M'), 1):
        folder = batch/size
        folder.mkdir(parents=True, exist_ok=True)
        path = folder/f'ABCDEFGHIJKL-{index}-1-ORDER{index}-1-1-1-4-棉-{size}.png'
        Image.new('RGBA', (100, 140), 'blue').save(path, dpi=(25.4, 25.4))
        paths.append(path)

    payloads = []
    output = tmp_path/'out'
    result = generate_layout(paths, output, LayoutSettings(
        dpi=25.4,
        cutter_mode='dual',
        cutter_auto_knife=True,
        output_parts=2,
        save_parallelism=2,
        save_memory_unlimited=True,
        png_engine='libvips',
        png_streaming=True,
        platform_name='S2B',
    ), plan_ready=payloads.append, batch_name=batch.name)

    assert len(payloads) == 1
    assert payloads[0]['blocking_warning'] == ''
    assert '订单颜色服务尚未配置' in payloads[0]['metadata_warning']
    assert payloads[0]['metadata_warning'] in payloads[0]['warning']
    assert result['segment_count'] == 2
    assert result['actual_save_parallelism'] == 2
    assert result['save_execution'] == '独立进程并行'
    assert all((output/name).is_file() for name in result['files'])
    assert calls == ['metadata']
    warning = result['analysis']['s2b_metadata'][0]['warning']
    assert '已保留本地订单信息继续排版' in warning
