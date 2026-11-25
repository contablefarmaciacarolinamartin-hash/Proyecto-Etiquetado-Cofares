import os
from datetime import datetime

import pytest

from seguimiento import leer_historico

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
