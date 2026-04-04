import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query

from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date

from database import get_db
from models import Envio, Direccion, EventoDeEnvio, EstadoEnvioEnum, AccionEnvioEnum, NivelPrioridadEnum, Usuario
from schemas import (
    EnvioCreate, EnvioOut, EnvioOutDetalle, EnvioListItem, EnvioListResponse,
    EnvioUpdateContacto, EnvioUpdateOperativo, EnvioCambioEstado, DireccionOut,
    EventoHistorialOut, EventoAuditoriaOut, MovimientoCreate, EnvioPublicoOut
)

from ml_predictor import predecir_prioridad
from auth import require_operador_supervisor, require_supervisor
logger = logging.getLogger(__name__)
router = APIRouter(prefix="/envios", tags=["Envíos"])


FLUJO_NORMAL = [
    EstadoEnvioEnum.REGISTRADO,
    EstadoEnvioEnum.EN_DEPOSITO,
    EstadoEnvioEnum.EN_TRANSITO,
    EstadoEnvioEnum.EN_SUCURSAL,
    EstadoEnvioEnum.EN_DISTRIBUCION,
    EstadoEnvioEnum.ENTREGADO,
]

ESTADOS_EXCEPCION = [
    EstadoEnvioEnum.RETRASADO,
    EstadoEnvioEnum.CANCELADO,
    EstadoEnvioEnum.BLOQUEADO,
]

TRANSICIONES_VALIDAS = {
    EstadoEnvioEnum.REGISTRADO:      [EstadoEnvioEnum.EN_DEPOSITO, EstadoEnvioEnum.CANCELADO],
    EstadoEnvioEnum.EN_DEPOSITO:     [EstadoEnvioEnum.EN_TRANSITO, EstadoEnvioEnum.RETRASADO, EstadoEnvioEnum.BLOQUEADO, EstadoEnvioEnum.CANCELADO],
    EstadoEnvioEnum.EN_TRANSITO:     [EstadoEnvioEnum.EN_SUCURSAL, EstadoEnvioEnum.RETRASADO],
    EstadoEnvioEnum.EN_SUCURSAL:     [EstadoEnvioEnum.EN_DISTRIBUCION, EstadoEnvioEnum.RETRASADO,
                                      EstadoEnvioEnum.BLOQUEADO, EstadoEnvioEnum.CANCELADO],
    EstadoEnvioEnum.EN_DISTRIBUCION: [EstadoEnvioEnum.ENTREGADO, EstadoEnvioEnum.RETRASADO],
    EstadoEnvioEnum.ENTREGADO:       [],
    EstadoEnvioEnum.RETRASADO:       [EstadoEnvioEnum.EN_DEPOSITO, EstadoEnvioEnum.EN_TRANSITO,
                                      EstadoEnvioEnum.EN_SUCURSAL, EstadoEnvioEnum.EN_DISTRIBUCION],
    EstadoEnvioEnum.BLOQUEADO:       [EstadoEnvioEnum.EN_DEPOSITO, EstadoEnvioEnum.EN_SUCURSAL],
    EstadoEnvioEnum.CANCELADO:       [],
    EstadoEnvioEnum.ELIMINADO:       [],
}


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


# ── GET /envios/publico/{tracking_id} ────────────────────────────────────────

@router.get("/publico/{tracking_id}", response_model=EnvioPublicoOut)
def consultar_envio_publico(tracking_id: str, db: Session = Depends(get_db)):
    """
    Consulta pública de estado de envío por tracking ID.
    Devuelve únicamente: tracking ID, estado, ciudades de origen/destino y
    fecha estimada de entrega. No expone nombre del remitente ni destinatario,
    ni calle, número o código postal de ninguna dirección.
    No requiere autenticación. CA-2, CA-3, CA-4, CA-5.
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró ningún envío con el tracking ID {tracking_id}",
        )
    return EnvioPublicoOut(
        tracking_id=envio.tracking_id,
        estado=envio.estado,
        fecha_entrega_estimada=envio.fecha_entrega_estimada,
        ciudad_origen=envio.direccion_origen.ciudad,
        provincia_origen=envio.direccion_origen.provincia,
        ciudad_destino=envio.direccion_destino.ciudad,
        provincia_destino=envio.direccion_destino.provincia,
    )


# ── GET /envios/{tracking_id} ─────────────────────────────────────────────────

@router.get("/{tracking_id}", response_model=EnvioOutDetalle)
def obtener_envio(
    tracking_id: str,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_operador_supervisor),
):
    """
    Devuelve el detalle de un envío por tracking ID.
    Incluye ultima_ubicacion: la dirección del último EventoDeEnvio con ubicación registrada.
    Requiere rol Operador o Supervisor.
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")

    resultado = EnvioOutDetalle.model_validate(envio)

    ultimo = (
        db.query(EventoDeEnvio)
        .filter(
            EventoDeEnvio.envio_uuid == envio.uuid,
            EventoDeEnvio.ubicacion_actual_id.isnot(None),
        )
        .order_by(EventoDeEnvio.fecha_hora.desc())
        .first()
    )
    if ultimo:
        dir_obj = db.query(Direccion).filter(Direccion.id == ultimo.ubicacion_actual_id).first()
        if dir_obj:
            resultado.ultima_ubicacion = DireccionOut.model_validate(dir_obj)

    # Para estados de excepción reversibles (RETRASADO, BLOQUEADO), determinar el estado previo al que revertir.
    # Buscamos el evento que transitó AL estado de excepción actual y leemos su estado_inicial —
    # eso es exactamente el estado desde el que se entró, sin depender del orden de timestamps.
    ESTADOS_REVERSIBLES = [EstadoEnvioEnum.RETRASADO, EstadoEnvioEnum.BLOQUEADO]
    if envio.estado in ESTADOS_REVERSIBLES:
        evento_excepcion = (
            db.query(EventoDeEnvio)
            .filter(
                EventoDeEnvio.envio_uuid == envio.uuid,
                EventoDeEnvio.estado_final == envio.estado,
                EventoDeEnvio.accion == AccionEnvioEnum.CAMBIO_ESTADO,
            )
            .order_by(EventoDeEnvio.fecha_hora.desc())
            .first()
        )
        resultado.estado_revertir = (
            evento_excepcion.estado_inicial.value if evento_excepcion else EstadoEnvioEnum.EN_DEPOSITO.value
        )

    return resultado


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
    if envio.estado != EstadoEnvioEnum.CANCELADO:
        raise HTTPException(status_code=422, detail=f"El envío debe estar en estado CANCELADO para ser eliminado")

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
    Requiere rol Operador o Supervisor.
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


def _resolver_ubicacion(payload_nueva, payload_reusar, envio, db):
    """
    Resuelve y persiste la ubicación para un cambio de estado o excepción.
    Retorna el UUID de la dirección a usar.
    """
    if payload_reusar:
        ultimo = (
            db.query(EventoDeEnvio)
            .filter(
                EventoDeEnvio.envio_uuid == envio.uuid,
                EventoDeEnvio.ubicacion_actual_id.isnot(None),
            )
            .order_by(EventoDeEnvio.fecha_hora.desc())
            .first()
        )
        if not ultimo:
            raise HTTPException(status_code=422, detail="No hay ubicación anterior registrada para este envío")
        return ultimo.ubicacion_actual_id
    else:
        nueva_dir = Direccion(
            id=uuid.uuid4(),
            calle=payload_nueva.calle,
            numero=payload_nueva.numero,
            ciudad=payload_nueva.ciudad,
            provincia=payload_nueva.provincia,
            codigo_postal=payload_nueva.codigo_postal,
        )
        db.add(nueva_dir)
        db.flush()
        return nueva_dir.id


# ── PATCH /envios/{tracking_id}/estado ───────────────────────────────────────

ESTADOS_SOLO_SUPERVISOR = [EstadoEnvioEnum.RETRASADO, EstadoEnvioEnum.BLOQUEADO, EstadoEnvioEnum.CANCELADO]


@router.patch("/{tracking_id}/estado", response_model=EnvioOut)
def cambiar_estado(
    tracking_id: str,
    payload: EnvioCambioEstado,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(require_operador_supervisor),
):
    """
    Cambia el estado de un envío validando contra el grafo de transiciones permitidas.
    Cubre flujo normal, estados de excepción y reversiones en un único endpoint.
    Solo SUPERVISOR puede asignar excepciones (RETRASADO, BLOQUEADO).
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")
    if envio.estado == EstadoEnvioEnum.ELIMINADO:
        raise HTTPException(status_code=409, detail=f"Envío {tracking_id} está eliminado y no puede modificarse")

    destinos_validos = TRANSICIONES_VALIDAS.get(envio.estado, [])
    if payload.nuevo_estado not in destinos_validos:
        raise HTTPException(
            status_code=422,
            detail=f"Transición inválida: {envio.estado.value} → {payload.nuevo_estado.value}"
        )

    if payload.nuevo_estado in ESTADOS_SOLO_SUPERVISOR and current_user.rol.nombre != "SUPERVISOR":
        raise HTTPException(
            status_code=403,
            detail="Acceso denegado: solo el Supervisor puede asignar excepciones o cancelar envíos",
        )

    # CANCELADO no requiere ubicación
    ESTADOS_UBICACION_OBLIGATORIA = [
        EstadoEnvioEnum.EN_DEPOSITO,
        EstadoEnvioEnum.EN_SUCURSAL,
        EstadoEnvioEnum.ENTREGADO,
    ]
    if payload.nuevo_estado == EstadoEnvioEnum.CANCELADO:
        ubicacion_id = None
    elif payload.nuevo_estado in ESTADOS_UBICACION_OBLIGATORIA:
        if payload.nueva_ubicacion is None:
            raise HTTPException(status_code=422, detail=f"La ubicación nueva es obligatoria para el estado {payload.nuevo_estado.value}")
        if payload.reusar_ubicacion_anterior:
            raise HTTPException(status_code=422, detail=f"No se puede reutilizar la ubicación anterior para el estado {payload.nuevo_estado.value}")
        ubicacion_id = _resolver_ubicacion(payload.nueva_ubicacion, False, envio, db)
    else:
        if payload.nueva_ubicacion is None and not payload.reusar_ubicacion_anterior:
            raise HTTPException(status_code=422, detail="Debe proveer una ubicación o indicar que se reutiliza la anterior")
        ubicacion_id = _resolver_ubicacion(payload.nueva_ubicacion, payload.reusar_ubicacion_anterior, envio, db)

    estado_anterior = envio.estado
    envio.estado    = payload.nuevo_estado

    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.CAMBIO_ESTADO,
        estado_inicial=estado_anterior,
        estado_final=payload.nuevo_estado,
        ubicacion_actual_id=ubicacion_id,
        usuario_uuid=current_user.uuid,
        envio_uuid=envio.uuid,
    )
    db.add(evento)
    db.commit()
    db.refresh(envio)
    return envio


# ── Historial de envío (LP-120) ───────────────────────────────────────────────

@router.get(
    "/{tracking_id}/historial",
    response_model=list[EventoHistorialOut],
    summary="Historial de estados y movimientos de un envío",
)
def get_historial(tracking_id: str, db: Session = Depends(get_db)):
    """
    Retorna el historial cronológico de CAMBIO_ESTADO y MOVIMIENTO de un envío.
    Excluye CREACION, MODIFICACION y ELIMINACION (accesibles solo para supervisores en LP-174).
    """
    envio = db.query(Envio).filter(
        Envio.tracking_id == tracking_id,
        Envio.estado != EstadoEnvioEnum.ELIMINADO,
    ).first()
    if not envio:
        raise HTTPException(status_code=404, detail="Envío no encontrado")

    eventos = (
        db.query(EventoDeEnvio)
        .filter(
            EventoDeEnvio.envio_uuid == envio.uuid,
            EventoDeEnvio.accion.in_([
                AccionEnvioEnum.CREACION,
                AccionEnvioEnum.CAMBIO_ESTADO,
                AccionEnvioEnum.MOVIMIENTO,
            ]),
        )
        .order_by(EventoDeEnvio.fecha_hora.asc())
        .all()
    )

    result = []
    for ev in eventos:
        ubicacion = None
        if ev.ubicacion_actual_id:
            ubicacion = db.query(Direccion).filter(
                Direccion.id == ev.ubicacion_actual_id
            ).first()
        result.append(EventoHistorialOut(
            accion=ev.accion,
            estado=ev.estado_final,
            ubicacion=DireccionOut.model_validate(ubicacion) if ubicacion else None,
            fecha_hora=ev.fecha_hora,
        ))
    return result


# ── Auditoría de envío (LP-174) ───────────────────────────────────────────────

@router.get(
    "/{tracking_id}/auditoria",
    response_model=list[EventoAuditoriaOut],
    summary="Historial completo de auditoría de un envío (solo supervisor)",
)
def get_auditoria(tracking_id: str, db: Session = Depends(get_db)):
    """
    Retorna todas las acciones registradas sobre un envío, incluyendo
    CREACION, MODIFICACION, CAMBIO_ESTADO, MOVIMIENTO y ELIMINACION.
    Incluye el email del usuario que realizó cada acción.
    Solo accesible por supervisores (control de roles pendiente de implementar con JWT).
    """
    envio = db.query(Envio).filter(Envio.tracking_id == tracking_id).first()
    if not envio:
        raise HTTPException(status_code=404, detail="Envío no encontrado")

    eventos = (
        db.query(EventoDeEnvio)
        .filter(EventoDeEnvio.envio_uuid == envio.uuid)
        .order_by(EventoDeEnvio.fecha_hora.asc())
        .all()
    )

    result = []
    for ev in eventos:
        ubicacion = None
        if ev.ubicacion_actual_id:
            ubicacion = db.query(Direccion).filter(
                Direccion.id == ev.ubicacion_actual_id
            ).first()
        usuario = db.query(Usuario).filter(Usuario.uuid == ev.usuario_uuid).first()
        result.append(EventoAuditoriaOut(
            accion=ev.accion,
            estado_inicial=ev.estado_inicial,
            estado_final=ev.estado_final,
            ubicacion=DireccionOut.model_validate(ubicacion) if ubicacion else None,
            usuario_email=usuario.email if usuario else "desconocido",
            fecha_hora=ev.fecha_hora,
        ))
    return result


# ── Movimiento físico (LP-162) ────────────────────────────────────────────────

@router.post(
    "/{tracking_id}/movimientos",
    status_code=201,
    summary="Registrar un movimiento físico del envío",
)
def registrar_movimiento(
    tracking_id: str,
    payload: MovimientoCreate,
    db: Session = Depends(get_db),
):
    """
    Persiste un EventoDeEnvio de tipo MOVIMIENTO asociado al envío.
    No modifica el estado del envío.
    """
    envio = db.query(Envio).filter(
        Envio.tracking_id == tracking_id,
        Envio.estado != EstadoEnvioEnum.ELIMINADO,
    ).first()
    if not envio:
        raise HTTPException(status_code=404, detail=f"Envío {tracking_id} no encontrado")

    nueva_dir = Direccion(
        id=uuid.uuid4(),
        calle=payload.ubicacion.calle,
        numero=payload.ubicacion.numero,
        ciudad=payload.ubicacion.ciudad,
        provincia=payload.ubicacion.provincia,
        codigo_postal=payload.ubicacion.codigo_postal,
    )
    db.add(nueva_dir)
    db.flush()

    USUARIO_OPERADOR_SEED = "b1b2c3d4-0002-0002-0002-000000000003"
    evento = EventoDeEnvio(
        uuid=uuid.uuid4(),
        accion=AccionEnvioEnum.MOVIMIENTO,
        estado_inicial=envio.estado,
        estado_final=envio.estado,
        ubicacion_actual_id=nueva_dir.id,
        usuario_uuid=uuid.UUID(USUARIO_OPERADOR_SEED),
        envio_uuid=envio.uuid,
    )
    db.add(evento)
    db.commit()
    return {"mensaje": "Movimiento registrado correctamente"}
