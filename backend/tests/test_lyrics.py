"""เทสต์การจัดเวลา/ตัดคำของเนื้อร้อง ด้วยข้อความสังเคราะห์ (ไม่ใช้เนื้อเพลงจริง)"""
from melotab.pipeline.lyrics import align_pasted, attach_notes, lines_from_asr, tokenize

ASR = [{"text": "alpha", "start": 1.0, "end": 1.5}, {"text": "beta", "start": 1.5, "end": 2.0},
       {"text": "gamma", "start": 4.0, "end": 4.6}, {"text": "delta", "start": 4.6, "end": 5.2}]


def test_tokenize_english_and_thai():
    assert tokenize("alpha  beta gamma") == ["alpha", "beta", "gamma"]
    assert tokenize("   ") == []
    th = tokenize("สวัสดีครับ")
    assert len(th) >= 1 and "".join(th) == "สวัสดีครับ"                 # ตัดคำแล้วต่อกลับได้เท่าเดิม


def test_align_transfers_times_from_matching_asr_chars():
    lines = align_pasted(["alpha beta", "gamma delta"], ASR)
    assert [l["text"] for l in lines] == ["alpha beta", "gamma delta"]
    w = {x["text"]: x for l in lines for x in l["words"]}
    assert abs(w["alpha"]["start"] - 1.0) < 0.02 and abs(w["beta"]["end"] - 2.0) < 0.02
    assert abs(w["gamma"]["start"] - 4.0) < 0.02 and abs(w["delta"]["end"] - 5.2) < 0.02
    assert lines[0]["start"] == 1.0 and lines[1]["end"] == 5.2


def test_align_tolerates_asr_errors_and_extra_words():
    asr = [{"text": "alfa", "start": 1.0, "end": 1.5}, {"text": "bta", "start": 1.5, "end": 2.0},          # ถอดผิด
           {"text": "gamma", "start": 4.0, "end": 4.6}]
    lines = align_pasted(["alpha beta", "omega", "gamma"], asr)         # "omega" ไม่มีใน ASR เลย
    flat = [w for l in lines for w in l["words"]]
    assert [w["text"] for w in flat] == ["alpha", "beta", "omega", "gamma"]
    starts = [w["start"] for w in flat]
    assert starts == sorted(starts)                                      # เวลาไม่ย้อนกลับ
    assert flat[1]["start"] < flat[2]["start"] < flat[3]["start"]            # omega ถูก interpolate อยู่ระหว่าง beta กับ gamma
    assert abs(flat[3]["start"] - 4.0) < 0.05
    assert all(w["end"] > w["start"] for w in flat)


def test_align_without_asr_spreads_over_span_proportionally():
    lines = align_pasted(["aaaa", "bb"], [], span=(10.0, 16.0))          # 6 ตัวอักษร ใน 6 วินาที = ตัวละ 1 วินาที
    a, b = lines
    assert abs(a["start"] - 10.0) < 1e-6 and abs(a["end"] - 14.0) < 1e-6
    assert abs(b["start"] - 14.0) < 1e-6 and abs(b["end"] - 16.0) < 1e-6
    assert align_pasted(["", "  "], ASR) == []


def test_lines_from_asr_and_attach_notes():
    segs = [{"start": 1.0, "end": 2.0, "text": "alpha beta", "words": [
        {"text": "alpha", "start": 1.0, "end": 1.5, "prob": 0.9}, {"text": "beta", "start": 1.5, "end": 2.0, "prob": 0.8}]}]
    lines = lines_from_asr(segs)
    assert lines[0]["id"] == "l1" and "prob" not in lines[0]["words"][0]
    notes = [{"id": "n1", "start": 0.9, "end": 1.4}, {"id": "n2", "start": 1.4, "end": 1.6}, {"id": "n3", "start": 3.0, "end": 3.5}]
    attach_notes(lines, notes)
    assert lines[0]["words"][0]["note_ids"] == ["n1", "n2"]              # alpha ทับ n1 และ n2
    assert lines[0]["words"][1]["note_ids"] == ["n2"]
