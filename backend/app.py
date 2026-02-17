# AMA-599: Reduced to minimal re-export file
# All @app.* decorators have been removed - endpoints are now in api/routers/
from backend.main import app
from backend.database import get_ios_companion_pending_workouts

__all__ = ["app"]
