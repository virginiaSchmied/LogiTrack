import uuid as _uuid_mod
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from database import get_db
from models import EventoDeUsuario, Envio, Direccion, EventoDeEnvio, EstadoEnvioEnum, AccionEnvioEnum, NivelPrioridadEnum, Usuario
from auth import hash_password, require_admin


router = APIRouter(prefix="/auditoria", tags=["Auditoría"])


@router.get("/eventos")
def obtener_eventos(
    usuario_afectado_uuid: Optional[str] = Query(None),
    usuario_ejecutor_uuid: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_admin),
):
    query = db.query(EventoDeUsuario)

    if usuario_afectado_uuid:
        query = query.filter(EventoDeUsuario.usuario_afectado_uuid == _uuid_mod.UUID(usuario_afectado_uuid))

    if usuario_ejecutor_uuid:
        query = query.filter(EventoDeUsuario.usuario_ejecutor_uuid == _uuid_mod.UUID(usuario_ejecutor_uuid))

    query = query.order_by(EventoDeUsuario.fecha_hora.desc())

    eventos = query.all()

    return eventos