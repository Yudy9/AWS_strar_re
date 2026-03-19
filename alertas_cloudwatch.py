import argparse
import logging
import random
import time
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
    BOLD     = "\033[1m"
    RESET    = "\033[0m"
 
 
# ─── 1. Publicar métricas personalizadas ──────────────────────────────────────
 
def publicar_metrica(
    region: str,
    namespace: str,
    nombre_metrica: str,
    valor: float,
    unidad: str = "Percent",
    dimensiones: list[dict] = None,
) -> None:
    """
    Publica una métrica personalizada en CloudWatch.
 
    Parámetros:
        namespace       : agrupa tus métricas (ej. "MiApp/Servidor")
        nombre_metrica  : nombre descriptivo (ej. "UsoMemoria")
        valor           : número a registrar
        unidad          : Percent | Count | Bytes | Seconds | None
        dimensiones     : lista de dicts [{"Name": "...", "Value": "..."}]
    """
    cw = boto3.client("cloudwatch", region_name=region)
 
    datos = {
        "MetricName": nombre_metrica,
        "Value":      valor,
        "Unit":       unidad,
        "Timestamp":  datetime.utcnow(),
    }
 
    if dimensiones:
        datos["Dimensions"] = dimensiones
 
    try:
        cw.put_metric_data(
            Namespace=namespace,
            MetricData=[datos],
        )
        log.info(f"Métrica publicada: {namespace}/{nombre_metrica} = {valor} {unidad}")
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error publicando métrica: {e}")
 
 
# ─── 2. Crear alarma ──────────────────────────────────────────────────────────
 
def crear_topic_sns(region: str, nombre: str, email: str) -> str:
    """Crea un topic SNS y suscribe un email para recibir alertas."""
    sns = boto3.client("sns", region_name=region)
 
    # Crear topic
    topic = sns.create_topic(Name=nombre)
    topic_arn = topic["TopicArn"]
    log.info(f"Topic SNS creado: {topic_arn}")
 
    # Suscribir email
    sns.subscribe(
        TopicArn=topic_arn,
        Protocol="email",
        Endpoint=email,
    )
    log.info(f"Suscripción enviada a: {email} — revisa tu correo para confirmar")
    return topic_arn
 
 
def crear_alarma(
    region: str,
    nombre_alarma: str,
    namespace: str,
    metrica: str,
    umbral: float,
    topic_arn: str,
    comparacion: str = "GreaterThanThreshold",
    periodos: int = 2,
    descripcion: str = "",
) -> None:
    """
    Crea una alarma en CloudWatch.
 
    Se activa cuando la métrica supera el umbral durante N periodos de 60s.
    Envía una notificación al topic SNS indicado.
    """
    cw = boto3.client("cloudwatch", region_name=region)
 
    try:
        cw.put_metric_alarm(
            AlarmName=nombre_alarma,
            AlarmDescription=descripcion or f"Alarma automática: {metrica} > {umbral}",
            MetricName=metrica,
            Namespace=namespace,
            Statistic="Average",
            Period=60,                    # evalúa cada 60 segundos
            EvaluationPeriods=periodos,   # debe superar el umbral N veces seguidas
            Threshold=umbral,
            ComparisonOperator=comparacion,
            AlarmActions=[topic_arn],
            OKActions=[topic_arn],
            TreatMissingData="notBreaching",
        )
        log.info(f"Alarma creada: '{nombre_alarma}' (umbral: {umbral})")
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error creando alarma: {e}")
 
 
# ─── 3. Listar alarmas ────────────────────────────────────────────────────────
 
def listar_alarmas(region: str) -> None:
    """Muestra todas las alarmas CloudWatch y su estado actual."""
    cw = boto3.client("cloudwatch", region_name=region)
 
    try:
        respuesta = cw.describe_alarms()
        alarmas   = respuesta.get("MetricAlarms", [])
 
        print(f"\n{C.BOLD}{'═'*80}")
        print(f"  Alarmas CloudWatch  |  Región: {region}")
        print(f"{'═'*80}{C.RESET}")
 
        if not alarmas:
            print(f"  {C.AMARILLO}No hay alarmas configuradas.{C.RESET}\n")
            return
 
        print(f"\n  {C.BOLD}{'NOMBRE':<35}{'ESTADO':<14}{'MÉTRICA':<25}{'UMBRAL'}{C.RESET}")
        print(f"  {'─'*75}")
 
        colores_estado = {
            "OK":                 C.VERDE,
            "ALARM":              C.ROJO,
            "INSUFFICIENT_DATA":  C.AMARILLO,
        }
 
        for alarma in alarmas:
            estado = alarma["StateValue"]
            color  = colores_estado.get(estado, "")
            umbral = alarma.get("Threshold", "-")
            metrica = alarma.get("MetricName", "-")
 
            print(
                f"  {alarma['AlarmName']:<35}"
                f"{color}{estado:<14}{C.RESET}"
                f"{metrica:<25}"
                f"{umbral}"
            )
 
        print(f"\n  Total: {len(alarmas)} alarmas\n")
 
    except (BotoCoreError, ClientError) as e:
        log.error(f"Error listando alarmas: {e}")
 
 
# ─── 4. Simulación de métricas ────────────────────────────────────────────────
 
def simular_metricas(region: str, ciclos: int = 5) -> None:
    """
    Simula el envío de métricas realistas durante N ciclos.
    Útil para probar que CloudWatch las recibe correctamente.
    """
    namespace = "MiApp/Servidor"
    servidor  = "servidor-prueba"
 
    print(f"\n{C.BOLD}Simulando métricas en CloudWatch ({ciclos} ciclos)...{C.RESET}")
    print(f"Namespace: {namespace}\n")
 
    for i in range(1, ciclos + 1):
        cpu     = round(random.uniform(10, 95), 2)
        memoria = round(random.uniform(40, 90), 2)
        errores = random.randint(0, 10)
        latencia = round(random.uniform(50, 500), 2)
 
        dimensiones = [{"Name": "Servidor", "Value": servidor}]
 
        publicar_metrica(region, namespace, "USOcpu",      cpu,      "Percent",      dimensiones)
        publicar_metrica(region, namespace, "USOmemoria",  memoria,  "Percent",      dimensiones)
        publicar_metrica(region, namespace, "Errores",     errores,  "Count",        dimensiones)
        publicar_metrica(region, namespace, "Latencia",    latencia, "Milliseconds", dimensiones)
 
        indicador_cpu = C.ROJO if cpu > 80 else (C.AMARILLO if cpu > 60 else C.VERDE)
        print(
            f"  Ciclo {i}/{ciclos}  |  "
            f"CPU: {indicador_cpu}{cpu}%{C.RESET}  |  "
            f"Memoria: {memoria}%  |  "
            f"Errores: {errores}  |  "
            f"Latencia: {latencia}ms"
        )
 
        if i < ciclos:
            time.sleep(3)
 
    print(f"\n{C.VERDE}Simulación completada. Revisa CloudWatch en AWS Console.{C.RESET}\n")
 
 
# ─── CLI ──────────────────────────────────────────────────────────────────────
 
def parse_args():
    parser = argparse.ArgumentParser(
        description="Métricas personalizadas y alertas con CloudWatch."
    )
    parser.add_argument(
        "--accion", "-a",
        choices=["listar", "publicar", "crear-alarma", "simular"],
        default="listar",
        help="Acción a ejecutar.",
    )
    parser.add_argument("--region",  "-r", default="us-east-1")
    parser.add_argument("--email",   "-e", default=None,
                        help="Email para recibir alertas (requerido en crear-alarma).")
    return parser.parse_args()
 
 
if __name__ == "__main__":
    args = parse_args()
 
    if args.accion == "listar":
        listar_alarmas(args.region)
 
    elif args.accion == "publicar":
        # Publica una métrica de ejemplo
        publicar_metrica(
            region=args.region,
            namespace="MiApp/Servidor",
            nombre_metrica="USOcpu",
            valor=75.5,
            unidad="Percent",
            dimensiones=[{"Name": "Servidor", "Value": "servidor-prueba"}],
        )
 
    elif args.accion == "crear-alarma":
        if not args.email:
            print(f"{C.ROJO}Error: debes indicar --email para crear una alarma.{C.RESET}")
        else:
            topic_arn = crear_topic_sns(args.region, "alertas-mi-app", args.email)
            crear_alarma(
                region=args.region,
                nombre_alarma="CPU-Alta",
                namespace="MiApp/Servidor",
                metrica="USOcpu",
                umbral=80.0,
                topic_arn=topic_arn,
                descripcion="Alerta cuando el uso de CPU supera el 80%",
            )
 
    elif args.accion == "simular":
        simular_metricas(args.region, ciclos=5)
 # pega aquí el contenido del archivo
