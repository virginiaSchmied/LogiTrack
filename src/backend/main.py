from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import envios
from routers import auth_router
from routers import usuarios
from routers import auditoria

app = FastAPI(
    title="LogiTrack API",
    description="API backend del sistema de gestión de envíos logísticos.",
    version="0.1.0",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router.router)
app.include_router(envios.router)
app.include_router(usuarios.router)
app.include_router(auditoria.router)


@app.get("/", tags=["Health"])
def health_check():
    return {"status": "ok", "app": "LogiTrack API"}