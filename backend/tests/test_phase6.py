"""Phase 6: Model Manager, Batch, Harmony API, Video export"""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent))
from test_export import _song, _tab  # noqa: E402,F401
from melotab import models as M  # noqa: E402
from melotab.api.app import create_app  # noqa: E402
from melotab.cache import StageCache  # noqa: E402
from melotab.export import model as EM, video  # noqa: E402
from melotab.store import ProjectStore  # noqa: E402


@pytest.fixture
def client(tmp_path):
    app = create_app(store=ProjectStore(tmp_path / "P"), cache=StageCache(tmp_path / "c"), runner=lambda *a: {}, stats_interval=0.05)
    with TestClient(app) as c:
        yield c, tmp_path


def _pid(c, tmp_path):
    a = tmp_path / "a.wav"
    a.write_bytes(b"RIFF....fake")
    pid = c.post("/projects", json={"source_path": str(a)}).json()["id"]
    assert c.put(f"/projects/{pid}/song", json=_song()).status_code == 200
    return pid


def test_models_list_shape(client):
    c, _ = client
    d = c.get("/models").json()
    assert {m["id"] for m in d["models"]} >= {"separation", "rmvpe", "some", "whisper"}
    assert all(isinstance(m["size_bytes"], int) for m in d["models"]) and d["disk_free_bytes"] > 0
    assert c.delete("/models/some").status_code == 422          # ติดตั้งเอง ห้ามลบ
    assert c.delete("/models/nope").status_code == 422


def test_model_delete_only_under_models_dir(tmp_path, monkeypatch):
    (tmp_path / "models").mkdir()
    f = tmp_path / "models" / "x.ckpt"
    f.write_bytes(b"0" * 1000)
    outside = tmp_path / "outside.ckpt"
    outside.write_bytes(b"1")
    monkeypatch.setattr(M, "MODELS_DIR", tmp_path / "models")
    monkeypatch.setattr(M, "_registry", lambda: [
        {"id": "ok", "paths": [f], "auto_download": True}, {"id": "bad", "paths": [outside], "auto_download": True}])
    assert M.delete_model("ok") == 1000 and not f.exists()
    with pytest.raises(ValueError):
        M.delete_model("bad")
    assert outside.exists()


def test_batch_folder_and_errors(client):
    c, tmp = client
    d = tmp / "songs"
    d.mkdir()
    for n in ("a.wav", "b.mp3"):
        (d / n).write_bytes(b"RIFF....fake")
    (d / "notes.txt").write_text("x")
    r = c.post("/batch", json={"folder": str(d), "paths": [str(tmp / "missing.wav")]})
    assert r.status_code == 202
    j = r.json()
    assert len(j["created"]) == 2 and len(j["errors"]) == 1
    assert len({x["job"]["id"] for x in j["created"]}) == 2
    assert c.post("/batch", json={}).status_code == 422
    assert c.post("/batch", json={"folder": str(tmp / "nope")}).status_code == 404


def test_harmony_endpoint_and_export(client):
    c, tmp = client
    pid = _pid(c, tmp)
    r = c.post(f"/projects/{pid}/harmony", json={"interval": "third"}).json()
    song = _song()
    assert len(r["notes"]) == len(song["notes"]) and len(r["tab"]["events"]) == len(song["notes"]) and "e|" in r["text"]
    assert c.post(f"/projects/{pid}/harmony", json={"interval": "fifth"}).status_code == 422
    _tab(c, pid, song)
    e = c.post(f"/projects/{pid}/export", json={"formats": ["harmony"], "harmony": {"interval": "sixth", "direction": "below"}}).json()
    assert {f["name"].rsplit("_", 1)[-1] for f in e["files"]} == {"harmony.mid", "tab.txt"}


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="ต้องมี ffmpeg")
def test_video_renders_mp4(tmp_path):
    song = _song()
    from melotab.tab import generate_tab
    tab = generate_tab(song["notes"])
    tab["techniques"] = {}
    m = EM.build(song, tab, "t")
    out = tmp_path / "v.mp4"
    wav = tmp_path / "t.wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=12", str(wav)], check=True)
    info = video.render_video(m, song["sections"][0], out, wav, size=(640, 360), fps=10)
    assert out.exists() and out.stat().st_size > 1000
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)],
                               capture_output=True, text=True).stdout)
    assert abs(dur - info["seconds"]) < 0.6 and info["frames"] == int(info["seconds"] * 10)
