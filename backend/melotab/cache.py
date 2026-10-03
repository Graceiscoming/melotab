"""Cache ต่อขั้น (plan หัวข้อ 16.2): key = hash(เสียงต้นฉบับ + ชื่อขั้น + พารามิเตอร์ + เวอร์ชันโมเดล)

แต่ละ entry เป็นโฟลเดอร์ `cache/<key>/` + ไฟล์ `.done` (เขียนเสร็จจึงใช้ได้ กันไฟล์ค้างครึ่งทางเมื่อโปรแกรมล่ม)
ยังไม่มีการล้างแบบ LRU/จำกัดขนาด (ทำภายหลัง)
"""
import hashlib
import json
import shutil
from pathlib import Path

from .config import ROOT

DEFAULT_CACHE_DIR = ROOT / "cache"


def make_key(stage: str, audio_hash: str, **params) -> str:
    blob = json.dumps({"stage": stage, "audio": audio_hash, "params": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:24]


class StageCache:
    def __init__(self, root: Path = DEFAULT_CACHE_DIR):
        self.root = Path(root)

    def get(self, key: str) -> Path | None:
        d = self.root / key
        return d if (d / ".done").exists() else None

    def begin(self, key: str) -> Path:
        """โฟลเดอร์ชั่วคราวสำหรับเขียนผลลัพธ์ (ถ้ามีของค้างจากรอบที่ล้มจะถูกล้างก่อน)"""
        d = self.root / f"{key}.tmp"
        shutil.rmtree(d, ignore_errors=True)
        d.mkdir(parents=True)
        return d

    def commit(self, key: str) -> Path:
        tmp, final = self.root / f"{key}.tmp", self.root / key
        shutil.rmtree(final, ignore_errors=True)
        (tmp / ".done").write_text("ok")
        tmp.rename(final)
        return final
