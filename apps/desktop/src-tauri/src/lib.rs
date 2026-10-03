//! MeloTab desktop shell: เปิดหน้าต่าง (WebView2) + สตาร์ท Python backend (FastAPI :8000) ให้เอง และปิดตอนออกจากแอป
//!
//! หา backend ตามลำดับ: ตัวแปรแวดล้อม MELOTAB_ROOT → โฟลเดอร์ของ exe ขึ้นไปไม่เกิน 6 ชั้นที่มี backend/.venv
//! ถ้าพอร์ต 8000 มี backend รันอยู่แล้ว (เช่นเปิดเองตอน dev) จะไม่สตาร์ทซ้ำ; สตาร์ทแบบไม่บล็อกหน้าต่าง (log: %TEMP%\melotab-backend.log)
//! ข้อจำกัด: ตัวติดตั้งยังไม่ได้รวม Python/PyTorch/โมเดล (ใหญ่หลาย GB) — ต้องมีโฟลเดอร์ MeloTab ที่ตั้ง backend/.venv ไว้แล้ว

use std::net::{SocketAddr, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::Mutex;
use std::time::Duration;
use tauri::{Manager, RunEvent};

struct Backend(Mutex<Option<Child>>);

fn backend_up() -> bool {
    let addr: SocketAddr = "127.0.0.1:8000".parse().unwrap();
    TcpStream::connect_timeout(&addr, Duration::from_millis(300)).is_ok()
}

fn find_root() -> Option<PathBuf> {
    if let Ok(r) = std::env::var("MELOTAB_ROOT") {
        let p = PathBuf::from(r);
        if p.join("backend").join(".venv").exists() {
            return Some(p);
        }
    }
    let exe = std::env::current_exe().ok()?;
    let mut dir = exe.parent()?.to_path_buf();
    for _ in 0..6 {
        if dir.join("backend").join(".venv").exists() {
            return Some(dir);
        }
        dir = dir.parent()?.to_path_buf();
    }
    None
}

fn log_file() -> Option<std::fs::File> {
    std::fs::File::create(std::env::temp_dir().join("melotab-backend.log")).ok()
}

/// สตาร์ท backend (ไม่รอให้พร้อม — คืน Child ทันที; หน้าเว็บมี status bar บอกสถานะการเชื่อมต่อเอง)
fn start_backend() -> Option<Child> {
    if backend_up() {
        return None;
    }
    let root = find_root()?;
    let py = root.join("backend").join(".venv").join("Scripts").join("python.exe");
    let mut cmd = Command::new(py);
    cmd.args(["-m", "uvicorn", "melotab.api.app:app", "--port", "8000", "--log-level", "warning"])
        .current_dir(root.join("backend"))
        .stdin(Stdio::null());
    if let (Some(o), Some(e)) = (log_file(), log_file()) {
        cmd.stdout(Stdio::from(o)).stderr(Stdio::from(e)); // log อยู่ที่ %TEMP%\melotab-backend.log
    }
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW
    }
    cmd.spawn().ok()
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            app.manage(Backend(Mutex::new(start_backend())));
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("สร้างแอปไม่สำเร็จ")
        .run(|app, event| {
            if let RunEvent::Exit = event {
                if let Some(state) = app.try_state::<Backend>() {
                    if let Some(mut c) = state.0.lock().unwrap().take() {
                        let _ = c.kill();
                    }
                }
            }
        });
}
