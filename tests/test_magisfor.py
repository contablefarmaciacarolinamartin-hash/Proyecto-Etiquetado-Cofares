"""Lectura de Farmacias.med / Farmacias.mee con fichas sintéticas del mismo formato."""
import pytest

from magisfor import ErrorMagisfor, farmacias_cofares, incompletas, leer_farmacias


def ficha(nombre, poblacion="", cp="", tel="", envio="", activa=True):
    med = bytearray(b" " * 368)
    for ini, largo, valor in ((0, 60, nombre), (60, 30, poblacion), (90, 5, cp),
                              (95, 20, "LAS PALMAS"), (115, 20, tel), (332, 20, envio)):
        med[ini:ini + largo] = valor.encode("cp1252").ljust(largo)[:largo]
    med[321:331] = b"\x01\x00\x01\x01@#$@#$"
    mee = bytearray(b" " * 540)
    mee[0:40] = b"\x00" * 40
    mee[33] = 0 if activa else 1
    return bytes(med), bytes(mee)


def escribir(carpeta, fichas):
    (carpeta / "Farmacias.med").write_bytes(b"".join(f[0] for f in fichas))
    (carpeta / "Farmacias.mee").write_bytes(b"".join(f[1] for f in fichas))


def test_lee_fichas(tmp_path):
    escribir(tmp_path, [
        ficha("DAVID MAYOR GOMA", "ARRECIFE (LANZAROTE)", "35500", "928802953", "COFARES#26542"),
        ficha("CORALIA QUINTERO CASANOVA", "ANTIGUA", "", "928878053", "#", activa=False),
        ficha("FARMACIA EJEMPLO", "VALENCIA", "46021", "3662255", "Mensajero#A1"),
        ficha("ANA PERERA BORDES", "ARUCAS", "35413", "928627099", "COFARES#"),
    ])
    f = leer_farmacias(tmp_path)
    assert [x.nombre for x in f] == ["DAVID MAYOR GOMA", "CORALIA QUINTERO CASANOVA",
                                    "FARMACIA EJEMPLO", "ANA PERERA BORDES"]
    d = f[0]
    assert (d.ficha, d.cp, d.poblacion, d.forma_envio, d.cooperador, d.activa) == \
        (1, "35500", "ARRECIFE (LANZAROTE)", "COFARES", "26542", True)
    assert f[1].activa is False
    assert f[2].cooperador == "1"  # "A1": la ruta no es un cooperador, pero no rompe
    # solo activas con cooperador y CP
    assert [x.nombre for x in farmacias_cofares(tmp_path)] == ["DAVID MAYOR GOMA", "FARMACIA EJEMPLO"]
    assert [x.nombre for x in incompletas(tmp_path)] == ["ANA PERERA BORDES"]


def test_acentos(tmp_path):
    escribir(tmp_path, [ficha("Mª DOLORES ZUMBADO PEÑA", "TÍAS", "35572", "", "COFARES#12345")])
    assert leer_farmacias(tmp_path)[0].nombre == "Mª DOLORES ZUMBADO PEÑA"


def test_formato_desconocido(tmp_path):
    (tmp_path / "Farmacias.med").write_bytes(b"x" * 100)
    (tmp_path / "Farmacias.mee").write_bytes(b"x" * 540)
    with pytest.raises(ErrorMagisfor, match="formato"):
        leer_farmacias(tmp_path)


def test_falta_archivo(tmp_path):
    with pytest.raises(ErrorMagisfor, match="No se encuentra"):
        leer_farmacias(tmp_path)
