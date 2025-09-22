import json
from pathlib import Path


# Keep this function in a file directly under project root / src
def get_mustrd_root() -> Path:
    return Path(__file__).parent


def is_json(myjson: str) -> bool:
    try:
        json.loads(myjson)
    except ValueError:
        return False
    return True
