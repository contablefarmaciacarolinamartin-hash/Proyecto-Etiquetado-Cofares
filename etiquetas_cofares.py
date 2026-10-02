"""Impresor automático de etiquetas Cofares para Brother QL-800.

Vigila la carpeta de descargas: cada PDF de etiqueta nuevo se lee, se imprime
con la plantilla de P-touch Editor y se renombra con '!' delante (o '#' si
ha fallado) para que no se vuelva a imprimir.
"""
import configparser
import fnmatch
import logging
import os
import subprocess
import sys
import time
import tkinter as tk
from tkinter import filedialog, messagebox

from extraer import ErrorExtraccion, extraer_datos
from impresion import ErrorImpresion, formatear, imprimir

INTERVALO_MS = 1000
REINTENTOS_LECTURA = 5  # el navegador puede no haber terminado de escribir

if getattr(sys, "frozen", False):
    BASE = os.path.dirname(sys.executable)
else:
    BASE = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(
    filename=os.path.join(BASE, "registro.log"),
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("etiquetas")


def cargar_config():
    cfg = configparser.ConfigParser(interpolation=None)
    ruta = os.path.join(BASE, "config.ini")
    if not os.path.isfile(ruta):
        raise RuntimeError(f"No se encuentra config.ini en {BASE}")
    try:
        cfg.read(ruta, encoding="utf-8-sig")
    except UnicodeDecodeError:  # guardado con el Bloc de notas como ANSI
        cfg.read(ruta, encoding="cp1252")

    g, imp = cfg["general"], cfg["impresora"]
    carpeta = os.path.expandvars(os.path.expanduser(g.get("carpeta_vigilada")))
    plantilla = os.path.expandvars(imp.get("plantilla", "plantilla.lbx"))
    if not os.path.isabs(plantilla):
        plantilla = os.path.join(BASE, plantilla)
    return {
        "carpeta": carpeta,
        "patron": g.get("patron", "*.pdf"),
        "marca_impresa": g.get("marca_impresa", "!").strip() or "!",
        "marca_error": g.get("marca_error", "#").strip() or "#",
        "pendientes": g.getboolean("imprimir_pendientes_al_arrancar", False),
        "impresora": imp.get("nombre", ""),
        "plantilla": plantilla,
        "copias": imp.getint("copias", 1),
        "formatos": dict(cfg["formato"]),
    }


def un_solo_ejemplar():
    """Evita que haya dos copias del programa abiertas (imprimirían doble)."""
    try:
        import win32api
        import win32event
        import winerror
    except ImportError:
        return True
    un_solo_ejemplar.mutex = win32event.CreateMutex(None, False, "EtiquetasCofaresQL800")
    return win32api.GetLastError() != winerror.ERROR_ALREADY_EXISTS


def marcar(ruta, marca):
    """Renombra 'etiqueta.pdf' a '!etiqueta.pdf' (sin pisar otro archivo)."""
    carpeta = os.path.dirname(ruta)
    nombre, ext = os.path.splitext(os.path.basename(ruta))
    destino = os.path.join(carpeta, f"{marca}{nombre}{ext}")
    n = 1
    while os.path.exists(destino):
        destino = os.path.join(carpeta, f"{marca}{nombre} ({n}){ext}")
        n += 1
    os.rename(ruta, destino)
    return destino


class App:
    def __init__(self, root, cfg):
        self.root, self.cfg = root, cfg
        self.tamanos = {}     # ruta -> (tamaño, fecha) de la vuelta anterior
        self.fallos = {}      # ruta -> intentos de lectura fallidos
        self.ignorados = set()
        self.ultimo = None    # (datos, textos) de la última etiqueta impresa
        self.pausado = False
        self.ocupado = False  # evita reentrar mientras hay un aviso abierto

        root.title("Etiquetas Cofares")
        root.geometry("460x330")
        root.minsize(380, 260)
        root.protocol("WM_DELETE_WINDOW", self.cerrar)

        tk.Label(root, text="Impresor de etiquetas Cofares", font=("Segoe UI", 13, "bold")).pack(pady=(10, 0))
        tk.Label(root, text=f"Vigilando: {cfg['carpeta']}  ({cfg['patron']})",
                 font=("Segoe UI", 8), fg="#555").pack()
        self.estado = tk.Label(root, text="", font=("Segoe UI", 11, "bold"))
        self.estado.pack(pady=6)

        self.lista = tk.Listbox(root, height=8, font=("Consolas", 9))
        self.lista.pack(fill="both", expand=True, padx=10)

        botones = tk.Frame(root)
        botones.pack(pady=8)
        tk.Button(botones, text="Imprimir PDF…", command=self.imprimir_manual).pack(side="left", padx=3)
        self.btn_reimprimir = tk.Button(botones, text="Reimprimir última", state="disabled",
                                        command=self.reimprimir)
        self.btn_reimprimir.pack(side="left", padx=3)
        self.btn_pausa = tk.Button(botones, text="Pausar", command=self.alternar_pausa)
        self.btn_pausa.pack(side="left", padx=3)
        tk.Button(botones, text="Abrir carpeta", command=self.abrir_carpeta).pack(side="left", padx=3)

        if not os.path.isdir(cfg["carpeta"]):
            messagebox.showerror("Carpeta no encontrada",
                                 f"No existe la carpeta vigilada:\n{cfg['carpeta']}\n\nRevisa config.ini.")
        elif not cfg["pendientes"]:
            self.ignorados = set(self.pdfs_en_carpeta())

        self.poner_estado("Esperando etiquetas…", "#1d4ed8")
        self.anotar("Programa iniciado")
        root.after(INTERVALO_MS, self.vigilar)

    # --- interfaz ---------------------------------------------------------
    def poner_estado(self, texto, color):
        self.estado.config(text=texto, fg=color)

    def anotar(self, texto, nivel=logging.INFO):
        log.log(nivel, texto)
        self.lista.insert(0, time.strftime("%H:%M:%S  ") + texto)
        self.lista.delete(200, "end")

    def avisar_error(self, titulo, texto):
        self.poner_estado("ERROR – revisa el aviso", "#b91c1c")
        self.anotar(f"ERROR {titulo}: {texto}", logging.ERROR)
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.bell()
        messagebox.showerror(titulo, texto, parent=self.root)
        self.root.attributes("-topmost", False)

    def alternar_pausa(self):
        self.pausado = not self.pausado
        self.btn_pausa.config(text="Reanudar" if self.pausado else "Pausar")
        if self.pausado:
            self.poner_estado("EN PAUSA – no se imprime nada", "#b45309")
        else:
            # lo descargado durante la pausa no se imprime
            self.ignorados |= set(self.pdfs_en_carpeta())
            self.poner_estado("Esperando etiquetas…", "#1d4ed8")

    def abrir_carpeta(self):
        if hasattr(os, "startfile"):
            os.startfile(self.cfg["carpeta"])
        else:
            subprocess.Popen(["xdg-open", self.cfg["carpeta"]])

    def cerrar(self):
        if messagebox.askyesno("Cerrar", "Si cierras el programa dejarán de imprimirse "
                               "las etiquetas automáticamente.\n\n¿Cerrar de todos modos?"):
            self.root.destroy()

    # --- vigilancia de la carpeta -----------------------------------------
    def pdfs_en_carpeta(self):
        try:
            nombres = os.listdir(self.cfg["carpeta"])
        except OSError:
            return []
        marcas = (self.cfg["marca_impresa"], self.cfg["marca_error"])
        return [os.path.join(self.cfg["carpeta"], n) for n in nombres
                if not n.startswith(marcas)
                and fnmatch.fnmatch(n.lower(), self.cfg["patron"].lower())]

    def vigilar(self):
        try:
            if not self.pausado and not self.ocupado:
                self.revisar_carpeta()
        except Exception as e:  # que un fallo inesperado no pare la vigilancia
            log.exception("Fallo vigilando la carpeta")
            self.anotar(f"Fallo inesperado: {e}", logging.ERROR)
        self.root.after(INTERVALO_MS, self.vigilar)

    def revisar_carpeta(self):
        actuales = set(self.pdfs_en_carpeta())
        self.ignorados &= actuales
        nuevos = []
        for ruta in actuales - self.ignorados:
            try:
                nuevos.append((os.stat(ruta), ruta))
            except OSError:
                pass
        for st, ruta in sorted(nuevos, key=lambda x: x[0].st_mtime):
            firma = (st.st_size, st.st_mtime)
            # se imprime cuando el archivo deja de crecer entre dos vueltas
            if st.st_size == 0 or self.tamanos.get(ruta) != firma:
                self.tamanos[ruta] = firma
                continue
            self.tamanos.pop(ruta, None)
            self.ocupado = True
            try:
                self.procesar(ruta)
            finally:
                self.ocupado = False

    def procesar(self, ruta):
        nombre = os.path.basename(ruta)
        try:
            datos = extraer_datos(ruta)
        except ErrorExtraccion as e:
            intentos = self.fallos.get(ruta, 0) + 1
            if intentos < REINTENTOS_LECTURA:
                self.fallos[ruta] = intentos
                return
            self.fallos.pop(ruta, None)
            self.a_errores(ruta)
            self.avisar_error("No se pudo leer la etiqueta", f"{nombre}\n\n{e}")
            return
        self.fallos.pop(ruta, None)

        if self.enviar(datos, nombre):
            try:
                marcar(ruta, self.cfg["marca_impresa"])
            except OSError as e:
                self.ignorados.add(ruta)
                self.anotar(f"No se pudo renombrar {nombre}: {e}", logging.WARNING)
        else:
            self.a_errores(ruta)

    def a_errores(self, ruta):
        try:
            marcar(ruta, self.cfg["marca_error"])
        except OSError:
            self.ignorados.add(ruta)

    def enviar(self, datos, origen):
        try:
            textos = formatear(datos, self.cfg["formatos"])
        except (KeyError, ValueError) as e:
            self.avisar_error("Error en config.ini", f"Revisa la sección [formato]: {e}")
            return False
        self.poner_estado(f"Imprimiendo {datos['codigo']}…", "#1d4ed8")
        self.root.update_idletasks()
        try:
            imprimir(textos, self.cfg["plantilla"], self.cfg["impresora"], self.cfg["copias"])
        except ErrorImpresion as e:
            self.avisar_error("No se pudo imprimir", f"{origen}\n\n{e}")
            return False
        except Exception as e:
            log.exception("Fallo de b-PAC")
            self.avisar_error("No se pudo imprimir", f"{origen}\n\nError de b-PAC: {e}")
            return False
        self.ultimo = (datos, textos)
        self.btn_reimprimir.config(state="normal")
        self.poner_estado(f"✔ Impresa {datos['codigo']}", "#15803d")
        self.anotar(f"Impresa {datos['codigo']}  {textos['remite']}  {textos['destino']}  "
                    f"{textos['n1']}  {textos['n3']}")
        return True

    def imprimir_manual(self):
        self.ocupado = True
        try:
            self._imprimir_manual()
        finally:
            self.ocupado = False

    def _imprimir_manual(self):
        ruta = filedialog.askopenfilename(title="Elige el PDF de la etiqueta",
                                          initialdir=self.cfg["carpeta"],
                                          filetypes=[("PDF", "*.pdf")])
        if not ruta:
            return
        try:
            datos = extraer_datos(ruta)
        except ErrorExtraccion as e:
            self.avisar_error("No se pudo leer la etiqueta", f"{os.path.basename(ruta)}\n\n{e}")
            return
        self.enviar(datos, os.path.basename(ruta))

    def reimprimir(self):
        if self.ultimo and not self.ocupado:
            self.ocupado = True
            try:
                self.enviar(self.ultimo[0], "Reimpresión")
            finally:
                self.ocupado = False


def main():
    if not un_solo_ejemplar():
        tk.Tk().withdraw()
        messagebox.showinfo("Etiquetas Cofares", "El programa ya está abierto.")
        return
    root = tk.Tk()
    try:
        cfg = cargar_config()
    except Exception as e:
        root.withdraw()
        messagebox.showerror("Etiquetas Cofares", f"Error en la configuración:\n{e}")
        return
    App(root, cfg)
    if "--minimizado" in sys.argv:
        root.iconify()
    root.mainloop()


if __name__ == "__main__":
    main()
