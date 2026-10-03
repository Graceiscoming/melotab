import numpy as np

from melotab.pipeline import ornaments as O
from melotab.tab import generate_tab
from melotab.tab.techniques import suggest_techniques

HOP = 0.01


def _curve(segments, total):
    t = np.arange(0, total, HOP)
    f = np.full(len(t), np.nan)
    for a, b, fn in segments:
        i, j = int(a / HOP), int(b / HOP)
        f[i:j] = fn(np.arange(j - i) * HOP)
    return t, f


def test_vibrato_detected_and_steady_not():
    n = {"id": "a", "midi": 64, "start": 0.0, "end": 1.0}
    t, f = _curve([(0, 1.0, lambda x: 64 + 0.4 * np.sin(2 * np.pi * 6 * x))], 1.2)
    assert any(o["type"] == "vibrato" for o in O.detect_note(n, t, f, HOP))
    t, f = _curve([(0, 1.0, lambda x: 64 + 0 * x)], 1.2)
    assert O.detect_note(n, t, f, HOP) == []


def test_scoop_and_bend():
    n = {"id": "a", "midi": 64, "start": 0.0, "end": 1.0}
    t, f = _curve([(0, 1.0, lambda x: 64 - 1.5 * np.clip(1 - x / 0.15, 0, 1))], 1.2)
    assert any(o["type"] == "scoop_in" for o in O.detect_note(n, t, f, HOP))
    t, f = _curve([(0, 1.0, lambda x: 64 + 1.0 * np.clip((x - 0.2) / 0.6, 0, 1))], 1.2)
    assert any(o["type"] == "bend_up" for o in O.detect_note(n, t, f, HOP))


def test_slide_vs_legato_vs_break():
    a = {"id": "a", "midi": 64, "start": 0.0, "end": 0.5}
    b = {"id": "b", "midi": 66, "start": 0.5, "end": 1.0}
    t, f = _curve([(0, 0.5, lambda x: 64 + 0 * x), (0.5, 1.0, lambda x: 66 + 0 * x)], 1.2)
    f[50] = 65                                                                # เปลี่ยนใน ~10 ms = legato
    assert O.detect_transition(a, b, t, f, HOP)["type"] == "legato_next"
    f2 = f.copy()
    f2[35:65] = np.linspace(64, 66, 30)                                       # glide 300 ms
    assert O.detect_transition(a, b, t, f2, HOP)["type"] == "slide_next"
    f3 = f.copy()
    f3[48:52] = np.nan                                                        # f0 ขาด = เริ่มเสียงใหม่
    assert O.detect_transition(a, b, t, f3, HOP) is None


def _notes(spec):
    return [{"id": f"n{i}", "midi": m, "start": i * 0.5, "end": i * 0.5 + 0.45, "ornaments": o} for i, (m, o) in enumerate(spec)]


def test_vibrato_avoids_open_string():
    notes = _notes([(64, [{"type": "vibrato"}])])             # E4 เล่นสายเปล่าสาย 1 ได้ แต่ต้องหลีกเลี่ยง
    assert generate_tab(notes)["events"][0]["fret"] > 0
    assert generate_tab(_notes([(64, [])]))["events"][0]["fret"] == 0


def test_mapping_rules():
    notes = _notes([(64, [{"type": "legato_next", "interval": 2}]), (66, [{"type": "slide_next", "interval": -2}]), (64, []),
                    (65, [{"type": "bend_up", "cents": 100}]), (67, [{"type": "vibrato"}])])
    ev = [
        {"note_id": "n0", "string": 2, "fret": 5, "start": 0, "end": .45},
        {"note_id": "n1", "string": 2, "fret": 7, "start": .5, "end": .95},
        {"note_id": "n2", "string": 2, "fret": 5, "start": 1, "end": 1.45},
        {"note_id": "n3", "string": 1, "fret": 1, "start": 1.5, "end": 1.95},
        {"note_id": "n4", "string": 1, "fret": 0, "start": 2, "end": 2.45},
    ]
    r = suggest_techniques(ev, notes)
    assert r["techniques"]["n0"]["to_next"] == "hammer"
    assert r["techniques"]["n1"]["to_next"] == "slide"
    assert r["techniques"]["n3"]["on"] == ["bend"] and r["bends"]["n3"] == 1
    assert "n4" not in r["techniques"] and any(x["note_id"] == "n4" and x["technique"] == "vibrato" for x in r["rejected"])
    ev[1]["string"] = 3                                                      # คนละสาย → hammer ไม่ได้
    assert "n0" not in suggest_techniques(ev, notes)["techniques"]


def test_auto_techniques_endpoint(tmp_path):
    from fastapi.testclient import TestClient

    from melotab.api.app import create_app
    from melotab.cache import StageCache
    from melotab.store import ProjectStore

    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF....fake")
    store = ProjectStore(tmp_path / "P")
    app = create_app(store=store, cache=StageCache(tmp_path / "c"), runner=lambda *a: {}, stats_interval=0.05)
    with TestClient(app) as c:
        pid = c.post("/projects", json={"source_path": str(audio)}).json()["id"]
        notes = [{"id": "a", "midi": 64, "start": 0.0, "end": 1.0}, {"id": "b", "midi": 69, "start": 1.2, "end": 2.2}]
        assert c.put(f"/projects/{pid}/song", json={"notes": notes}).status_code == 200
        r = c.post(f"/projects/{pid}/tab/techniques/auto", json={"settings": {}})
        assert r.status_code == 200 and r.json()["techniques"] == {}                       # ไม่มี f0 → ไม่มี ornament
        t = np.arange(0, 2.5, HOP)
        hz = 440 * 2 ** ((np.where(t < 1.1, 64 + 0.45 * np.sin(2 * np.pi * 6 * t), 69.0) - 69) / 12)
        (store.path(pid) / "analysis").mkdir(exist_ok=True)
        np.savez(store.path(pid) / "analysis" / "f0.npz", f0_hz=hz, times=t, hop_s=HOP)
        j = c.post(f"/projects/{pid}/tab/techniques/auto", json={"settings": {}}).json()
        assert j["ornaments"] >= 1 and j["techniques"]["a"]["on"] == ["vibrato"]
        assert c.post(f"/projects/{pid}/tab/techniques/auto", json={"settings": {"tuning": "zzz"}}).status_code == 422
