"""Route for beta dashboard — mounted only when JARVIS_BETA_DASHBOARD=1"""
import os

from fastapi import APIRouter
from fastapi.responses import FileResponse, JSONResponse

from config.paths import STATIC_DIR

router = APIRouter()

@router.get("/beta-dashboard")
def get_beta_dashboard():
    # Laisse sync : renvoie un FileResponse (lecture/stream disque I/O bloquant).
    if os.environ.get('JARVIS_BETA_DASHBOARD') != '1':
        return JSONResponse({'error': 'Not enabled'}, status_code=404)
    path = os.path.join(STATIC_DIR, 'beta-dashboard.html')
    if not os.path.exists(path):
        return JSONResponse({'error': 'Not found'}, status_code=404)
    return FileResponse(path)
