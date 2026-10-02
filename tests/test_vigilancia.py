"""Simula la carpeta de descargas sin impresora ni Windows."""
import os
import shutil

import pytest

tk = pytest.importorskip("tkinter")

import etiquetas_cofares as app_mod  # noqa: E402

PDF = os.path.join(os.path.dirname(__file__), "datos", "etiqueta_FM0000921557_1.pdf")


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("sin pantalla")
    root.withdraw()
    impresas, errores = [], []
    monkeypatch.setattr(app_mod, "imprimir", lambda textos, *a: impresas.append(textos))
    monkeypatch.setattr(app_mod.messagebox, "showerror", lambda *a, **k: errores.append(a))
    cfg = {
        "carpeta": str(tmp_path), "patron": "etiqueta_*.pdf",
        "impresos": str(tmp_path / "Etiquetas impresas"),
        "errores": str(tmp_path / "Etiquetas con error"),
        "pendientes": False, "impresora": "x", "plantilla": "x", "copias": 1,
        "formatos": {"titulo": "Envío: {codigo}", "codigo": "{codigo}",
                     "remite": "Remite: {remite}", "destino": "Destino: {destino}",
                     "centro": "Centro={centro}", "n1": "N1:{n1}", "n3": "N3:{n3}"},
    }
    (tmp_path / "etiqueta_FM0000000000_1.pdf").write_bytes(b"viejo")  # ya estaba antes
    app = app_mod.App(root, cfg)
    yield app, tmp_path, impresas, errores
    root.destroy()


def vueltas(app, n=3):
    for _ in range(n):
        app.revisar_carpeta()


def test_imprime_y_mueve(entorno):
    app, carpeta, impresas, errores = entorno
    (carpeta / "otro.pdf").write_bytes(b"no es etiqueta")
    shutil.copy(PDF, carpeta)
    vueltas(app)
    assert errores == []
    assert len(impresas) == 1
    assert impresas[0]["n1"] == "N1:35105/1" and impresas[0]["titulo"] == "Envío: FM0000921557"
    assert os.listdir(carpeta / "Etiquetas impresas") == ["etiqueta_FM0000921557_1.pdf"]
    # lo que ya estaba al arrancar y lo que no encaja con el patrón no se toca
    assert (carpeta / "etiqueta_FM0000000000_1.pdf").exists() and (carpeta / "otro.pdf").exists()
    vueltas(app)
    assert len(impresas) == 1


def test_descarga_a_medias_no_imprime_hasta_completar(entorno):
    app, carpeta, impresas, errores = entorno
    destino = carpeta / "etiqueta_FM0000921557_1.pdf"
    destino.write_bytes(b"")  # Firefox crea primero el archivo vacío
    vueltas(app)
    assert impresas == []
    shutil.copy(PDF, destino)
    vueltas(app)
    assert len(impresas) == 1 and errores == []


def test_pdf_ilegible_va_a_errores(entorno):
    app, carpeta, impresas, errores = entorno
    (carpeta / "etiqueta_roto.pdf").write_bytes(b"%PDF-basura")
    vueltas(app, 10)
    assert impresas == [] and len(errores) == 1
    assert os.listdir(carpeta / "Etiquetas con error") == ["etiqueta_roto.pdf"]
