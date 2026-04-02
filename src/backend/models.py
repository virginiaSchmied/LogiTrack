import uuid
from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from database import Base


# ── Enums ──────────────────────────────────────────────────────────────────

class EstadoEnvioEnum(str, enum.Enum):
    REGISTRADO     = "REGISTRADO"
    EN_DEPOSITO    = "EN_DEPOSITO"
    ELIMINADO      = "ELIMINADO"
    EN_TRANSITO    = "EN_TRANSITO"
    EN_SUCURSAL    = "EN_SUCURSAL"
    EN_DISTRIBUCION = "EN_DISTRIBUCION"
    ENTREGADO      = "ENTREGADO"
    BLOQUEADO      = "BLOQUEADO"
    RETRASADO      = "RETRASADO"
    CANCELADO      = "CANCELADO"


class NivelPrioridadEnum(str, enum.Enum):
    ALTA  = "ALTA"
    MEDIA = "MEDIA"
    BAJA  = "BAJA"


class EstadoUsuarioEnum(str, enum.Enum):
    ALTA = "ALTA"
    BAJA = "BAJA"


class AccionEnvioEnum(str, enum.Enum):
    CREACION      = "CREACION"
    MODIFICACION  = "MODIFICACION"
    CAMBIO_ESTADO = "CAMBIO_ESTADO"
    MOVIMIENTO    = "MOVIMIENTO"
    ELIMINACION   = "ELIMINACION"


class AccionUsuarioEnum(str, enum.Enum):
    ALTA   = "ALTA"
    BAJA   = "BAJA"
    LOGIN  = "LOGIN"
    LOGOUT = "LOGOUT"


# ── Modelos ─────────────────────────────────────────────────────────────────

class Rol(Base):
    __tablename__ = "rol"

    uuid   = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nombre = Column(String(50), nullable=False, unique=True)

    usuarios = relationship("Usuario", back_populates="rol")


class Usuario(Base):
    __tablename__ = "usuario"

    uuid            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email           = Column(String(255), nullable=False, unique=True)
    contrasena_hash = Column(String(255), nullable=False)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    estado          = Column(SAEnum(EstadoUsuarioEnum, name="estado_usuario"), nullable=False, default=EstadoUsuarioEnum.ALTA)
    rol_uuid        = Column(UUID(as_uuid=True), ForeignKey("rol.uuid"), nullable=False)

    rol              = relationship("Rol", back_populates="usuarios")
    eventos_de_envio = relationship("EventoDeEnvio", back_populates="usuario")


class Direccion(Base):
    __tablename__ = "direccion"

    id            = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    calle         = Column(String(255), nullable=False)
    numero        = Column(String(20), nullable=False)
    ciudad        = Column(String(100), nullable=False)
    provincia     = Column(String(100), nullable=False)
    codigo_postal = Column(String(10), nullable=False)

    envios_como_origen  = relationship("Envio", foreign_keys="Envio.direccion_origen_id",  back_populates="direccion_origen")
    envios_como_destino = relationship("Envio", foreign_keys="Envio.direccion_destino_id", back_populates="direccion_destino")


class Envio(Base):
    __tablename__ = "envio"

    uuid                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tracking_id           = Column(String(50), nullable=False, unique=True)
    remitente             = Column(String(255), nullable=False)
    destinatario          = Column(String(255), nullable=False)
    probabilidad_retraso  = Column(Numeric(5, 2), nullable=True)
    prioridad             = Column(SAEnum(NivelPrioridadEnum, name="nivel_prioridad"), nullable=True)
    estado                = Column(SAEnum(EstadoEnvioEnum, name="estado_envio"), nullable=False, default=EstadoEnvioEnum.REGISTRADO)
    created_at            = Column(DateTime(timezone=True), server_default=func.now())
    updated_at            = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    fecha_entrega_estimada = Column(Date, nullable=False)
    direccion_origen_id   = Column(UUID(as_uuid=True), ForeignKey("direccion.id"), nullable=False)
    direccion_destino_id  = Column(UUID(as_uuid=True), ForeignKey("direccion.id"), nullable=False)

    direccion_origen  = relationship("Direccion", foreign_keys=[direccion_origen_id],  back_populates="envios_como_origen")
    direccion_destino = relationship("Direccion", foreign_keys=[direccion_destino_id], back_populates="envios_como_destino")
    eventos           = relationship("EventoDeEnvio", back_populates="envio")


class EventoDeEnvio(Base):
    __tablename__ = "evento_de_envio"

    uuid                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    accion               = Column(SAEnum(AccionEnvioEnum, name="accion_envio"), nullable=False)
    estado_inicial       = Column(SAEnum(EstadoEnvioEnum, name="estado_envio"), nullable=True)
    estado_final         = Column(SAEnum(EstadoEnvioEnum, name="estado_envio"), nullable=False)
    ubicacion_actual_id  = Column(UUID(as_uuid=True), ForeignKey("direccion.id"), nullable=True)
    usuario_uuid         = Column(UUID(as_uuid=True), ForeignKey("usuario.uuid"), nullable=False)
    envio_uuid           = Column(UUID(as_uuid=True), ForeignKey("envio.uuid"), nullable=False)
    fecha_hora           = Column(DateTime(timezone=True), server_default=func.now())

    usuario = relationship("Usuario", back_populates="eventos_de_envio")
    envio   = relationship("Envio", back_populates="eventos")


class EventoDeUsuario(Base):
    __tablename__ = "evento_de_usuario"

    uuid                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    accion                = Column(SAEnum(AccionUsuarioEnum, name="accion_usuario"), nullable=False)
    estado_inicial        = Column(SAEnum(EstadoUsuarioEnum, name="estado_usuario"), nullable=True)
    estado_final          = Column(SAEnum(EstadoUsuarioEnum, name="estado_usuario"), nullable=False)
    usuario_ejecutor_uuid = Column(UUID(as_uuid=True), ForeignKey("usuario.uuid"), nullable=False)
    usuario_afectado_uuid = Column(UUID(as_uuid=True), ForeignKey("usuario.uuid"), nullable=False)
    fecha_hora            = Column(DateTime(timezone=True), server_default=func.now())