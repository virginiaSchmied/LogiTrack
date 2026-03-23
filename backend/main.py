from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from routers import envios

app = FastAPI(
    title="LogiTrack API",
    description="API backend del sistema de gestión de envíos logísticos.",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# Permite que el frontend consuma la API.
# En producción restringir origins a la URL real del frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(envios.router, prefix="/api")

# ── Frontend estático ─────────────────────────────────────────────────────────
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

@app.get("/{full_path:path}", include_in_schema=False)
async def serve_frontend(full_path: str):
    file = FRONTEND_DIR / full_path
    if file.is_file():
        return FileResponse(file)
    return FileResponse(FRONTEND_DIR / "index.html")