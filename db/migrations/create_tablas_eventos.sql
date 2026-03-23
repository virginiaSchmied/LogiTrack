CREATE TABLE evento_de_envio (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    accion accion_envio NOT NULL,
    estado_inicial estado_envio,       
    estado_final estado_envio NOT NULL,
    ubicacion_actual_id UUID REFERENCES direccion(id),  
    usuario_uuid UUID NOT NULL REFERENCES usuario(uuid),
    envio_uuid UUID NOT NULL REFERENCES envio(uuid),
    fecha_hora TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE evento_de_usuario (
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    accion accion_usuario NOT NULL,
    estado_inicial estado_usuario,    
    estado_final estado_usuario NOT NULL,
    usuario_ejecutor_uuid UUID NOT NULL REFERENCES usuario(uuid),
    usuario_afectado_uuid UUID NOT NULL REFERENCES usuario(uuid),
    fecha_hora TIMESTAMP WITH TIME ZONE DEFAULT NOW()
); 