import glob
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import dotenv_values, load_dotenv, set_key
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────

_MAX_LOGS = 500
_log_records: list = []
_log_lock = threading.Lock()


class _PortalLogHandler(logging.Handler):
    def emit(self, record):
        entry = {
            "ts": datetime.now().strftime("%H:%M:%S"),
            "level": record.levelname,
            "msg": self.format(record),
        }
        with _log_lock:
            _log_records.append(entry)
            if len(_log_records) > _MAX_LOGS:
                _log_records.pop(0)


_portal_handler = _PortalLogHandler()
_portal_handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[logging.StreamHandler(), _portal_handler])
logger = logging.getLogger("portal")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="PDF AI Annotator")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ── Processor state ───────────────────────────────────────────────────────────

_processor_thread: Optional[threading.Thread] = None
_stop_event = threading.Event()
_stats = {"processed": 0, "errors": 0, "last_file": None, "started_at": None}
_stats_lock = threading.Lock()


def _run_processor() -> None:
    # Lazy import so env is fully loaded before genai client is created
    from pdf_ai_annotator import process_file  # noqa: PLC0415

    input_dir = os.getenv("INPUT_DIR", "")
    output_dir = os.getenv("OUTPUT_DIR", "")
    file_pattern = os.getenv("FILE_PATTERN", "*.pdf")
    poll_interval = int(os.getenv("POLL_INTERVAL", "5"))
    task_pause = int(os.getenv("TASK_PAUSE_TIME", "60"))

    if not input_dir or not os.path.isdir(input_dir):
        logger.error(f"INPUT_DIR '{input_dir}' does not exist — processor aborted")
        return
    if not output_dir or not os.path.isdir(output_dir):
        logger.error(f"OUTPUT_DIR '{output_dir}' does not exist — processor aborted")
        return

    logger.info(f"Processor started — watching {input_dir} for {file_pattern}")

    while not _stop_event.is_set():
        try:
            files = glob.glob(os.path.join(input_dir, file_pattern))
            for path in files:
                if _stop_event.is_set():
                    break
                try:
                    process_file(path, output_dir, cautious=False)
                    with _stats_lock:
                        _stats["processed"] += 1
                        _stats["last_file"] = os.path.basename(path)
                except Exception as exc:
                    logger.error(f"Failed to process '{os.path.basename(path)}': {exc}")
                    with _stats_lock:
                        _stats["errors"] += 1
                if _stop_event.wait(task_pause):
                    break
        except Exception as exc:
            logger.error(f"Processor loop error: {exc}")
        _stop_event.wait(poll_interval)

    logger.info("Processor stopped.")


# ── Page routes ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    is_running = _processor_thread is not None and _processor_thread.is_alive()
    with _stats_lock:
        s = dict(_stats)
    config = dotenv_values(".env") if os.path.exists(".env") else {}
    return templates.TemplateResponse(request, "dashboard.html", {
        "is_running": is_running,
        "stats": s,
        "config": config,
    })


@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request, msg: str = ""):
    input_dir = os.getenv("INPUT_DIR", "")
    output_dir = os.getenv("OUTPUT_DIR", "")

    def list_dir(d: str) -> list:
        if not d or not os.path.isdir(d):
            return []
        result = []
        for f in Path(d).iterdir():
            if f.is_file():
                st = f.stat()
                result.append({
                    "name": f.name,
                    "size_kb": round(st.st_size / 1024, 1),
                    "modified": datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M"),
                })
        return sorted(result, key=lambda x: x["modified"], reverse=True)

    return templates.TemplateResponse(request, "files.html", {
        "input_files": list_dir(input_dir),
        "output_files": list_dir(output_dir),
        "input_dir": input_dir,
        "output_dir": output_dir,
        "msg": msg,
    })


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    input_dir = os.getenv("INPUT_DIR", "")
    if not input_dir or not os.path.isdir(input_dir):
        raise HTTPException(400, "INPUT_DIR is not configured or does not exist")
    safe_name = os.path.basename(file.filename or "upload.pdf")
    dest = os.path.join(input_dir, safe_name)
    with open(dest, "wb") as fh:
        fh.write(await file.read())
    logger.info(f"Uploaded: {safe_name}")
    return RedirectResponse("/files?msg=uploaded", status_code=303)


@app.post("/files/delete/{location}/{filename:path}")
async def delete_file(location: str, filename: str):
    if location == "input":
        base = os.getenv("INPUT_DIR", "")
    elif location == "output":
        base = os.getenv("OUTPUT_DIR", "")
    else:
        raise HTTPException(400, "Invalid location")
    if not base:
        raise HTTPException(400, "Directory not configured")
    path = os.path.join(base, os.path.basename(filename))
    if not os.path.isfile(path):
        raise HTTPException(404, "File not found")
    os.remove(path)
    logger.info(f"Deleted {filename} from {location}")
    return RedirectResponse("/files?msg=deleted", status_code=303)


@app.get("/config", response_class=HTMLResponse)
async def config_page(request: Request, saved: str = ""):
    config = dotenv_values(".env") if os.path.exists(".env") else {}
    return templates.TemplateResponse(request, "config.html", {
        "config": config,
        "saved": bool(saved),
    })


@app.post("/config")
async def save_config(
    GEMINI_KEY: str = Form(""),
    INPUT_DIR: str = Form(""),
    OUTPUT_DIR: str = Form(""),
    FILE_PATTERN: str = Form("*.pdf"),
    POLL_INTERVAL: str = Form("5"),
    TASK_PAUSE_TIME: str = Form("60"),
    CAUTIOUS: str = Form("false"),
):
    env_file = ".env"
    if not os.path.exists(env_file):
        Path(env_file).touch()
    for key, val in [
        ("GEMINI_KEY", GEMINI_KEY),
        ("INPUT_DIR", INPUT_DIR),
        ("OUTPUT_DIR", OUTPUT_DIR),
        ("FILE_PATTERN", FILE_PATTERN),
        ("POLL_INTERVAL", POLL_INTERVAL),
        ("TASK_PAUSE_TIME", TASK_PAUSE_TIME),
        ("CAUTIOUS", CAUTIOUS),
    ]:
        set_key(env_file, key, val)
    load_dotenv(override=True)
    logger.info("Configuration saved.")
    return RedirectResponse("/config?saved=1", status_code=303)


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    with _log_lock:
        recent = list(_log_records[-200:])
    return templates.TemplateResponse(request, "logs.html", {
        "logs": recent,
    })


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def api_logs():
    with _log_lock:
        return {"logs": list(_log_records[-200:])}


@app.get("/api/status")
async def api_status():
    is_running = _processor_thread is not None and _processor_thread.is_alive()
    with _stats_lock:
        return {"is_running": is_running, **_stats}


@app.post("/api/processor/start")
async def api_start():
    global _processor_thread, _stop_event
    if _processor_thread and _processor_thread.is_alive():
        return {"status": "already_running"}
    _stop_event = threading.Event()
    with _stats_lock:
        _stats["started_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _processor_thread = threading.Thread(target=_run_processor, daemon=True, name="annotator")
    _processor_thread.start()
    return {"status": "started"}


@app.post("/api/processor/stop")
async def api_stop():
    _stop_event.set()
    return {"status": "stopping"}


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run("web_portal:app", host="0.0.0.0", port=8000, reload=False)
