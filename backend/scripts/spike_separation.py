"""Spike Phase 0: รัน separation บนไฟล์เสียงหนึ่งไฟล์ แล้ววัดเวลา + VRAM สูงสุด (ผ่าน NVML)"""
import sys, time, threading
import pynvml
from audio_separator.separator import Separator

audio, model, outdir = sys.argv[1], sys.argv[2], sys.argv[3]

pynvml.nvmlInit()
h = pynvml.nvmlDeviceGetHandleByIndex(0)
peak = [0]
stop = threading.Event()

def poll():
    while not stop.is_set():
        used = pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20
        peak[0] = max(peak[0], used)
        time.sleep(0.2)

base = pynvml.nvmlDeviceGetMemoryInfo(h).used / 2**20
t = threading.Thread(target=poll, daemon=True); t.start()

sep = Separator(model_file_dir=r"D:\melotab\models", output_dir=outdir, output_format="FLAC")
t0 = time.time(); sep.load_model(model_filename=model); t1 = time.time()
files = sep.separate(audio); t2 = time.time()
stop.set()
print(f"RESULT model={model} load={t1-t0:.1f}s separate={t2-t1:.1f}s vram_base={base:.0f}MB vram_peak={peak[0]:.0f}MB delta={peak[0]-base:.0f}MB files={files}")
