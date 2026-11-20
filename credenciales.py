"""Usuario y contraseña de Cofares guardados en el Administrador de credenciales de Windows.

La contraseña nunca se guarda en archivos del programa: la cifra Windows para el
usuario que tiene la sesión iniciada.
"""
OBJETIVO = "EtiquetasCofares/areaprivada.cofares.es"


def leer():
    """(cooperador, contraseña) o None si no hay nada guardado."""
    try:
        import win32cred
        c = win32cred.CredRead(OBJETIVO, win32cred.CRED_TYPE_GENERIC)
    except Exception:
        return None
    clave = c["CredentialBlob"]
    if isinstance(clave, bytes):
        clave = clave.decode("utf-16-le")
    return c["UserName"], clave


def guardar(cooperador, contraseña):
    import win32cred
    win32cred.CredWrite({
        "Type": win32cred.CRED_TYPE_GENERIC,
        "TargetName": OBJETIVO,
        "UserName": cooperador,
        "CredentialBlob": contraseña,
        "Persist": win32cred.CRED_PERSIST_LOCAL_MACHINE,
        "Comment": "Acceso al área privada de Cofares para Etiquetas Cofares",
    }, 0)


def borrar():
    try:
        import win32cred
        win32cred.CredDelete(OBJETIVO, win32cred.CRED_TYPE_GENERIC)
    except Exception:
        pass
