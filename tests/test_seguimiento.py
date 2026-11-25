import os
from datetime import datetime

import pytest

from seguimiento import leer_historico, totales

DATOS = os.path.join(os.path.dirname(__file__), "datos")


def test_historico_real_de_cofares():
    with open(os.path.join(DATOS, "historico_cofares.html"), encoding="utf-8") as f:
        envios = leer_historico(f.read())
    assert [(e.tipo, e.fm, e.cooperador, e.estado, e.entregado) for e in envios] == [
        ("Enviado", "FM0000961063", "26542", "En reparto", False),
        ("Por recibir", "FM0000953714", "24145", "En tránsito", False),
        ("Por recibir", "FM0000944080", "24145", "En tránsito", False),
    ]
    assert envios[0].solicitado == datetime(2026, 11, 20, 20, 33, 11)
    assert envios[0].pasos == ["Solicitado", "En almacén", "En tránsito", "En reparto"]


def test_entregado_con_fecha():
    html = ('<div id="collapseBultosEnvios">Envío solicitado el 01/11/2026 a las 10:00:00 a la farmacia '
            '0000012345 <p class="pSegPed active"><span>Solicitado</span></p>'
            '<p class="pSegPed active"><span>Entregado</span></p>'
            "<a onclick=\"showDetalle('x?_enviobultos_idBulto=FM0000000001&amp;"
            "_enviobultos_fechaEntrega=03%2F11%2F2026', 'FM0000000001')\">Ver</a></div>")
    e, = leer_historico(html)
    assert (e.fm, e.entregado, e.fecha_entrega, e.cooperador) == ("FM0000000001", True, "03/11/2026", "12345")


def test_sin_historico():
    assert leer_historico("<html>nada</html>") == []


def test_historico_desde_la_web(tmp_path):
    pytest.importorskip("playwright")
    from test_cofares_web import envio, web  # noqa: F401
    gen = web.__wrapped__()
    url, estado = next(gen)
    try:
        html = envio(tmp_path, url).historico()
        e, = leer_historico(html)
        assert (e.fm, e.cooperador, e.estado, e.entregado) == ("FM0000900000", "26542", "Entregado", True)
    finally:
        next(gen, None)


def test_totales_de_cofares():
    with open(os.path.join(DATOS, "historico_cofares.html"), encoding="utf-8") as f:
        assert totales(f.read()) == {"Por recibir": 2}  # el fragmento empieza tras "realizados"


@pytest.mark.parametrize("cabecera, cuando, coop", [
    ("Envío solicitado el 05/11/2026 a las 9:05:03 a la farmacia 0000024145",
     datetime(2026, 11, 5, 9, 5, 3), "24145"),
    ("Envío solicitado el 5/11/2026 a las 09:05 a la farmacia 0000024145",
     datetime(2026, 11, 5, 9, 5), "24145"),
    ("Env&iacute;o solicitado el 05/11/2026 a las 18:40:58 a la farmacia 0000024145",
     datetime(2026, 11, 5, 18, 40, 58), "24145"),
    ("Envío solicitado el 05/11/2026", datetime(2026, 11, 5), ""),
])
def test_cabeceras_variadas(cabecera, cuando, coop):
    html = (f'<div id="collapseBultosRecibidos"><p>{cabecera}</p>'
            '<p class="pSegPed active"><span>Solicitado</span></p>'
            "<a onclick=\"showDetalle('x?_enviobultos_idBulto=FM0000000002', 'FM0000000002')\">Ver</a></div>")
    e, = leer_historico(html)
    assert (e.tipo, e.solicitado, e.cooperador, e.fm) == ("Por recibir", cuando, coop, "FM0000000002")
