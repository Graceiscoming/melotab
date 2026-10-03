"""สถิติเครื่อง (plan หัวข้อ 17): GPU util/VRAM/อุณหภูมิ ผ่าน NVML + CPU/RAM ผ่าน psutil"""
import psutil

try:
    import pynvml
    pynvml.nvmlInit()
    _GPU = pynvml.nvmlDeviceGetHandleByIndex(0)
except Exception:          # ไม่มี GPU/driver — รายงานเฉพาะ CPU/RAM
    pynvml, _GPU = None, None


def system_stats() -> dict:
    vm = psutil.virtual_memory()
    s = {"cpu_pct": psutil.cpu_percent(interval=None), "ram_used_gb": round(vm.used / 2**30, 2),
         "ram_total_gb": round(vm.total / 2**30, 1), "gpu": None}
    if _GPU is not None:
        try:
            mem = pynvml.nvmlDeviceGetMemoryInfo(_GPU)
            s["gpu"] = {
                "name": pynvml.nvmlDeviceGetName(_GPU),
                "util_pct": pynvml.nvmlDeviceGetUtilizationRates(_GPU).gpu,
                "vram_used_gb": round(mem.used / 2**30, 2), "vram_total_gb": round(mem.total / 2**30, 1),
                "temp_c": pynvml.nvmlDeviceGetTemperature(_GPU, pynvml.NVML_TEMPERATURE_GPU),
            }
        except Exception:
            pass
    return s
