from pathlib import Path

WORKSPACE = (Path(__file__).parent.parent / "workspace").resolve()

MAX_FILE_SIZE = 100_000


def safe_path(relative_path):
    target = (WORKSPACE / relative_path).resolve()

    if not target.is_relative_to(WORKSPACE):
        raise PermissionError("Access outside workspace is prohibited.")

    return target


def list_files(relative_path="."):
    directory = safe_path(relative_path)

    if not directory.is_dir():
        raise ValueError("Directory does not exist.")

    return [
        {
            "name": item.name,
            "type": "directory" if item.is_dir() else "file"
        }
        for item in sorted(directory.iterdir())
    ]


def read_file(relative_path):
    file_path = safe_path(relative_path)

    if not file_path.is_file():
        raise ValueError("File does not exist.")

    if file_path.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 100 KB reading limit.")

    return file_path.read_text(encoding="utf-8")

def write_file(relative_path, content):
    if not isinstance(content, str):
        raise ValueError("File content must be text.")

    if len(content.encode("utf-8")) > MAX_FILE_SIZE:
        raise ValueError("File exceeds the 100 KB writing limit.")

    file_path = safe_path(relative_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return f"File saved successfully: {relative_path}"

def delete_file(relative_path):
    file_path = safe_path(relative_path)

    if not file_path.is_file():
        raise ValueError("File does not exist.")

    file_path.unlink()

    return f"File deleted successfully: {relative_path}"


if __name__ == "__main__":
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    print("NEXUS AI FILESYSTEM")
    print("------------------")
    print("Workspace:", WORKSPACE)
    print("Status: READY")
