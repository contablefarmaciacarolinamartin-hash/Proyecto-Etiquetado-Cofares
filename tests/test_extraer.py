import os

import pytest

from extraer import ErrorExtraccion, extraer_datos, extraer_de_texto

DATOS = os.path.join(os.path.dirname(__file__), "datos")


def test_pdf_real():
    assert extraer_datos(os.path.join(DATOS, "etiqueta_FM0000921557_1.pdf")) == {
        "codigo": "FM0000921557",
        "remite": "23333",
        "destino": "24145",
        "centro": "4501",
        "n1": "35105/1",
        "n3": "35303/21",
    }


def test_espacios_y_saltos_de_linea_variables():
    texto = ("Etiqueta para el envío: FM0000000001\nFM0000000001\n"
             "Remite: 1  Destino:2\nCentro = 3   N1: 4 / 5\nN3:6/7")
    d = extraer_de_texto(texto)
    assert (d["remite"], d["destino"], d["centro"], d["n1"], d["n3"]) == ("1", "2", "3", "4/5", "6/7")


def test_codigo_desde_nombre_de_archivo():
    texto = "Remite:1 Destino:2 Centro=3 N1:4 N3:5"
    assert extraer_de_texto(texto, r"C:\x\etiqueta_FM0000000009_1.pdf")["codigo"] == "FM0000000009"


def test_falta_un_dato():
    with pytest.raises(ErrorExtraccion, match="N3"):
        extraer_de_texto("FM0000000001 Remite:1 Destino:2 Centro=3 N1:4")
