"""FastAPI: REST สำหรับคำสั่ง + WebSocket `/ws` สำหรับ progress / system stats / heartbeat (plan หัวข้อ 20)

สร้างด้วย `create_app(...)` เพื่อให้เทสต์ใส่ runner ปลอม/โฟลเดอร์ชั่วคราวได้
รัน:  cd backend && .venv\\Scripts\\python -m uvicorn melotab.api.app:app --port 8000
"""
import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import monitor
from ..analysis import run_analysis
from ..cache import StageCache
from ..jobs.manager import Job, JobManager
from ..store import ProjectStore


class NewProject(BaseModel):
    source_path: str           # path ของไฟล์เสียงบนเครื่องนี้ (แอป desktop รันบนเครื่องเดียวกัน)
    title: str | None = None


class AnalyzeOptions(BaseModel):
    karaoke: bool = False
    dereverb: bool = False


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

    @app.get("/projects")
    def list_projects() -> list[dict]:
        return store.list()

    @app.get("/projects/{pid}")
    def get_project(pid: str) -> dict:
        try:
            return {**store.meta(pid), "song": store.song(pid)}
        except (FileNotFoundError, ValueError):
            raise HTTPException(404, "ไม่พบโปรเจกต์")

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
