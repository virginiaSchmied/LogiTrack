"""
Genera un dataset aumentado para entrenar el modelo de prioridad de envíos.

Flujo:
  1. Lee los datos reales desde envios_historicos.csv (generado por exportar_desde_db.py).
  2. Genera FILAS_SINTETICAS filas sintéticas usando la misma regla de negocio + ruido gaussiano.
  3. Combina ambos y guarda en dataset_aumentado.csv.

Regla de negocio (matriz prioridad):

                  dias_para_entrega
                 ≤ 2 días  3-7 días  > 7 días
               ┌─────────┬─────────┬─────────┐
  prob > 0.70  │  ALTA   │  ALTA   │  MEDIA  │
  0.40-0.70    │  ALTA   │  MEDIA  │  MEDIA  │
  prob < 0.40  │  MEDIA  │  BAJA   │  BAJA   │
               └─────────┴─────────┴─────────┘

Se agrega ruido gaussiano (±0.05 prob, ±1 día) para que el modelo no aprenda
una regla determinística trivial.

Uso:
    # Primero exportar datos reales:
    python3 ml/dataset/exportar_desde_db.py

    # Luego generar el dataset aumentado:
    python3 ml/dataset/generar_dataset.py
    # → Genera ml/dataset/dataset_aumentado.csv
"""

import csv
import random
from pathlib import Path

random.seed(42)

FILAS_SINTETICAS = 2000
DATASET_DIR = Path(__file__).parent
OUTPUT_PATH = DATASET_DIR / "dataset_aumentado.csv"
HISTORICOS_PATH = DATASET_DIR / "dataset_inicial.csv"


def clasificar(prob: float, dias: int) -> str:
    """Regla de negocio determinística (sin ruido)."""
    if prob > 0.70:
        return "ALTA" if dias <= 7 else "MEDIA"
    elif prob >= 0.40:
        return "ALTA" if dias <= 2 else "MEDIA"
    else:
        return "MEDIA" if dias <= 2 else "BAJA"


def generar_fila() -> dict:
    """Genera una fila aleatoria con ruido gaussiano."""
    # Samplear de distribuciones que cubran bien los 9 cuadrantes
    cuadrante = random.randint(0, 8)

    if cuadrante == 0:    # prob>0.70, dias<=2
        prob_base = random.uniform(0.71, 0.99)
        dias_base = random.randint(0, 2)
    elif cuadrante == 1:  # prob>0.70, dias 3-7
        prob_base = random.uniform(0.71, 0.99)
        dias_base = random.randint(3, 7)
    elif cuadrante == 2:  # prob>0.70, dias>7
        prob_base = random.uniform(0.71, 0.99)
        dias_base = random.randint(8, 60)
    elif cuadrante == 3:  # 0.40-0.70, dias<=2
        prob_base = random.uniform(0.40, 0.70)
        dias_base = random.randint(0, 2)
    elif cuadrante == 4:  # 0.40-0.70, dias 3-7
        prob_base = random.uniform(0.40, 0.70)
        dias_base = random.randint(3, 7)
    elif cuadrante == 5:  # 0.40-0.70, dias>7
        prob_base = random.uniform(0.40, 0.70)
        dias_base = random.randint(8, 60)
    elif cuadrante == 6:  # prob<0.40, dias<=2
        prob_base = random.uniform(0.01, 0.39)
        dias_base = random.randint(0, 2)
    elif cuadrante == 7:  # prob<0.40, dias 3-7
        prob_base = random.uniform(0.01, 0.39)
        dias_base = random.randint(3, 7)
    else:                 # prob<0.40, dias>7
        prob_base = random.uniform(0.01, 0.39)
        dias_base = random.randint(8, 60)

    # Ruido gaussiano (±0.05 prob, ±1 dia)
    prob = round(max(0.01, min(0.99, prob_base + random.gauss(0, 0.05))), 2)
    dias = max(0, dias_base + int(random.gauss(0, 1)))

    prioridad = clasificar(prob, dias)
    return {"probabilidad_retraso": prob, "dias_para_entrega": dias, "prioridad": prioridad}


def leer_historicos() -> list[dict]:
    """Lee envios_historicos.csv generado por exportar_desde_db.py."""
    if not HISTORICOS_PATH.exists():
        print(f"AVISO: no se encontró {HISTORICOS_PATH}")
        print("Ejecutá primero: python3 ml/dataset/exportar_desde_db.py")
        print("Continuando sin datos reales (solo sintéticos)...")
        return []

    filas = []
    with open(HISTORICOS_PATH, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            filas.append({
                "probabilidad_retraso": float(row["probabilidad_retraso"]),
                "dias_para_entrega":    int(row["dias_para_entrega"]),
                "prioridad":            row["prioridad"],
            })
    print(f"Datos reales cargados desde {HISTORICOS_PATH}: {len(filas)} filas")
    return filas


def main():
    datos_reales = leer_historicos()
    filas_sinteticas = [generar_fila() for _ in range(FILAS_SINTETICAS)]
    todas = datos_reales + filas_sinteticas
    random.shuffle(todas)

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["probabilidad_retraso", "dias_para_entrega", "prioridad"])
        writer.writeheader()
        writer.writerows(todas)

    total = len(todas)
    conteo = {"ALTA": 0, "MEDIA": 0, "BAJA": 0}
    for fila in todas:
        conteo[fila["prioridad"]] += 1

    print(f"Dataset generado: {OUTPUT_PATH}")
    print(f"Total filas: {total}")
    print(f"  ALTA:  {conteo['ALTA']} ({conteo['ALTA']/total*100:.1f}%)")
    print(f"  MEDIA: {conteo['MEDIA']} ({conteo['MEDIA']/total*100:.1f}%)")
    print(f"  BAJA:  {conteo['BAJA']} ({conteo['BAJA']/total*100:.1f}%)")


if __name__ == "__main__":
    main()
