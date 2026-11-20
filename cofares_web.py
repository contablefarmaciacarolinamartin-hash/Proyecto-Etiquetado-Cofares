"""Rellena el formulario "Envío entre farmacias" del área privada de Cofares.

Maneja un navegador real (Edge o Chrome instalados en Windows) con Playwright,
haciendo los mismos pasos que se hacen a mano:

    login (si hace falta) -> enlace "Nuevo envío" (abre un marco emergente)
    -> cooperador + CP -> Validar destino -> fórmula magistral [+ frío]
    -> Solicitar Recogida -> Aceptar -> PDF

El PDF se guarda en la carpeta vigilada y el resto del programa lo imprime.
Si la página no lo descarga sola, se coge del histórico de envíos (icono PDF,
función descargarPDF de Cofares). En modo prueba se para antes de "Solicitar
Recogida", así que no se genera ningún envío real.

Si algo no aparece donde se espera, guarda una captura y el HTML de la página
(y del formulario) en la carpeta "diagnostico" para poder ajustarlo.
"""
import os
import re
import time
from datetime import datetime
from urllib.parse import urljoin

URL_ENVIOS = "https://areaprivada.cofares.es/group/canal-online/envio-de-bultos"
ESPERA = 20_000  # ms para que aparezca cada elemento
MARCO = "iframe[id^='altaEnvio_iframe'], iframe[title*='ENTRE FARMACIAS' i]"


class ErrorCofares(Exception):
    pass


class EnvioCofares:
    def __init__(self, carpeta_descargas, perfil, canal="msedge", url=URL_ENVIOS,
                 credenciales=None, carpeta_diagnostico=None, avisar=print,
                 visible=True, ejecutable=None):
        """credenciales: función que devuelve (cooperador, contraseña) o None."""
        self.carpeta_descargas = carpeta_descargas
        self.perfil = perfil
        self.canal = canal
        self.url = url
        self.credenciales = credenciales
        self.carpeta_diagnostico = carpeta_diagnostico
        self.avisar = avisar
        self.visible = visible
        self.ejecutable = ejecutable  # solo para pruebas: ruta a un Chromium concreto
        self.descargados = []
        self._descargando = False
        self.sufijo = ""

    # --- utilidades ---------------------------------------------------------
    def _diagnostico(self, page, motivo):
        if not self.carpeta_diagnostico or page is None:
            return None
        os.makedirs(self.carpeta_diagnostico, exist_ok=True)
        base = os.path.join(self.carpeta_diagnostico, time.strftime("%Y%m%d-%H%M%S"))
        try:
            with open(base + ".txt", "w", encoding="utf-8") as f:
                f.write(f"{motivo}\nURL: {page.url}\n")
            page.screenshot(path=base + ".png", full_page=True)
            with open(base + ".html", "w", encoding="utf-8") as f:
                f.write(page.content())
            for n, marco in enumerate(page.frames[1:], 1):
                if "envio" in marco.url:
                    with open(f"{base}_marco{n}.html", "w", encoding="utf-8") as f:
                        f.write(marco.content())
        except Exception:
            pass
        return base

    def _nombre_destino(self, nombre):
        nombre = os.path.basename(nombre or "") or "etiqueta.pdf"
        if not nombre.lower().endswith(".pdf"):
            nombre += ".pdf"
        if not nombre.lower().startswith("etiqueta"):
            nombre = "etiqueta_" + nombre  # que lo recoja el patrón de la carpeta vigilada
        if self.sufijo:
            nombre = nombre[:-4] + self.sufijo + ".pdf"
        destino = os.path.join(self.carpeta_descargas, nombre)
        base, ext = os.path.splitext(destino)
        n = 1
        while os.path.exists(destino):
            destino = f"{base} ({n}){ext}"
            n += 1
        return destino

    def _guardar(self, nombre, escribir):
        destino = self._nombre_destino(nombre)
        # Se escribe con otro nombre y luego se renombra, para que la carpeta
        # vigilada nunca vea un PDF a medio escribir.
        temporal = destino + ".parcial"
        escribir(temporal)
        os.replace(temporal, destino)
        self.descargados.append(destino)
        self.avisar(f"PDF descargado: {os.path.basename(destino)}")

    def _al_descargar(self, descarga):
        if self._descargando:  # ya tenemos el PDF de este envío: no duplicar la impresión
            descarga.cancel()
            return
        self._descargando = True
        self._guardar(descarga.suggested_filename, descarga.save_as)

    def _pausa(self, segundos):
        # Pausa que deja al navegador entregar sus avisos (p. ej. "descarga lista");
        # con time.sleep la descarga no se vería hasta mucho después.
        self._page.wait_for_timeout(int(segundos * 1000))

    @staticmethod
    def _visible(locator):
        for i in range(locator.count()):
            if locator.nth(i).is_visible():
                return locator.nth(i)
        return None

    def _pulsar(self, zonas, texto, espera=ESPERA):
        """Pulsa un botón o enlace con ese texto en la primera zona donde aparezca."""
        patron = re.compile(texto, re.I)
        limite = time.monotonic() + espera / 1000
        while True:
            for zona in zonas:
                for loc in (zona.get_by_role("button", name=patron),
                            zona.get_by_role("link", name=patron),
                            zona.get_by_text(patron)):
                    try:
                        el = self._visible(loc)
                    except Exception:
                        el = None
                    if el:
                        el.click()
                        return
            if time.monotonic() > limite:
                raise ErrorCofares(f"No encuentro «{texto.strip('^$')}» en la web de Cofares.")
            self._pausa(0.3)

    def _casilla(self, zona, texto):
        """La casilla (checkbox) que acompaña a un texto como 'Requiere frío'."""
        por_etiqueta = zona.get_by_label(texto, exact=False)
        if por_etiqueta.count():
            return por_etiqueta.first
        t = _xpath_texto(texto)
        detras = zona.locator(  # casilla cuyo primer texto a continuación es ese texto
            "xpath=//input[@type='checkbox']"
            f"[following::text()[normalize-space()][1][contains(normalize-space(), {t})]]")
        if detras.count():
            return detras.first
        return zona.locator(
            "xpath=//input[@type='checkbox']"
            f"[preceding::text()[normalize-space()][1][contains(normalize-space(), {t})]]").first

    def _marcar(self, zona, casilla, valor, nombre):
        """Marca o desmarca una casilla. En Cofares la casilla real está oculta y lo que
        se ve es su etiqueta dibujada, así que se pulsa la etiqueta (como con el ratón)."""
        if casilla.is_checked() == valor:
            return
        if casilla.is_visible():
            casilla.click()
        else:
            ident = casilla.get_attribute("id")
            etiqueta = zona.locator(f"label[for='{ident}']") if ident else None
            if etiqueta is not None and etiqueta.count() and etiqueta.first.is_visible():
                etiqueta.first.click()
            else:  # último recurso: el clic directamente sobre la casilla oculta
                casilla.evaluate("e => e.click()")
        self._pausa(0.3)
        if casilla.is_checked() != valor:
            raise ErrorCofares(f"No se ha podido {'marcar' if valor else 'desmarcar'} «{nombre}».")

    # --- pasos --------------------------------------------------------------
    def _iniciar_sesion_si_hace_falta(self, page):
        usuario = page.get_by_placeholder(re.compile("Ej: ?12345", re.I))
        if not usuario.count():
            return
        datos = self.credenciales() if self.credenciales else None
        if not datos:
            self.avisar("Cofares pide iniciar sesión: entra en la ventana del navegador.")
            usuario.wait_for(state="detached", timeout=5 * 60_000)
            page.wait_for_load_state("domcontentloaded")
            return
        self.avisar("Iniciando sesión en Cofares…")
        usuario.fill(datos[0])
        page.get_by_placeholder(re.compile("contrase", re.I)).fill(datos[1])
        self._pulsar([page], "^Iniciar sesi")
        try:  # ha entrado cuando desaparece el formulario de acceso
            usuario.wait_for(state="detached", timeout=ESPERA)
            page.wait_for_load_state("domcontentloaded")
        except Exception:
            raise ErrorCofares("No se pudo iniciar sesión en Cofares. "
                               "Revisa el nº de cooperador y la contraseña guardados.")

    def _formulario(self, page):
        """El formulario va en un marco emergente; si no lo hay, en la propia página."""
        try:
            marco = page.wait_for_selector(MARCO, timeout=ESPERA // 2)
            frame = marco.content_frame()
            frame.wait_for_load_state("domcontentloaded")
            frame.get_by_placeholder(re.compile("cooperador", re.I)).wait_for(timeout=ESPERA)
            return frame
        except Exception:
            return page

    def enviar(self, cooperador, cp, frio, prueba=True, confirmar=None):
        """Hace el envío y devuelve la ruta del PDF (None en modo prueba o si se cancela).

        confirmar(): última pregunta antes de pedir la recogida.
        """
        from playwright.sync_api import sync_playwright

        self.sufijo = "_FRIO" if frio else ""
        self.descargados, self._descargando = [], False
        with sync_playwright() as p:
            opciones = dict(headless=not self.visible, accept_downloads=True,
                            no_viewport=True, args=["--start-maximized"])
            if self.ejecutable:
                opciones["executable_path"] = self.ejecutable
            elif self.canal:
                opciones["channel"] = self.canal
            contexto = p.chromium.launch_persistent_context(self.perfil, **opciones)
            contexto.on("download", self._al_descargar)
            page = contexto.pages[0] if contexto.pages else contexto.new_page()
            self._page = page
            try:
                return self._pasos(contexto, page, str(cooperador), str(cp), frio, prueba, confirmar)
            except Exception as e:
                base = self._diagnostico(page, repr(e))
                texto = str(e) if isinstance(e, ErrorCofares) else \
                    f"Algo no ha ido como se esperaba en la web de Cofares:\n{e}"
                if base:
                    texto += f"\n\nSe ha guardado una captura en:\n{base}.png"
                raise ErrorCofares(texto) from e
            finally:
                contexto.close()

    def _pasos(self, contexto, page, cooperador, cp, frio, prueba, confirmar):
        self.avisar("Abriendo Cofares…")
        page.goto(self.url)
        page.wait_for_load_state("domcontentloaded")
        self._iniciar_sesion_si_hace_falta(page)
        if "envio-de-bultos" not in page.url:
            page.goto(self.url)
        previos = set(re.findall(r"envio=(FM\d+)", page.content()))

        self._pulsar([page], "^Nuevo env[ií]o$")
        form = self._formulario(page)
        form.get_by_placeholder(re.compile("cooperador", re.I)).fill(cooperador, timeout=ESPERA)
        form.get_by_placeholder(re.compile("postal", re.I)).fill(cp)
        self._pulsar([form], "^Validar destino$")

        formula = self._casilla(form, "fórmula magistral")
        limite = time.monotonic() + ESPERA / 1000
        while not (formula.count() and formula.is_enabled()):
            if time.monotonic() > limite:
                raise ErrorCofares(
                    f"Cofares no ha validado el destino (cooperador {cooperador}, CP {cp}).\n"
                    "Comprueba esos datos en la ficha de Magisfor.")
            self._pausa(0.3)
        self.avisar("Destino validado.")

        self._marcar(form, formula, True, "Contiene fórmula magistral")
        self._marcar(form, self._casilla(form, "Requiere fr"), frio, "Requiere frío")

        if prueba:
            self.avisar("MODO PRUEBA: formulario rellenado, no se ha solicitado la recogida.")
            if self.visible:
                page.wait_for_timeout(8000)  # que se vea cómo ha quedado
            return None

        if confirmar and not confirmar():
            self.avisar("Envío cancelado antes de solicitar la recogida.")
            return None

        self._pulsar([form], "^Solicitar Recogida$")
        self._pulsar([form, page], "^Aceptar$")
        self.avisar("Recogida solicitada. Esperando el PDF…")
        return self._esperar_pdf(page, cooperador, previos)

    def _esperar_pdf(self, page, cooperador, previos):
        # 1) que la propia página lo descargue o muestre el icono/enlace del PDF
        limite = time.monotonic() + 20
        pulsado = False  # una sola vez: pulsarlo dos veces imprimiría dos etiquetas
        while time.monotonic() < limite:
            if self.descargados:
                return self.descargados[-1]
            for zona in ([] if pulsado else page.frames):
                try:
                    enlace = self._visible(zona.locator(
                        "[onclick*='descargarPDF'], a:has(img.ancho-pdf), a[href*='descargarPDF']"))
                except Exception:
                    enlace = None
                if enlace:
                    enlace.click()
                    pulsado = True
                    limite = time.monotonic() + 30
                    break
            self._pausa(0.5)
        if self.descargados:
            return self.descargados[-1]

        while self._descargando and not self.descargados:  # descarga empezada: que termine
            self._pausa(0.5)
        if self.descargados:
            return self.descargados[-1]

        # 2) cogerlo del histórico de envíos
        self.avisar("Buscando el PDF en el histórico de envíos…")
        page.goto(self.url)
        url = self._pdf_del_historico(page.content(), page.url, cooperador, previos)
        if not url:
            raise ErrorCofares("La recogida se ha solicitado, pero no encuentro su PDF.\n"
                               "Descárgalo a mano desde el histórico de Cofares: se imprimirá solo.")
        respuesta = page.request.get(url)
        if not respuesta.ok:
            raise ErrorCofares(f"Cofares no ha devuelto el PDF (error {respuesta.status}).")
        fm = re.search(r"envio=(FM\d+)", url)
        nombre = f"etiqueta_{fm.group(1)}.pdf" if fm else "etiqueta.pdf"
        datos = respuesta.body()
        self._guardar(nombre, lambda ruta: open(ruta, "wb").write(datos))
        return self.descargados[-1]

    @staticmethod
    def _pdf_del_historico(html, url_pagina, cooperador, previos):
        """URL de descargarPDF del envío nuevo (no estaba al empezar) a ese cooperador."""
        candidatos = []
        for trozo in re.split(r"(?=Env[ií]o solicitado el )", html)[1:]:
            m = re.match(r"Env[ií]o solicitado el (\d{2}/\d{2}/\d{4}) a las (\d{2}:\d{2}:\d{2})"
                         r" a la farmacia (\d+)", trozo)
            enlace = re.search(r"descargarPDF\('([^']+)'\)", trozo)
            if not (m and enlace) or int(m.group(3)) != int(cooperador):
                continue
            url = enlace.group(1).replace("&amp;", "&")
            fm = re.search(r"envio=(FM\d+)", url)
            if fm and fm.group(1) in previos:
                continue
            cuando = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M:%S")
            candidatos.append((cuando, urljoin(url_pagina, url)))
        return max(candidatos)[1] if candidatos else None


def _xpath_texto(texto):
    if "'" not in texto:
        return f"'{texto}'"
    return "concat('" + texto.replace("'", "', \"'\", '") + "')"
