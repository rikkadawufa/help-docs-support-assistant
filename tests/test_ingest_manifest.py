from app.config import Settings
from app.ingest import plan_sync, sync


def test_plan_sync_sorts_files_into_four_groups():
    disk = {"a.md": "1", "b.md": "2-new", "c.md": "3"}
    manifest = {"a.md": "1", "b.md": "2-old", "gone.md": "9"}
    r = plan_sync(disk, manifest)
    assert r.unchanged == ["a.md"]
    assert r.updated == ["b.md"]
    assert r.added == ["c.md"]
    assert r.removed == ["gone.md"]


def test_sync_only_touches_changed_files(tmp_path, monkeypatch):
    import app.config as config
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path / "out")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text("# A\n\n## Hours\nOpen 9 to 5.\n", encoding="utf-8")
    (docs / "b.md").write_text("# B\n\n## Fees\nNo fees.\n", encoding="utf-8")
    settings = Settings(llm_mode="mock")
    # point the index and manifest at tmp_path
    monkeypatch.setattr(Settings, "chroma_dir", property(lambda s: tmp_path / "chroma"))
    monkeypatch.setattr(Settings, "manifest_path", property(lambda s: tmp_path / "manifest.json"))

    first = sync(settings, folder=docs)
    assert sorted(first.added) == ["a.md", "b.md"]

    second = sync(settings, folder=docs)
    assert second.chunks_written == 0 and sorted(second.unchanged) == ["a.md", "b.md"]

    (docs / "b.md").write_text("# B\n\n## Fees\nA $5 fee applies.\n", encoding="utf-8")
    (docs / "a.md").unlink()
    third = sync(settings, folder=docs)
    assert third.updated == ["b.md"] and third.removed == ["a.md"]

    from app.store import open_store
    store = open_store(settings)
    texts = store.get()["documents"]
    assert any("$5 fee" in t for t in texts)
    assert not any("No fees" in t for t in texts)
    assert not any("Open 9 to 5" in t for t in texts)
