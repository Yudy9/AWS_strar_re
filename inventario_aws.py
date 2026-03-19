import argparse
import json
import logging
from datetime import datetime
 
import boto3
from botocore.exceptions import BotoCoreError, ClientError
 
# ─── Logging ──────────────────────────────────────────────────────────────────
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
 
 
# ─── Colores terminal ─────────────────────────────────────────────────────────
 
class C:
    VERDE    = "\033[92m"
    ROJO     = "\033[91m"
    AMARILLO = "\033[93m"
    AZUL     = "\033[94m"
    CYAN     = "\033[96m"
    BOLD     = "\033[1m"
    RESET    = "\033[0m"
 
 
# ─── Escaneo EC2 ──────────────────────────────────────────────────────────────
 
def escanear_ec2(region: str) -> list[dict]:
    """Obtiene todas las instancias EC2."""
    try:
        ec2 = boto3.client("ec2", region_name=region)
        respuesta = ec2.describe_instances()
        instancias = []
 
        for reserva in respuesta["Reservations"]:
            for inst in reserva["Instances"]:
                nombre = next(
                    (t["Value"] for t in inst.get("Tags", []) if t["Key"] == "Name"),
                    "-"
                )
                instancias.append({
                    "id":         inst.get("InstanceId", "-"),
                    "nombre":     nombre,
                    "estado":     inst.get("State", {}).get("Name", "-"),
                    "tipo":       inst.get("InstanceType", "-"),
                    "ip_publica": inst.get("PublicIpAddress", "Sin IP"),
                    "region":     region,
                })
 
        log.info(f"EC2: {len(instancias)} instancias encontradas")
        return instancias
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error escaneando EC2: {e}")
        return []
 
 
# ─── Escaneo S3 ───────────────────────────────────────────────────────────────
 
def escanear_s3() -> list[dict]:
    """Lista todos los buckets S3 con su región y cantidad de objetos."""
    try:
        s3 = boto3.client("s3")
        respuesta = s3.list_buckets()
        buckets = []
 
        for bucket in respuesta.get("Buckets", []):
            nombre = bucket["Name"]
            fecha  = bucket["CreationDate"].strftime("%Y-%m-%d")
 
            # Obtener región del bucket
            try:
                loc = s3.get_bucket_location(Bucket=nombre)
                region_bucket = loc["LocationConstraint"] or "us-east-1"
            except ClientError:
                region_bucket = "desconocida"
 
            # Contar objetos (máx. 1000 para no tardar mucho)
            try:
                objs = s3.list_objects_v2(Bucket=nombre, MaxKeys=1000)
                total_objetos = objs.get("KeyCount", 0)
            except ClientError:
                total_objetos = "sin acceso"
 
            buckets.append({
                "nombre":        nombre,
                "region":        region_bucket,
                "fecha_creacion": fecha,
                "objetos":       total_objetos,
            })
 
        log.info(f"S3: {len(buckets)} buckets encontrados")
        return buckets
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error escaneando S3: {e}")
        return []
 
 
# ─── Escaneo Lambda ───────────────────────────────────────────────────────────
 
def escanear_lambda(region: str) -> list[dict]:
    """Lista todas las funciones Lambda."""
    try:
        lmb = boto3.client("lambda", region_name=region)
        funciones = []
        paginator = lmb.get_paginator("list_functions")
 
        for pagina in paginator.paginate():
            for fn in pagina["Functions"]:
                funciones.append({
                    "nombre":   fn["FunctionName"],
                    "runtime":  fn.get("Runtime", "-"),
                    "memoria":  f"{fn.get('MemorySize', 0)} MB",
                    "timeout":  f"{fn.get('Timeout', 0)}s",
                    "region":   region,
                })
 
        log.info(f"Lambda: {len(funciones)} funciones encontradas")
        return funciones
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error escaneando Lambda: {e}")
        return []
 
 
# ─── Escaneo RDS ──────────────────────────────────────────────────────────────
 
def escanear_rds(region: str) -> list[dict]:
    """Lista todas las instancias RDS."""
    try:
        rds = boto3.client("rds", region_name=region)
        respuesta = rds.describe_db_instances()
        bases = []
 
        for db in respuesta.get("DBInstances", []):
            bases.append({
                "id":      db["DBInstanceIdentifier"],
                "motor":   db["Engine"],
                "version": db.get("EngineVersion", "-"),
                "estado":  db["DBInstanceStatus"],
                "clase":   db["DBInstanceClass"],
                "region":  region,
            })
 
        log.info(f"RDS: {len(bases)} instancias encontradas")
        return bases
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error escaneando RDS: {e}")
        return []
 
 
# ─── Mostrar resultados ───────────────────────────────────────────────────────
 
def mostrar_seccion(titulo: str, color: str, datos: list[dict], columnas: list[str]) -> None:
    ancho = 90
    print(f"\n{color}{C.BOLD}{'━'*ancho}")
    print(f"  {titulo}  ({len(datos)} recursos)")
    print(f"{'━'*ancho}{C.RESET}")
 
    if not datos:
        print(f"  {C.AMARILLO}Sin recursos encontrados.{C.RESET}")
        return
 
    # Encabezado
    encabezado = "  " + "".join(f"{col:<22}" for col in columnas)
    print(f"{C.BOLD}{encabezado}{C.RESET}")
    print(f"  {'─'*85}")
 
    # Filas
    for item in datos:
        fila = "  " + "".join(f"{str(item.get(k, '-')):<22}" for k in columnas)
        print(fila)
 
 
def mostrar_inventario(inventario: dict) -> None:
    import os
    os.system("clear" if os.name != "nt" else "cls")
 
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{C.BOLD}{'═'*90}")
    print(f"  INVENTARIO AWS  |  Región: {inventario['region']}  |  {ahora}")
    print(f"{'═'*90}{C.RESET}")
 
    # EC2
    mostrar_seccion(
        "EC2 — Instancias",
        C.CYAN,
        inventario["ec2"],
        ["id", "nombre", "estado", "tipo", "ip_publica"],
    )
 
    # S3
    mostrar_seccion(
        "S3 — Buckets",
        C.VERDE,
        inventario["s3"],
        ["nombre", "region", "fecha_creacion", "objetos"],
    )
 
    # Lambda
    mostrar_seccion(
        "Lambda — Funciones",
        C.AZUL,
        inventario["lambda"],
        ["nombre", "runtime", "memoria", "timeout"],
    )
 
    # RDS
    mostrar_seccion(
        "RDS — Bases de datos",
        C.AMARILLO,
        inventario["rds"],
        ["id", "motor", "version", "estado", "clase"],
    )
 
    # Resumen total
    total = (
        len(inventario["ec2"]) +
        len(inventario["s3"]) +
        len(inventario["lambda"]) +
        len(inventario["rds"])
    )
    print(f"\n{C.BOLD}  Total de recursos encontrados: {total}{C.RESET}")
    print(f"{C.BOLD}{'═'*90}{C.RESET}\n")
 
 
# ─── Guardar JSON ─────────────────────────────────────────────────────────────
 
def guardar_json(inventario: dict, ruta: str) -> None:
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(inventario, f, indent=2, ensure_ascii=False, default=str)
    log.info(f"Inventario guardado en: {ruta}")
 
 
# ─── Principal ────────────────────────────────────────────────────────────────
 
def generar_inventario(region: str) -> dict:
    log.info(f"Iniciando escaneo de cuenta AWS en región: {region}")
    return {
        "region":    region,
        "timestamp": datetime.now().isoformat(),
        "ec2":       escanear_ec2(region),
        "s3":        escanear_s3(),
        "lambda":    escanear_lambda(region),
        "rds":       escanear_rds(region),
    }
 
 
# ─── CLI ──────────────────────────────────────────────────────────────────────
 
def parse_args():
    parser = argparse.ArgumentParser(
        description="Genera un inventario de recursos AWS."
    )
    parser.add_argument("--region",  "-r", default="us-east-1",
                        help="Región AWS a escanear (default: us-east-1).")
    parser.add_argument("--output",  "-o", default=None,
                        help="Ruta para guardar el inventario en JSON.")
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
    inventario = generar_inventario(args.region)
    mostrar_inventario(inventario)
 
    if args.output:
        guardar_json(inventario, args.output)