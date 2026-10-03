"""แยกเสียงด้วย audio-separator: vocal → (ตัวเลือก) karaoke ตัดเสียงประสาน → (ตัวเลือก) de-reverb

Phase 0 พบว่าเสียงประสานใน vocal stem ทำให้ SOME ให้โน้ตผิด octave ได้ (63 โน้ตใน song02)
karaoke ช่วยลดเหลือ 0–1 โน้ต แต่ช้า (~118 s/เพลง 4:50) จึงเป็นตัวเลือก
"""
import shutil
from pathlib import Path

from ..config import MODELS_DIR, SEP_DEREVERB_MODEL, SEP_KARAOKE_MODEL, SEP_VOCAL_MODEL
from ..gpu import free_gpu


def _run_model(audio: Path, model: str, work: Path) -> list[Path]:
    """รันโมเดลเดียว คืน path ของไฟล์ผลลัพธ์ (audio-separator เขียนลง output_dir)"""
    from audio_separator.separator import Separator  # import ช้า (หนัก) เลยโหลดตอนใช้จริง

    work.mkdir(parents=True, exist_ok=True)
    sep = Separator(model_file_dir=str(MODELS_DIR), output_dir=str(work), output_format="FLAC")
    try:
        sep.load_model(model_filename=model)
        names = sep.separate(str(audio))
    finally:
        del sep
        free_gpu()
    return [work / n if not Path(n).is_absolute() else Path(n) for n in names]


def _pick(files: list[Path], keyword: str) -> Path:
    for f in files:
        if keyword.lower() in f.name.lower():
            return f
    raise RuntimeError(f"ไม่พบ stem '{keyword}' ในผลลัพธ์: {[f.name for f in files]}")


def separate(audio: Path, stems_dir: Path, karaoke: bool = False, dereverb: bool = False) -> dict[str, Path]:
    """คืน dict ชื่อ stem → path: vocals, instrumental, [lead, backing], [lead_dry]; และ `melody_source` = stem ที่ใช้แกะโน้ต"""
    stems_dir.mkdir(parents=True, exist_ok=True)
    tmp = stems_dir / "_tmp"
    out: dict[str, Path] = {}

    def keep(name: str, src: Path) -> Path:
        dst = stems_dir / f"{name}.flac"
        shutil.move(str(src), dst)
        out[name] = dst
        return dst

    files = _run_model(audio, SEP_VOCAL_MODEL, tmp / "vocal")
    vocals = keep("vocals", _pick(files, "(vocals)"))
    keep("instrumental", _pick(files, "(other)"))
    melody = vocals

    if karaoke:
        files = _run_model(vocals, SEP_KARAOKE_MODEL, tmp / "karaoke")
        melody = keep("lead", _pick(files, "(vocals)"))
        keep("backing", _pick(files, "(instrumental)"))
    if dereverb:
        files = _run_model(melody, SEP_DEREVERB_MODEL, tmp / "dereverb")
        melody = keep("lead_dry", _pick(files, "(noreverb)"))

    shutil.rmtree(tmp, ignore_errors=True)
    out["melody_source"] = melody
    return out
