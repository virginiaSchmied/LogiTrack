from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
from uuid import UUID
import re

from models import EstadoEnvioEnum, NivelPrioridadEnum


# ── Dirección ────────────────────────────────────────────────────────────────

class DireccionCreate(BaseModel):
    calle:         str = Field(..., min_length=2, description="Debe contener letras")
    numero:        str = Field(..., description="Solo números")
    ciudad:        str = Field(..., min_length=2)
    provincia:     str = Field(..., min_length=2)
    codigo_postal: str = Field(..., description="Solo números")

    @field_validator("calle")
    @classmethod
    def calle_debe_tener_letras(cls, v: str) -> str:
        if v.isdigit():
            raise ValueError("La calle debe contener letras, no solo números")
        return v

    @field_validator("numero", "codigo_postal")
    @classmethod
    def debe_ser_numerico(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("Debe ser un valor numérico")
        return v

    @field_validator("ciudad", "provincia")
    @classmethod
    def solo_letras_y_espacios(cls, v: str) -> str:
        if not re.match(r"^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s]+$", v):
            raise ValueError("Solo se permiten letras y espacios")
        return v


class DireccionOut(BaseModel):
    id:            UUID
    calle:         str
    numero:        str
    ciudad:        str
    provincia:     str
    codigo_postal: str

    model_config = {"from_attributes": True}


# ── Envío ────────────────────────────────────────────────────────────────────

class EnvioCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}

    remitente:              str = Field(..., min_length=1, max_length=255)
    destinatario:           str = Field(..., min_length=1, max_length=255)
    fecha_entrega_estimada: date
    direccion_origen:       DireccionCreate
    direccion_destino:      DireccionCreate

    @field_validator("fecha_entrega_estimada")
    @classmethod
    def fecha_no_puede_ser_pasada(cls, v: date) -> date:
        from datetime import date as date_type
        if v < date_type.today():
            raise ValueError("La fecha estimada de entrega no puede ser anterior a hoy")
        return v

    @model_validator(mode="after")
    def origen_y_destino_no_pueden_ser_iguales(self) -> "EnvioCreate":
        o = self.direccion_origen
        d = self.direccion_destino
        if (
            o.calle.strip().lower()     == d.calle.strip().lower() and
            o.numero.strip()            == d.numero.strip() and
            o.ciudad.strip().lower()    == d.ciudad.strip().lower() and
            o.provincia.strip().lower() == d.provincia.strip().lower() and
            o.codigo_postal.strip()     == d.codigo_postal.strip()
        ):
            raise ValueError("La dirección de origen y destino no pueden ser la misma")
        return self


class EnvioListItem(BaseModel):
    """Schema reducido para el listado — no expone dirección completa (LP-136)"""
    uuid:                   UUID
    tracking_id:            str
    remitente:              str
    destinatario:           str
    ciudad_origen:          str
    provincia_origen:       str
    ciudad_destino:         str
    provincia_destino:      str
    estado:                 EstadoEnvioEnum
    prioridad:              Optional[NivelPrioridadEnum]
    fecha_entrega_estimada: date
    created_at:             datetime

    model_config = {"from_attributes": True}


class EnvioOut(BaseModel):
    """Schema completo para el detalle de un envío"""
    uuid:                   UUID
    tracking_id:            str
    remitente:              str
    destinatario:           str
    estado:                 EstadoEnvioEnum
    prioridad:              Optional[NivelPrioridadEnum]
    probabilidad_retraso:   Optional[float]
    fecha_entrega_estimada: date
    created_at:             datetime
    updated_at:             datetime
    direccion_origen:       DireccionOut
    direccion_destino:      DireccionOut

    model_config = {"from_attributes": True}


# ── Respuesta paginada ────────────────────────────────────────────────────────

class EnvioListResponse(BaseModel):
    total: int
    items: list[EnvioListItem]