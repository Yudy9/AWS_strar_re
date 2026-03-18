import argparse
import logging
import time
import os
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
 
 
# ─── Colores para la terminal ─────────────────────────────────────────────────
 
class Color:
    VERDE   = "\033[92m"
    ROJO    = "\033[91m"
    AMARILLO= "\033[93m"
    AZUL    = "\033[94m"
    GRIS    = "\033[90m"
    RESET   = "\033[0m"
    BOLD    = "\033[1m"
 
 
def colorear_estado(estado: str) -> str:
    colores = {
        "running":        Color.VERDE   + estado + Color.RESET,
        "stopped":        Color.ROJO    + estado + Color.RESET,
        "stopping":       Color.AMARILLO+ estado + Color.RESET,
        "pending":        Color.AMARILLO+ estado + Color.RESET,
        "terminated":     Color.GRIS    + estado + Color.RESET,
        "shutting-down":  Color.GRIS    + estado + Color.RESET,
    }
    return colores.get(estado, estado)
 
 
# ─── Obtener instancias ───────────────────────────────────────────────────────
 
def obtener_instancias(region: str) -> list[dict]:
    """
    Consulta AWS y devuelve una lista de dicts con los datos de cada instancia.
    """
    ec2 = boto3.client("ec2", region_name=region)
 
    try:
        respuesta = ec2.describe_instances()
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error al consultar EC2: {e}")
        return []
 
    instancias = []
    for reserva in respuesta["Reservations"]:
        for inst in reserva["Instances"]:
 
            # Obtener nombre del tag si existe
            nombre = "-"
            for tag in inst.get("Tags", []):
                if tag["Key"] == "Name":
                    nombre = tag["Value"]
                    break
 
            instancias.append({
                "id":         inst.get("InstanceId",       "-"),
                "estado":     inst.get("State", {}).get("Name", "-"),
                "tipo":       inst.get("InstanceType",     "-"),
                "ip_publica": inst.get("PublicIpAddress",  "Sin IP"),
                "nombre":     nombre,
            })
 
    return instancias
 
 
# ─── Mostrar tabla ────────────────────────────────────────────────────────────
 
def mostrar_tabla(instancias: list[dict], region: str) -> None:
    """
    Imprime una tabla formateada en la terminal.
    """
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
 
    # Limpiar pantalla en modo watch
    os.system("clear" if os.name != "nt" else "cls")
 
    print(f"\n{Color.BOLD}{'='*70}{Color.RESET}")
    print(f"{Color.BOLD}  Monitor EC2  |  Región: {region}  |  {ahora}{Color.RESET}")
    print(f"{Color.BOLD}{'='*70}{Color.RESET}")
 
    if not instancias:
        print(f"\n  {Color.AMARILLO}No se encontraron instancias EC2 en esta región.{Color.RESET}\n")
        return
 
    # Encabezado de tabla
    print(f"\n  {Color.BOLD}"
          f"{'INSTANCE ID':<22}"
          f"{'NOMBRE':<20}"
          f"{'ESTADO':<16}"
          f"{'TIPO':<16}"
          f"{'IP PÚBLICA':<18}"
          f"{Color.RESET}")
    print(f"  {'-'*90}")
 
    # Filas
    for inst in instancias:
        estado_color = colorear_estado(inst["estado"])
        # Ajuste de padding considerando los caracteres de color
        pad_extra = len(estado_color) - len(inst["estado"])
 
        print(
            f"  {inst['id']:<22}"
            f"{inst['nombre']:<20}"
            f"{estado_color:<{16 + pad_extra}}"
            f"{inst['tipo']:<16}"
            f"{inst['ip_publica']:<18}"
        )
 
    # Resumen
    total     = len(instancias)
    running   = sum(1 for i in instancias if i["estado"] == "running")
    stopped   = sum(1 for i in instancias if i["estado"] == "stopped")
    otras     = total - running - stopped
 
    print(f"\n  {Color.BOLD}Resumen:{Color.RESET}  "
          f"Total: {total}  |  "
          f"{Color.VERDE}Running: {running}{Color.RESET}  |  "
          f"{Color.ROJO}Stopped: {stopped}{Color.RESET}  |  "
          f"{Color.AMARILLO}Otras: {otras}{Color.RESET}")
    print(f"{Color.BOLD}{'='*70}{Color.RESET}\n")
 
 
# ─── Modo watch ──────────────────────────────────────────────────────────────
 
def watch(region: str, interval: int) -> None:
    """Refresca la tabla cada `interval` segundos."""
    print(f"Modo monitor activo — actualizando cada {interval}s. Ctrl+C para salir.\n")
    try:
        while True:
            instancias = obtener_instancias(region)
            mostrar_tabla(instancias, region)
            print(f"  {Color.GRIS}Próxima actualización en {interval}s...{Color.RESET}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n  Monitor detenido.\n")
 
 
# ─── CLI ─────────────────────────────────────────────────────────────────────
 
def parse_args():
    parser = argparse.ArgumentParser(
        description="Lista y monitorea instancias EC2."
    )
    parser.add_argument(
        "--region", "-r",
        default="us-west-2",
        help="Región de AWS (default: us-west-2).",
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Modo monitor: refresca automáticamente.",
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=30,
        help="Segundos entre refrescos en modo watch (default: 30).",
    )
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
 
    if args.watch:
        watch(args.region, args.interval)
    else:
        instancias = obtener_instancias(args.region)
        mostrar_tabla(instancias, args.region)