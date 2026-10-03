"""Job manager: คิวงานวิเคราะห์ + worker เธรดเดียว (GPU ถูกใช้ทีละงาน — plan หัวข้อ 4/18.2)

- งานหนักทั้งหมดรันใน worker เธรด ไม่บล็อก API/UI
- เหตุการณ์ (job.queued / job.stage / job.done / job.error / job.cancelled) ถูกส่งให้ subscriber (WebSocket hub)
- ยกเลิกงานที่ "รออยู่ในคิว" ได้ทันที; งานที่กำลังรันยกเลิกได้ระหว่างขั้น (ไม่ขัดจังหวะโมเดลกลางคัน)
"""
import queue
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, field
from typing import Callable

from ..analysis import Cancelled

Runner = Callable[["Job", Callable[[dict], None], Callable[[], bool]], dict]


@dataclass
class Job:
    id: str
    project_id: str
    params: dict
    status: str = "queued"           # queued | running | done | error | cancelled
    overall_pct: float = 0.0
    stage: str | None = None
    error: str | None = None
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    cancel_requested: bool = False

    def public(self) -> dict:
        return {"id": self.id, "project_id": self.project_id, "params": self.params, "status": self.status,
                "overall_pct": self.overall_pct, "stage": self.stage, "error": self.error,
                "elapsed_s": round((self.finished or time.time()) - self.started, 1) if self.started else 0.0}


class JobManager:
    def __init__(self, runner: Runner):
        self._runner = runner
        self._jobs: dict[str, Job] = {}
        self._q: "queue.Queue[str | None]" = queue.Queue()
        self._subs: list[Callable[[dict], None]] = []
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._loop, name="melotab-worker", daemon=True)
        self._thread.start()

    # --- subscribers ---
    def subscribe(self, fn: Callable[[dict], None]) -> Callable[[], None]:
        with self._lock:
            self._subs.append(fn)
        return lambda: self._subs.remove(fn) if fn in self._subs else None

    def _emit(self, event: dict) -> None:
        for fn in list(self._subs):
            try:
                fn(event)
            except Exception:       # subscriber พังต้องไม่ทำให้งานล้ม
                traceback.print_exc()

    # --- public API ---
    def submit(self, project_id: str, params: dict) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], project_id=project_id, params=params)
        with self._lock:
            self._jobs[job.id] = job
        self._q.put(job.id)
        self._emit({"type": "job.queued", "job_id": job.id, "project_id": project_id})
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        return sorted(self._jobs.values(), key=lambda j: j.created, reverse=True)

    def cancel(self, job_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.status in ("done", "error", "cancelled"):
            return False
        job.cancel_requested = True
        if job.status == "queued":          # ยังไม่เริ่ม → ยกเลิกทันที (worker จะข้ามเมื่อหยิบมา)
            job.status, job.finished = "cancelled", time.time()
            self._emit({"type": "job.cancelled", "job_id": job.id})
        return True

    def shutdown(self) -> None:
        self._q.put(None)

    # --- worker ---
    def _loop(self) -> None:
        while True:
            jid = self._q.get()
            if jid is None:
                return
            job = self._jobs[jid]
            if job.status != "queued":
                continue
            job.status, job.started = "running", time.time()

            def on_event(e: dict, _job=job) -> None:
                if e.get("type") == "job.stage":
                    _job.stage, _job.overall_pct = e["stage"], e.get("overall_pct", _job.overall_pct)
                self._emit({**e, "job_id": _job.id})

            try:
                self._runner(job, on_event, lambda _j=job: _j.cancel_requested)
                job.status, job.overall_pct = "done", 100.0
                job.finished = time.time()
                self._emit({"type": "job.done", "job_id": job.id, "project_id": job.project_id})
            except Cancelled:
                job.status, job.finished = "cancelled", time.time()
                self._emit({"type": "job.cancelled", "job_id": job.id})
            except Exception as ex:          # noqa: BLE001  — รายงานข้อความอ่านรู้เรื่อง ไม่ให้ worker ตาย
                job.status, job.finished = "error", time.time()
                job.error = f"{type(ex).__name__}: {ex}"
                traceback.print_exc()
                self._emit({"type": "job.error", "job_id": job.id, "message": job.error})
