import os
import stat
from pathlib import Path
from zoneinfo import ZoneInfo

APP_NAME = "calm"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

GOOGLE_CREDENTIALS_PATH = CONFIG_DIR / "credentials.json" 
GOOGLE_TOKEN_PATH = CONFIG_DIR / "token.json"

CAL_SCOPES = ["https://www.googleapis.com/auth/calendar"]
DEFAULT_TZ = ZoneInfo("Asia/Taipei")  

def ensure_600(path: Path):
    try:
        if os.name == "posix":
            path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 0o600
    except Exception:
        pass