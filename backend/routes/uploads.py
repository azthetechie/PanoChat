"""File upload endpoint (local filesystem)."""
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from auth import get_current_user

router = APIRouter(prefix="/uploads", tags=["uploads"])

ALLOWED_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _upload_dir() -> Path:
    path = Path(os.environ.get("UPLOAD_DIR", "/app/backend/uploads"))
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...), _user: dict = Depends(get_current_user)
):
    max_mb = int(os.environ.get("MAX_UPLOAD_MB", "15"))
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Unsupported extension. Allowed: {sorted(ALLOWED_EXT)}")

    contents = await file.read()
    if len(contents) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large (max {max_mb}MB)")

    filename = f"{uuid.uuid4().hex}{ext}"
    dest = _upload_dir() / filename
    dest.write_bytes(contents)

    url = f"/api/uploads/file/{filename}"
    return {
        "url": url,
        "filename": filename,
        "content_type": file.content_type or "image/*",
        "size": len(contents),
        "type": "gif" if ext == ".gif" else "image",
    }


@router.get("/file/{filename}")
async def serve_file(filename: str):
    from fastapi.responses import FileResponse

    # Sanitize
    safe = os.path.basename(filename)
    path = _upload_dir() / safe
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)
