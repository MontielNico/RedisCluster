"""Conexión al cluster y utilidades comunes a los scripts."""

import argparse
import os

from redis.cluster import ClusterNode, RedisCluster

NODO_POR_DEFECTO = os.environ.get("REDIS_NODO", "127.0.0.1:7000")


def parsear_nodo(texto):
    """'192.168.1.10:7000' -> ('192.168.1.10', 7000)"""
    host, puerto = texto.rsplit(":", 1)
    return host, int(puerto)


def direccion(nodo):
    return f"{nodo.host}:{nodo.port}"


def crear_cliente(nodo):
    """Cliente de cluster: con un nodo alcanza, el resto lo descubre solo."""
    host, puerto = parsear_nodo(nodo)
    return RedisCluster(
        startup_nodes=[ClusterNode(host, puerto)],
        decode_responses=True,
        socket_timeout=1,
        socket_connect_timeout=1,
    )


def crear_parser(descripcion):
    parser = argparse.ArgumentParser(description=descripcion)
    parser.add_argument(
        "--nodo",
        default=NODO_POR_DEFECTO,
        help="IP:PUERTO de cualquier nodo del cluster (por defecto %(default)s)",
    )
    return parser
