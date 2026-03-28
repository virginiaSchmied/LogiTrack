"""
Tests E2E para accesibilidad visual.

Cubre:
  LP-248 — CP-0281: Contraste mínimo WCAG 2.1 AA (≥4.5:1) para texto sobre fondo
  LP-248 — CP-0282: Colores claramente diferenciados para cada estado del envío

Prerequisito: frontend corriendo en BASE_URL (por defecto http://localhost:8080).
"""
from typing import Optional, Tuple
from playwright.sync_api import Page


# ── Helpers de contraste WCAG 2.1 ────────────────────────────────────────────

def _canal_lineal(c: int) -> float:
    s = c / 255
    return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4


def _luminancia(r: int, g: int, b: int) -> float:
    return 0.2126 * _canal_lineal(r) + 0.7152 * _canal_lineal(g) + 0.0722 * _canal_lineal(b)


def _ratio_contraste(rgb1: tuple, rgb2: tuple) -> float:
    l1, l2 = _luminancia(*rgb1), _luminancia(*rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def _parse_rgb(css: str) -> Optional[Tuple[int, int, int]]:
    """Convierte 'rgb(r, g, b)' o 'rgba(r, g, b, a)' a tupla (r, g, b). Retorna None si no parseable."""
    try:
        nums = [
            int(x.strip())
            for x in css.replace("rgba", "").replace("rgb", "").strip("() ").split(",")[:3]
        ]
        return tuple(nums)
    except (ValueError, IndexError):
        return None


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_cp0281_contraste_texto_cumple_wcag_aa(page: Page, base_url):
    """CP-0281 — Happy Path: texto sobre fondo cumple contraste WCAG 2.1 AA (≥4.5:1)."""
    page.goto(base_url)
    page.wait_for_selector(".page-title", state="visible")

    elementos = page.evaluate("""() => {
        const selectores = 'h1, .page-title, .page-subtitle, td, th, .form-label';
        return Array.from(document.querySelectorAll(selectores)).slice(0, 15).map(el => {
            const s = window.getComputedStyle(el);
            return { tag: el.tagName, color: s.color, background: s.backgroundColor };
        });
    }""")

    TRANSPARENTE = {"rgba(0, 0, 0, 0)", "transparent"}
    fallos = []
    for el in elementos:
        if el["background"] in TRANSPARENTE:
            continue
        fg = _parse_rgb(el["color"])
        bg = _parse_rgb(el["background"])
        if fg is None or bg is None:
            continue
        ratio = _ratio_contraste(fg, bg)
        if ratio < 4.5:
            fallos.append(
                f"<{el['tag']}> ratio={ratio:.2f}:1  color={el['color']}  fondo={el['background']}"
            )

    assert not fallos, "Elementos con contraste insuficiente (WCAG AA < 4.5:1):\n" + "\n".join(fallos)


def test_cp0282_badges_de_estados_tienen_colores_diferenciados(page: Page, base_url):
    """CP-0282 — Happy Path: cada clase de badge de estado tiene un color de fondo visualmente distinto."""
    page.goto(base_url)

    colores = page.evaluate("""() => {
        const clases = [
            'badge-registrado', 'badge-transito', 'badge-sucursal',
            'badge-distribucion', 'badge-entregado', 'badge-cancelado'
        ];
        const result = {};
        clases.forEach(cls => {
            const el = document.createElement('span');
            el.className = 'badge ' + cls;
            el.style.position = 'absolute';
            el.style.visibility = 'hidden';
            document.body.appendChild(el);
            result[cls] = window.getComputedStyle(el).backgroundColor;
            document.body.removeChild(el);
        });
        return result;
    }""")

    colores_unicos = set(colores.values())
    assert len(colores_unicos) == len(colores), (
        "Hay colores de badge duplicados entre estados del envío:\n"
        + "\n".join(f"  {cls}: {color}" for cls, color in colores.items())
    )
