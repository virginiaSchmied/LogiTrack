from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
app.include_router(envios.router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "app": "LogiTrack API"}