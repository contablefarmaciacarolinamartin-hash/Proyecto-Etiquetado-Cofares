"""Simula b-PAC tal como lo ve pywin32 en modo dinámico."""
import impresion


class Objeto:
    Text = ""


class DocDinamico:
    """Métodos sin parámetros devuelven ya un bool al nombrarlos, como en Windows."""

    def __init__(self):
        self.objetos = {n: Objeto() for n in impresion.OBJETOS}
        self.llamadas = []

    def Open(self, ruta):
        self.llamadas.append("Open")
        return True

    def SetPrinter(self, nombre, ajustar):
        return True

    def GetObject(self, nombre):
        return self.objetos.get(nombre)

    def StartPrint(self, nombre, opciones):
        self.llamadas.append("StartPrint")
        return True

    def PrintOut(self, copias, opciones):
        self.llamadas.append(f"PrintOut{copias}")
        return True

    @property
    def EndPrint(self):
        self.llamadas.append("EndPrint")
        return True

    @property
    def Close(self):
        self.llamadas.append("Close")
        return True


def test_imprime_con_bpac_dinamico(tmp_path, monkeypatch):
    plantilla = tmp_path / "plantilla.lbx"
    plantilla.write_bytes(b"x")
    doc = DocDinamico()
    monkeypatch.setattr(impresion, "_crear_documento", lambda: doc)
    textos = {clave: f"valor {clave}" for clave in impresion.OBJETOS.values()}

    impresion.imprimir(textos, str(plantilla), "Brother QL-800 COFARES", 2)

    assert doc.llamadas == ["Open", "StartPrint", "PrintOut2", "EndPrint", "Close"]
    assert doc.objetos["obj_n1"].Text == "valor n1"
    assert doc.objetos["obj_codigo"].Text == "valor codigo"


def test_formato_vacio_conserva_texto_de_plantilla(tmp_path, monkeypatch):
    plantilla = tmp_path / "plantilla.lbx"
    plantilla.write_bytes(b"x")
    doc = DocDinamico()
    doc.objetos["obj_titulo"].Text = "Etiqueta para envio:"
    monkeypatch.setattr(impresion, "_crear_documento", lambda: doc)
    formatos = {clave: "{codigo}" for clave in impresion.OBJETOS.values()}
    formatos["titulo"] = ""
    textos = impresion.formatear({"codigo": "FM1"}, formatos)

    impresion.imprimir(textos, str(plantilla), "x")

    assert doc.objetos["obj_titulo"].Text == "Etiqueta para envio:"
    assert doc.objetos["obj_remite"].Text == "FM1"


def test_plantilla_del_repositorio_tiene_todos_los_objetos():
    import os
    import re
    import zipfile
    from xml.dom import minidom

    ruta = os.path.join(os.path.dirname(__file__), "..", "plantilla.lbx")
    xml = zipfile.ZipFile(ruta).read("label.xml").decode("utf-8")
    minidom.parseString(xml)
    assert set(re.findall(r'objectName="(\w+)"', xml)) == set(impresion.OBJETOS)
