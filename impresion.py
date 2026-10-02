"""Impresión en la Brother QL-800 usando la plantilla de P-touch Editor (b-PAC)."""
import os


class ErrorImpresion(Exception):
    pass


# Nombre del objeto en la plantilla -> clave del texto ya formateado
OBJETOS = {
    "obj_titulo": "titulo",
    "obj_codigo": "codigo",
    "obj_remite": "remite",
    "obj_destino": "destino",
    "obj_centro": "centro",
    "obj_n1": "n1",
    "obj_n3": "n3",
}


def formatear(datos, formatos):
    """Aplica los formatos de config.ini, p. ej. 'Remite: {remite}'."""
    return {clave: formatos[clave].format(**datos) for clave in OBJETOS.values()}


def _crear_documento():
    try:
        import win32com.client
    except ImportError as e:
        raise ErrorImpresion("Falta pywin32 (pip install pywin32).") from e
    try:
        return win32com.client.Dispatch("bpac.Document")
    except Exception as e:
        raise ErrorImpresion(
            "No se encuentra Brother b-PAC.\n\n"
            "Instala 'b-PAC Client Component' de la web de Brother. Debe ser de "
            "64 bits si este programa es de 64 bits (lo normal)."
        ) from e


def _llamar(doc, metodo, *args):
    """Llama a un método de b-PAC.

    Con pywin32 en modo dinámico, los métodos sin parámetros (EndPrint, Close)
    se ejecutan ya al nombrarlos y devuelven su resultado (un bool), así que
    volver a llamarlos daba "'bool' object is not callable".
    """
    atributo = getattr(doc, metodo)
    return atributo(*args) if callable(atributo) else atributo


def imprimir(textos, plantilla, impresora, copias=1):
    if not os.path.isfile(plantilla):
        raise ErrorImpresion(f"No se encuentra la plantilla:\n{plantilla}")

    doc = _crear_documento()
    if not _llamar(doc, "Open", os.path.abspath(plantilla)):
        raise ErrorImpresion(f"b-PAC no puede abrir la plantilla:\n{plantilla}")
    try:
        if impresora and not _llamar(doc, "SetPrinter", impresora, True):
            raise ErrorImpresion(
                f"No se encuentra la impresora '{impresora}'.\n"
                "Revisa el nombre en config.ini (Panel de control > Impresoras)."
            )
        for nombre, clave in OBJETOS.items():
            obj = _llamar(doc, "GetObject", nombre)
            if obj is None:
                raise ErrorImpresion(f"La plantilla no tiene el objeto '{nombre}'.")
            obj.Text = textos[clave]

        if _llamar(doc, "StartPrint", "", 0) is False:
            raise ErrorImpresion("No se pudo iniciar la impresión.")
        ok = _llamar(doc, "PrintOut", int(copias), 0)
        if _llamar(doc, "EndPrint") is False or ok is False:
            raise ErrorImpresion(
                "La impresora no ha aceptado el trabajo. "
                "¿Está encendida, conectada y con etiquetas?"
            )
    finally:
        try:
            _llamar(doc, "Close")
        except Exception:
            pass  # que un fallo al cerrar no tape el error real
