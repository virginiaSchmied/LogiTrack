"""
Entrenamiento y comparación de modelos de clasificación de prioridad de envíos.

Cubre LP-114 (comparación de algoritmos) y LP-115 (entrenamiento + métricas).

Features:
    - probabilidad_retraso (float 0-1)
    - dias_para_entrega    (int)

Target:
    - prioridad: ALTA / MEDIA / BAJA

Uso:
    python3 ml/train.py
    # → imprime métricas comparativas
    # → exporta ml/modelo_prioridad.joblib
"""

import csv
from pathlib import Path

import joblib
import numpy as np
import matplotlib
matplotlib.use("Agg")  # sin ventana gráfica
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

DATASET_PATH  = Path(__file__).parent / "dataset" / "dataset_aumentado.csv"
MODEL_PATH    = Path(__file__).parent / "modelo_prioridad.joblib"
REPORTES_DIR  = Path(__file__).parent / "reportes"

RANDOM_STATE = 42


# ── Carga de datos ────────────────────────────────────────────────────────────

def cargar_dataset(path: Path):
    X, y = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            X.append([float(row["probabilidad_retraso"]), int(row["dias_para_entrega"])])
            y.append(row["prioridad"])
    return np.array(X), np.array(y)


# ── Helpers de visualización ──────────────────────────────────────────────────

def guardar_tabla_reporte(nombre: str, reporte_dict: dict, y_test, y_pred):
    """Guarda el classification report como imagen PNG."""
    clases = ["ALTA", "MEDIA", "BAJA"]
    cols   = ["precision", "recall", "f1-score", "support"]

    filas       = []
    etiquetas   = []
    for clase in clases:
        r = reporte_dict[clase]
        filas.append([f"{r['precision']:.2f}", f"{r['recall']:.2f}", f"{r['f1-score']:.2f}", f"{int(r['support'])}"])
        etiquetas.append(clase)
    # macro avg
    m = reporte_dict["macro avg"]
    filas.append([f"{m['precision']:.2f}", f"{m['recall']:.2f}", f"{m['f1-score']:.2f}", ""])
    etiquetas.append("macro avg")
    # accuracy
    filas.append(["", "", f"{reporte_dict['accuracy']:.2f}", ""])
    etiquetas.append("accuracy")

    fig, ax = plt.subplots(figsize=(7, 3))
    ax.axis("off")
    tabla = ax.table(
        cellText=filas,
        rowLabels=etiquetas,
        colLabels=cols,
        cellLoc="center",
        loc="center",
    )
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(11)
    tabla.scale(1.2, 1.6)

    # Color de encabezados
    for j in range(len(cols)):
        tabla[0, j].set_facecolor("#4472C4")
        tabla[0, j].set_text_props(color="white", fontweight="bold")
    for i in range(1, len(etiquetas) + 1):
        tabla[i, -1].set_facecolor("#f0f0f0")

    ax.set_title(f"Classification Report — {nombre}", fontsize=13, fontweight="bold", pad=12)
    path = REPORTES_DIR / f"reporte_{nombre.lower()}.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Imagen guardada: {path}")


def guardar_matriz_confusion(nombre: str, y_test, y_pred):
    """Guarda la matriz de confusión como imagen PNG."""
    clases = ["ALTA", "MEDIA", "BAJA"]
    cm = confusion_matrix(y_test, y_pred, labels=clases)

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(cm, interpolation="nearest", cmap="Blues")
    fig.colorbar(im, ax=ax)

    ax.set_xticks(range(len(clases)))
    ax.set_yticks(range(len(clases)))
    ax.set_xticklabels(clases, fontsize=11)
    ax.set_yticklabels(clases, fontsize=11)
    ax.set_xlabel("Predicho", fontsize=11)
    ax.set_ylabel("Real", fontsize=11)
    ax.set_title(f"Matriz de confusión — {nombre}", fontsize=13, fontweight="bold", pad=12)

    for i in range(len(clases)):
        for j in range(len(clases)):
            color = "white" if cm[i, j] > cm.max() / 2 else "black"
            ax.text(j, i, str(cm[i, j]), ha="center", va="center", color=color, fontsize=13, fontweight="bold")

    path = REPORTES_DIR / f"confusion_{nombre.lower()}.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Imagen guardada: {path}")


def guardar_tabla_comparacion(resultados: dict):
    """Guarda la tabla resumen comparativa como imagen PNG."""
    nombres   = list(resultados.keys())
    filas     = [[f"{resultados[n]['accuracy']:.4f}", f"{resultados[n]['f1_macro']:.4f}"] for n in nombres]
    cols      = ["Accuracy", "F1-score macro"]

    fig, ax = plt.subplots(figsize=(6, 2.5))
    ax.axis("off")
    tabla = ax.table(
        cellText=filas,
        rowLabels=nombres,
        colLabels=cols,
        cellLoc="center",
        loc="center",
    )
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(11)
    tabla.scale(1.3, 1.8)

    # Encabezados
    for j in range(len(cols)):
        tabla[0, j].set_facecolor("#4472C4")
        tabla[0, j].set_text_props(color="white", fontweight="bold")

    # Destacar el mejor por F1
    mejor_idx = max(range(len(nombres)), key=lambda i: resultados[nombres[i]]["f1_macro"])
    for j in range(len(cols)):
        tabla[mejor_idx + 1, j].set_facecolor("#E2EFDA")

    ax.set_title("Comparación de algoritmos (LP-114)", fontsize=13, fontweight="bold", pad=12)
    path = REPORTES_DIR / "comparacion_algoritmos.png"
    fig.savefig(path, bbox_inches="tight", dpi=150)
    plt.close(fig)
    print(f"  Imagen guardada: {path}")


# ── Comparación de algoritmos (LP-114) ───────────────────────────────────────

def comparar_modelos(X_train, X_test, y_train, y_test):
    modelos = {
        "DecisionTree":   DecisionTreeClassifier(random_state=RANDOM_STATE),
        "RandomForest":   RandomForestClassifier(n_estimators=100, random_state=RANDOM_STATE),
        "KNeighbors":     KNeighborsClassifier(n_neighbors=5),
    }

    resultados = {}
    print("\n" + "=" * 60)
    print("COMPARACIÓN DE ALGORITMOS (LP-114)")
    print("=" * 60)

    REPORTES_DIR.mkdir(exist_ok=True)

    for nombre, modelo in modelos.items():
        modelo.fit(X_train, y_train)
        y_pred  = modelo.predict(X_test)
        reporte = classification_report(y_test, y_pred, output_dict=True)
        accuracy  = reporte["accuracy"]
        f1_macro  = reporte["macro avg"]["f1-score"]
        resultados[nombre] = {"accuracy": accuracy, "f1_macro": f1_macro, "modelo": modelo}

        print(f"\n── {nombre} ──")
        print(classification_report(y_test, y_pred))
        guardar_tabla_reporte(nombre, reporte, y_test, y_pred)
        guardar_matriz_confusion(nombre, y_test, y_pred)

    guardar_tabla_comparacion(resultados)
    return resultados


# ── Selección y entrenamiento final (LP-115) ──────────────────────────────────

def seleccionar_y_entrenar(resultados, X, y):
    mejor_nombre = max(resultados, key=lambda n: resultados[n]["f1_macro"])
    mejor_info   = resultados[mejor_nombre]

    print("=" * 60)
    print("SELECCIÓN DEL MODELO (LP-115)")
    print("=" * 60)
    for nombre, info in resultados.items():
        marca = " ← ELEGIDO" if nombre == mejor_nombre else ""
        print(f"  {nombre:20s}  accuracy={info['accuracy']:.4f}  f1_macro={info['f1_macro']:.4f}{marca}")

    print(f"\nMotivo: mayor F1-score macro promedio entre las 3 clases.")

    # Reentrenar sobre el dataset completo
    clase = type(mejor_info["modelo"])
    kwargs = {"random_state": RANDOM_STATE} if hasattr(clase(), "random_state") else {}
    modelo_final = clase(**{**mejor_info["modelo"].get_params(), **kwargs})
    modelo_final.fit(X, y)

    return mejor_nombre, modelo_final


# ── Exportar modelo (LP-116) ──────────────────────────────────────────────────

def exportar(modelo, nombre: str):
    joblib.dump(modelo, MODEL_PATH)
    print(f"\nModelo exportado: {MODEL_PATH}")

    # Verificación rápida
    modelo_cargado = joblib.load(MODEL_PATH)
    ejemplo = np.array([[0.80, 2]])   # prob alta, 2 días → esperado: ALTA
    pred = modelo_cargado.predict(ejemplo)[0]
    print(f"Verificación (prob=0.80, dias=2) → prioridad predicha: {pred}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
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

    resultados   = comparar_modelos(X_train, X_test, y_train, y_test)
    nombre, modelo = seleccionar_y_entrenar(resultados, X, y)
    exportar(modelo, nombre)


if __name__ == "__main__":
    main()
