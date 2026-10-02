"""Lectura de los datos de una etiqueta de envío Cofares en PDF.

No depende de Windows, así que se puede probar en cualquier equipo:
    python extraer.py ruta\\a\\etiqueta.pdf
"""
import os
import re
import sys

from pypdf import PdfReader

# Etiquetas que aparecen en la línea de datos del PDF, p. ej.:
#   Remite:23333      Destino:24145      Centro=4501 N1:35105 /1   N3:35303/21
CAMPOS = {
    "remite": "Remite",
    "destino": "Destino",
    "centro": "Centro",
    "n1": "N1",
    "n3": "N3",
}
_SIGUIENTE = r"(?=\s+(?:Remite|Destino|Centro|N\d)\s*[:=]|\s*$)"


class ErrorExtraccion(Exception):
    pass


def leer_texto(ruta_pdf):
    reader = PdfReader(ruta_pdf)
    return "\n".join((pagina.extract_text() or "") for pagina in reader.pages)


def _limpiar(valor):
    valor = re.sub(r"\s+", " ", valor).strip()
    # "35105 /1" -> "35105/1" (mismo formato que N3)
    return re.sub(r"\s*/\s*", "/", valor)


def extraer_de_texto(texto, nombre_archivo=""):
    datos = {}

    codigo = re.search(r"\b(FM\d{6,})\b", texto)
    if not codigo:
        codigo = re.search(r"(FM\d{6,})", os.path.basename(nombre_archivo))
    if not codigo:
        raise ErrorExtraccion("No se encuentra el código de envío (FM...) en el PDF.")
    datos["codigo"] = codigo.group(1)

    faltan = []
    for clave, etiqueta in CAMPOS.items():
        m = re.search(rf"\b{etiqueta}\s*[:=]\s*(.+?){_SIGUIENTE}", texto, re.MULTILINE)
        if m and _limpiar(m.group(1)):
            datos[clave] = _limpiar(m.group(1))
        else:
            faltan.append(etiqueta)
    if faltan:
        raise ErrorExtraccion("Faltan datos en el PDF: " + ", ".join(faltan))
    return datos


def extraer_datos(ruta_pdf):
    try:
        texto = leer_texto(ruta_pdf)
    except Exception as e:
        raise ErrorExtraccion(f"No se puede leer el PDF: {e}") from e
    return extraer_de_texto(texto, ruta_pdf)


if __name__ == "__main__":
    for ruta in sys.argv[1:]:
        print(ruta)
        for k, v in extraer_datos(ruta).items():
            print(f"  {k:8} {v}")
