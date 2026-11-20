"""Lectura (solo lectura) de las farmacias clientes de Magisfor.

Magisfor guarda las farmacias en dos archivos de registros de tamaño fijo y
texto Windows-1252: Farmacias.med (368 bytes por farmacia) y Farmacias.mee
(540 bytes). La farmacia n.º i ocupa la posición i en los dos.

Se trabaja sobre una copia para no bloquear los archivos mientras Magisfor
está abierto, y nunca se escribe en ellos.
"""
import os
import re
import shutil
import tempfile
from dataclasses import dataclass

LARGO_MED = 368
LARGO_MEE = 540


class ErrorMagisfor(Exception):
    pass


@dataclass
class Farmacia:
    ficha: int
    nombre: str
    poblacion: str
    cp: str
    provincia: str
    telefono: str
    forma_envio: str
    ruta: str
    activa: bool

    @property
    def cooperador(self):
        """En la ficha se apunta el nº de cooperador de Cofares en 'Ruta'."""
        return re.sub(r"\D", "", self.ruta)

    def __str__(self):
        return f"{self.nombre} — {self.poblacion} (coop. {self.cooperador}, CP {self.cp})"


def _texto(b):
    return b.decode("cp1252", errors="replace").replace("\x00", " ").strip()


def _registros(ruta, largo):
    with open(ruta, "rb") as f:
        datos = f.read()
    if not datos or len(datos) % largo:
        raise ErrorMagisfor(
            f"{os.path.basename(ruta)} no tiene el formato esperado "
            f"({len(datos)} bytes no es múltiplo de {largo}). "
            "¿Ha cambiado la versión de Magisfor?")
    return [datos[i:i + largo] for i in range(0, len(datos), largo)]


def leer_farmacias(carpeta):
    rutas = [os.path.join(carpeta, n) for n in ("Farmacias.med", "Farmacias.mee")]
    for r in rutas:
        if not os.path.isfile(r):
            raise ErrorMagisfor(f"No se encuentra {r}")
    with tempfile.TemporaryDirectory() as tmp:
        copias = []
        for r in rutas:
            destino = os.path.join(tmp, os.path.basename(r))
            shutil.copyfile(r, destino)
            copias.append(destino)
        med = _registros(copias[0], LARGO_MED)
        mee = _registros(copias[1], LARGO_MEE)
    if len(med) != len(mee):
        raise ErrorMagisfor("Farmacias.med y Farmacias.mee no tienen el mismo número de fichas.")

    farmacias = []
    for i, (a, e) in enumerate(zip(med, mee), 1):
        forma, _, ruta = _texto(a[332:352]).partition("#")
        farmacias.append(Farmacia(
            ficha=i,
            nombre=_texto(a[0:60]),
            poblacion=_texto(a[60:90]),
            cp=_texto(a[90:95]),
            provincia=_texto(a[95:115]),
            telefono=_texto(a[115:135]),
            forma_envio=forma.strip(),
            ruta=ruta.strip(),
            activa=e[33] == 0,  # 0 = activa, 1 = no activa
        ))
    return farmacias


def farmacias_cofares(carpeta):
    """Farmacias activas con nº de cooperador y CP: las que se pueden enviar por Cofares."""
    return sorted((f for f in leer_farmacias(carpeta) if f.activa and f.cooperador and f.cp),
                  key=lambda f: f.nombre)


def incompletas(carpeta):
    """Activas a las que les falta cooperador o CP (para avisar)."""
    return [f for f in leer_farmacias(carpeta) if f.activa and not (f.cooperador and f.cp)]
