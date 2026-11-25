"""Ventana "Seguimiento": en qué paso va cada envío de Cofares."""
import os
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import credenciales
from magisfor import ErrorMagisfor, leer_farmacias
from seguimiento import PASOS, leer_historico, totales

DIAS_AVISO = 3  # sin entregar después de estos días: se marca en naranja


class VentanaSeguimiento(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app, self.cfg = app, app.cfg
        self.title("Seguimiento de envíos Cofares")
        self.geometry("1000x480")
        self.minsize(700, 300)
        self.mensajes = queue.Queue()
        self.envios = []

        try:
            self.nombres = {f.cooperador: f.nombre for f in leer_farmacias(self.cfg["magisfor"])
                            if f.cooperador}
        except ErrorMagisfor:
            self.nombres = {}
        acceso = credenciales.leer()
        self.mi_cooperador = str(int(acceso[0])) if acceso and acceso[0].isdigit() else ""

        arriba = tk.Frame(self)
        arriba.pack(fill="x", padx=10, pady=(10, 4))
        tk.Label(arriba, text="Buscar:").pack(side="left")
        self.filtro = tk.StringVar()
        self.filtro.trace_add("write", lambda *a: self.rellenar())
        tk.Entry(arriba, textvariable=self.filtro, width=30).pack(side="left", padx=4)
        self.solo_pendientes = tk.BooleanVar(value=False)
        tk.Checkbutton(arriba, text="Solo sin entregar", variable=self.solo_pendientes,
                       command=self.rellenar).pack(side="left", padx=8)
        self.btn = tk.Button(arriba, text="Actualizar", command=self.actualizar)
        self.btn.pack(side="right")

        columnas = ("tipo", "fecha", "fm", "farmacia", "estado", "dias", "entrega")
        self.tabla = ttk.Treeview(self, columns=columnas, show="headings")
        for col, titulo, ancho in (("tipo", "Tipo", 85), ("fecha", "Solicitado", 130),
                                   ("fm", "Código", 120), ("farmacia", "Farmacia", 280),
                                   ("estado", "Estado", 160), ("dias", "Días", 50),
                                   ("entrega", "Entregado el", 110)):
            self.tabla.heading(col, text=titulo)
            self.tabla.column(col, width=ancho, minwidth=ancho, anchor="w",
                              stretch=(col == "farmacia"))
        self.tabla.tag_configure("entregado", foreground="#15803d")
        self.tabla.tag_configure("retraso", background="#fde68a")
        barra = ttk.Scrollbar(self, orient="vertical", command=self.tabla.yview)
        self.tabla.configure(yscrollcommand=barra.set)
        barra.pack(side="right", fill="y", padx=(0, 10))
        self.tabla.pack(fill="both", expand=True, padx=(10, 0))

        self.estado = tk.Label(self, text="", fg="#1d4ed8", anchor="w")
        self.estado.pack(fill="x", padx=10, pady=6)
        tk.Label(self, text=f"En amarillo: sin entregar después de {DIAS_AVISO} días.",
                 fg="#555", font=("Segoe UI", 8), anchor="w").pack(fill="x", padx=10, pady=(0, 6))
        self.actualizar()

    def farmacia(self, e):
        if e.tipo == "Por recibir" or e.cooperador == self.mi_cooperador:
            return "Para mi farmacia"
        nombre = self.nombres.get(e.cooperador)
        return f"{nombre} ({e.cooperador})" if nombre else f"Cooperador {e.cooperador}"

    def rellenar(self):
        self.tabla.delete(*self.tabla.get_children())
        texto = self.filtro.get().strip().lower()
        for e in self.envios:
            if self.solo_pendientes.get() and e.entregado:
                continue
            fila = (e.tipo, e.solicitado.strftime("%d/%m/%Y %H:%M"), e.fm, self.farmacia(e),
                    f"{e.estado}  ({len(e.pasos)}/{len(PASOS)})", e.dias, e.fecha_entrega)
            if texto and texto not in " ".join(map(str, fila)).lower():
                continue
            etiqueta = "entregado" if e.entregado else ("retraso" if e.dias >= DIAS_AVISO else "")
            self.tabla.insert("", "end", values=fila, tags=(etiqueta,))

    def actualizar(self):
        self.btn.config(state="disabled")
        self.estado.config(text="Consultando Cofares…", fg="#1d4ed8")
        threading.Thread(target=self._consultar, daemon=True).start()
        self.after(200, self._atender)

    def _consultar(self):
        from cofares_web import EnvioCofares, ErrorCofares
        web = EnvioCofares(self.cfg["carpeta"], self.cfg["perfil_navegador"],
                           canal=self.cfg["navegador"] or None, url=self.cfg["cofares_url"],
                           credenciales=credenciales.leer,
                           carpeta_diagnostico=self.cfg["diagnostico"],
                           visible=self.cfg.get("mostrar_navegador", False),
                           avisar=lambda m: self.mensajes.put(("aviso", m)))
        try:
            html = web.historico()
            try:  # la última consulta queda guardada por si hay que revisarla
                os.makedirs(self.cfg["diagnostico"], exist_ok=True)
                with open(os.path.join(self.cfg["diagnostico"], "seguimiento_ultimo.html"),
                          "w", encoding="utf-8") as f:
                    f.write(html)
            except OSError:
                pass
            self.mensajes.put(("fin", (leer_historico(html), totales(html))))
        except ErrorCofares as e:
            self.mensajes.put(("error", str(e)))
        except Exception as e:
            self.mensajes.put(("error", f"Error inesperado: {e}"))

    def _atender(self):
        try:
            while True:
                tipo, dato = self.mensajes.get_nowait()
                if tipo == "aviso":
                    self.estado.config(text=dato, fg="#1d4ed8")
                    continue
                self.btn.config(state="normal")
                if tipo == "error":
                    self.estado.config(text="No se pudo consultar Cofares.", fg="#b91c1c")
                    messagebox.showerror("Seguimiento", dato, parent=self)
                else:
                    self.envios, segun_cofares = dato
                    pendientes = sum(not e.entregado for e in self.envios)
                    texto, color = f"{len(self.envios)} envíos · {pendientes} sin entregar", "#15803d"
                    leidos = {t: sum(e.tipo == t for e in self.envios) for t in segun_cofares}
                    faltan = [f"{t}: Cofares dice {n}, leídos {leidos[t]}"
                              for t, n in segun_cofares.items() if leidos[t] != n]
                    if faltan:
                        texto += ("   ⚠ " + "; ".join(faltan) +
                                  " — manda diagnostico\\seguimiento_ultimo.html")
                        color = "#b45309"
                    self.estado.config(text=texto, fg=color)
                    self.rellenar()
                return
        except queue.Empty:
            pass
        try:
            self.after(200, self._atender)
        except tk.TclError:
            pass  # ventana cerrada
