"""Model Manager (plan หัวข้อ 16): รายการโมเดลที่ใช้ สถานะ (มี/ไม่มี) ขนาดบนดิสก์ บทบาท และ VRAM ที่วัดจริง (DECISIONS.md)

โมเดลดาวน์โหลดอัตโนมัติโดยไลบรารีเองเมื่อใช้ครั้งแรก (audio-separator, faster-whisper); ที่นี่ "ดู/ลบ" เท่านั้น
การลบเฉพาะไฟล์ใต้ models/ ที่อยู่ในรายการนี้ (กัน path traversal) — ลบแล้วถูกดาวน์โหลดใหม่เมื่อใช้งานครั้งหน้า
ยกเว้น SOME/RMVPE/BTC ที่ติดตั้งเอง (ไม่โหลดอัตโนมัติ) จึงห้ามลบจาก UI
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .config import MODELS_DIR, THIRD_PARTY


def _registry() -> list[dict]:
    m = MODELS_DIR
    return [
        {"id": "separation", "name": "Mel-Band RoFormer (แยกเสียงร้อง)", "role": "แยก vocals/instrumental", "stage": "separation",
         "paths": [m / "vocals_mel_band_roformer.ckpt", m / "vocals_mel_band_roformer.yaml"], "vram_gb": 3.8, "auto_download": True, "required": True},
        {"id": "karaoke", "name": "Karaoke RoFormer (แยกเสียงประสาน)", "role": "ตัดเสียงประสาน เหลือ lead", "stage": "karaoke",
         "paths": [m / "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956.ckpt", m / "mel_band_roformer_karaoke_aufr33_viperx_sdr_10.1956_config.yaml"],
         "vram_gb": 3.3, "auto_download": True, "required": False},
        {"id": "dereverb", "name": "De-reverb RoFormer", "role": "ลดเสียงก้อง", "stage": "dereverb",
         "paths": [m / "dereverb_mel_band_roformer_anvuew_sdr_19.1729.ckpt", m / "dereverb_mel_band_roformer_anvuew.yaml"],
         "vram_gb": 3.3, "auto_download": True, "required": False},
        {"id": "rmvpe", "name": "RMVPE (f0)", "role": "เส้น pitch ของเสียงร้อง", "stage": "f0", "paths": [m / "RMVPE"], "vram_gb": 0.5, "auto_download": False, "required": True},
        {"id": "some", "name": "SOME (singing → โน้ต)", "role": "แปลง f0/เสียงเป็นโน้ต MIDI", "stage": "notes", "paths": [m / "SOME"], "vram_gb": 1.2, "auto_download": False, "required": True},
        {"id": "whisper", "name": "faster-whisper (เนื้อร้อง)", "role": "ถอดเนื้อ + timestamp ระดับคำ", "stage": "lyrics", "paths": [m / "whisper"], "vram_gb": 1.0, "auto_download": True, "required": False},
        {"id": "btc", "name": "BTC (คอร์ด)", "role": "จำแนกคอร์ดจาก instrumental", "stage": "chords", "paths": [THIRD_PARTY / "BTC"], "vram_gb": 0.3, "auto_download": False, "required": False},
    ]


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def list_models() -> dict:
    out = []
    for r in _registry():
        size = sum(_size(p) for p in r["paths"])
        present = all(p.exists() for p in r["paths"])
        out.append({"id": r["id"], "name": r["name"], "role": r["role"], "stage": r["stage"], "present": present, "size_bytes": size,
                    "vram_gb": r["vram_gb"], "required": r["required"], "auto_download": r["auto_download"],
                    "deletable": r["auto_download"] and present, "paths": [str(p) for p in r["paths"]]})
    total, _used, free = shutil.disk_usage(MODELS_DIR if MODELS_DIR.exists() else MODELS_DIR.parent)
    return {"models": out, "total_bytes": sum(m["size_bytes"] for m in out), "disk_free_bytes": free, "models_dir": str(MODELS_DIR)}


def delete_model(model_id: str) -> int:
    """ลบไฟล์ของโมเดลที่ดาวน์โหลดอัตโนมัติ คืนจำนวนไบต์ที่คืนพื้นที่; ValueError ถ้าไม่ได้รับอนุญาต"""
    r = next((x for x in _registry() if x["id"] == model_id), None)
    if r is None:
        raise ValueError("ไม่รู้จักโมเดล")
    if not r["auto_download"]:
        raise ValueError("โมเดลนี้ติดตั้งเอง ไม่ลบจาก UI (ลบเองในโฟลเดอร์ models/ หรือ third_party/)")
    freed = 0
    root = MODELS_DIR.resolve()
    for p in r["paths"]:
        if not p.exists():
            continue
        if root not in p.resolve().parents:
            raise ValueError("path อยู่นอก models/")
        freed += _size(p)
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    return freed
