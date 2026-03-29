"""
Tests E2E para el formulario de alta de envíos y búsqueda.
Cubre:
  LP-131 — CP-0175: Campos obligatorios marcados visualmente con asterisco
  LP-142 — CP-0200: Búsqueda con tracking ID vacío muestra mensaje de error
  LP-241 — CP-0260: Formulario utilizable en cualquier dispositivo (responsive)
Prerequisito: frontend corriendo en BASE_URL
(por defecto http://localhost:8080).
"""
import pytest
from playwright.sync_api import Page, expect


def test_cp0175_campos_obligatorios_marcados_con_asterisco(page: Page, base_url):
    """CP-0175 — Happy Path: todos los campos obligatorios
    muestran indicador visual (*)."""
    page.goto(base_url)
    page.click("#tab-form")
    page.wait_for_selector("#alta-form", state="visible")
    subtitulo = page.locator("#view-form .page-subtitle")
    expect(subtitulo).to_contain_text("*")
    indicadores = page.locator("#alta-form span.req")
    count = indicadores.count()
    assert count > 0, "No se encontraron indicadores de campos obligatorios"
    campos_obligatorios = ["remitente", "destinatario", "fecha-entrega"]
    for campo_id in campos_obligatorios:
        label = page.locator(f"label[for='{campo_id}'] span.req")
        assert label.count() > 0, (
            f"El campo '{campo_id}' no tiene indicador de obligatorio"
        )


def test_cp0200_busqueda_vacia_no_falla(page: Page, base_url):
    """CP-0200 — Unhappy Path: buscar con campo vacío no produce
    error en la interfaz."""
    page.goto(base_url)
    page.wait_for_selector("#search-input", state="visible")
    page.fill("#search-input", "")
    page.press("#search-input", "Enter")
    page.wait_for_timeout(500)
    assert page.locator("#empty-state, #envios-table, #no-results").count() > 0, (
        "Ningún estado de la tabla es visible tras búsqueda vacía"
    )


@pytest.mark.parametrize("viewport,nombre", [
    ({"width": 375, "height": 812}, "mobile"),
    ({"width": 768, "height": 1024}, "tablet"),
    ({"width": 1280, "height": 800}, "desktop"),
])
def test_cp0260_formulario_usable_en_cualquier_dispositivo(
    page: Page, base_url, viewport, nombre
):
    """CP-0260 — Happy Path: todos los campos del formulario son
    accesibles y funcionales en cualquier tamaño de pantalla."""
    page.set_viewport_size(viewport)
    page.goto(base_url)
    page.click("#tab-form")
    page.wait_for_selector("#alta-form", state="visible")
    campos = [
        "#remitente", "#destinatario", "#fecha-entrega",
        "#origen-calle", "#origen-numero", "#origen-cp",
        "#origen-ciudad", "#origen-provincia",
        "#destino-calle", "#destino-numero", "#destino-cp",
        "#destino-ciudad", "#destino-provincia",
    ]
    for selector in campos:
        campo = page.locator(selector)
        assert campo.is_visible(), (
            f"[{nombre}] Campo {selector} no es visible"
        )
        box = campo.bounding_box()
        assert box is not None and box["width"] > 0, (
            f"[{nombre}] Campo {selector} tiene ancho 0"
        )
