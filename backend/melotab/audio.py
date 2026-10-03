"""Ingest: แปลงไฟล์เสียง/วิดีโอใด ๆ เป็น WAV 44.1 kHz stereo float32 + hash สำหรับ cache"""
import hashlib
import subprocess
from pathlib import Path

from .config import ANALYSIS_SR


def to_wav(src: Path, dst: Path, sr: int = ANALYSIS_SR) -> Path:
    """ffmpeg ต้องอยู่ใน PATH"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "2", "-ar", str(sr),
           "-c:a", "pcm_f32le", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg แปลงไฟล์ไม่สำเร็จ: {r.stderr.strip()}")
    return dst


def file_hash(path: Path, chunk: int = 1 << 20) -> str:
    """sha256 ของไฟล์ต้นฉบับ = key หลักของ cache (plan หัวข้อ 16.2)"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()
