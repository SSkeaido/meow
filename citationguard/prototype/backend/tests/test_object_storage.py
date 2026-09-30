from app.services.object_storage import ObjectStorage


def test_local_object_storage_persists_bytes(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OBJECT_STORAGE_PROVIDER", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    storage = ObjectStorage()

    uri = storage.save(b"%PDF fixture", "papers/project-1/paper.pdf")

    assert uri == str(tmp_path / "papers/project-1/paper.pdf")
    assert (tmp_path / "papers/project-1/paper.pdf").read_bytes() == b"%PDF fixture"
