import argparse
import logging
import time
import sys
 
import boto3
from botocore.exceptions import BotoCoreError, ClientError
 
# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)
 
 
# ─── Colores ──────────────────────────────────────────────────────────────────
class C:
    VERDE    = "\033[92m"
    ROJO     = "\033[91m"
    AMARILLO = "\033[93m"
    CYAN     = "\033[96m"
    BOLD     = "\033[1m"
    RESET    = "\033[0m"
 
 
COLORES_ESTADO = {
    "CREATE_COMPLETE":     C.VERDE,
    "UPDATE_COMPLETE":     C.VERDE,
    "CREATE_IN_PROGRESS":  C.AMARILLO,
    "UPDATE_IN_PROGRESS":  C.AMARILLO,
    "ROLLBACK_IN_PROGRESS":C.ROJO,
    "ROLLBACK_COMPLETE":   C.ROJO,
    "DELETE_IN_PROGRESS":  C.AMARILLO,
    "DELETE_COMPLETE":     C.ROJO,
    "CREATE_FAILED":       C.ROJO,
}
 
 
# ─── Crear stack ──────────────────────────────────────────────────────────────
def crear_stack(cf, nombre_stack: str, template_file: str, region: str) -> None:
    with open(template_file, "r") as f:
        template_body = f.read()
 
    log.info(f"Creando stack: {nombre_stack}")
    log.info(f"Región: {region}")
 
    try:
        cf.create_stack(
            StackName=nombre_stack,
            TemplateBody=template_body,
            Parameters=[
                {"ParameterKey": "NombreProyecto",     "ParameterValue": "MiAppWeb"},
                {"ParameterKey": "AmbienteDespliegue", "ParameterValue": "dev"},
                {"ParameterKey": "TipoInstanciaEC2",   "ParameterValue": "t2.micro"},
                {"ParameterKey": "CantidadInstancias", "ParameterValue": "2"},
            ],
            Capabilities=["CAPABILITY_IAM", "CAPABILITY_NAMED_IAM"],
            Tags=[
                {"Key": "Proyecto",   "Value": "MiAppWeb"},
                {"Key": "Ambiente",   "Value": "dev"},
                {"Key": "GestionadoPor", "Value": "CloudFormation"},
            ],
        )
        log.info("Stack enviado a CloudFormation. Esperando que termine...")
        esperar_stack(cf, nombre_stack, "CREATE_COMPLETE")
 
    except ClientError as e:
        log.error(f"Error creando stack: {e}")
        sys.exit(1)
 
 
# ─── Esperar stack ────────────────────────────────────────────────────────────
def esperar_stack(cf, nombre_stack: str, estado_esperado: str) -> None:
    estados_finales = {
        "CREATE_COMPLETE", "CREATE_FAILED",
        "ROLLBACK_COMPLETE", "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE", "DELETE_COMPLETE",
    }
 
    print(f"\n{C.BOLD}Esperando estado: {estado_esperado}...{C.RESET}")
    print(f"{'─'*60}")
 
    spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    i = 0
 
    while True:
        try:
            respuesta = cf.describe_stacks(StackName=nombre_stack)
            stack = respuesta["Stacks"][0]
            estado = stack["StackStatus"]
            color  = COLORES_ESTADO.get(estado, "")
 
            print(
                f"\r  {spinner[i % len(spinner)]}  Estado: "
                f"{color}{estado}{C.RESET}          ",
                end="", flush=True
            )
 
            if estado in estados_finales:
                print()
                if estado == estado_esperado:
                    print(f"\n{C.VERDE}{C.BOLD}✅  Stack listo: {estado}{C.RESET}\n")
                    mostrar_outputs(cf, nombre_stack)
                else:
                    print(f"\n{C.ROJO}{C.BOLD}❌  Stack terminó con error: {estado}{C.RESET}\n")
                    mostrar_eventos_error(cf, nombre_stack)
                break
 
            time.sleep(10)
            i += 1
 
        except ClientError as e:
            log.error(f"Error consultando stack: {e}")
            break
 
 
# ─── Ver estado ───────────────────────────────────────────────────────────────
def ver_estado(cf, nombre_stack: str) -> None:
    try:
        respuesta = cf.describe_stacks(StackName=nombre_stack)
        stack = respuesta["Stacks"][0]
        estado = stack["StackStatus"]
        color  = COLORES_ESTADO.get(estado, "")
 
        print(f"\n{C.BOLD}{'═'*60}{C.RESET}")
        print(f"{C.BOLD}  Estado del Stack: {nombre_stack}{C.RESET}")
        print(f"{'═'*60}")
        print(f"  Estado    : {color}{C.BOLD}{estado}{C.RESET}")
        print(f"  Creado    : {stack.get('CreationTime', '-')}")
        print(f"  Actualizado: {stack.get('LastUpdatedTime', '-')}")
        print(f"  Descripción: {stack.get('Description', '-')[:60]}")
 
        # Recursos del stack
        recursos = cf.describe_stack_resources(StackName=nombre_stack)
        print(f"\n{C.BOLD}  Recursos ({len(recursos['StackResources'])} total):{C.RESET}")
        print(f"  {'─'*55}")
        print(f"  {C.BOLD}{'RECURSO':<35}{'TIPO':<25}{'ESTADO'}{C.RESET}")
        print(f"  {'─'*70}")
 
        for r in recursos["StackResources"]:
            est = r["ResourceStatus"]
            col = COLORES_ESTADO.get(est, "")
            tipo_corto = r["ResourceType"].split("::")[-1]
            print(
                f"  {r['LogicalResourceId']:<35}"
                f"{tipo_corto:<25}"
                f"{col}{est}{C.RESET}"
            )
 
        print(f"\n{'═'*60}\n")
 
    except ClientError as e:
        log.error(f"Error obteniendo estado: {e}")
 
 
# ─── Mostrar outputs ──────────────────────────────────────────────────────────
def mostrar_outputs(cf, nombre_stack: str) -> None:
    try:
        respuesta = cf.describe_stacks(StackName=nombre_stack)
        outputs = respuesta["Stacks"][0].get("Outputs", [])
 
        print(f"\n{C.CYAN}{C.BOLD}{'═'*60}")
        print(f"  OUTPUTS DEL STACK")
        print(f"{'═'*60}{C.RESET}")
 
        if not outputs:
            print(f"  {C.AMARILLO}No hay outputs disponibles aún.{C.RESET}\n")
            return
 
        for out in outputs:
            clave = out["OutputKey"]
            valor = out["OutputValue"]
            desc  = out.get("Description", "")
 
            # Resaltar la URL de la aplicación
            if "URL" in clave or "url" in clave.lower():
                print(f"\n  {C.BOLD}{clave}{C.RESET}")
                print(f"  {C.VERDE}→ {valor}{C.RESET}")
            else:
                print(f"\n  {C.BOLD}{clave}{C.RESET}")
                print(f"  → {valor}")
 
            if desc:
                print(f"  {C.AMARILLO}{desc}{C.RESET}")
 
        print(f"\n{'═'*60}\n")
 
    except ClientError as e:
        log.error(f"Error obteniendo outputs: {e}")
 
 
# ─── Eventos de error ─────────────────────────────────────────────────────────
def mostrar_eventos_error(cf, nombre_stack: str) -> None:
    try:
        eventos = cf.describe_stack_events(StackName=nombre_stack)
        errores = [
            e for e in eventos["StackEvents"]
            if "FAILED" in e.get("ResourceStatus", "")
        ]
 
        if errores:
            print(f"{C.ROJO}{C.BOLD}Eventos con error:{C.RESET}")
            for e in errores[:5]:
                print(f"  ❌ {e['LogicalResourceId']}: {e.get('ResourceStatusReason', '-')}")
 
    except ClientError:
        pass
 
 
# ─── Eliminar stack ───────────────────────────────────────────────────────────
def eliminar_stack(cf, nombre_stack: str) -> None:
    print(f"\n{C.AMARILLO}⚠️  Eliminando stack: {nombre_stack}{C.RESET}")
    confirmar = input("¿Estás seguro? Escribe 'si' para confirmar: ")
 
    if confirmar.lower() != "si":
        print("Operación cancelada.")
        return
 
    try:
        cf.delete_stack(StackName=nombre_stack)
        log.info("Eliminando stack... esto puede tardar varios minutos.")
        esperar_stack(cf, nombre_stack, "DELETE_COMPLETE")
    except ClientError as e:
        log.error(f"Error eliminando stack: {e}")
 
 
# ─── CLI ──────────────────────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(
        description="Despliega y gestiona el stack CloudFormation."
    )
    parser.add_argument(
        "--accion", "-a",
        choices=["crear", "estado", "outputs", "eliminar"],
        default="estado",
    )
    parser.add_argument("--region",   "-r", default="us-west-2")
    parser.add_argument("--stack",    "-s", default="MiAppWeb-dev")
    parser.add_argument("--template", "-t", default="infraestructura-web.yaml")
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
    cf   = boto3.client("cloudformation", region_name=args.region)
 
    if args.accion == "crear":
        crear_stack(cf, args.stack, args.template, args.region)
    elif args.accion == "estado":
        ver_estado(cf, args.stack)
    elif args.accion == "outputs":
        mostrar_outputs(cf, args.stack)
    elif args.accion == "eliminar":
        eliminar_stack(cf, args.stack)