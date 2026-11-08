"""Create local credentials interactively without overwriting existing .env."""
import getpass
import hashlib
from pathlib import Path
import secrets

path = Path(__file__).resolve().parents[1] / ".env"
if path.exists():
    raise SystemExit(".env exists. Edit it manually; existing configuration preserved.")
username = input("Demo username: ").strip()
password = getpass.getpass("Demo password (at least 12 characters): ")
if not username or len(password) < 12:
    raise SystemExit("Username required, password must contain at least 12 characters")
salt = secrets.token_bytes(16)
encoded = "pbkdf2_sha256$310000$"+salt.hex()+"$"+hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310000).hex()
with path.open("x", encoding="utf-8") as output:
    output.write("DEMO_USER="+username+"\nDEMO_PASSWORD_HASH='"+encoded+"'\nJWT_SECRET="+secrets.token_urlsafe(48)+"\nTASK_MODE=local\nOLLAMA_BASE_URL=http://127.0.0.1:11434\nVLM_MODEL=qwen3-vl:4b\nVLM_NUM_PREDICT=4000\n")
print("Created local .env. Start Redis and worker before changing TASK_MODE to celery.")
