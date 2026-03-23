CREATE TABLE usuario (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    contrasena_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    estado estado_usuario NOT NULL DEFAULT 'ALTA',
    rol_uuid UUID NOT NULL REFERENCES rol(uuid)
);