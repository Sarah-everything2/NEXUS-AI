from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from tools.filesystem import WORKSPACE, MAX_FILE_SIZE

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])

# Pending requests remain in memory, as in the previous implementation.
# Each request is now bound to the account that created it.
pending_writes = {}


class WriteRequest(BaseModel):
    path: str
    content: str


class ApprovalRequest(BaseModel):
    request_id: str
    confirmation: str


def _identity(http_request: Request):
    user = getattr(http_request.state, "current_user", None)

    if not isinstance(user, dict):
        raise HTTPException(401, "Authentication required.")

    user_id = user.get("id")
    role = user.get("role")

    if not isinstance(user_id, int) or user_id < 1:
        raise HTTPException(403, "Invalid account identity.")

    if role not in ("admin", "user"):
        raise HTTPException(403, "Account role is not permitted.")

    return user_id, role


def _account_root(user_id: int, role: str) -> Path:
    if role == "admin":
        root = WORKSPACE.resolve()
    else:
        root = (WORKSPACE / "users" / str(user_id)).resolve()

    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def _safe_target(root: Path, relative_path: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise ValueError("A valid relative file path is required.")

    target = (root / relative_path).resolve()

    if not target.is_relative_to(root):
        raise PermissionError("Access outside your workspace is prohibited.")

    return target


def _list_files(root: Path, relative_path: str):
    directory = _safe_target(root, relative_path)

    if not directory.is_dir():
        raise ValueError("Directory does not exist.")

    return [
        {
            "name": item.name,
            "type": "directory" if item.is_dir() else "file"
        }
        for item in sorted(directory.iterdir())
    ]


def _read_file(root: Path, relative_path: str):
    file_path = _safe_target(root, relative_path)

    if not file_path.is_file():
        raise ValueError("File does not exist.")

    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 100 KB reading limit.")

    return file_path.read_text(encoding="utf-8")


def _write_file(root: Path, relative_path: str, content: str):
    if not isinstance(content, str):
        raise ValueError("File content must be text.")

    if len(content.encode("utf-8")) > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 100 KB writing limit.")

    file_path = _safe_target(root, relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)

    # Re-check after creating parent directories, including symlink resolution.
    file_path = _safe_target(root, relative_path)
    file_path.write_text(content, encoding="utf-8")

    return f"File saved successfully: {relative_path}"


@router.get("/files")
def workspace_files(http_request: Request, path: str = Query(default=".")):
    user_id, role = _identity(http_request)

    try:
        root = _account_root(user_id, role)
        return {"files": _list_files(root, path)}
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/read")
def workspace_read(http_request: Request, path: str = Query(...)):
    user_id, role = _identity(http_request)

    try:
        root = _account_root(user_id, role)
        return {
            "path": path,
            "content": _read_file(root, path)
        }
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/write/request")
def request_file_write(request: WriteRequest, http_request: Request):
    user_id, role = _identity(http_request)

    if not request.path.strip():
        raise HTTPException(400, "File path is required.")

    if not isinstance(request.content, str):
        raise HTTPException(400, "File content must be text.")

    if len(request.content.encode("utf-8")) > MAX_FILE_SIZE:
        raise HTTPException(400, "File exceeds the 100 KB limit.")

    try:
        root = _account_root(user_id, role)
        _safe_target(root, request.path)
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))

    request_id = str(uuid4())
    pending_writes[request_id] = {
        "owner_id": user_id,
        "role": role,
        "path": request.path,
        "content": request.content
    }

    return {
        "status": "PENDING_APPROVAL",
        "request_id": request_id,
        "message": "File creation requires your approval."
    }


@router.get("/write/pending")
def get_pending_writes(http_request: Request):
    user_id, _role = _identity(http_request)

    return {
        "requests": [
            {
                "request_id": request_id,
                "path": item["path"]
            }
            for request_id, item in pending_writes.items()
            if item.get("owner_id") == user_id
        ]
    }


@router.post("/write/approve")
def approve_file_write(request: ApprovalRequest, http_request: Request):
    user_id, _role = _identity(http_request)

    if request.confirmation != "APPROVE":
        raise HTTPException(403, "Explicit approval is required.")

    item = pending_writes.get(request.request_id)

    if item is None or item.get("owner_id") != user_id:
        raise HTTPException(404, "Approval request not found.")

    try:
        root = _account_root(item["owner_id"], item["role"])
        result = _write_file(root, item["path"], item["content"])
        del pending_writes[request.request_id]

        return {
            "status": "APPROVED_AND_SAVED",
            "result": result
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))
