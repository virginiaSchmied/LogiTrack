-- Rol como tabla (no enum)
CREATE TABLE rol (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(50) NOT NULL UNIQUE
);

-- Insertar los tres roles con UUIDs fijos (requeridos por insert_datos_iniciales.sql)
INSERT INTO rol (uuid, nombre) VALUES
    ('9438fc9c-b584-4873-8f00-694c4d8c4b6c', 'ADMINISTRADOR'),
    ('10974788-0589-4a53-bb6a-c5bce8e511ec', 'SUPERVISOR'),
    ('96aa365b-d4b1-45a1-a9f5-3310c00b364b', 'OPERADOR')
ON CONFLICT (uuid) DO NOTHING;

-- Direccion
CREATE TABLE direccion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    calle VARCHAR(255) NOT NULL,
    numero VARCHAR(20) NOT NULL,
    ciudad VARCHAR(100) NOT NULL,
    provincia VARCHAR(100) NOT NULL,
    codigo_postal VARCHAR(10) NOT NULL
);