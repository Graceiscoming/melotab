"""เทสต์ API + job manager ด้วย runner ปลอม (ไม่ใช้ GPU/โมเดล)"""
import time

import pytest
from fastapi.testclient import TestClient

from melotab.analysis import Cancelled
from melotab.api.app import create_app
from melotab.cache import StageCache, make_key
from melotab.store import ProjectStore


def fake_runner(job, on_event, cancelled):
    for i, name in enumerate(["ingest", "separation", "f0"], 1):
        if cancelled():
            raise Cancelled()
        on_event({"type": "job.stage", "stage": name, "stage_index": i, "stage_total": 3, "status": "start", "overall_pct": (i - 1) * 33.3})
        time.sleep(0.05)
        on_event({"type": "job.stage", "stage": name, "stage_index": i, "stage_total": 3, "status": "done", "seconds": 0.05, "overall_pct": i * 33.3})
    return {}


def failing_runner(job, on_event, cancelled):
    raise RuntimeError("VRAM ไม่พอ")


@pytest.fixture
def audio_file(tmp_path):
    p = tmp_path / "a.wav"
    p.write_bytes(b"RIFF....fake")
    return p


def make_client(tmp_path, runner):
    app = create_app(store=ProjectStore(tmp_path / "Projects"), cache=StageCache(tmp_path / "cache"),
                     runner=runner, stats_interval=0.05)
    return TestClient(app)


def wait_status(c, jid, want, timeout=5):
    t = time.time()
    while time.time() - t < timeout:
        s = c.get(f"/jobs/{jid}").json()
        if s["status"] in want:
            return s
        time.sleep(0.02)
    raise AssertionError(f"timeout, last={s}")


def test_project_create_and_list(tmp_path, audio_file):
    with make_client(tmp_path, fake_runner) as c:
        r = c.post("/projects", json={"source_path": str(audio_file), "title": "เพลงทดสอบ"})
        assert r.status_code == 201
        pid = r.json()["id"]
        assert [p["id"] for p in c.get("/projects").json()] == [pid]
        assert c.get(f"/projects/{pid}").json()["song"] is None


def test_missing_source_is_404_and_bad_id_rejected(tmp_path):
    with make_client(tmp_path, fake_runner) as c:
        assert c.post("/projects", json={"source_path": str(tmp_path / "nope.wav")}).status_code == 404
        assert c.get("/projects/..%2F..%2Fetc").status_code == 404
        assert c.get("/audio/x/passwd").status_code == 404


def test_job_runs_and_streams_events(tmp_path, audio_file):
    with make_client(tmp_path, fake_runner) as c:
        pid = c.post("/projects", json={"source_path": str(audio_file)}).json()["id"]
        with c.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "hello"
            jid = c.post(f"/projects/{pid}/analyze", json={}).json()["id"]
            seen = set()
            while "job.done" not in seen:
                seen.add(ws.receive_json()["type"])
        assert {"job.queued", "job.stage", "job.done"} <= seen
        assert wait_status(c, jid, {"done"})["overall_pct"] == 100.0


def test_ws_gets_heartbeat_and_system_stats(tmp_path):
    with make_client(tmp_path, fake_runner) as c, c.websocket_connect("/ws") as ws:
        types = {ws.receive_json()["type"] for _ in range(6)}
        assert {"heartbeat", "system.stats"} <= types


def test_error_is_reported_readably(tmp_path, audio_file):
    with make_client(tmp_path, failing_runner) as c:
        pid = c.post("/projects", json={"source_path": str(audio_file)}).json()["id"]
        jid = c.post(f"/projects/{pid}/analyze").json()["id"]
        s = wait_status(c, jid, {"error"})
        assert "VRAM ไม่พอ" in s["error"]
        assert c.post(f"/jobs/{jid}/cancel").status_code == 409      # งานจบแล้วยกเลิกไม่ได้


def test_cancel_queued_and_running(tmp_path, audio_file):
    def slow(job, on_event, cancelled):
        for _ in range(100):
            if cancelled():
                raise Cancelled()
            time.sleep(0.02)

    with make_client(tmp_path, slow) as c:
        pid = c.post("/projects", json={"source_path": str(audio_file)}).json()["id"]
        j1 = c.post(f"/projects/{pid}/analyze").json()["id"]
        j2 = c.post(f"/projects/{pid}/analyze").json()["id"]          # ติดคิวหลัง j1
        assert c.post(f"/jobs/{j2}/cancel").status_code == 200
        assert wait_status(c, j2, {"cancelled"})["status"] == "cancelled"
        wait_status(c, j1, {"running"})
        assert c.post(f"/jobs/{j1}/cancel").status_code == 200
        assert wait_status(c, j1, {"cancelled"})["status"] == "cancelled"


def test_cache_key_depends_on_params_and_audio(tmp_path):
    a = make_key("sep", "h1", karaoke=False)
    assert a == make_key("sep", "h1", karaoke=False)
    assert a != make_key("sep", "h1", karaoke=True) and a != make_key("sep", "h2", karaoke=False)
    c = StageCache(tmp_path)
    assert c.get(a) is None
    d = c.begin(a)
    (d / "x.txt").write_text("hi")
    assert c.get(a) is None                      # ยังไม่ commit = ยังใช้ไม่ได้
    final = c.commit(a)
    assert c.get(a) == final and (final / "x.txt").read_text() == "hi"


def test_upload_creates_project_and_song_put_roundtrip(tmp_path):
    with make_client(tmp_path, fake_runner) as c:
        r = c.post("/projects/upload", files={"file": ("เพลง.wav", b"RIFFxxxx", "audio/wav")}, data={"title": "อัปโหลด"})
        assert r.status_code == 201
        pid = r.json()["id"]
        assert c.get(f"/projects/{pid}/f0").status_code == 404           # ยังไม่วิเคราะห์
        assert c.put(f"/projects/{pid}/song", json={"notes": [{"id": "n1"}]}).json() == {"ok": True, "notes": 1}
        assert c.get(f"/projects/{pid}").json()["song"]["notes"][0]["id"] == "n1"
        assert c.put(f"/projects/{pid}/song", json={"x": 1}).status_code == 422
        assert c.put("/projects/nope/song", json={"notes": []}).status_code == 404


def test_history_snapshots_and_restore(tmp_path, audio_file):
    from melotab.store import ProjectStore
    st = ProjectStore(tmp_path / "P")
    pid = st.create(audio_file)["id"]
    st.save_song(pid, {"notes": [{"id": "v1"}]})
    assert st.history(pid) == []                              # ครั้งแรกยังไม่มีของเก่าให้เก็บ
    st.save_song(pid, {"notes": [{"id": "v2"}]})
    snaps = st.history(pid)
    assert len(snaps) == 1
    st.save_song(pid, {"notes": [{"id": "v3"}]})              # ภายใน 120 s → ไม่เก็บซ้ำ
    assert len(st.history(pid)) == 1
    assert st.restore(pid, snaps[0])["notes"][0]["id"] == "v1"
    assert st.song(pid)["notes"][0]["id"] == "v1"
    import pytest as _p
    with _p.raises(ValueError):
        st.restore(pid, "../../etc/passwd")


def _song_with_notes(c, audio_file):
    pid = c.post("/projects", json={"source_path": str(audio_file)}).json()["id"]
    notes = [{"id": f"n{i}", "midi": m, "start": i * 0.5, "end": i * 0.5 + 0.4, "start_beat_q": i, "dur_beats_q": 0.8}
             for i, m in enumerate([60, 62, 64, 65, 67, 69, 71, 72])]
    song = {"notes": notes, "key": {"tonic": "C", "mode": "major"}, "beats": []}
    assert c.put(f"/projects/{pid}/song", json=song).status_code == 200
    return pid, notes


def test_tab_endpoints(tmp_path, audio_file):
    from melotab.tab.theory import TUNINGS, pitch_at
    with make_client(tmp_path, fake_runner) as c:
        pid, notes = _song_with_notes(c, audio_file)
        assert c.get(f"/projects/{pid}/tab").json() == {}                              # ยังไม่เคยสร้าง
        r = c.post(f"/projects/{pid}/tab/generate", json={"settings": {"capo": 2}}).json()
        assert len(r["events"]) == 8 and r["summary"]["unplayable"] == 0
        for e, n in zip(r["events"], notes):
            assert pitch_at(e["string"], e["fret"], TUNINGS["standard"], 2) == n["midi"]
        assert c.get(f"/projects/{pid}/tab").json()["settings"]["capo"] == 2           # เก็บลง tab.json แล้ว
        lock = {"n2": {"string": 3, "fret": 9}}
        r2 = c.post(f"/projects/{pid}/tab/generate", json={"settings": {}, "locked": lock}).json()
        assert (r2["events"][2]["string"], r2["events"][2]["fret"]) == (3, 9) and r2["events"][2]["locked"]
        alts = c.post(f"/projects/{pid}/tab/alternatives", json={"note_id": "n3", "settings": {}}).json()
        assert alts and all(a["pitch"] == 65 for a in alts)
        b = c.post(f"/projects/{pid}/tab/blocks", json={"system": "pentatonic", "transpose": 2}).json()
        assert b["tonic"] == "D" and len(b["blocks"]) >= 3 and b["coverage"] is None
        b2 = c.post(f"/projects/{pid}/tab/blocks", json={"selected": b["blocks"][:1]}).json()
        assert 0.0 <= b2["coverage"] <= 1.0
        s = c.post(f"/projects/{pid}/keys/suggest", json={"settings": {}}).json()
        assert s["same_sound"] and s["transposed"] and s["best"]["unplayable"] == 0
        assert c.get("/tab/presets").json()["tunings"][0] == "standard"


def test_tab_endpoints_validate_input(tmp_path, audio_file):
    with make_client(tmp_path, fake_runner) as c:
        pid = c.post("/projects", json={"source_path": str(audio_file)}).json()["id"]
        assert c.post(f"/projects/{pid}/tab/generate", json={}).status_code == 404       # ยังไม่มีโน้ต
        pid, _ = _song_with_notes(c, audio_file)
        assert c.post(f"/projects/{pid}/tab/generate", json={"settings": {"tuning": "nope"}}).status_code == 422
        assert c.post(f"/projects/{pid}/tab/generate", json={"settings": {"capo": 99}}).status_code == 422
        assert c.put(f"/projects/{pid}/tab", json={"x": 1}).status_code == 422
        assert c.put("/projects/nope/tab", json={"events": []}).status_code == 404
