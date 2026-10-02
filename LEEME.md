# Impresor automático de etiquetas Cofares (Brother QL-800)

Descargas el PDF de la etiqueta en la web de Cofares y sale impresa sola en la
QL-800 con tu plantilla de P-touch Editor (`plantilla.lbx`). No hay que hacer
ningún clic más.

## Cómo funciona

1. El programa vigila la carpeta de **Descargas** (se puede cambiar en `config.ini`).
2. Cuando aparece un PDF que se llama `etiqueta_*.pdf`, espera a que termine de
   descargarse y lee: código FM, Remite, Destino, Centro, N1 y N3.
   Si el PDF dice **FRÍO** o **NEVERA**, usa `plantilla_frio.lbx`, que lleva
   **F R Í O** en grande de lado a lado en la parte de abajo. La normal mide
   62 × 53 mm y la de frío 62 × 62 mm (más larga solo cuando hace falta, para
   ahorrar rollo).
3. Rellena esos datos en `plantilla.lbx` y la imprime en la *Brother QL-800 COFARES*.
4. Le pone una marca delante del nombre para no imprimirlo dos veces:
   - `!etiqueta_FM0000921557_1.pdf` → ya impresa.
   - `#etiqueta_FM0000921557_1.pdf` → no se pudo leer o imprimir (sale además un
     aviso en pantalla). Para reintentarla, quita el `#` del nombre.

Otros PDF de Descargas no se tocan. Los PDF de etiqueta que ya estaban en
Descargas al abrir el programa tampoco se imprimen (para evitar sorpresas).

La ventana tiene además:
- **Imprimir PDF…**: imprimir a mano cualquier PDF (como el programa antiguo).
- **Reimprimir última**: vuelve a sacar la última etiqueta.
- **Pausar**: deja de imprimir automáticamente hasta pulsar *Reanudar*.
- **Abrir carpeta**: abre la carpeta vigilada.

## Instalación (una sola vez)

1. **Driver de la impresora**: la QL-800 ya debe aparecer en Windows con el nombre
   `Brother QL-800 COFARES` (si tiene otro nombre, cámbialo en `config.ini`).
2. **Brother b-PAC Client Component** (gratis):
   <https://support.brother.com/g/s/es/dev/en/bpac/download/index.html?c=eu_ot&lang=en&navi=offall&comple=on&redirect=on>
   Descarga **b-PAC Client Component (64-bit ver.)** (no hace falta el SDK completo).
   Es lo que permite usar tu plantilla `.lbx` tal cual.
3. Copia la carpeta `EtiquetasCofares` (con el `.exe`, `config.ini` y
   `plantilla.lbx`) a, por ejemplo, `C:\Impresora envios cofares\`.
4. **Antes de descomprimir** el zip descargado: clic derecho → *Propiedades* →
   marca **Desbloquear** → *Aceptar*. Así Windows no avisa de "editor
   desconocido" cada vez que se abre el programa. (Si ya lo descomprimiste, no
   pasa nada: el paso siguiente también lo arregla.)
5. Haz doble clic en `instalar_inicio_automatico.bat` (si Windows avisa, pulsa
   *Ejecutar* esta única vez). Arranca el programa y lo
   deja configurado para que se abra solo cada vez que se encienda el ordenador.

### ¿De dónde saco el .exe?
- En GitHub: pestaña **Actions** → *Construir ejecutable Windows* → última
  ejecución → descarga **EtiquetasCofares-windows**.
- O en un Windows con Python 3.12 (64 bits): doble clic en `construir_exe.bat`;
  queda en `dist\EtiquetasCofares\`.

## Cambiar cosas (`config.ini`)

- `carpeta_vigilada`: otra carpeta de descarga, p. ej. `C:\Etiquetas`.
- `nombre` (impresora), `plantilla`, `copias`.
- Sección `[formato]`: el texto exacto de cada cuadro, p. ej.
  `remite = Remite: {remite}`.

Si cambias el diseño en P-touch Editor, solo tienes que guardar encima de
`plantilla.lbx` y mantener los nombres de los objetos: `obj_titulo`,
`obj_codigo` (código de barras), `obj_remite`, `obj_destino`, `obj_centro`,
`obj_n1`, `obj_n3`.

Consejos para que la etiqueta salga igual que en el diseño:
- Los cuadros de datos están **alineados a la izquierda** y en dos columnas: al
  meter el dato, el cuadro crece hacia la derecha sin descolocarse.
- Si un formato de `[formato]` se deja vacío (como `titulo =`), ese cuadro se
  imprime con el texto que tenga la plantilla.
- `plantilla_original.lbx` es la versión anterior, por si quieres volver a ella.

## Si algo falla

- *"No se encuentra Brother b-PAC"*: falta instalar b-PAC o se instaló el de
  32 bits. Instala el de 64 bits.
- *"No se encuentra la impresora"*: el nombre de `config.ini` no coincide con el
  de Windows (Configuración → Impresoras).
- *"Faltan datos en el PDF"*: Cofares ha cambiado el formato del PDF. El PDF queda
  marcado con `#`; mándalo para ajustar el programa.
- Todo lo que pasa queda anotado en `registro.log`, junto al programa.

## Para desarrolladores

```
pip install -r requirements.txt pytest
python -m pytest            # pruebas (funcionan sin impresora ni Windows)
python extraer.py archivo.pdf   # ver qué datos se leen de un PDF
python etiquetas_cofares.py     # ejecutar desde el código
```
