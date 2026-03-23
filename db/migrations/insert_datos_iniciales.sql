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
-- ENVÍOS
-- ==============================================
INSERT INTO envio (
    uuid, tracking_id, remitente, destinatario,
    probabilidad_retraso, prioridad, estado,
    fecha_entrega_estimada,
    direccion_origen_id, direccion_destino_id
) VALUES
    ('d1000000-0004-0004-0004-000000000001', 'LT-00000001', 'Juan Pérez', 'María García',
     0.15, 'BAJA', 'REGISTRADO', CURRENT_DATE + INTERVAL '5 days',
     'c1000000-0003-0003-0003-000000000001', 'c1000000-0003-0003-0003-000000000003'),
    ('d1000000-0004-0004-0004-000000000002', 'LT-00000002', 'Carlos López', 'Ana Martínez',
     0.45, 'MEDIA', 'EN_TRANSITO', CURRENT_DATE + INTERVAL '3 days',
     'c1000000-0003-0003-0003-000000000002', 'c1000000-0003-0003-0003-000000000004'),
    ('d1000000-0004-0004-0004-000000000003', 'LT-00000003', 'Pedro Rodríguez', 'Laura Sánchez',
     0.30, 'MEDIA', 'EN_SUCURSAL', CURRENT_DATE + INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000003', 'c1000000-0003-0003-0003-000000000005'),
    ('d1000000-0004-0004-0004-000000000004', 'LT-00000004', 'Lucía Fernández', 'Diego Torres',
     0.05, 'BAJA', 'ENTREGADO', CURRENT_DATE - INTERVAL '1 days',
     'c1000000-0003-0003-0003-000000000004', 'c1000000-0003-0003-0003-000000000006'),
    ('d1000000-0004-0004-0004-000000000005', 'LT-00000005', 'Martín González', 'Sofía Díaz',
     0.85, 'ALTA', 'RETRASADO', CURRENT_DATE - INTERVAL '2 days',
     'c1000000-0003-0003-0003-000000000005', 'c1000000-0003-0003-0003-000000000001'),
    ('d1000000-0004-0004-0004-000000000006', 'LT-00000006', 'Roberto Silva', 'Carmen Ruiz',
     0.60, 'ALTA', 'ELIMINADO', CURRENT_DATE + INTERVAL '2 days',
     'c1000000-0003-0003-0003-000000000006', 'c1000000-0003-0003-0003-000000000002')
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