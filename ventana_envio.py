"""Ventana "Nuevo envío Cofares": elegir farmacia, frío sí/no, y generar la etiqueta."""
import queue
import threading
import tkinter as tk
from tkinter import messagebox, simpledialog

import credenciales
from magisfor import ErrorMagisfor, farmacias_cofares, incompletas


class VentanaEnvio(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app, self.cfg = app, app.cfg
        self.title("Nuevo envío Cofares")
        self.geometry("560x460")
        self.minsize(460, 380)
        self.transient(app.root)
        self.mensajes = queue.Queue()
        self.trabajando = False

        try:
            self.farmacias = farmacias_cofares(self.cfg["magisfor"])
            faltan = incompletas(self.cfg["magisfor"])
        except ErrorMagisfor as e:
            messagebox.showerror("Magisfor", f"No se pueden leer las farmacias de Magisfor:\n{e}",
                                 parent=app.root)
            self.destroy()
            return

        tk.Label(self, text="Farmacia de destino", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=10, pady=(10, 0))
        self.filtro = tk.StringVar()
        self.filtro.trace_add("write", lambda *a: self.rellenar())
        buscar = tk.Entry(self, textvariable=self.filtro, font=("Segoe UI", 10))
        buscar.pack(fill="x", padx=10)
        buscar.focus_set()
        self.lista = tk.Listbox(self, font=("Segoe UI", 10), activestyle="dotbox", exportselection=False)
        self.lista.pack(fill="both", expand=True, padx=10, pady=4)
        self.lista.bind("<Double-Button-1>", lambda e: self.generar())
        if faltan:
            tk.Label(self, fg="#b45309", font=("Segoe UI", 8), justify="left", wraplength=520,
                     text=f"{len(faltan)} farmacia(s) activa(s) sin cooperador o CP en Magisfor no salen "
                          "en la lista: " + ", ".join(f.nombre for f in faltan[:4])
                          + ("…" if len(faltan) > 4 else "")).pack(anchor="w", padx=10)

        self.frio = tk.BooleanVar()
        tk.Checkbutton(self, text="Requiere FRÍO", variable=self.frio,
                       font=("Segoe UI", 11, "bold"), fg="#1d4ed8").pack(anchor="w", padx=10, pady=4)
        tk.Label(self, text="Se marca siempre «Contiene fórmula magistral».",
                 font=("Segoe UI", 8), fg="#555").pack(anchor="w", padx=10)

        if self.cfg["cofares_prueba"]:
            tk.Label(self, text="MODO PRUEBA: rellena el formulario pero NO solicita la recogida "
                                "(se cambia en config.ini).", fg="#b91c1c",
                     font=("Segoe UI", 9, "bold"), wraplength=520).pack(anchor="w", padx=10, pady=(4, 0))

        self.estado = tk.Label(self, text="", font=("Segoe UI", 9), fg="#1d4ed8")
        self.estado.pack(anchor="w", padx=10, pady=4)

        botones = tk.Frame(self)
        botones.pack(pady=(0, 10))
        self.btn = tk.Button(botones, text="Generar e imprimir", font=("Segoe UI", 10, "bold"),
                             bg="#15803d", fg="white", padx=12, command=self.generar)
        self.btn.pack(side="left", padx=4)
        tk.Button(botones, text="Acceso Cofares…", command=self.pedir_acceso).pack(side="left", padx=4)
        tk.Button(botones, text="Cerrar", command=self.cerrar).pack(side="left", padx=4)
        self.protocol("WM_DELETE_WINDOW", self.cerrar)
        self.rellenar()

    def rellenar(self):
        texto = self.filtro.get().strip().lower()
        self.visibles = [f for f in self.farmacias
                         if texto in f"{f.nombre} {f.poblacion} {f.cooperador} {f.cp}".lower()]
        self.lista.delete(0, "end")
        for f in self.visibles:
            self.lista.insert("end", f"{f.nombre}  ·  {f.poblacion}  ·  coop. {f.cooperador}  ·  CP {f.cp}")
        if self.visibles:
            self.lista.selection_set(0)

    def pedir_acceso(self):
        actual = credenciales.leer()
        coop = simpledialog.askstring("Acceso Cofares", "Nº de cooperador (el de tu farmacia):",
                                      initialvalue=actual[0] if actual else "", parent=self)
        if not coop:
            return None
        clave = simpledialog.askstring("Acceso Cofares", "Contraseña del área privada de Cofares:",
                                       show="•", parent=self)
        if not clave:
            return None
        try:
            credenciales.guardar(coop.strip(), clave)
        except Exception as e:
            messagebox.showerror("Acceso Cofares", f"No se pudo guardar:\n{e}", parent=self)
            return None
        messagebox.showinfo("Acceso Cofares", "Guardado en el Administrador de credenciales de Windows.",
                            parent=self)
        return coop.strip(), clave

    def generar(self):
        if self.trabajando:
            return
        sel = self.lista.curselection()
        if not sel:
            messagebox.showwarning("Nuevo envío", "Elige la farmacia de destino.", parent=self)
            return
        f = self.visibles[sel[0]]
        frio = self.frio.get()
        prueba = self.cfg["cofares_prueba"]
        pregunta = (f"{'[MODO PRUEBA] ' if prueba else ''}¿Solicitar la recogida a\n\n{f.nombre}\n"
                    f"{f.poblacion}\ncooperador {f.cooperador} · CP {f.cp}\n\n"
                    f"{'CON FRÍO' if frio else 'sin frío'} · fórmula magistral?")
        if not messagebox.askyesno("Confirmar envío", pregunta, parent=self,
                                   icon="warning" if frio else "question"):
            return
        if not credenciales.leer() and messagebox.askyesno(
                "Acceso Cofares", "¿Quieres guardar ahora tu acceso a Cofares para que el programa "
                "entre solo?\n\nSi dices que no, tendrás que iniciar sesión en la ventana del navegador.",
                parent=self):
            self.pedir_acceso()

        self.trabajando = True
        self.btn.config(state="disabled")
        self.app.anotar(f"Nuevo envío a {f.nombre} (coop. {f.cooperador}, CP {f.cp})"
                        f"{' CON FRÍO' if frio else ''}{' [PRUEBA]' if prueba else ''}")
        threading.Thread(target=self._trabajar, args=(f, frio, prueba), daemon=True).start()
        self.after(200, self._atender)

    def _trabajar(self, f, frio, prueba):
        from cofares_web import EnvioCofares, ErrorCofares
        envio = EnvioCofares(self.cfg["carpeta"], self.cfg["perfil_navegador"],
                             canal=self.cfg["navegador"] or None, url=self.cfg["cofares_url"],
                             credenciales=credenciales.leer,
                             carpeta_diagnostico=self.cfg["diagnostico"],
                             avisar=lambda m: self.mensajes.put(("aviso", m)))
        try:
            pdf = envio.enviar(f.cooperador, f.cp, frio, prueba=prueba)
            self.mensajes.put(("fin", pdf))
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
                    self.app.anotar(f"Cofares: {dato}")
                    continue
                self.trabajando = False
                self.btn.config(state="normal")
                if tipo == "error":
                    self.estado.config(text="Error: revisa el aviso", fg="#b91c1c")
                    self.app.anotar(f"Cofares: ERROR {dato}")
                    messagebox.showerror("Envío Cofares", dato, parent=self)
                else:
                    self.estado.config(text="Hecho." if dato else "Modo prueba terminado.", fg="#15803d")
                    if dato:  # el PDF ya está en la carpeta vigilada: se imprimirá solo
                        self.after(1500, self.destroy)
                return
        except queue.Empty:
            pass
        self.after(200, self._atender)

    def cerrar(self):
        if self.trabajando and not messagebox.askyesno(
                "Nuevo envío", "Hay un envío en curso. ¿Cerrar la ventana igualmente?\n"
                "(el envío seguirá hasta terminar)", parent=self):
            return
        self.destroy()
