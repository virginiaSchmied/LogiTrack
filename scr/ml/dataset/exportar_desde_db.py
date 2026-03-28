"""
Exporta los envíos con prioridad asignada desde la BD a envios_historicos.csv.

Requiere que DATABASE_URL esté definida en el entorno o en backend/.env.

Uso:
    # Desde la raíz del proyecto:
    DATABASE_URL=postgresql://user:pass@host/db python3 ml/dataset/exportar_desde_db.py

    # O con el .env del backend:
    cd backend && python3 ../ml/dataset/exportar_desde_db.py
"""

import csv
import os
import sys
from datetime import date
from pathlib import Path

# Intentar cargar DATABASE_URL desde backend/.env si no está en el entorno
if "DATABASE_URL" not in os.environ:
    env_path = Path(__file__).parent.parent.parent / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("DATABASE_URL="):
                os.environ["DATABASE_URL"] = line.split("=", 1)[1].strip().strip('"')
                break

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL no está definida.")
    print("Definila en el entorno o en backend/.env")
    sys.exit(1)

try:
    from sqlalchemy import create_engine, text
except ImportError:
    print("ERROR: sqlalchemy no instalado. Ejecutá: pip install sqlalchemy psycopg2-binary")
    sys.exit(1)

OUTPUT_PATH = Path(__file__).parent / "envios_historicos.csv"

QUERY = """
SELECT
    CAST(probabilidad_retraso AS FLOAT)           AS probabilidad_retraso,
    (fecha_entrega_estimada - CURRENT_DATE)::int  AS dias_para_entrega,
    prioridad
FROM envio
WHERE probabilidad_retraso IS NOT NULL
  AND prioridad IS NOT NULL
  AND estado != 'ELIMINADO'
ORDER BY prioridad;
"""


def main():
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        rows = conn.execute(text(QUERY)).fetchall()

    if not rows:
        print("No se encontraron envíos con prioridad asignada en la BD.")
        print("Asegurate de haber ejecutado insert_datos_iniciales.sql primero.")
        sys.exit(1)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["probabilidad_retraso", "dias_para_entrega", "prioridad"])
        for row in rows:
            writer.writerow([row.probabilidad_retraso, max(0, row.dias_para_entrega), row.prioridad])

    conteo = {"ALTA": 0, "MEDIA": 0, "BAJA": 0}
    for row in rows:
        conteo[row.prioridad] += 1

    print(f"Exportado: {OUTPUT_PATH}")
    print(f"Total filas: {len(rows)}")
    print(f"  ALTA:  {conteo['ALTA']}")
    print(f"  MEDIA: {conteo['MEDIA']}")
    print(f"  BAJA:  {conteo['BAJA']}")


if __name__ == "__main__":
    main()
