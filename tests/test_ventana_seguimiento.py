import os
import time

import pytest

tk = pytest.importorskip("tkinter")

import ventana_seguimiento  # noqa: E402
from test_magisfor import escribir, ficha  # noqa: E402

DATOS = os.path.join(os.path.dirname(__file__), "datos")


class AppFalsa:
    def __init__(self, root, cfg):
        self.root, self.cfg = root, cfg


def test_ventana_muestra_el_seguimiento(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla")
    root.withdraw()
    escribir(tmp_path, [ficha("DAVID MAYOR GOMA", "ARRECIFE", "35500", "", "COFARES#26542")])
    with open(os.path.join(DATOS, "historico_cofares.html"), encoding="utf-8") as f:
        html = f.read()

    import cofares_web

    class WebFalsa:
        def __init__(self, *a, **k):
            pass

        def historico(self):
            return html
    monkeypatch.setattr(cofares_web, "EnvioCofares", WebFalsa)
    monkeypatch.setattr(ventana_seguimiento.credenciales, "leer", lambda: ("24145", "x"))
    cfg = {"magisfor": str(tmp_path), "carpeta": "", "perfil_navegador": "", "navegador": "",
           "cofares_url": "", "diagnostico": ""}
    v = ventana_seguimiento.VentanaSeguimiento(AppFalsa(root, cfg))
    limite = time.time() + 10
    while not v.tabla.get_children() and time.time() < limite:
        root.update()
        time.sleep(0.05)
    filas = [v.tabla.item(i, "values") for i in v.tabla.get_children()]
    assert [(f[0], f[2], f[3], f[4]) for f in filas] == [
        ("Enviado", "FM0000961063", "DAVID MAYOR GOMA (26542)", "En reparto  (4/5)"),
        ("Por recibir", "FM0000953714", "Para mi farmacia", "En tránsito  (3/5)"),
        ("Por recibir", "FM0000944080", "Para mi farmacia", "En tránsito  (3/5)"),
    ]
    v.filtro.set("mayor")
    assert len(v.tabla.get_children()) == 1
    v.filtro.set("")
    v.mostrar.set("Por recibir")
    v.rellenar()
    assert [v.tabla.item(i, "values")[2] for i in v.tabla.get_children()] == ["FM0000953714", "FM0000944080"]
    v.ordenar("fecha")  # misma columna: invierte el orden
    assert [v.tabla.item(i, "values")[2] for i in v.tabla.get_children()] == ["FM0000944080", "FM0000953714"]
    v.mostrar.set("Todos")
    if os.environ.get("CAPTURA_SEGUIMIENTO"):
        v.filtro.set("")
        root.deiconify()
        v.lift()
        for _ in range(20):
            root.update()
            time.sleep(0.05)
        os.system(f"import -window root {os.environ['CAPTURA_SEGUIMIENTO']}")
    root.destroy()
