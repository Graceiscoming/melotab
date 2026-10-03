"""ช่วยเรื่อง VRAM: ปลดโมเดลหลังจบแต่ละขั้น (plan หัวข้อ 18.2: โหลด → ประมวลผล → ปลด)"""
import gc


def free_gpu() -> None:
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except ImportError:
        pass
