"""เทสต์ export: ทุกฟอร์แมตเขียนได้, อ่านกลับแล้วโน้ต/เลขช่องตรงกับแทป, ห้องรวมความยาวถูกต้อง"""
import xml.etree.ElementTree as ET
from pathlib import Path

import guitarpro
import pretty_midi
import pytest
from fastapi.testclient import TestClient

from melotab.api.app import create_app
from melotab.cache import StageCache
from melotab.export.model import build
from melotab.store import ProjectStore


def _song():
    beats = [{"time": 0.5 * i, "bar": 1 + i // 4, "beat": 1 + i % 4} for i in range(24)]
    mids = [64, 66, 67, 69, 71, 69, 67, 66, 64, 62, 64, 66, 67, 69, 71, 74]
    notes = [{"id": f"n{i}", "midi": m, "start": i * 0.5, "end": i * 0.5 + 0.45, "start_beat_q": float(i), "dur_beats_q": 0.9,
              "start_beat": float(i), "dur_beats": 0.9, "confidence": 0.8} for i, m in enumerate(mids)]
    return {
        "source": {"title": "เพลงทดสอบ", "duration": 12.0}, "key": {"tonic": "E", "mode": "minor"}, "tempo": {"bpm": 120.0},
        "time_signature": {"num": 4, "den": 4}, "beats": beats, "notes": notes,
        "chords": [{"start_beat": 0, "end_beat": 8, "start": 0.0, "end": 4.0, "symbol": "Em", "root": 4, "quality": "min", "bass": None},
                   {"start_beat": 8, "end_beat": 16, "start": 4.0, "end": 8.0, "symbol": "D", "root": 2, "quality": "maj", "bass": None}],
        "sections": [{"id": "s1", "label": "Verse", "start_bar": 1, "end_bar": 3, "start": 0.0, "end": 4.0},
                     {"id": "s2", "label": "Chorus", "start_bar": 3, "end_bar": 5, "start": 4.0, "end": 8.0}],
        "lyrics": {"language": "th", "source": "pasted", "lines": [
            {"id": "l1", "start": 0.0, "end": 3.9, "text": "สวัสดี ชาวโลก", "words": [
                {"text": "สวัสดี", "start": 0.0, "end": 1.0}, {"text": "ชาวโลก", "start": 2.0, "end": 3.0}]}]},
    }


@pytest.fixture
def client_pid(tmp_path):
    audio = tmp_path / "a.wav"
    audio.write_bytes(b"RIFF....fake")
    app = create_app(store=ProjectStore(tmp_path / "P"), cache=StageCache(tmp_path / "c"), runner=lambda *a: {}, stats_interval=0.05)
    with TestClient(app) as c:
        pid = c.post("/projects", json={"source_path": str(audio)}).json()["id"]
        song = _song()
        assert c.put(f"/projects/{pid}/song", json=song).status_code == 200
        yield c, pid, song


def _tab(c, pid, song, techniques=None):
    tab = c.post(f"/projects/{pid}/tab/generate", json={"settings": {}, "notes": song["notes"]}).json()
    tab["techniques"] = techniques or {}
    assert c.put(f"/projects/{pid}/tab", json=tab).status_code == 200
    return tab


def test_model_measures_are_complete(client_pid):
    c, pid, song = client_pid
    tab = _tab(c, pid, song)
    m = build(song, tab)
    placed = 0
    for ms in m["measures"]:
        assert sum(it["dur16"] for it in ms["items"]) == ms["beats"] * 4          # ห้องเต็มพอดี (โน้ต+พัก)
        pos = 0
        for it in ms["items"]:
            assert it["start16"] == pos
            pos += it["dur16"]
            placed += it["event"] is not None
    assert placed == len(song["notes"])                                           # ไม่มีโน้ตหาย


def test_all_formats_roundtrip(client_pid):
    c, pid, song = client_pid
    tab = _tab(c, pid, song, {"n0": {"to_next": "hammer"}, "n2": {"on": ["bend"], "bend_semitones": 1}, "n4": {"on": ["vibrato"]}})
    r = c.post(f"/projects/{pid}/export", json={
        "formats": ["png", "svg", "pdf", "midi", "musicxml", "gp5", "txt", "chordsheet", "lrc"], "sections": "all", "scale": 1})
    assert r.status_code == 200, r.text
    r = r.json()
    assert r["skipped"] == []
    names = {f["name"]: f for f in r["files"]}
    assert any(n.endswith("_01_Verse.png") for n in names) and any(n.endswith("_02_Chorus.svg") for n in names)
    d = c.get(f"/projects/{pid}/exports").json()
    assert {x["name"] for x in d} == set(names)
    png = next(n for n in names if n.endswith(".png"))
    body = c.get(f"/projects/{pid}/exports/{png}").content
    assert body[:8] == b"\x89PNG\r\n\x1a\n"
    svg = c.get(f"/projects/{pid}/exports/{next(n for n in names if n.endswith('.svg'))}").text
    assert "<svg" in svg and "เพลงทดสอบ" in svg and "Verse" in svg or "Chorus" in svg
    assert c.get(f"/projects/{pid}/exports/{next(n for n in names if n.endswith('.pdf'))}").content[:4] == b"%PDF"

    pm = pretty_midi.PrettyMIDI(str(Path(r["dir"]) / next(n for n in names if n.endswith(".mid"))))
    assert len(pm.instruments[0].notes) == len(song["notes"])

    xml_path = Path(r["dir"]) / next(n for n in names if n.endswith(".musicxml"))
    root = ET.parse(xml_path).getroot()
    staff2 = [n for n in root.iter("note") if n.findtext("staff") == "2" and n.find("rest") is None]
    assert len(staff2) == len(song["notes"])
    assert [(int(n.findtext("notations/technical/string")), int(n.findtext("notations/technical/fret"))) for n in staff2] == \
        [(e["string"], e["fret"]) for e in tab["events"]]
    assert root.find(".//harmony") is not None and list(root.iter("hammer-on")) and list(root.iter("bend-alter"))

    g = guitarpro.parse(str(Path(r["dir"]) / next(n for n in names if n.endswith(".gp5"))))
    got = [(n.string, n.value) for ms in g.tracks[0].measures for b in ms.voices[0].beats for n in b.notes]
    assert got == [(e["string"], e["fret"]) for e in tab["events"]]
    notes = [n for ms in g.tracks[0].measures for b in ms.voices[0].beats for n in b.notes]
    assert notes[0].effect.hammer and notes[2].effect.bend is not None and notes[4].effect.vibrato

    txt = (Path(r["dir"]) / next(n for n in names if n.endswith("_tab.txt"))).read_text(encoding="utf-8")
    assert "[Verse]" in txt and "h" in txt and "~" in txt
    cs = (Path(r["dir"]) / next(n for n in names if n.endswith("_chords.txt"))).read_text(encoding="utf-8")
    assert "Em" in cs and "สวัสดี" in cs
    lrc = (Path(r["dir"]) / next(n for n in names if n.endswith(".lrc"))).read_text(encoding="utf-8")
    assert "[00:00.00]สวัสดี ชาวโลก" in lrc


def test_export_errors_and_skips(client_pid):
    c, pid, song = client_pid
    assert c.post(f"/projects/{pid}/export", json={"formats": ["docx"]}).status_code == 422
    assert c.post(f"/projects/{pid}/export", json={"formats": []}).status_code == 422
    assert c.post(f"/projects/{pid}/export", json={"formats": ["png"], "preset": "zzz"}).status_code == 422
    r = c.post(f"/projects/{pid}/export", json={"formats": ["png", "gp5", "midi", "stems"]}).json()      # ยังไม่มีแทป
    assert {s["format"] for s in r["skipped"]} == {"png", "gp5", "stems"}
    assert [f["format"] for f in r["files"]] == ["midi"]
    assert c.get(f"/projects/{pid}/exports/..%2F..%2Fproject.json").status_code in (404, 422)
    assert c.get(f"/projects/{pid}/exports/nope.png").status_code == 404


def test_presets_and_custom_range(client_pid):
    c, pid, song = client_pid
    _tab(c, pid, song)
    r = c.post(f"/projects/{pid}/export", json={"formats": ["png"], "preset": "story", "theme": "transparent",
                                                 "custom_range": {"start": 0.0, "end": 4.0}}).json()
    assert len(r["files"]) == 1
    from PIL import Image
    im = Image.open(Path(r["dir"]) / r["files"][0]["name"])
    assert im.size == (1080, 1920) and im.mode == "RGBA" and im.getpixel((2, 2))[3] == 0          # พื้นโปร่งใส
