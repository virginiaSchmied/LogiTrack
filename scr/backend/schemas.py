from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
from datetime import date, datetime
from uuid import UUID
import re

from models import EstadoEnvioEnum, NivelPrioridadEnum


# ── Dirección ────────────────────────────────────────────────────────────────

class DireccionCreate(BaseModel):
    model_config = {"str_strip_whitespace": True}

    calle:         str = Field(..., min_length=2, description="Debe contener letras",
                               examples=["Av. Corrientes"])
    numero:        str = Field(..., description="Solo números", examples=["1234"])
    ciudad:        str = Field(..., min_length=2, examples=["Buenos Aires"])
    provincia:     str = Field(..., min_length=2, examples=["CABA"])
    codigo_postal: str = Field(..., description="Solo números", examples=["1043"])

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

    remitente:              str   = Field(..., min_length=1, max_length=255,
                                          examples=["Juan Pérez"])
    destinatario:           str   = Field(..., min_length=1, max_length=255,
                                          examples=["María García"])
    probabilidad_retraso:   float = Field(..., ge=0.0, le=1.0,
                                          examples=[0.75])
    fecha_entrega_estimada: date  = Field(..., examples=["2026-05-15"])
    direccion_origen:       DireccionCreate = Field(..., examples=[{
        "calle": "Av. Corrientes", "numero": "1234",
        "ciudad": "Buenos Aires", "provincia": "CABA", "codigo_postal": "1043",
    }])
    direccion_destino:      DireccionCreate = Field(..., examples=[{
        "calle": "Belgrano", "numero": "890",
        "ciudad": "Córdoba", "provincia": "Córdoba", "codigo_postal": "5000",
    }])

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


class EnvioOutDetalle(EnvioOut):
    """EnvioOut extendido con la última ubicación registrada en eventos y el estado previo al de excepción."""
    ultima_ubicacion: Optional[DireccionOut] = None
    estado_revertir:  Optional[str]          = None  # último estado del flujo normal (para revertir excepción)


# ── Respuesta paginada ────────────────────────────────────────────────────────

class EnvioListResponse(BaseModel):
    total: int
    items: list[EnvioListItem]


# ── Edición de envío ──────────────────────────────────────────────────────────

class EnvioUpdateContacto(BaseModel):
    model_config = {"str_strip_whitespace": True}

    destinatario:      str = Field(..., min_length=1, max_length=255,
                                   examples=["Carlos López"])
    direccion_destino: DireccionCreate = Field(..., examples=[{
        "calle": "San Martín", "numero": "321",
        "ciudad": "Rosario", "provincia": "Santa Fe", "codigo_postal": "2000",
    }])


class EnvioUpdateOperativo(BaseModel):
    model_config = {"str_strip_whitespace": True}

    fecha_entrega_estimada: date  = Field(..., examples=["2026-05-20"])
    probabilidad_retraso:   float = Field(..., ge=0.0, le=1.0, examples=[0.60])

    @field_validator("fecha_entrega_estimada")
    @classmethod
    def fecha_no_puede_ser_pasada(cls, v: date) -> date:
        from datetime import date as date_type
        if v < date_type.today():
            raise ValueError("La fecha estimada de entrega no puede ser anterior a hoy")
        return v


# ── Cambio de estado ──────────────────────────────────────────────────────────

class EnvioCambioEstado(BaseModel):
    model_config = {"str_strip_whitespace": True}

    nuevo_estado:              EstadoEnvioEnum = Field(..., examples=["EN_DEPOSITO"])
    nueva_ubicacion:           Optional[DireccionCreate] = Field(None, examples=[{
        "calle": "Mitre", "numero": "456",
        "ciudad": "Mendoza", "provincia": "Mendoza", "codigo_postal": "5500",
    }])
    reusar_ubicacion_anterior: bool = Field(False, examples=[False])
