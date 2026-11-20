"""Prueba el envío automático contra una copia simulada del área privada de Cofares.

La simulación imita lo visto en la web real: "Nuevo envío" es un enlace que abre
el formulario en un marco emergente (altaEnvio_iframe_), las casillas se activan
al validar el destino, hay confirmación con "Aceptar" y el histórico tiene un
icono PDF por envío que llama a descargarPDF(...).
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

pytest.importorskip("playwright")

from cofares_web import EnvioCofares, ErrorCofares  # noqa: E402

AQUI = os.path.dirname(__file__)
WEB = os.path.join(AQUI, "web_simulada")
PDF = os.path.join(AQUI, "datos", "etiqueta_FM0000961063.pdf")
# Chromium para las pruebas: el de la variable, el preinstalado o el de "playwright install".
CHROMIUM = os.environ.get("CHROMIUM_PRUEBAS", "/opt/pw-browsers/chromium")
if not os.path.exists(CHROMIUM):
    CHROMIUM = None
CANAL = os.environ.get("PRUEBAS_CANAL") or None  # p. ej. "msedge" en Windows
RUTA = "/group/canal-online/envio-de-bultos"
EMERGENTE = RUTA + "?p_p_id=enviobultos&p_p_state=pop_up&_enviobultos_mvcRenderCommandName=%2Fenvio%2Fbultos%2FaltaEnvio"


def pagina_envios(recogidas):
    historico = "".join(
        f'<p class="envio-title">Envío solicitado el 20/11/2026 a las {r["hora"]} a la farmacia '
        f'{int(r["coop"]):010d}</p><div class="descargar-pdf"><a href="javascript:void(0)" '
        f"onclick=\"descargarPDF('{RUTA}?p_p_resource_id=%2Fenvio%2Fbultos%2FdescargarPDF"
        f"&amp;_enviobultos_envio={r['fm']}')\"><img class=\"ancho-pdf\"></a></div>"
        for r in reversed(recogidas))
    return f"""<!doctype html><meta charset="utf-8"><title>Envío de Bultos</title>
<a href="javascript:void(0)" onclick="showDetalle('{EMERGENTE}','altaEnvio')">Nuevo envío</a>
<h1>Histórico de envíos</h1><div id="collapseBultosEnvios" class="collapse">{historico}</div>
<script>
function descargarPDF(url) {{ window.location = url; }}
function showDetalle(url, id) {{
  const f = document.createElement('iframe');
  f.id = id + '_iframe_'; f.title = 'ENVÍO ENTRE FARMACIAS'; f.src = url;
  f.style = 'width:900px;height:600px'; document.body.appendChild(f);
}}
</script>""".encode()


@pytest.fixture
def web():
    estado = {"sesion": False, "sin_enlace": False, "recogidas": [
        # envío anterior a la misma farmacia: no debe confundirse con el nuevo
        {"coop": "26542", "fm": "FM0000900000", "hora": "08:00:00"}]}

    class Manejador(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _enviar(self, cuerpo, tipo="text/html; charset=utf-8", extra=None):
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(cuerpo)

        def do_GET(self):
            if self.path.startswith(RUTA) and estado["sesion"]:
                if "descargarPDF" in self.path:
                    fm = self.path.rsplit("envio=", 1)[1]
                    with open(PDF, "rb") as f:
                        return self._enviar(f.read(), "application/pdf", {
                            "Content-Disposition": f'attachment; filename="etiqueta_{fm}.pdf"'})
                if "pop_up" in self.path:
                    with open(os.path.join(WEB, "formulario.html"), "rb") as f:
                        html = f.read()
                    if estado["sin_enlace"]:
                        html = b"<script>window.SIN_ENLACE=true</script>" + html
                    return self._enviar(html)
                return self._enviar(pagina_envios(estado["recogidas"]))
            if self.path.startswith("/pdf?envio="):
                fm = self.path.split("=", 1)[1]
                with open(PDF, "rb") as f:
                    return self._enviar(f.read(), "application/pdf", {
                        "Content-Disposition": f'attachment; filename="etiqueta_{fm}.pdf"'})
            with open(os.path.join(WEB, "login.html"), "rb") as f:
                self._enviar(f.read())

        def do_POST(self):
            datos = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if self.path == "/entrar":
                if datos == {"u": "24145", "p": "secreta"}:
                    estado["sesion"] = True
                    return self._enviar(b"ok")
                self.send_response(403)
                return self.end_headers()
            datos["fm"] = f"FM{961063 + len(estado['recogidas']):010d}"
            datos["hora"] = "23:59:59"
            estado["recogidas"].append(datos)
            self._enviar(datos["fm"].encode())

    servidor = ThreadingHTTPServer(("127.0.0.1", 0), Manejador)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{servidor.server_port}{RUTA}", estado
    servidor.shutdown()


def envio(tmp_path, url, credenciales=("24145", "secreta")):
    descargas = tmp_path / "descargas"
    descargas.mkdir(exist_ok=True)
    return EnvioCofares(str(descargas), str(tmp_path / "perfil"), canal=CANAL, url=url,
                        credenciales=lambda: credenciales, visible=False, ejecutable=CHROMIUM,
                        carpeta_diagnostico=str(tmp_path / "diagnostico"), avisar=lambda m: None)


def nuevas(estado):
    return [{k: r[k] for k in ("coop", "cp", "frio", "formula")} for r in estado["recogidas"][1:]]


def test_envio_con_frio(tmp_path, web):
    url, estado = web
    pdf = envio(tmp_path, url).enviar("26542", "35500", frio=True, prueba=False, confirmar=lambda: True)
    assert nuevas(estado) == [{"coop": "26542", "cp": "35500", "frio": True, "formula": True}]
    # el nombre lleva _FRIO para que se imprima con la plantilla de frío
    assert os.path.basename(pdf) == "etiqueta_FM0000961064_FRIO.pdf"
    with open(pdf, "rb") as a, open(PDF, "rb") as b:
        assert a.read() == b.read()
    assert os.listdir(tmp_path / "descargas") == ["etiqueta_FM0000961064_FRIO.pdf"]


def test_envio_sin_frio(tmp_path, web):
    url, estado = web
    pdf = envio(tmp_path, url).enviar("26542", "35500", frio=False, prueba=False, confirmar=lambda: True)
    assert nuevas(estado) == [{"coop": "26542", "cp": "35500", "frio": False, "formula": True}]
    assert os.path.basename(pdf) == "etiqueta_FM0000961064.pdf"


def test_pdf_desde_el_historico_si_no_hay_enlace(tmp_path, web):
    url, estado = web
    estado["sin_enlace"] = True
    pdf = envio(tmp_path, url).enviar("26542", "35500", frio=False, prueba=False, confirmar=lambda: True)
    # coge el envío nuevo, no el FM0000900000 que ya estaba en el histórico
    assert os.path.basename(pdf) == "etiqueta_FM0000961064.pdf"


def test_modo_prueba_no_solicita_recogida(tmp_path, web):
    url, estado = web
    assert envio(tmp_path, url).enviar("26542", "35500", frio=True, prueba=True) is None
    assert nuevas(estado) == []


def test_cancelar_en_la_confirmacion(tmp_path, web):
    url, estado = web
    e = envio(tmp_path, url)
    assert e.enviar("26542", "35500", frio=False, prueba=False, confirmar=lambda: False) is None
    assert nuevas(estado) == []


def test_destino_no_valido(tmp_path, web, monkeypatch):
    import cofares_web
    monkeypatch.setattr(cofares_web, "ESPERA", 3000)
    url, estado = web
    with pytest.raises(ErrorCofares, match="no ha validado el destino"):
        envio(tmp_path, url).enviar("11111", "35500", frio=False, prueba=False, confirmar=lambda: True)
    assert nuevas(estado) == []
    assert any(n.endswith(".png") for n in os.listdir(tmp_path / "diagnostico"))


def test_contraseña_incorrecta(tmp_path, web, monkeypatch):
    import cofares_web
    monkeypatch.setattr(cofares_web, "ESPERA", 3000)
    url, _ = web
    with pytest.raises(ErrorCofares, match="iniciar sesión"):
        envio(tmp_path, url, ("24145", "mala")).enviar("26542", "35500", frio=False, prueba=True)


def test_pdf_del_historico_con_html_real():
    """Fragmento del histórico real de Cofares (20/11/2026)."""
    html = (
        '<p class="envio-title">Envío solicitado el 20/11/2026 a las 20:33:11 a la farmacia 0000026542</p>'
        '<div class="descargar-pdf"><a id="" class="" href="javascript:void(0)" onclick="descargarPDF('
        "'https://areaprivada.cofares.es/group/canal-online/envio-de-bultos?p_p_id=enviobultos&amp;"
        "p_p_resource_id=%2Fenvio%2Fbultos%2FdescargarPDF&amp;_enviobultos_envio=FM0000961063&amp;"
        "_enviobultos_descripcionBulto=+Remite%3A24145');\"><img class=\"ancho-pdf\"></a></div>")
    url = EnvioCofares._pdf_del_historico(html, "https://areaprivada.cofares.es/x", "26542", set())
    assert "envio=FM0000961063" in url and "&amp;" not in url
    assert EnvioCofares._pdf_del_historico(html, "https://x", "26542", {"FM0000961063"}) is None
    assert EnvioCofares._pdf_del_historico(html, "https://x", "11111", set()) is None
