import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
from backend.config import settings


async def cleanup_expired_sessions() -> None:
    """Remove session directories older than SESSION_TTL_HOURS."""
    base = Path(settings.sessions_base_dir)
    if not base.exists():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.session_ttl_hours)
    for session_dir in base.iterdir():
        if not session_dir.is_dir():
            continue
        mtime = datetime.fromtimestamp(session_dir.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            shutil.rmtree(session_dir, ignore_errors=True)
