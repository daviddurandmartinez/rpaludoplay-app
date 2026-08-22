import logging
import smtplib
import ssl
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import pandas as pd

from config import NOTIFICACION_SETTINGS
from sync_merger import ResultadoSync

logger = logging.getLogger(__name__)

MAXIMO_FILAS_TABLA = 20

ESTILO_HTML = """
<style>
  body { font-family: Arial, sans-serif; color: #333; }
  h1 { color: #2c3e50; }
  h2 { color: #2c3e50; margin-bottom: 4px; }
  table { border-collapse: collapse; margin: 10px 0; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 6px 10px; text-align: left; font-size: 12px; }
  th { background-color: #2c3e50; color: #ffffff; }
  tr:nth-child(even) { background-color: #f4f6f7; }
</style>
"""


def _tabla_html(df: pd.DataFrame) -> str:
    if df.empty:
        return "<p><em>Sin registros.</em></p>"
    html = df.head(MAXIMO_FILAS_TABLA).to_html(index=False, border=0)
    if len(df) > MAXIMO_FILAS_TABLA:
        html += f"<p><em>... {len(df) - MAXIMO_FILAS_TABLA} registro(s) adicionales omitidos.</em></p>"
    return html


def construir_html(resultado_sync: ResultadoSync, resumen_fotos: dict | None = None) -> str:
    """Construye el cuerpo HTML del correo con las tablas de registros insertados y actualizados."""
    secciones = [
        ("Registros a INSERTAR (nuevos en el registro oficial)", resultado_sync.df_insert),
        ("Registros a ACTUALIZAR / desactivar (salieron del registro oficial)", resultado_sync.df_update),
        ("Registros RECURRENTES a reactivar (reaparecieron en el registro oficial)", resultado_sync.df_update_recurrent),
    ]

    partes = [ESTILO_HTML]
    partes.append("<h1>Reporte de sincronizaci&oacute;n Ludoplay</h1>")
    partes.append(f"<p>Fecha de ejecuci&oacute;n: <strong>{datetime.now():%d/%m/%Y %H:%M:%S}</strong></p>")

    for titulo, df in secciones:
        partes.append(f"<h2>{titulo} ({len(df)})</h2>")
        partes.append(_tabla_html(df))

    if resumen_fotos is not None:
        movidas = resumen_fotos.get("movidas", [])
        faltantes = resumen_fotos.get("faltantes", [])
        partes.append(f"<h2>Fotograf&iacute;as ({len(movidas)} movidas / {len(faltantes)} faltantes)</h2>")
        if movidas:
            partes.append(f"<p>Movidas a destino: {', '.join(map(str, movidas))}</p>")
        if faltantes:
            partes.append(f"<p style='color:#b00020'>Faltantes: {', '.join(map(str, faltantes))}</p>")

    return "".join(partes)


def enviar_notificacion(resultado_sync: ResultadoSync, resumen_fotos: dict | None = None) -> bool:
    """Envía por SMTP el reporte a los administradores. Retorna True si se envió."""
    cfg = NOTIFICACION_SETTINGS
    destinatarios = cfg.obtener_destinatarios()

    if not cfg.smtp_host or not destinatarios:
        logger.warning("SMTP sin configurar (SMTP_HOST o ADMIN_EMAILS vacíos); no se envía correo.")
        print("Notificación omitida: falta SMTP_HOST o ADMIN_EMAILS en .env")
        return False

    total = (
        len(resultado_sync.df_insert)
        + len(resultado_sync.df_update)
        + len(resultado_sync.df_update_recurrent)
    )

    mensaje = MIMEMultipart("alternative")
    mensaje["Subject"] = f"[Ludoplay] Sincronización MINCETUR - {total} registro(s) - {datetime.now():%d/%m/%Y}"
    mensaje["From"] = cfg.smtp_user or "ludoplay@localhost"
    mensaje["To"] = ", ".join(destinatarios)
    mensaje.attach(MIMEText(construir_html(resultado_sync, resumen_fotos), "html", "utf-8"))

    contexto = ssl.create_default_context()
    try:
        if cfg.smtp_use_ssl:
            with smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, context=contexto) as server:
                if cfg.smtp_user and cfg.smtp_password:
                    server.login(cfg.smtp_user, cfg.smtp_password.get_secret_value())
                server.sendmail(mensaje["From"], destinatarios, mensaje.as_string())
        else:
            with smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=30) as server:
                server.starttls(context=contexto)
                if cfg.smtp_user and cfg.smtp_password:
                    server.login(cfg.smtp_user, cfg.smtp_password.get_secret_value())
                server.sendmail(mensaje["From"], destinatarios, mensaje.as_string())

        logger.info("Correo enviado correctamente a %s", destinatarios)
        print(f"Notificación enviada por correo a: {', '.join(destinatarios)}")
        return True
    except Exception as e:
        logger.error("Fallo el envío del correo: %s", e)
        print(f"No se pudo enviar la notificación: {e}")
        return False
