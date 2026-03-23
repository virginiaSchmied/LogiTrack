-- Búsqueda de envíos por tracking_id (consulta pública)
CREATE INDEX idx_envio_tracking_id ON envio(tracking_id);

-- Filtrado de eventos por envío
CREATE INDEX idx_evento_envio_envio_uuid ON evento_de_envio(envio_uuid);

-- Filtrado de eventos por usuario ejecutor y afectado
CREATE INDEX idx_evento_usuario_ejecutor ON evento_de_usuario(usuario_ejecutor_uuid);
CREATE INDEX idx_evento_usuario_afectado ON evento_de_usuario(usuario_afectado_uuid);

-- Filtrado por fecha en ambas tablas de eventos
CREATE INDEX idx_evento_envio_fecha ON evento_de_envio(fecha_hora);
CREATE INDEX idx_evento_usuario_fecha ON evento_de_usuario(fecha_hora);

-- Búsqueda de usuarios por email (login)
CREATE INDEX idx_usuario_email ON usuario(email);