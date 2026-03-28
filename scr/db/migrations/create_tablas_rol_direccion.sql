-- Rol como tabla (no enum)
CREATE TABLE rol (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- Insertar los tres roles
INSERT INTO rol (nombre) VALUES ('ADMINISTRADOR'), ('SUPERVISOR'), ('OPERADOR');

-- Direccion
CREATE TABLE direccion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calle VARCHAR(255) NOT NULL,
    numero VARCHAR(20) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    codigo_postal VARCHAR(10) NOT NULL
);