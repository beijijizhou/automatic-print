from automatic_print.automation.transfer import local_mirror


def files(folder, values):
    folder.mkdir(parents=True, exist_ok=True)
    result = []
    for name, payload in values:
        path = folder / name
        path.write_bytes(payload)
        result.append(path)
    return result


def test_remote_batch_uses_exact_downloaded_mirror(tmp_path, monkeypatch):
    batch = '609182134017'
    source = tmp_path / 'remote' / batch
    originals = files(source, [('one.png', b'111'), ('two.png', b'2222')])
    mirror = tmp_path / 'downloads' / '隆丰' / 'BATCHES' / batch / batch
    local = files(mirror, [('two.png', b'abcd'), ('one.png', b'xyz')])
    monkeypatch.setattr(local_mirror, 'is_remote_path', lambda _path: True)

    selected = local_mirror.prefer_downloaded_batch(
        originals, source, tmp_path / 'downloads', '隆丰')

    assert selected.used
    assert selected.images == (local[1], local[0])
    assert selected.aliases[str(local[1].resolve())] == str(originals[0].resolve())
    assert '2张' in selected.detail and '本地下载副本' in selected.detail


def test_mirror_mismatch_falls_back_to_remote_sources(tmp_path, monkeypatch):
    batch = '609182134017'
    source = tmp_path / 'remote' / batch
    originals = files(source, [('one.png', b'111'), ('two.png', b'2222')])
    mirror = tmp_path / 'downloads' / '隆丰' / 'BATCHES' / batch
    files(mirror, [('one.png', b'wrong-size'), ('two.png', b'2222')])
    monkeypatch.setattr(local_mirror, 'is_remote_path', lambda _path: True)

    selected = local_mirror.prefer_downloaded_batch(
        originals, source, tmp_path / 'downloads', '隆丰')

    assert not selected.used
    assert selected.images == tuple(originals)
    assert not selected.aliases


def test_local_source_never_redirects_to_another_copy(tmp_path, monkeypatch):
    source = tmp_path / '609182134017'
    originals = files(source, [('one.png', b'111')])
    monkeypatch.setattr(local_mirror, 'is_remote_path', lambda _path: False)

    selected = local_mirror.prefer_downloaded_batch(
        originals, source, tmp_path / 'downloads', '隆丰')

    assert not selected.used
    assert selected.images == tuple(originals)
