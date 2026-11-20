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
        "frio": "",
    }


def test_pdf_real_sin_n3():
    d = extraer_datos(os.path.join(DATOS, "etiqueta_FM0000961063.pdf"))
    assert d == {"codigo": "FM0000961063", "remite": "24145", "destino": "26542",
                 "centro": "4501", "n1": "35124/55", "n3": "", "frio": ""}


def test_espacios_y_saltos_de_linea_variables():
    texto = ("Etiqueta para el envío: FM0000000001\nFM0000000001\n"
             "Remite: 1  Destino:2\nCentro = 3   N1: 4 / 5\nN3:6/7")
    d = extraer_de_texto(texto)
    assert (d["remite"], d["destino"], d["centro"], d["n1"], d["n3"]) == ("1", "2", "3", "4/5", "6/7")


def test_codigo_desde_nombre_de_archivo():
    texto = "Remite:1 Destino:2 Centro=3 N1:4 N3:5"
    assert extraer_de_texto(texto, r"C:\x\etiqueta_FM0000000009_1.pdf")["codigo"] == "FM0000000009"


def test_falta_un_dato_obligatorio():
    with pytest.raises(ErrorExtraccion, match="Centro"):
        extraer_de_texto("FM0000000001 Remite:1 Destino:2 N1:4 N3:5")


@pytest.mark.parametrize("texto, n1, n3", [
    ("FM0000961063 Remite:1 Destino:2 Centro=3 N1:4", "4", ""),          # sin N3
    ("FM0000961063 Remite:1 Destino:2 Centro=3 N1:4 N3:", "4", ""),      # N3 vacío
    ("FM0000961063 Remite:1 Destino:2 Centro=3 N1: N3:5", "", "5"),      # N1 vacío
    ("FM0000961063 Remite:1 Destino:2 Centro=3", "", ""),                # ninguno
    ("FM0000961063 Remite:1 Destino:2 Centro=3 N1:4 N3:\nFRIO", "4", ""),  # N3 vacío y frío
])
def test_n1_n3_son_opcionales(texto, n1, n3):
    d = extraer_de_texto(texto)
    assert (d["remite"], d["destino"], d["centro"], d["n1"], d["n3"]) == ("1", "2", "3", n1, n3)


LINEA = "FM0000000001\nRemite:1 Destino:2 Centro=3 N1:4 /1 N3:5/21"


@pytest.mark.parametrize("texto, esperado", [
    (LINEA + " FRIO", "FRÍO"),
    (LINEA + "   Frío", "FRÍO"),
    (LINEA + "\nNEVERA", "NEVERA"),
    ("FRÍO\n" + LINEA, "FRÍO"),
    (LINEA, ""),
    (LINEA + "\nFrioleras", ""),
])
def test_aviso_de_frio(texto, esperado):
    d = extraer_de_texto(texto)
    assert d["frio"] == esperado
    assert d["n3"] == "5/21" and d["n1"] == "4/1"


def test_frio_por_nombre_de_archivo():
    texto = "FM0000961063 Remite:1 Destino:2 Centro=3 N1:4"
    assert extraer_de_texto(texto, r"C:\D\etiqueta_FM0000961063_FRIO.pdf")["frio"] == "FRÍO"
    assert extraer_de_texto(texto, r"C:\D\etiqueta_FM0000961063_FRIO (1).pdf")["frio"] == "FRÍO"
    assert extraer_de_texto(texto, r"C:\D\etiqueta_FM0000961063.pdf")["frio"] == ""
