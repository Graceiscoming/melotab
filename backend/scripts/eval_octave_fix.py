"""Phase 2: ตรวจผลของ fix_octave — เทียบโน้ตจาก vocal stem เดิม (ไม่แก้ / แก้) กับโน้ตจากเสียงที่ผ่าน karaoke

reference คือผลของเสียงที่ตัดเสียงประสานแล้ว (ใกล้ความจริงกว่า แต่ไม่ใช่ ground truth) จึงวัดได้แค่ว่า "ใกล้ reference แค่ไหน"
    python scripts/eval_octave_fix.py ../testdata/song02.mp3
"""
import sys
import tempfile
from pathlib import Path

from melotab.analysis import run_analysis
from melotab.evaluate import evaluate_notes, load_notes

src = Path(sys.argv[1])
work = Path(tempfile.mkdtemp(prefix="melotab_eval_"))
runs = {
    "ref (karaoke)": dict(karaoke=True, fix_octave=False),
    "plain, ไม่แก้ octave": dict(karaoke=False, fix_octave=False),
    "plain, แก้ octave": dict(karaoke=False, fix_octave=True),
}
songs = {}
for name, kw in runs.items():
    out = work / name.split(",")[0].split(" ")[0] / str(kw["fix_octave"])
    songs[name] = run_analysis(src, out, **kw)
    s = songs[name]
    print(f"{name}: {len(s['notes'])} โน้ต, octave_suspect={sum(n['octave_suspect'] for n in s['notes'])}, "
          f"octave_fixed={sum(n.get('octave_fixed', False) for n in s['notes'])}")


def to_arrays(song):
    import numpy as np
    iv = np.array([[n["start"], n["end"]] for n in song["notes"]], dtype=float)
    hz = np.array([440.0 * 2 ** ((n["midi"] - 69) / 12) for n in song["notes"]], dtype=float)
    return iv, hz


ref = to_arrays(songs["ref (karaoke)"])
for name in ("plain, ไม่แก้ octave", "plain, แก้ octave"):
    r = evaluate_notes(ref, to_arrays(songs[name]))
    print(f"{name} vs ref: COnP P={r['COnP']['precision']:.3f} R={r['COnP']['recall']:.3f} F1={r['COnP']['f1']:.3f}")
