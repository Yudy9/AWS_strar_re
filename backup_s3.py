import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
 
import boto3
from botocore.exceptions import BotoCoreError, ClientError
 
# ─── Configuración de logging ─────────────────────────────────────────────────
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
 
 
# ─── Funciones principales ────────────────────────────────────────────────────
 
def scan_folder(source_path: Path) -> list[Path]:
    """
    Escanea la carpeta origen de forma recursiva y devuelve
    una lista con las rutas de todos los archivos encontrados.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"La carpeta origen no existe: {source_path}")
    if not source_path.is_dir():
        raise NotADirectoryError(f"La ruta indicada no es una carpeta: {source_path}")
 
    files = [f for f in source_path.rglob("*") if f.is_file()]
    log.info(f"📂  Carpeta escaneada: {source_path}")
    log.info(f"📄  Archivos encontrados: {len(files)}")
    return files
 
 
def build_s3_key(file_path: Path, source_root: Path, s3_prefix: str) -> str:
    """
    Construye la clave (ruta) del objeto en S3 conservando la
    estructura de subdirectorios relativa al origen.
 
    Ejemplo:
        source_root  = /home/user/datos
        file_path    = /home/user/datos/reportes/enero.csv
        s3_prefix    = backups/2025-06-01
        → s3_key     = backups/2025-06-01/reportes/enero.csv
    """
    relative = file_path.relative_to(source_root)
    return f"{s3_prefix}/{relative}".replace("\\", "/")   # compatibilidad Windows
 
 
def upload_files(
    files: list[Path],
    source_root: Path,
    bucket: str,
    s3_prefix: str,
    dry_run: bool = False,
) -> dict:
    """
    Sube cada archivo a S3.
 
    Returns:
        dict con claves 'uploaded', 'skipped', 'errors'
    """
    s3 = boto3.client("s3")
    stats = {"uploaded": 0, "skipped": 0, "errors": 0}
 
    for file_path in files:
        s3_key = build_s3_key(file_path, source_root, s3_prefix)
 
        if dry_run:
            log.info(f"[DRY-RUN]  {file_path.name}  →  s3://{bucket}/{s3_key}")
            stats["skipped"] += 1
            continue
 
        try:
            s3.upload_file(str(file_path), bucket, s3_key)
            log.info(f"✅  {file_path.name}  →  s3://{bucket}/{s3_key}")
            stats["uploaded"] += 1
 
        except (BotoCoreError, ClientError) as exc:
            log.error(f"❌  Error subiendo {file_path.name}: {exc}")
            stats["errors"] += 1
 
    return stats
 
 
def run_backup(
    source: str,
    bucket: str,
    prefix: str = "backups",
    dry_run: bool = False,
) -> None:
    """
    Orquesta el proceso completo de backup:
      1. Escanea la carpeta origen.
      2. Construye el prefijo con fecha: <prefix>/YYYY-MM-DD_HH-MM-SS
      3. Sube todos los archivos a S3.
      4. Imprime un resumen.
    """
    source_path = Path(source).resolve()
 
    # Carpeta con fecha y hora dentro del bucket
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    s3_prefix = f"{prefix}/{timestamp}"
 
    log.info("=" * 60)
    log.info("🚀  Iniciando backup hacia S3")
    log.info(f"    Origen  : {source_path}")
    log.info(f"    Destino : s3://{bucket}/{s3_prefix}/")
    log.info("=" * 60)
 
    # 1. Escanear
    files = scan_folder(source_path)
    if not files:
        log.warning("⚠️   No se encontraron archivos. Backup finalizado sin cambios.")
        return
 
    # 2. Subir
    stats = upload_files(files, source_path, bucket, s3_prefix, dry_run=dry_run)
 
    # 3. Resumen
    log.info("─" * 60)
    log.info(f"📊  Resumen del backup")
    log.info(f"    ✅  Subidos  : {stats['uploaded']}")
    log.info(f"    ⏭️   Omitidos : {stats['skipped']}")
    log.info(f"    ❌  Errores  : {stats['errors']}")
    log.info("─" * 60)
 
    if stats["errors"]:
        sys.exit(1)
 
 
# ─── CLI ──────────────────────────────────────────────────────────────────────
 
def parse_args():
    parser = argparse.ArgumentParser(
        description="Backup automático de una carpeta local hacia Amazon S3."
    )
    parser.add_argument(
        "--source", "-s",
        required=True,
        help="Ruta de la carpeta local a respaldar.",
    )
    parser.add_argument(
        "--bucket", "-b",
        required=True,
        help="Nombre del bucket S3 destino.",
    )
    parser.add_argument(
        "--prefix", "-p",
        default="backups",
        help="Prefijo base dentro del bucket (default: 'backups').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula el backup sin subir ningún archivo.",
    )
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
    run_backup(
        source=args.source,
        bucket=args.bucket,
        prefix=args.prefix,
        dry_run=args.dry_run,
    )