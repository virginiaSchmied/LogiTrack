"""
Entrenamiento del modelo de clasificación de prioridad de envíos.

Cubre LP-115 (entrenamiento) y LP-116 (exportación del modelo).

Algoritmo: Decision Tree (seleccionado en LP-114 por mayor F1-score macro).
Semilla fija (RANDOM_STATE=42) para resultados reproducibles (CP-0144).

Uso:
    python3 ml/train.py
    # → entrena Decision Tree sobre el 80% del dataset
    # → exporta ml/modelo_prioridad.joblib
    # → valida el modelo contra los 9 cuadrantes de la matriz de prioridad
"""

import csv
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.tree import DecisionTreeClassifier

DATASET_PATH = Path(__file__).parent / "dataset" / "dataset_aumentado.csv"
MODEL_PATH   = Path(__file__).parent / "modelo_prioridad.joblib"

RANDOM_STATE = 42


# ── Carga de datos ────────────────────────────────────────────────────────────

def cargar_dataset(path: Path):
    X, y = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            X.append([float(row["probabilidad_retraso"]), int(row["dias_para_entrega"])])
            y.append(row["prioridad"])
    return np.array(X), np.array(y)


# ── Entrenamiento (LP-115) ────────────────────────────────────────────────────

def entrenar(X_train, X_test, y_train, y_test):
    modelo = DecisionTreeClassifier(random_state=RANDOM_STATE)
    modelo.fit(X_train, y_train)

    y_pred  = modelo.predict(X_test)
    reporte = classification_report(y_test, y_pred, output_dict=True)

    print("\n" + "=" * 60)
    print("ENTRENAMIENTO — Decision Tree (LP-115)")
    print("=" * 60)
    print(f"  Train: {len(X_train)} filas  |  Test: {len(X_test)} filas  |  Split: 80/20")
    print(f"  random_state={RANDOM_STATE}")
    print()
    print(classification_report(y_test, y_pred))
    print(f"  accuracy : {reporte['accuracy']:.4f}")
    print(f"  f1 macro : {reporte['macro avg']['f1-score']:.4f}")

    return modelo


# ── Exportar y validar (LP-116) ───────────────────────────────────────────────

def exportar_y_validar(modelo):
    joblib.dump(modelo, MODEL_PATH)
    print(f"\nModelo exportado: {MODEL_PATH}")

    # Valida los 9 cuadrantes de la matriz de prioridad con valores fijos.
    # No depende de fechas ni del dataset → resultado siempre reproducible.
    CASOS = [
        #  prob    dias   esperado
        (0.85,    1,    "ALTA"),   # prob>0.70 , ≤2 días  → ALTA
        (0.85,    5,    "ALTA"),   # prob>0.70 , 3-7 días → ALTA
        (0.85,   10,   "MEDIA"),   # prob>0.70 , >7 días  → MEDIA
        (0.55,    1,    "ALTA"),   # 0.40-0.70 , ≤2 días  → ALTA
        (0.55,    5,   "MEDIA"),   # 0.40-0.70 , 3-7 días → MEDIA
        (0.55,   10,   "MEDIA"),   # 0.40-0.70 , >7 días  → MEDIA
        (0.20,    1,   "MEDIA"),   # prob<0.40 , ≤2 días  → MEDIA
        (0.20,    5,    "BAJA"),   # prob<0.40 , 3-7 días → BAJA
        (0.20,   10,    "BAJA"),   # prob<0.40 , >7 días  → BAJA
    ]

    modelo_cargado = joblib.load(MODEL_PATH)
    print("\n" + "=" * 60)
    print("VALIDACIÓN DEL MODELO (matriz de prioridad completa)")
    print("=" * 60)
    print(f"  {'prob':>6}  {'dias':>5}  {'esperado':>10}  {'predicho':>10}  {'ok':>4}")
    print(f"  {'-'*6}  {'-'*5}  {'-'*10}  {'-'*10}  {'-'*4}")
    errores = 0
    for prob, dias, esperado in CASOS:
        predicho = modelo_cargado.predict(np.array([[prob, dias]]))[0]
        ok = "✓" if predicho == esperado else "✗ ERROR"
        if predicho != esperado:
            errores += 1
        print(f"  {prob:>6.2f}  {dias:>5}  {esperado:>10}  {predicho:>10}  {ok}")
    print("=" * 60)
    if errores == 0:
        print("Todos los casos correctos. El modelo reproduce la matriz de prioridad.")
    else:
        print(f"ADVERTENCIA: {errores} caso(s) no coinciden con la regla de negocio.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Ejecución: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if not DATASET_PATH.exists():
        print(f"ERROR: no se encontró {DATASET_PATH}")
        print("Ejecutá primero: python3 ml/dataset/generar_dataset.py")
        return

    X, y = cargar_dataset(DATASET_PATH)
    print(f"Dataset cargado: {len(X)} filas")
    for clase in ["ALTA", "MEDIA", "BAJA"]:
        n = (y == clase).sum()
        print(f"  {clase}: {n} ({n/len(y)*100:.1f}%)")

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=RANDOM_STATE, stratify=y
    )

    modelo = entrenar(X_train, X_test, y_train, y_test)
    exportar_y_validar(modelo)


if __name__ == "__main__":
    main()
