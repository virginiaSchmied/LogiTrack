"""
Tests para el servicio de predicción de prioridad.

Cubre:
  LP-117 — Servicio de predicción

  CP-0313 (HP)  — CA-1: Servicio invocable, devuelve prioridad sin errores
  CP-0314 (UP)  — CA-1: Formato inválido → error descriptivo, modelo no ejecutado
  CP-0146 (HP)  — CA-2: Servicio acepta exactamente las dos features requeridas
  CP-0147 (HP)  — CA-4: Prioridad devuelta pertenece siempre a {ALTA, MEDIA, BAJA}

Tests NO implementados (requieren endpoint de actualización de envíos):
  CP-0148 — CA-5: Servicio invocado al cambiar probabilidad de retraso
  CP-0149 — CA-5: Error al cambiar probabilidad con valor inválido
"""
import pytest

from ml_predictor import predecir_prioridad

PRIORIDADES_VALIDAS = {"ALTA", "MEDIA", "BAJA"}

VALORES_VALIDOS = {
    "ALTA":  [
        (0.85, 1),   # prob > 0.70, días ≤ 2
        (0.75, 5),   # prob > 0.70, días 3-7
        (0.65, 1),   # 0.40-0.70,  días ≤ 2
    ],
    "MEDIA": [
        (0.72, 10),  # prob > 0.70, días > 7
        (0.55, 5),   # 0.40-0.70,  días 3-7
        (0.68, 15),  # 0.40-0.70,  días > 7
        (0.30, 1),   # prob < 0.40, días ≤ 2
    ],
    "BAJA": [
        (0.15, 5),   # prob < 0.40, días 3-7
        (0.05, 10),  # prob < 0.40, días > 7
    ],
}


# ── CP-0313 — CA-1: Servicio invocable ───────────────────────────────────────

class TestCP0313ServicioInvocable:

    def test_cp0313_servicio_carga_modelo_y_devuelve_prioridad(self):
        """CP-0313 (HP) — El servicio carga el modelo, genera predicción y devuelve prioridad sin errores."""
        resultado = predecir_prioridad(0.85, 2)
        assert resultado in PRIORIDADES_VALIDAS

    def test_cp0313_no_lanza_excepcion_con_input_valido(self):
        """CP-0313 (HP) — El servicio no lanza excepciones con datos válidos."""
        try:
            predecir_prioridad(0.5, 5)
        except Exception as e:
            pytest.fail(f"No debería lanzar excepción con input válido: {e}")

    def test_cp0313_retorna_string(self):
        """CP-0313 (HP) — El resultado es un string (no None ni otro tipo)."""
        assert isinstance(predecir_prioridad(0.5, 5), str)


# ── CP-0314 — CA-1: Formato inválido no ejecuta el modelo ────────────────────

class TestCP0314FormatoInvalido:

    def test_cp0314_probabilidad_tipo_string_lanza_valueerror(self):
        """CP-0314 (UP) — probabilidad_retraso con tipo string → ValueError descriptivo."""
        with pytest.raises(ValueError, match="probabilidad_retraso"):
            predecir_prioridad("alto", 5)

    def test_cp0314_probabilidad_tipo_none_lanza_valueerror(self):
        """CP-0314 (UP) — probabilidad_retraso None → ValueError descriptivo."""
        with pytest.raises(ValueError, match="probabilidad_retraso"):
            predecir_prioridad(None, 5)

    def test_cp0314_probabilidad_tipo_lista_lanza_valueerror(self):
        """CP-0314 (UP) — probabilidad_retraso con tipo lista → ValueError descriptivo."""
        with pytest.raises(ValueError, match="probabilidad_retraso"):
            predecir_prioridad([0.5], 5)

    def test_cp0314_probabilidad_mayor_a_uno_lanza_valueerror(self):
        """CP-0314 (UP) — probabilidad_retraso > 1.0 → ValueError con rango."""
        with pytest.raises(ValueError, match="0.0 y 1.0"):
            predecir_prioridad(1.5, 5)

    def test_cp0314_probabilidad_negativa_lanza_valueerror(self):
        """CP-0314 (UP) — probabilidad_retraso < 0.0 → ValueError con rango."""
        with pytest.raises(ValueError, match="0.0 y 1.0"):
            predecir_prioridad(-0.1, 5)

    def test_cp0314_dias_tipo_string_lanza_valueerror(self):
        """CP-0314 (UP) — dias_para_entrega con tipo string → ValueError descriptivo."""
        with pytest.raises(ValueError, match="dias_para_entrega"):
            predecir_prioridad(0.5, "cinco")

    def test_cp0314_dias_tipo_none_lanza_valueerror(self):
        """CP-0314 (UP) — dias_para_entrega None → ValueError descriptivo."""
        with pytest.raises(ValueError, match="dias_para_entrega"):
            predecir_prioridad(0.5, None)

    def test_cp0314_dias_negativo_lanza_valueerror(self):
        """CP-0314 (UP) — dias_para_entrega < 0 → ValueError descriptivo."""
        with pytest.raises(ValueError, match="dias_para_entrega"):
            predecir_prioridad(0.5, -1)

    def test_cp0314_mensaje_error_menciona_campo_probabilidad(self):
        """CP-0314 (UP) — El mensaje de error identifica el campo probabilidad_retraso."""
        with pytest.raises(ValueError) as exc_info:
            predecir_prioridad(2.0, 5)
        assert "probabilidad_retraso" in str(exc_info.value)

    def test_cp0314_mensaje_error_menciona_campo_dias(self):
        """CP-0314 (UP) — El mensaje de error identifica el campo dias_para_entrega."""
        with pytest.raises(ValueError) as exc_info:
            predecir_prioridad(0.5, -5)
        assert "dias_para_entrega" in str(exc_info.value)


# ── CP-0146 — CA-2: Servicio acepta exactamente las dos features ──────────────

class TestCP0146ServicioAceptaFeatures:

    def test_cp0146_acepta_probabilidad_en_extremos(self):
        """CP-0146 (HP) — El servicio acepta probabilidad_retraso en los extremos del rango (0.0 y 1.0)."""
        assert predecir_prioridad(0.0, 5) in PRIORIDADES_VALIDAS
        assert predecir_prioridad(1.0, 5) in PRIORIDADES_VALIDAS

    def test_cp0146_acepta_dias_en_cero(self):
        """CP-0146 (HP) — El servicio acepta dias_para_entrega = 0."""
        assert predecir_prioridad(0.5, 0) in PRIORIDADES_VALIDAS

    def test_cp0146_acepta_dias_alto(self):
        """CP-0146 (HP) — El servicio acepta dias_para_entrega con valor alto."""
        assert predecir_prioridad(0.5, 365) in PRIORIDADES_VALIDAS


# ── CP-0147 — CA-4: Prioridad devuelta pertenece a las categorías definidas ───

class TestCP0147PrioridadEnCategorias:

    @pytest.mark.parametrize("prob,dias", VALORES_VALIDOS["ALTA"])
    def test_cp0147_devuelve_alta(self, prob, dias):
        """CP-0147 (HP) — Combinaciones que deben resultar en ALTA."""
        assert predecir_prioridad(prob, dias) == "ALTA"

    @pytest.mark.parametrize("prob,dias", VALORES_VALIDOS["MEDIA"])
    def test_cp0147_devuelve_media(self, prob, dias):
        """CP-0147 (HP) — Combinaciones que deben resultar en MEDIA."""
        assert predecir_prioridad(prob, dias) == "MEDIA"

    @pytest.mark.parametrize("prob,dias", VALORES_VALIDOS["BAJA"])
    def test_cp0147_devuelve_baja(self, prob, dias):
        """CP-0147 (HP) — Combinaciones que deben resultar en BAJA."""
        assert predecir_prioridad(prob, dias) == "BAJA"

    @pytest.mark.parametrize("prob,dias", [(0.9, 1), (0.5, 5), (0.1, 10)])
    def test_cp0147_resultado_siempre_en_conjunto_valido(self, prob, dias):
        """CP-0147 (HP) — El resultado siempre pertenece a {ALTA, MEDIA, BAJA}."""
        assert predecir_prioridad(prob, dias) in PRIORIDADES_VALIDAS
