from datetime import datetime


def pytest_configure(config):
    """Genera el reporte HTML con fecha y hora en el nombre para trazabilidad."""
    now = datetime.now().strftime("%Y-%m-%d_%H-%M")
    config.option.htmlpath = f"tests/reporte_{now}.html"
