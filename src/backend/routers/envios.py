import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db
from models import Envio, Direccion, EventoDeEnvio, EstadoEnvioEnum, AccionEnvioEnum, NivelPrioridadEnum, Usuario
from schemas import EnvioCreate, EnvioOut, EnvioListItem, EnvioListResponse, EnvioUpdateContacto, EnvioUpdateOperativo
from ml_predictor import predecir_prioridad
from auth import require_operador_supervisor, require_supervisor

router = APIRouter(prefix="/envios", tags=["Envíos"])


def _generar_tracking_id(db: Session) -> str:
    """
    Genera el próximo tracking ID correlativo en formato LT-00000001.
    Toma el número más alto existente en la tabla para evitar colisiones
    con los datos del seed o cualquier otro envío existente.
    """
    todos = db.query(Envio.tracking_id).all()
    maximo = 0
    for (tid,) in todos:
        if tid and tid.startswith("LT-"):
            try:
                numero = int(tid.split("LT-")[1])
                if numero > maximo:
                    maximo = numero
            except ValueError:
                continue
    return f"LT-{str(maximo + 1).zfill(8)}"


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
def crear_envio(
    payload: EnvioCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_operador_supervisor),
):
    """
    Registra un nuevo envío con sus direcciones de origen y destino.
    Genera el tracking ID automáticamente y registra el EventoDeEnvio de CREACION.
    Requiere rol Operador o Supervisor. Cubre LP-2, LP-249.
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
    db.flush()

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

    # LP-118: predecir prioridad con el modelo ML
    dias = (payload.fecha_entrega_estimada - date.today()).days
    prioridad = None
    try:
        resultado = predecir_prioridad(payload.probabilidad_retraso, dias)
        prioridad = NivelPrioridadEnum(resultado)
    except (ValueError, RuntimeError) as e:
        logger.warning("No se pudo predecir la prioridad: %s", e)

    envio = Envio(
        uuid=uuid.uuid4(),
        tracking_id=tracking_id,
        remitente=payload.remitente,
        destinatario=payload.destinatario,
        probabilidad_retraso=payload.probabilidad_retraso,
        fecha_entrega_estimada=payload.fecha_entrega_estimada,
        estado=EstadoEnvioEnum.REGISTRADO,
        prioridad=prioridad,
        direccion_origen_id=origen.id,
        direccion_destino_id=destino.id,
    )
    db.add(envio)
    db.flush()

    # 4. Registrar EventoDeEnvio de CREACION (LP-106)
    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.CREACION,
        estado_inicial=None,
        estado_final=EstadoEnvioEnum.REGISTRADO,
        ubicacion_actual_id=None,
        usuario_uuid=current_user.uuid,
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
    current_user: Usuario = Depends(require_operador_supervisor),
):
    """
    Lista todos los envíos activos (excluye ELIMINADO).
    Soporta búsqueda por tracking ID, remitente o destinatario.
    Requiere rol Operador o Supervisor. Cubre LP-3 (listado), LP-4 (búsqueda), LP-249.
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
    envios = query.order_by(Envio.tracking_id.asc()).offset(skip).limit(limit).all()

    return EnvioListResponse(
        total=total,
        items=[_build_envio_list_item(e) for e in envios],
    )


# ── GET /envios/{tracking_id} ─────────────────────────────────────────────────

@router.get("/{tracking_id}", response_model=EnvioOut)
def obtener_envio(tracking_id: str, db: Session = Depends(get_db)):
    """
    Devuelve el detalle de un envío por tracking ID.
    Endpoint de acceso público — no requiere autenticación. LP-136, LP-250 CA-4.
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")
    return envio


# ── DELETE /envios/{tracking_id} ──────────────────────────────────────────────

@router.delete("/{tracking_id}", status_code=200)
def eliminar_envio(
    tracking_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_supervisor),
):
    """
    Eliminación lógica de un envío: marca el estado como ELIMINADO sin borrar
    el registro físicamente, preservando el historial de auditoría.
    Registra un EventoDeEnvio de ELIMINACION.
    Requiere rol Supervisor. Cubre LP-7, LP-249 CA-1, LP-252 CA-3.
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")
    if envio.estado == EstadoEnvioEnum.ELIMINADO:
        raise HTTPException(status_code=409, detail=f"Envío {tracking_id} ya fue eliminado")

    estado_anterior = envio.estado
    envio.estado    = EstadoEnvioEnum.ELIMINADO

    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.ELIMINACION,
        estado_inicial=estado_anterior,
        estado_final=EstadoEnvioEnum.ELIMINADO,
        ubicacion_actual_id=None,
        usuario_uuid=current_user.uuid,
        envio_uuid=envio.uuid,
    )
    db.add(evento)
    db.commit()
    return {"message": f"Envío {tracking_id} eliminado correctamente"}


# ── PATCH /envios/{tracking_id}/contacto ─────────────────────────────────────

@router.patch("/{tracking_id}/contacto", response_model=EnvioOut)
def actualizar_contacto(
    tracking_id: str,
    payload: EnvioUpdateContacto,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_operador_supervisor),
):
    """
    Modifica el destinatario y la dirección de destino de un envío.
    Registra un EventoDeEnvio de MODIFICACION.
    Requiere rol Operador o Supervisor. Cubre LP-148, LP-249.
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")
    if envio.estado == EstadoEnvioEnum.ELIMINADO:
        raise HTTPException(status_code=409, detail=f"Envío {tracking_id} está eliminado y no puede modificarse")

    envio.destinatario = payload.destinatario

    destino = envio.direccion_destino
    destino.calle         = payload.direccion_destino.calle
    destino.numero        = payload.direccion_destino.numero
    destino.ciudad        = payload.direccion_destino.ciudad
    destino.provincia     = payload.direccion_destino.provincia
    destino.codigo_postal = payload.direccion_destino.codigo_postal

    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.MODIFICACION,
        estado_inicial=envio.estado,
        estado_final=envio.estado,
        ubicacion_actual_id=None,
        usuario_uuid=current_user.uuid,
        envio_uuid=envio.uuid,
    )
    db.add(evento)
    db.commit()
    db.refresh(envio)
    return envio


# ── PATCH /envios/{tracking_id}/operativo ────────────────────────────────────

@router.patch("/{tracking_id}/operativo", response_model=EnvioOut)
def actualizar_operativo(
    tracking_id: str,
    payload: EnvioUpdateOperativo,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_operador_supervisor),
):
    """
    Modifica la fecha estimada de entrega y la probabilidad de retraso de un envío.
    Recalcula la prioridad con el modelo ML si se provee probabilidad_retraso.
    Registra un EventoDeEnvio de MODIFICACION.
    Requiere rol Operador o Supervisor. Cubre LP-154, LP-249.
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")
    if envio.estado == EstadoEnvioEnum.ELIMINADO:
        raise HTTPException(status_code=409, detail=f"Envío {tracking_id} está eliminado y no puede modificarse")

    envio.fecha_entrega_estimada = payload.fecha_entrega_estimada
    envio.probabilidad_retraso   = payload.probabilidad_retraso

    dias = (payload.fecha_entrega_estimada - date.today()).days
    envio.prioridad = None
    try:
        resultado = predecir_prioridad(payload.probabilidad_retraso, dias)
        envio.prioridad = NivelPrioridadEnum(resultado)
    except (ValueError, RuntimeError) as e:
        logger.warning("No se pudo predecir la prioridad: %s", e)

    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.MODIFICACION,
        estado_inicial=envio.estado,
        estado_final=envio.estado,
        ubicacion_actual_id=None,
        usuario_uuid=current_user.uuid,
        envio_uuid=envio.uuid,
    )
    db.add(evento)
    db.commit()
    db.refresh(envio)
    return envio
