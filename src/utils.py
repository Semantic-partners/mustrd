from pathlib import Path


# Keep this function in a file directly under project root / src
def get_project_root() -> Path:
    return Path(__file__).parent.parent
