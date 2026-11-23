"""De principio a fin: ventana de envío -> web simulada -> PDF -> se imprime con plantilla de frío."""
import os
import time

import pytest

tk = pytest.importorskip("tkinter")
pytest.importorskip("playwright")

import etiquetas_cofares as app_mod  # noqa: E402
import ventana_envio  # noqa: E402
from test_cofares_web import CANAL, CHROMIUM, web  # noqa: E402,F401
from test_magisfor import escribir, ficha  # noqa: E402


@pytest.fixture
def app(tmp_path, monkeypatch, web):  # noqa: F811
    url, estado = web
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla")
    root.withdraw()
    descargas = tmp_path / "Descargas"
    descargas.mkdir()
    magis = tmp_path / "MagisFor"
    magis.mkdir()
    escribir(magis, [ficha("DAVID MAYOR GOMA", "ARRECIFE (LANZAROTE)", "35500", "928802953", "COFARES#26542"),
                     ficha("ANA PERERA BORDES", "ARUCAS", "", "", "COFARES#")])
    impresas, errores = [], []
    monkeypatch.setattr(app_mod, "imprimir",
                        lambda textos, plantilla, *a: impresas.append(dict(textos, plantilla=plantilla)))
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: errores.append(a))
    monkeypatch.setattr(ventana_envio.messagebox, "showerror", lambda *a, **k: errores.append(a))
    monkeypatch.setattr(ventana_envio.messagebox, "askyesno", lambda *a, **k: True)
    monkeypatch.setattr(ventana_envio.credenciales, "leer", lambda: ("24145", "secreta"))

    import cofares_web
    original = cofares_web.EnvioCofares

    def navegador_de_pruebas(*a, **k):
        k.update(visible=False, ejecutable=CHROMIUM, canal=CANAL)
        return original(*a, **k)
    monkeypatch.setattr(cofares_web, "EnvioCofares", navegador_de_pruebas)

    cfg = {
        "carpeta": str(descargas), "patron": "etiqueta_*.pdf", "marca_impresa": "!", "marca_error": "#",
        "pendientes": False, "impresora": "x", "plantilla": "normal.lbx",
        "plantilla_frio": "frio.lbx", "copias": 1,
        "formatos": {"titulo": "Etiq. envío: {codigo}", "codigo": "{codigo}", "remite": "Remite: {remite}",
                     "destino": "Destino: {destino}", "centro": "Centro={centro}",
                     "n1": "N1:{n1}", "n3": "N3:{n3}", "frio": ""},
        "magisfor": str(magis), "cofares_prueba": False, "navegador": "", "cofares_url": url,
        "mostrar_navegador": False,
        "perfil_navegador": str(tmp_path / "perfil"), "diagnostico": str(tmp_path / "diag"),
    }
    a = app_mod.App(root, cfg)
    yield a, descargas, estado, impresas, errores
    root.destroy()


def test_envio_con_frio_de_principio_a_fin(app):
    a, descargas, estado, impresas, errores = app
    v = ventana_envio.VentanaEnvio(a)
    assert v.lista.get(0, "end") == ("DAVID MAYOR GOMA  ·  ARRECIFE (LANZAROTE)  ·  coop. 26542  ·  CP 35500",)
    v.frio.set(True)
    v.generar()
    limite = time.time() + 60
    while not impresas and time.time() < limite:
        a.root.update()
        a.revisar_carpeta()
        time.sleep(0.1)
    assert errores == []
    r = estado["recogidas"][-1]
    assert (r["coop"], r["cp"], r["frio"], r["formula"], r["fm"]) == ("26542", "35500", True, True, "FM0000961064")
    assert len(impresas) == 1
    assert impresas[0]["plantilla"] == "frio.lbx"
    assert impresas[0]["titulo"] == "Etiq. envío: FM0000961063"  # el PDF de pruebas es ese
    assert os.listdir(descargas) == ["!etiqueta_FM0000961064_FRIO.pdf"]
