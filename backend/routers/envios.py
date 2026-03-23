import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db
from models import Envio, Direccion, EventoDeEnvio, EstadoEnvioEnum, AccionEnvioEnum
from schemas import EnvioCreate, EnvioOut, EnvioListItem, EnvioListResponse

router = APIRouter(prefix="/envios", tags=["Envíos"])


def _generar_tracking_id(db: Session) -> str:
    """Genera el próximo tracking ID correlativo en formato LT-00000001."""
    ultimo = (
        db.query(Envio)
        .order_by(Envio.created_at.desc())
        .first()
    )
    if ultimo and ultimo.tracking_id.startswith("LT-"):
        try:
            numero = int(ultimo.tracking_id.split("LT-")[1]) + 1
        except ValueError:
            numero = 1
    else:
        numero = 1
    return f"LT-{str(numero).zfill(8)}"


def _build_envio_list_item(envio: Envio) -> EnvioListItem:
    """Construye el schema de listado a partir del modelo ORM."""
    return EnvioListItem(
        uuid=envio.uuid,
        tracking_id=envio.tracking_id,
        remitente=envio.remitente,
        destinatario=envio.destinatario,
        ciudad_origen=envio.direccion_origen.ciudad,
        provincia_origen=envio.direccion_origen.provincia,
        ciudad_destino=envio.direccion_destino.ciudad,
        provincia_destino=envio.direccion_destino.provincia,
        estado=envio.estado,
        prioridad=envio.prioridad,
        fecha_entrega_estimada=envio.fecha_entrega_estimada,
        created_at=envio.created_at,
    )


# ── POST /envios ─────────────────────────────────────────────────────────────

@router.post("/", response_model=EnvioOut, status_code=201)
def crear_envio(payload: EnvioCreate, db: Session = Depends(get_db)):
    """
    Registra un nuevo envío con sus direcciones de origen y destino.
    Genera el tracking ID automáticamente y registra el EventoDeEnvio de CREACION.
    Cubre LP-2.
    """
    # 1. Persistir dirección de origen
    origen = Direccion(
        id=uuid.uuid4(),
        calle=payload.direccion_origen.calle,
        numero=payload.direccion_origen.numero,
        ciudad=payload.direccion_origen.ciudad,
        provincia=payload.direccion_origen.provincia,
        codigo_postal=payload.direccion_origen.codigo_postal,
    )
    db.add(origen)
    db.flush()  # obtener el id sin hacer commit todavía

    # 2. Persistir dirección de destino
    destino = Direccion(
        id=uuid.uuid4(),
        calle=payload.direccion_destino.calle,
        numero=payload.direccion_destino.numero,
        ciudad=payload.direccion_destino.ciudad,
        provincia=payload.direccion_destino.provincia,
        codigo_postal=payload.direccion_destino.codigo_postal,
    )
    db.add(destino)
    db.flush()

    # 3. Generar tracking ID y crear envío
    tracking_id = _generar_tracking_id(db)
    envio = Envio(
        uuid=uuid.uuid4(),
        tracking_id=tracking_id,
        remitente=payload.remitente,
        destinatario=payload.destinatario,
        fecha_entrega_estimada=payload.fecha_entrega_estimada,
        estado=EstadoEnvioEnum.REGISTRADO,
        direccion_origen_id=origen.id,
        direccion_destino_id=destino.id,
    )
    db.add(envio)
    db.flush()

    # 4. Registrar EventoDeEnvio de CREACION automáticamente (LP-106)
    # TODO: reemplazar usuario_uuid hardcodeado por el del token JWT cuando se implemente auth
    USUARIO_OPERADOR_SEED = "b1b2c3d4-0002-0002-0002-000000000003"
    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.CREACION,
        estado_inicial=None,
        estado_final=EstadoEnvioEnum.REGISTRADO,
        ubicacion_actual_id=None,
        usuario_uuid=uuid.UUID(USUARIO_OPERADOR_SEED),
        envio_uuid=envio.uuid,
    )
    db.add(evento)

    db.commit()
    db.refresh(envio)
    return envio


# ── GET /envios ───────────────────────────────────────────────────────────────

@router.get("/", response_model=EnvioListResponse)
def listar_envios(
    q: str = Query(default="", description="Buscar por tracking ID, remitente o destinatario"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Lista todos los envíos activos (excluye ELIMINADO).
    Soporta búsqueda por tracking ID, remitente o destinatario.
    Cubre LP-3 (listado) y LP-4 (búsqueda).
    """
    query = db.query(Envio).filter(Envio.estado != EstadoEnvioEnum.ELIMINADO)

    if q.strip():
        termino = f"%{q.strip().lower()}%"
        query = query.filter(
            func.lower(Envio.tracking_id).like(termino)
            | func.lower(Envio.remitente).like(termino)
            | func.lower(Envio.destinatario).like(termino)
        )

    total = query.count()
    envios = query.order_by(Envio.created_at.desc()).offset(skip).limit(limit).all()

    return EnvioListResponse(
        total=total,
        items=[_build_envio_list_item(e) for e in envios],
    )


# ── GET /envios/{tracking_id} ─────────────────────────────────────────────────

@router.get("/{tracking_id}", response_model=EnvioOut)
def obtener_envio(tracking_id: str, db: Session = Depends(get_db)):
    """
    Devuelve el detalle de un envío por tracking ID.
    Usado para la consulta pública — solo expone ciudad de origen/destino
    a través del schema EnvioOut (LP-136 se maneja en el frontend).
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")
    return envio