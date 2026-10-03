"""FastAPI: REST สำหรับคำสั่ง + WebSocket `/ws` สำหรับ progress / system stats / heartbeat (plan หัวข้อ 20)

สร้างด้วย `create_app(...)` เพื่อให้เทสต์ใส่ runner ปลอม/โฟลเดอร์ชั่วคราวได้
รัน:  cd backend && .venv\\Scripts\\python -m uvicorn melotab.api.app:app --port 8000
"""
import asyncio
import contextlib
from pathlib import Path

import shutil
import tempfile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import monitor
from ..analysis import run_analysis
from ..audio import to_preview_mp3
from ..cache import StageCache
from ..jobs.manager import Job, JobManager
from ..retranscribe import retranscribe
from ..store import ProjectStore
from .. import tab as tabmod
from ..tab.theory import TUNINGS


class NewProject(BaseModel):
    source_path: str           # path ของไฟล์เสียงบนเครื่องนี้ (แอป desktop รันบนเครื่องเดียวกัน)
    title: str | None = None


class AnalyzeOptions(BaseModel):
    karaoke: bool = False
    dereverb: bool = False
    fix_octave: bool = True
    min_dur_ms: float = 0.0
    merge_gap_ms: float = 0.0


class RetranscribeOptions(BaseModel):
    fix_octave: bool = True
    min_dur_ms: float = 0.0
    merge_gap_ms: float = 0.0


class TabRequest(BaseModel):
    settings: dict = {}
    locked: dict[str, dict] = {}
    notes: list[dict] | None = None        # โน้ตปัจจุบันจากหน้าจอ (ถ้าไม่ส่ง ใช้ song.json ที่บันทึกไว้)


class AltRequest(TabRequest):
    note_id: str


class BlocksRequest(BaseModel):
    system: str = "position"               # position | pentatonic
    transpose: int = 0
    capo: int = 0
    tuning: str = "standard"
    key: dict | None = None                # ไม่ส่ง = ใช้คีย์ใน song.json
    selected: list[dict] = []              # block ที่เลือก (ใช้คำนวณ coverage)
    notes: list[dict] | None = None


class _Hub:
    """กระจาย event จาก worker เธรดไปยัง WebSocket ทุกตัว (ผ่าน asyncio.Queue ต่อ client)"""

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.clients: set[asyncio.Queue] = set()

    def publish(self, event: dict) -> None:          # เรียกจากเธรดไหนก็ได้
        if self.loop is None:
            return
        for q in list(self.clients):
            self.loop.call_soon_threadsafe(q.put_nowait, event)


def create_app(*, store: ProjectStore | None = None, cache: StageCache | None = None,
               runner=None, stats_interval: float = 1.0, allow_origins: list[str] | None = None) -> FastAPI:
    store = store or ProjectStore()
    cache = cache or StageCache()
    hub = _Hub()

    def default_runner(job: Job, on_event, cancelled) -> dict:
        return run_analysis(store.source_path(job.project_id), store.path(job.project_id),
                            karaoke=job.params.get("karaoke", False), dereverb=job.params.get("dereverb", False),
                            fix_octave=job.params.get("fix_octave", True), min_dur_ms=job.params.get("min_dur_ms", 0.0),
                            merge_gap_ms=job.params.get("merge_gap_ms", 0.0),
                            cache=cache, on_event=on_event, cancelled=cancelled)

    manager = JobManager(runner or default_runner)
    manager.subscribe(hub.publish)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        hub.loop = asyncio.get_running_loop()

        async def ticker():
            while True:
                hub.publish({"type": "heartbeat"})
                hub.publish({"type": "system.stats", **monitor.system_stats()})
                await asyncio.sleep(stats_interval)

        task = asyncio.create_task(ticker())
        yield
        task.cancel()
        manager.shutdown()

    app = FastAPI(title="MeloTab", lifespan=lifespan)
    # dev server ของ Vite รันคนละ port → อนุญาตเฉพาะ origin ที่ระบุ (ค่าเริ่มต้น: localhost เท่านั้น)
    app.add_middleware(CORSMiddleware, allow_origins=allow_origins or ["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["*"], allow_headers=["*"])
    app.state.manager, app.state.store = manager, store

    @app.get("/health")
    def health() -> dict:
        return {"ok": True}

    @app.post("/projects", status_code=201)
    def create_project(body: NewProject) -> dict:
        try:
            return store.create(Path(body.source_path), body.title)
        except FileNotFoundError as e:
            raise HTTPException(404, str(e))

    @app.post("/projects/upload", status_code=201)
    def upload_project(file: UploadFile = File(...), title: str | None = Form(None)) -> dict:
        """อัปโหลดไฟล์เสียง/วิดีโอจากเบราว์เซอร์ (เบราว์เซอร์ส่ง path เครื่องให้ไม่ได้)"""
        suffix = Path(file.filename or "audio").suffix or ".bin"
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / f"{Path(file.filename or 'audio').stem}{suffix}"
            with open(tmp, "wb") as f:
                shutil.copyfileobj(file.file, f)
            return store.create(tmp, title or Path(file.filename or "song").stem)

    @app.get("/projects")
    def list_projects() -> list[dict]:
        return store.list()

    @app.get("/projects/{pid}")
    def get_project(pid: str) -> dict:
        try:
            return {**store.meta(pid), "song": store.song(pid)}
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "ไม่พบโปรเจกต์")

    @app.get("/projects/{pid}/f0")
    def get_f0(pid: str) -> dict:
        try:
            c = store.f0_curve(pid)
        except ValueError:
            c = None
        if c is None:
            raise HTTPException(404, "ยังไม่มีเส้น f0 (ยังไม่ได้วิเคราะห์)")
        return c

    @app.put("/projects/{pid}/song")
    def put_song(pid: str, song: dict) -> dict:
        if "notes" not in song or not isinstance(song["notes"], list):
            raise HTTPException(422, "song ต้องมี notes")
        try:
            store.save_song(pid, song)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "ไม่พบโปรเจกต์")
        return {"ok": True, "notes": len(song["notes"])}

    @app.post("/projects/{pid}/retranscribe")
    def retranscribe_project(pid: str, opts: RetranscribeOptions) -> dict:
        """แกะโน้ตใหม่จากผลดิบที่เก็บไว้ (เร็ว ไม่รันโมเดลซ้ำ) — โน้ตที่แก้ไว้จะถูกแทนที่"""
        try:
            store.meta(pid)
            return retranscribe(store.path(pid), **opts.model_dump())
        except (FileNotFoundError, ValueError) as e:
            raise HTTPException(404, str(e))

    @app.get("/projects/{pid}/history")
    def song_history(pid: str) -> list[str]:
        try:
            return store.history(pid)
        except ValueError:
            raise HTTPException(404, "ไม่พบโปรเจกต์")

    @app.post("/projects/{pid}/history/{name}/restore")
    def restore_history(pid: str, name: str) -> dict:
        try:
            return store.restore(pid, name)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "ไม่พบ snapshot")

    # ---------------- Tab Engine ----------------
    def _song_or_404(pid: str) -> dict:
        try:
            song = store.song(pid)
        except ValueError:
            song = None
        if song is None:
            raise HTTPException(404, "ยังไม่มีโน้ต (ยังไม่ได้วิเคราะห์)")
        return song

    def _check_settings(s: dict) -> dict:
        if s.get("tuning", "standard") not in TUNINGS:
            raise HTTPException(422, f"tuning ไม่รู้จัก: {s.get('tuning')}")
        if not -12 <= int(s.get("transpose", 0)) <= 12 or not 0 <= int(s.get("capo", 0)) <= 12:
            raise HTTPException(422, "transpose ต้องอยู่ใน −12…12 และ capo ใน 0…12")
        return s

    @app.get("/projects/{pid}/tab")
    def get_tab(pid: str) -> dict:
        try:
            return store.tab(pid) or {}
        except ValueError:
            raise HTTPException(404, "ไม่พบโปรเจกต์")

    @app.put("/projects/{pid}/tab")
    def put_tab(pid: str, tab: dict) -> dict:
        if "events" not in tab:
            raise HTTPException(422, "tab ต้องมี events")
        try:
            store.save_tab(pid, tab)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "ไม่พบโปรเจกต์")
        return {"ok": True, "events": len(tab["events"])}

    @app.post("/projects/{pid}/tab/generate")
    def tab_generate(pid: str, body: TabRequest) -> dict:
        notes = body.notes if body.notes is not None else _song_or_404(pid)["notes"]
        res = tabmod.generate_tab(notes, _check_settings(body.settings), body.locked)
        res["locked"] = body.locked
        store.save_tab(pid, res)
        return res

    @app.post("/projects/{pid}/tab/alternatives")
    def tab_alternatives(pid: str, body: AltRequest) -> list[dict]:
        notes = body.notes if body.notes is not None else _song_or_404(pid)["notes"]
        return tabmod.alternatives(notes, _check_settings(body.settings), body.locked, body.note_id)

    @app.post("/projects/{pid}/tab/blocks")
    def tab_blocks(pid: str, body: BlocksRequest) -> dict:
        song = _song_or_404(pid)
        key = body.key or song.get("key")
        if not key:
            raise HTTPException(422, "ไม่มีคีย์ของเพลง ระบุ key เองได้")
        if body.tuning not in TUNINGS:
            raise HTTPException(422, "tuning ไม่รู้จัก")
        from ..tab.theory import NOTE_NAMES, pc_of
        tonic = NOTE_NAMES[(pc_of(key["tonic"]) + body.transpose) % 12]       # คีย์ของเสียงที่เล่นจริงหลัง transpose
        blocks = tabmod.generate_blocks(tonic, key["mode"], TUNINGS[body.tuning], body.capo, body.system)
        notes = body.notes if body.notes is not None else song["notes"]
        pitches = [n["midi"] + body.transpose for n in notes]
        cov = tabmod.coverage(pitches, body.selected, TUNINGS[body.tuning], body.capo) if body.selected else None
        return {"tonic": tonic, "mode": key["mode"], "blocks": blocks, "coverage": cov}

    @app.post("/projects/{pid}/keys/suggest")
    def keys_suggest(pid: str, body: TabRequest) -> dict:
        song = _song_or_404(pid)
        notes = body.notes if body.notes is not None else song["notes"]
        return tabmod.suggest(notes, song.get("key"), _check_settings(body.settings))

    @app.get("/tab/presets")
    def tab_presets() -> dict:
        return {"presets": list(tabmod.PRESETS), "tunings": list(TUNINGS)}

    @app.post("/projects/{pid}/analyze", status_code=202)
    def analyze(pid: str, opts: AnalyzeOptions | None = None) -> dict:
        try:
            store.meta(pid)
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "ไม่พบโปรเจกต์")
        o = opts or AnalyzeOptions()
        return manager.submit(pid, o.model_dump()).public()

    @app.get("/jobs")
    def jobs() -> list[dict]:
        return [j.public() for j in manager.list()]

    @app.get("/jobs/{jid}")
    def get_job(jid: str) -> dict:
        j = manager.get(jid)
        if not j:
            raise HTTPException(404, "ไม่พบงาน")
        return j.public()

    @app.post("/jobs/{jid}/cancel")
    def cancel(jid: str) -> dict:
        if not manager.cancel(jid):
            raise HTTPException(409, "ยกเลิกไม่ได้ (ไม่พบงาน หรืองานจบไปแล้ว)")
        return manager.get(jid).public()

    @app.get("/audio/{pid}/{stem}")
    def audio(pid: str, stem: str):
        try:
            p = store.stem_path(pid, stem)
            wav = store.path(pid) / "audio" / "source.wav"
            if not p and stem == "mix" and wav.exists():          # โปรเจกต์เก่าที่วิเคราะห์ก่อนมี mix.mp3
                p = to_preview_mp3(wav, store.path(pid) / "audio" / "mix.mp3")
        except ValueError:
            p = None
        if not p:
            raise HTTPException(404, "ไม่พบไฟล์เสียง")
        return FileResponse(p)

    @app.websocket("/ws")
    async def ws(sock: WebSocket):
        await sock.accept()
        q: asyncio.Queue = asyncio.Queue()
        hub.clients.add(q)
        try:
            await sock.send_json({"type": "hello", "jobs": [j.public() for j in manager.list()]})
            while True:
                await sock.send_json(await q.get())
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(q)

    return app


app = create_app()
