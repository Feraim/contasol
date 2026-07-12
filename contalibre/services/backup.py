"""Copia de seguridad descargable de la base de datos de una empresa.

Usa la API de backup de sqlite3 (no una simple copia de fichero) para
obtener una instantánea consistente aunque haya conexiones abiertas.
"""

import sqlite3
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path

from .. import database


def exportar_zip(empresa_id: int) -> bytes:
    origen = database.EMPRESAS_DIR / f"{empresa_id}.db"
    if not origen.exists():
        # Primer acceso: crea el fichero y precarga el PGC si hiciera falta.
        database.sesion_empresa(empresa_id).close()

    with tempfile.TemporaryDirectory() as tmp:
        destino = Path(tmp) / f"empresa_{empresa_id}.db"
        con_origen = sqlite3.connect(origen)
        try:
            con_destino = sqlite3.connect(destino)
            try:
                con_origen.backup(con_destino)
            finally:
                con_destino.close()
        finally:
            con_origen.close()

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(destino, arcname=f"empresa_{empresa_id}.db")
        return buffer.getvalue()
