"""รัน BTC (chord recognition) ในโปรเซสแยก — เรียกด้วย `python -m melotab.pipeline.btc_worker AUDIO OUT.lab [--voca]` โดย cwd = third_party/BTC

เหตุผลที่ต้องแยกโปรเซส: แพ็กเกจ `utils` ของ BTC ชื่อชนกับ `utils` ของ SOME ที่ใช้ in-process
shim ความเข้ากันได้ (โค้ด BTC เก่า) ทำตอนรันที่นี่ ไม่ต้องแก้ไฟล์ใน third_party/:
  - numpy 2.x ลบ np.float/np.int/np.bool → ใส่ alias กลับ
  - yaml.load() ต้องมี Loader → ใช้ safe_load
  - torch.load ค่าเริ่มต้น weights_only=True ปฏิเสธไฟล์น้ำหนักเก่า → ตั้ง False (โหลดได้เฉพาะไฟล์น้ำหนักที่มากับ repo BTC ที่เชื่อถือ)
"""
import argparse
import os
import sys
import warnings

import numpy as np
import torch
import yaml

warnings.filterwarnings("ignore")

for _n, _t in (("float", float), ("int", int), ("bool", bool)):          # numpy 2.x
    if not hasattr(np, _n):
        setattr(np, _n, _t)
_yaml_load = yaml.load


def _load_with_default_loader(stream, Loader=None, **kw):               # yaml เวอร์ชันใหม่บังคับต้องระบุ Loader — ใช้ SafeLoader เป็นค่าเริ่มต้น
    return _yaml_load(stream, Loader=Loader or yaml.SafeLoader, **kw)   # (ห้ามเรียก yaml.safe_load ที่นี่ เพราะภายในมันเรียก yaml.load → วนซ้ำ)


yaml.load = _load_with_default_loader
_torch_load = torch.load
torch.load = lambda *a, **kw: _torch_load(*a, **{**kw, "weights_only": False})   # noqa: E731


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("out")
    ap.add_argument("--voca", action="store_true", help="large vocabulary (7th, sus ฯลฯ) — ละเอียดกว่าแต่สั่นกว่า")
    a = ap.parse_args()

    sys.path.insert(0, os.getcwd())                                       # cwd ต้องเป็น third_party/BTC
    from btc_model import BTC_model, HParams                              # noqa: E402
    from utils.mir_eval_modules import audio_file_to_features, idx2chord, idx2voca_chord  # noqa: E402

    config = HParams.load("run_config.yaml")
    if a.voca:
        config.feature["large_voca"] = True
        config.model["num_chords"] = 170
        model_file, idx_to_chord = "./test/btc_model_large_voca.pt", idx2voca_chord()
    else:
        model_file, idx_to_chord = "./test/btc_model.pt", idx2chord
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = BTC_model(config=config.model).to(device)
    ckpt = torch.load(model_file, map_location=device)
    mean, std = ckpt["mean"], ckpt["std"]
    model.load_state_dict(ckpt["model"])

    feature, per_sec, _ = audio_file_to_features(a.audio, config)
    feature = (feature.T - mean) / std
    n_t = config.model["timestep"]
    pad = n_t - (feature.shape[0] % n_t)
    feature = np.pad(feature, ((0, pad), (0, 0)), mode="constant", constant_values=0)
    n_inst = feature.shape[0] // n_t
    x = torch.tensor(feature, dtype=torch.float32).unsqueeze(0).to(device)

    lines, start, prev = [], 0.0, None
    with torch.no_grad():
        model.eval()
        for t in range(n_inst):
            enc, _ = model.self_attn_layers(x[:, n_t * t:n_t * (t + 1), :])
            pred, _ = model.output_layer(enc)
            pred = pred.squeeze()
            for i in range(n_t):
                c = pred[i].item()
                now = per_sec * (n_t * t + i)
                if prev is None:
                    prev = c
                    continue
                if c != prev:
                    lines.append(f"{start:.3f} {now:.3f} {idx_to_chord[prev]}\n")
                    start, prev = now, c
        end = per_sec * (n_inst * n_t - pad)
        if prev is not None and end > start:
            lines.append(f"{start:.3f} {end:.3f} {idx_to_chord[prev]}\n")
    with open(a.out, "w", encoding="utf-8") as f:
        f.writelines(lines)


if __name__ == "__main__":
    main()
