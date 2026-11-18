from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from uuid import uuid4

from skills.executor import execute_skill
from tools.filesystem import write_file

router = APIRouter(prefix="/api/workspace", tags=["Workspace"])

pending_writes = {}


class WriteRequest(BaseModel):
    path: str
    content: str


class ApprovalRequest(BaseModel):
    request_id: str
    confirmation: str


@router.get("/files")
def workspace_files(path: str = Query(default=".")):
    try:
        return {
            "files": execute_skill(
                "file_management",
                "list",
                relative_path=path
            )
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.get("/read")
def workspace_read(path: str = Query(...)):
    try:
        return {
            "path": path,
            "content": execute_skill(
                "file_management",
                "read",
                relative_path=path
            )
        }
    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))


@router.post("/write/request")
def request_file_write(request: WriteRequest):

    if not request.path.strip():
        raise HTTPException(400, "File path is required.")

    if not isinstance(request.content, str):
        raise HTTPException(400, "File content must be text.")

    if len(request.content.encode("utf-8")) > 100_000:
        raise HTTPException(400, "File exceeds the 100 KB limit.")

    request_id = str(uuid4())

    pending_writes[request_id] = {
        "path": request.path,
        "content": request.content
    }

    return {
        "status": "PENDING_APPROVAL",
        "request_id": request_id,
        "message": "File creation requires your approval."
    }


@router.get("/write/pending")
def get_pending_writes():

    return {
        "requests": [
            {
                "request_id": request_id,
                "path": item["path"]
            }
            for request_id, item in pending_writes.items()
        ]
    }


@router.post("/write/approve")
def approve_file_write(request: ApprovalRequest):

    if request.confirmation != "APPROVE":
        raise HTTPException(403, "Explicit approval is required.")

    item = pending_writes.get(request.request_id)

    if item is None:
        raise HTTPException(404, "Approval request not found.")

    try:
        result = write_file(item["path"], item["content"])
        del pending_writes[request.request_id]

        return {
            "status": "APPROVED_AND_SAVED",
            "result": result
        }

    except Exception as error:
        raise HTTPException(status_code=400, detail=str(error))