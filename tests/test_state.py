from plaud_brain.state import ProcessedStore


def test_mark_and_has(tmp_path):
    store = ProcessedStore(tmp_path / "state" / "processed.json")
    assert store.has("cloud:1") is False
    store.mark("cloud:1", source="cloud", note_path="/v/n.md", title="Hi")
    assert store.has("cloud:1") is True
    assert store.get("cloud:1")["title"] == "Hi"


def test_persisted_across_instances(tmp_path):
    path = tmp_path / "processed.json"
    ProcessedStore(path).mark("usb:abc", source="usb", note_path="/v/a.md", title="A")
    reopened = ProcessedStore(path)
    assert reopened.has("usb:abc") is True
    assert reopened.entries["usb:abc"]["source"] == "usb"


def test_forget(tmp_path):
    store = ProcessedStore(tmp_path / "processed.json")
    store.mark("cloud:1", source="cloud", note_path="x", title="t")
    assert store.forget("cloud:1") is True
    assert store.has("cloud:1") is False
    assert store.forget("cloud:1") is False


def test_corrupt_file_is_ignored(tmp_path):
    path = tmp_path / "processed.json"
    path.write_text("not json {{{")
    store = ProcessedStore(path)
    assert store.entries == {}
