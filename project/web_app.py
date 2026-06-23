import os
import shutil
import tempfile
import threading
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from core.chat_interface import ChatInterface
from core.document_manager import DocumentManager
from core.image_claim_extractor import IMAGE_EXTENSIONS, is_supported_image
from core.rag_system import RAGSystem


BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"


def _message_title(message):
    metadata = message.get("metadata") or {}
    return metadata.get("title") or message.get("title") or ""


def _normalise_messages(payload):
    if isinstance(payload, str):
        return [{"role": "assistant", "title": "检测状态", "content": payload}]

    if not isinstance(payload, list):
        return [{"role": "assistant", "title": "检测状态", "content": str(payload)}]

    messages = []
    for item in payload:
        if not isinstance(item, dict):
            messages.append({"role": "assistant", "title": "检测状态", "content": str(item)})
            continue
        messages.append(
            {
                "role": item.get("role", "assistant"),
                "title": _message_title(item),
                "content": str(item.get("content", "")),
            }
        )
    return messages


def _final_answer(messages):
    for message in reversed(messages):
        if message.get("role") == "assistant" and not message.get("title"):
            content = message.get("content", "").strip()
            if content:
                return content
    for message in reversed(messages):
        content = message.get("content", "").strip()
        if content:
            return content
    return "没有生成可展示的检测结果。"


def create_web_app():
    rag_system = RAGSystem()
    rag_system.initialize()
    doc_manager = DocumentManager(rag_system)
    chat_interface = ChatInterface(rag_system)
    request_lock = threading.Lock()

    app = FastAPI(title="RumorDetection RAG")
    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/api/database/summary")
    def database_summary():
        return {"summary": doc_manager.get_database_summary()}

    @app.post("/api/database/rebuild")
    def rebuild_database():
        with request_lock:
            result, parent_count, child_count = doc_manager.build_rumor_database()
        return {
            "summary": doc_manager.get_database_summary(),
            "rows": result["rows"],
            "parent_chunks": parent_count,
            "child_chunks": child_count,
        }

    @app.post("/api/session/reset")
    def reset_session():
        with request_lock:
            chat_interface.clear_session()
        return {"ok": True}

    @app.post("/api/detect")
    def detect(text: str = Form(""), image: UploadFile | None = File(None)):
        text = (text or "").strip()
        temp_path = None

        try:
            files = []
            if image and image.filename:
                suffix = Path(image.filename).suffix.lower()
                if suffix not in IMAGE_EXTENSIONS:
                    supported = ", ".join(sorted(IMAGE_EXTENSIONS))
                    raise HTTPException(status_code=400, detail=f"不支持的图片格式。支持格式：{supported}")

                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    shutil.copyfileobj(image.file, tmp)
                    temp_path = tmp.name

                if not is_supported_image(temp_path):
                    raise HTTPException(status_code=400, detail="上传文件不是有效图片。")
                files.append({"path": temp_path, "name": image.filename})

            if not text and not files:
                raise HTTPException(status_code=400, detail="请输入文本，或上传一张图片。")

            message = {"text": text, "files": files}
            latest_payload = None
            with request_lock:
                for payload in chat_interface.chat(message, []):
                    latest_payload = payload

            messages = _normalise_messages(latest_payload)
            return {
                "answer": _final_answer(messages),
                "messages": messages,
                "database": doc_manager.get_database_summary(),
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        finally:
            if temp_path:
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    return app
