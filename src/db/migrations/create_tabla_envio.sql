CREATE TABLE envio (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tracking_id VARCHAR(50) NOT NULL UNIQUE,
    remitente VARCHAR(255) NOT NULL,
    destinatario VARCHAR(255) NOT NULL,
    probabilidad_retraso NUMERIC(3,2),
    prioridad nivel_prioridad,
    estado estado_envio NOT NULL DEFAULT 'REGISTRADO',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    fecha_entrega_estimada DATE NOT NULL,
    direccion_origen_id UUID NOT NULL REFERENCES direccion(id),
    direccion_destino_id UUID NOT NULL REFERENCES direccion(id)
);
