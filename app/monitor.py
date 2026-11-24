"""Muestra en vivo el estado de cada nodo: rol, estado, slots y cantidad de claves."""

import sys
import time
from datetime import datetime

import redis

from conexion import crear_parser, parsear_nodo


def conectar(direccion):
    host, puerto = parsear_nodo(direccion)
    return redis.Redis(
        host=host, port=puerto, decode_responses=True,
        socket_timeout=0.5, socket_connect_timeout=0.5,
    )


def parsear_cluster_nodes(texto):
    """Convierte la salida de CLUSTER NODES en un dict por dirección."""
    nodos = {}
    for linea in texto.strip().splitlines():
        campos = linea.split()
        direccion = campos[1].split("@")[0]
        nodos[direccion] = {
            "id": campos[0],
            "flags": campos[2].split(","),
            "master_id": campos[3],
            "slots": [s for s in campos[8:] if not s.startswith("[")],
        }
    return nodos


def obtener_vista(conocidos):
    """Pide CLUSTER NODES e INFO al primer nodo que responda."""
    for direccion in sorted(conocidos):
        try:
            r = conectar(direccion)
            nodos = parsear_cluster_nodes(r.execute_command("CLUSTER", "NODES"))
            estado = r.execute_command("CLUSTER", "INFO")
            estado = estado.split("cluster_state:")[1].split()[0]
            return direccion, estado, nodos
        except redis.RedisError:
            continue
    return None, "sin respuesta", {}


def contar_claves(direccion):
    try:
        return conectar(direccion).dbsize()
    except redis.RedisError:
        return None


def contar_slots(rangos):
    total = 0
    for rango in rangos:
        inicio, _, fin = rango.partition("-")
        total += int(fin or inicio) - int(inicio) + 1
    return total


def describir_estado(flags):
    if "fail" in flags:
        return "CAIDO"
    if "fail?" in flags:
        return "SOSPECHOSO"
    return "ok"


def mostrar_estado(visto_desde, estado, nodos):
    print("\033[2J\033[H", end="")  # limpia la pantalla
    print(f"Redis Cluster  {datetime.now():%H:%M:%S}   estado: {estado.upper()}   (visto desde {visto_desde})\n")
    print(f"{'NODO':<21} {'ROL':<8} {'ESTADO':<11} {'REPLICA DE':<21} {'SLOTS':>6} {'CLAVES':>8}  RANGOS")
    direccion_por_id = {n["id"]: d for d, n in nodos.items()}
    for direccion, nodo in sorted(nodos.items(), key=lambda item: parsear_nodo(item[0])):
        rol = "master" if "master" in nodo["flags"] else "replica"
        replica_de = direccion_por_id.get(nodo["master_id"], "")
        claves = contar_claves(direccion)
        claves = "-" if claves is None else str(claves)
        rangos = " ".join(nodo["slots"])
        print(f"{direccion:<21} {rol:<8} {describir_estado(nodo['flags']):<11} "
              f"{replica_de:<21} {contar_slots(nodo['slots']):>6} {claves:>8}  {rangos}")


def monitorear(nodo, intervalo):
    conocidos = {nodo}
    while True:
        visto_desde, estado, nodos = obtener_vista(conocidos)
        conocidos.update(nodos)
        mostrar_estado(visto_desde, estado, nodos)
        sys.stdout.flush()
        time.sleep(intervalo)


def main():
    parser = crear_parser(__doc__)
    parser.add_argument("--intervalo", type=float, default=1.0)
    args = parser.parse_args()
    try:
        monitorear(args.nodo, args.intervalo)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
