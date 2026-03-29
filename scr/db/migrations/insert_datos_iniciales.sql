-- ==============================================
-- USUARIOS
-- ==============================================
INSERT INTO usuario (uuid, email, contrasena_hash, estado, rol_uuid) VALUES
    (
        'b1b2c3d4-0002-0002-0002-000000000001',
        'admin@logitrack.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGc.0n8X.6J1Q8Q8Q8Q8Q8Q8Q8u',
        'ALTA',
        '9438fc9c-b584-4873-8f00-694c4d8c4b6c'
    ),
    (
        'b1b2c3d4-0002-0002-0002-000000000002',
        'supervisor@logitrack.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGc.0n8X.6J1Q8Q8Q8Q8Q8Q8Q8u',
        'ALTA',
        '10974788-0589-4a53-bb6a-c5bce8e511ec'
    ),
    (
        'b1b2c3d4-0002-0002-0002-000000000003',
        'operador@logitrack.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGc.0n8X.6J1Q8Q8Q8Q8Q8Q8Q8u',
        'ALTA',
        '96aa365b-d4b1-45a1-a9f5-3310c00b364b'
    ),
    (
        'b1b2c3d4-0002-0002-0002-000000000004',
        'operador2@logitrack.com',
        '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TiGc.0n8X.6J1Q8Q8Q8Q8Q8Q8Q8u',
        'BAJA',
        '96aa365b-d4b1-45a1-a9f5-3310c00b364b'
    )
ON CONFLICT (uuid) DO NOTHING;

-- ==============================================
-- DIRECCIONES
-- ==============================================
INSERT INTO direccion (id, calle, numero, ciudad, provincia, codigo_postal) VALUES
    ('c1000000-0003-0003-0003-000000000001', 'Av. Corrientes', '1234', 'Buenos Aires', 'CABA', '1043'),
    ('c1000000-0003-0003-0003-000000000002', 'Av. Santa Fe', '5678', 'Buenos Aires', 'CABA', '1425'),
    ('c1000000-0003-0003-0003-000000000003', 'Belgrano', '890', 'Córdoba', 'Córdoba', '5000'),
    ('c1000000-0003-0003-0003-000000000004', 'San Martín', '321', 'Rosario', 'Santa Fe', '2000'),
    ('c1000000-0003-0003-0003-000000000005', 'Mitre', '456', 'Mendoza', 'Mendoza', '5500'),
    ('c1000000-0003-0003-0003-000000000006', 'Rivadavia', '789', 'La Plata', 'Buenos Aires', '1900')
ON CONFLICT (id) DO NOTHING;

-- ==============================================
-- ENVÍOS (24 registros — cobertura completa de la matriz ML)
--
-- Matriz prioridad (prob_retraso × dias_para_entrega):
--
--                  ≤ 2 días   3-7 días   > 7 días
--   prob > 0.70  →  ALTA      ALTA       MEDIA
--   0.40-0.70    →  ALTA      MEDIA      MEDIA
--   prob < 0.40  →  MEDIA     BAJA       BAJA
--
-- ==============================================
INSERT INTO envio (
    uuid, tracking_id, remitente, destinatario,
    probabilidad_retraso, prioridad, estado,
    fecha_entrega_estimada,
    direccion_origen_id, direccion_destino_id
) VALUES
    -- prob < 0.40, días 3-7 → BAJA
    ('d1000000-0004-0004-0004-000000000001', 'LT-00000001', 'Juan Pérez', 'María García',
     0.15, 'BAJA', 'REGISTRADO', CURRENT_DATE + INTERVAL '5 days',
     'c1000000-0003-0003-0003-000000000001', 'c1000000-0003-0003-0003-000000000003'),

    -- 0.40-0.70, días 3-7 → MEDIA
    ('d1000000-0004-0004-0004-000000000002', 'LT-00000002', 'Carlos López', 'Ana Martínez',
     0.45, 'MEDIA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '3 days',
     'c1000000-0003-0003-0003-000000000002', 'c1000000-0003-0003-0003-000000000004'),

    -- prob < 0.40, días ≤ 2 → MEDIA
    ('d1000000-0004-0004-0004-000000000003', 'LT-00000003', 'Pedro Rodríguez', 'Laura Sánchez',
     0.30, 'MEDIA', 'EN_SUCURSAL', CURRENT_DATE + INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000003', 'c1000000-0003-0003-0003-000000000005'),

    -- prob < 0.40, días > 7 → BAJA
    ('d1000000-0004-0004-0004-000000000004', 'LT-00000004', 'Lucía Fernández', 'Diego Torres',
     0.05, 'BAJA', 'REGISTRADO', CURRENT_DATE + INTERVAL '10 days',
     'c1000000-0003-0003-0003-000000000004', 'c1000000-0003-0003-0003-000000000006'),

    -- prob > 0.70, días ≤ 2 → ALTA
    ('d1000000-0004-0004-0004-000000000005', 'LT-00000005', 'Martín González', 'Sofía Díaz',
     0.85, 'ALTA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000005', 'c1000000-0003-0003-0003-000000000001'),

    -- 0.40-0.70, días ≤ 2 → ALTA  (ELIMINADO: excluido del export ML)
    ('d1000000-0004-0004-0004-000000000006', 'LT-00000006', 'Roberto Silva', 'Carmen Ruiz',
     0.60, 'ALTA', 'ELIMINADO', CURRENT_DATE + INTERVAL '2 days',
     'c1000000-0003-0003-0003-000000000006', 'c1000000-0003-0003-0003-000000000002'),

    -- prob > 0.70, días ≤ 2 → ALTA
    ('d1000000-0004-0004-0004-000000000007', 'LT-00000007', 'Valeria Ríos', 'Tomás Herrera',
     0.75, 'ALTA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000001', 'c1000000-0003-0003-0003-000000000004'),

    -- prob > 0.70, días ≤ 2 → ALTA
    ('d1000000-0004-0004-0004-000000000008', 'LT-00000008', 'Natalia Vega', 'Ignacio Mora',
     0.92, 'ALTA', 'EN_DISTRIBUCION', CURRENT_DATE + INTERVAL '2 days',
     'c1000000-0003-0003-0003-000000000002', 'c1000000-0003-0003-0003-000000000005'),

    -- prob > 0.70, días 3-7 → ALTA
    ('d1000000-0004-0004-0004-000000000009', 'LT-00000009', 'Claudia Ortiz', 'Esteban Reyes',
     0.78, 'ALTA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '5 days',
     'c1000000-0003-0003-0003-000000000003', 'c1000000-0003-0003-0003-000000000006'),

    -- prob > 0.70, días 3-7 → ALTA
    ('d1000000-0004-0004-0004-000000000010', 'LT-00000010', 'Felipe Castro', 'Verónica Núñez',
     0.88, 'ALTA', 'EN_SUCURSAL', CURRENT_DATE + INTERVAL '4 days',
     'c1000000-0003-0003-0003-000000000004', 'c1000000-0003-0003-0003-000000000001'),

    -- prob > 0.70, días > 7 → MEDIA
    ('d1000000-0004-0004-0004-000000000011', 'LT-00000011', 'Agustín Blanco', 'Elena Fuentes',
     0.72, 'MEDIA', 'REGISTRADO', CURRENT_DATE + INTERVAL '15 days',
     'c1000000-0003-0003-0003-000000000005', 'c1000000-0003-0003-0003-000000000002'),

    -- prob > 0.70, días > 7 → MEDIA
    ('d1000000-0004-0004-0004-000000000012', 'LT-00000012', 'Lorena Mendoza', 'Sebastián Cruz',
     0.95, 'MEDIA', 'REGISTRADO', CURRENT_DATE + INTERVAL '20 days',
     'c1000000-0003-0003-0003-000000000006', 'c1000000-0003-0003-0003-000000000003'),

    -- 0.40-0.70, días ≤ 2 → ALTA
    ('d1000000-0004-0004-0004-000000000013', 'LT-00000013', 'Ramón Vargas', 'Patricia Delgado',
     0.65, 'ALTA', 'EN_DISTRIBUCION', CURRENT_DATE + INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000001', 'c1000000-0003-0003-0003-000000000005'),

    -- 0.40-0.70, días ≤ 2 → ALTA
    ('d1000000-0004-0004-0004-000000000014', 'LT-00000014', 'Silvia Romero', 'Andrés Molina',
     0.42, 'ALTA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '2 days',
     'c1000000-0003-0003-0003-000000000002', 'c1000000-0003-0003-0003-000000000006'),

    -- 0.40-0.70, días 3-7 → MEDIA
    ('d1000000-0004-0004-0004-000000000015', 'LT-00000015', 'Héctor Ibáñez', 'Roxana Pereira',
     0.55, 'MEDIA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '5 days',
     'c1000000-0003-0003-0003-000000000003', 'c1000000-0003-0003-0003-000000000001'),

    -- 0.40-0.70, días 3-7 → MEDIA
    ('d1000000-0004-0004-0004-000000000016', 'LT-00000016', 'Gloria Suárez', 'Marcelo Acosta',
     0.48, 'MEDIA', 'EN_SUCURSAL', CURRENT_DATE + INTERVAL '7 days',
     'c1000000-0003-0003-0003-000000000004', 'c1000000-0003-0003-0003-000000000002'),

    -- 0.40-0.70, días > 7 → MEDIA
    ('d1000000-0004-0004-0004-000000000017', 'LT-00000017', 'Daniela Rojas', 'Gustavo Medina',
     0.68, 'MEDIA', 'REGISTRADO', CURRENT_DATE + INTERVAL '12 days',
     'c1000000-0003-0003-0003-000000000005', 'c1000000-0003-0003-0003-000000000003'),

    -- 0.40-0.70, días > 7 → MEDIA
    ('d1000000-0004-0004-0004-000000000018', 'LT-00000018', 'Pablo Guerrero', 'Miriam León',
     0.41, 'MEDIA', 'REGISTRADO', CURRENT_DATE + INTERVAL '30 days',
     'c1000000-0003-0003-0003-000000000006', 'c1000000-0003-0003-0003-000000000004'),

    -- prob < 0.40, días ≤ 2 → MEDIA
    ('d1000000-0004-0004-0004-000000000019', 'LT-00000019', 'Isabel Paredes', 'Omar Castillo',
     0.35, 'MEDIA', 'EN_DISTRIBUCION', CURRENT_DATE + INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000001', 'c1000000-0003-0003-0003-000000000003'),

    -- prob < 0.40, días ≤ 2 → MEDIA
    ('d1000000-0004-0004-0004-000000000020', 'LT-00000020', 'Ernesto Pinto', 'Alicia Navarro',
     0.20, 'MEDIA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '2 days',
     'c1000000-0003-0003-0003-000000000002', 'c1000000-0003-0003-0003-000000000005'),

    -- prob < 0.40, días 3-7 → BAJA
    ('d1000000-0004-0004-0004-000000000021', 'LT-00000021', 'Beatriz Cano', 'Rodrigo Espinoza',
     0.25, 'BAJA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '5 days',
     'c1000000-0003-0003-0003-000000000003', 'c1000000-0003-0003-0003-000000000006'),

    -- prob < 0.40, días 3-7 → BAJA
    ('d1000000-0004-0004-0004-000000000022', 'LT-00000022', 'Fernando Soto', 'Alejandra Flores',
     0.38, 'BAJA', 'REGISTRADO', CURRENT_DATE + INTERVAL '6 days',
     'c1000000-0003-0003-0003-000000000004', 'c1000000-0003-0003-0003-000000000001'),

    -- prob < 0.40, días > 7 → BAJA
    ('d1000000-0004-0004-0004-000000000023', 'LT-00000023', 'Mariana Campos', 'Luis Bravo',
     0.10, 'BAJA', 'REGISTRADO', CURRENT_DATE + INTERVAL '14 days',
     'c1000000-0003-0003-0003-000000000005', 'c1000000-0003-0003-0003-000000000002'),

    -- prob < 0.40, días > 7 → BAJA
    ('d1000000-0004-0004-0004-000000000024', 'LT-00000024', 'Ricardo Peña', 'Susana Aguilar',
     0.05, 'BAJA', 'REGISTRADO', CURRENT_DATE + INTERVAL '60 days',
     'c1000000-0003-0003-0003-000000000006', 'c1000000-0003-0003-0003-000000000003')
ON CONFLICT (uuid) DO NOTHING;

-- ==============================================
-- EVENTOS DE ENVÍO
-- ==============================================
INSERT INTO evento_de_envio (
    uuid, accion, estado_inicial, estado_final,
    ubicacion_actual_id, usuario_uuid, envio_uuid, fecha_hora
) VALUES
    ('e1000000-0005-0005-0005-000000000001', 'CREACION', NULL, 'REGISTRADO', NULL,
     'b1b2c3d4-0002-0002-0002-000000000003', 'd1000000-0004-0004-0004-000000000001', NOW() - INTERVAL '1 hour'),
    ('e1000000-0005-0005-0005-000000000002', 'CREACION', NULL, 'REGISTRADO', NULL,
     'b1b2c3d4-0002-0002-0002-000000000003', 'd1000000-0004-0004-0004-000000000002', NOW() - INTERVAL '2 days'),
    ('e1000000-0005-0005-0005-000000000003', 'CAMBIO_ESTADO', 'REGISTRADO', 'EN_TRANSITO',
     'c1000000-0003-0003-0003-000000000002', 'b1b2c3d4-0002-0002-0002-000000000003',
     'd1000000-0004-0004-0004-000000000002', NOW() - INTERVAL '1 day'),
    ('e1000000-0005-0005-0005-000000000004', 'CREACION', NULL, 'REGISTRADO', NULL,
     'b1b2c3d4-0002-0002-0002-000000000003', 'd1000000-0004-0004-0004-000000000005', NOW() - INTERVAL '5 days'),
    ('e1000000-0005-0005-0005-000000000005', 'CAMBIO_ESTADO', 'REGISTRADO', 'EN_TRANSITO',
     'c1000000-0003-0003-0003-000000000005', 'b1b2c3d4-0002-0002-0002-000000000003',
     'd1000000-0004-0004-0004-000000000005', NOW() - INTERVAL '4 days'),
    ('e1000000-0005-0005-0005-000000000006', 'CAMBIO_ESTADO', 'EN_TRANSITO', 'RETRASADO',
     'c1000000-0003-0003-0003-000000000005', 'b1b2c3d4-0002-0002-0002-000000000002',
     'd1000000-0004-0004-0004-000000000005', NOW() - INTERVAL '2 days'),
    ('e1000000-0005-0005-0005-000000000007', 'CREACION', NULL, 'REGISTRADO', NULL,
     'b1b2c3d4-0002-0002-0002-000000000003', 'd1000000-0004-0004-0004-000000000006', NOW() - INTERVAL '3 days'),
    ('e1000000-0005-0005-0005-000000000008', 'ELIMINACION', 'REGISTRADO', 'ELIMINADO', NULL,
     'b1b2c3d4-0002-0002-0002-000000000002', 'd1000000-0004-0004-0004-000000000006', NOW() - INTERVAL '1 day')
ON CONFLICT (uuid) DO NOTHING;

-- ==============================================
-- EVENTOS DE USUARIO
-- ==============================================
INSERT INTO evento_de_usuario (
    uuid, accion, estado_inicial, estado_final,
    usuario_ejecutor_uuid, usuario_afectado_uuid, fecha_hora
) VALUES
    ('f1000000-0006-0006-0006-000000000001', 'ALTA', NULL, 'ALTA',
     'b1b2c3d4-0002-0002-0002-000000000001', 'b1b2c3d4-0002-0002-0002-000000000003', NOW() - INTERVAL '10 days'),
    ('f1000000-0006-0006-0006-000000000002', 'LOGIN', 'ALTA', 'ALTA',
     'b1b2c3d4-0002-0002-0002-000000000003', 'b1b2c3d4-0002-0002-0002-000000000003', NOW() - INTERVAL '2 days'),
    ('f1000000-0006-0006-0006-000000000003', 'LOGIN', 'ALTA', 'ALTA',
     'b1b2c3d4-0002-0002-0002-000000000002', 'b1b2c3d4-0002-0002-0002-000000000002', NOW() - INTERVAL '2 days'),
    ('f1000000-0006-0006-0006-000000000004', 'ALTA', NULL, 'ALTA',
     'b1b2c3d4-0002-0002-0002-000000000001', 'b1b2c3d4-0002-0002-0002-000000000004', NOW() - INTERVAL '7 days'),
    ('f1000000-0006-0006-0006-000000000005', 'BAJA', 'ALTA', 'BAJA',
     'b1b2c3d4-0002-0002-0002-000000000001', 'b1b2c3d4-0002-0002-0002-000000000004', NOW() - INTERVAL '1 day')
ON CONFLICT (uuid) DO NOTHING;