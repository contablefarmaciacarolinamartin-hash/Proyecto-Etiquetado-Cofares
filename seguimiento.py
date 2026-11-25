"""Interpreta el histórico de "Envío de Bultos" de Cofares: en qué paso va cada envío.

Cada envío aparece así en la página:
    Envío solicitado el 20/11/2026 a las 20:33:11 a la farmacia 0000026542
    Solicitado · En almacén · En tránsito · En reparto · Entregado
(los pasos cumplidos llevan la clase "pSegPed active") y un enlace "Ver" con
idBulto=FM..., fechaSolicitud y fechaEntrega (00/00/0000 si aún no se ha entregado).
"""
import html as html_mod
import re
from dataclasses import dataclass, field
from datetime import datetime

PASOS = ["Solicitado", "En almacén", "En tránsito", "En reparto", "Entregado"]
SECCIONES = {"collapseBultosEnvios": "Enviado", "collapseBultosRecibidos": "Por recibir"}


@dataclass
class Envio:
    tipo: str                 # "Enviado" (míos) o "Por recibir"
    fm: str
    solicitado: datetime
    cooperador: str
    pasos: list = field(default_factory=list)   # pasos cumplidos
    fecha_entrega: str = ""

    @property
    def estado(self):
        return self.pasos[-1] if self.pasos else "Desconocido"

    @property
    def entregado(self):
        return "Entregado" in self.pasos

    @property
    def dias(self):
        return (datetime.now() - self.solicitado).days


def _texto(s):
    return re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def leer_historico(html):
    """Lista de Envio a partir del HTML de la página de envío de bultos."""
    envios = []
    # trozos de cada sección (de su id hasta la siguiente sección)
    posiciones = sorted((html.find(f'id="{sid}"'), tipo) for sid, tipo in SECCIONES.items()
                        if html.find(f'id="{sid}"') >= 0)
    for n, (inicio, tipo) in enumerate(posiciones):
        fin = posiciones[n + 1][0] if n + 1 < len(posiciones) else len(html)
        seccion = html[inicio:fin]
        trozos = re.split(r"(?=Env[ií]o solicitado el )", seccion)[1:]
        for trozo in trozos:
            m = re.match(r"Env[ií]o solicitado el (\d{2}/\d{2}/\d{4}) a las (\d{2}:\d{2}:\d{2})"
                         r" a la farmacia (\d+)", trozo)
            if not m:
                continue
            fm = re.search(r"(?:idBulto|envio)=(FM\d+)", trozo) or re.search(r"'(FM\d+)'", trozo)
            pasos = [_texto(p) for p in re.findall(
                r'<p class="pSegPed active"[^>]*>(.*?)</p>', trozo, re.S)]
            entrega = re.search(r"fechaEntrega=(\d{2})%2F(\d{2})%2F(\d{4})", trozo)
            fecha_entrega = ""
            if entrega and entrega.group(3) != "0000":
                fecha_entrega = "/".join(entrega.groups())
            envios.append(Envio(
                tipo=tipo,
                fm=fm.group(1) if fm else "",
                solicitado=datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M:%S"),
                cooperador=str(int(m.group(3))),
                pasos=[p for p in pasos if p],
                fecha_entrega=fecha_entrega,
            ))
    return sorted(envios, key=lambda e: e.solicitado, reverse=True)
