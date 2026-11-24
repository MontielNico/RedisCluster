"""Simula usuarios usando la red social sin parar: likes, tweets y lectura de timelines.
Muestra a qué nodo va cada operación y cuánto tarda el cluster en recuperarse
cuando se cae un master."""

import random
import time
from datetime import datetime

from redis.exceptions import RedisError

import datos_ejemplo as datos
import red_social as rs
from conexion import crear_cliente, crear_parser, direccion


def hora():
    return datetime.now().strftime("%H:%M:%S")


def nodo_de(cliente, clave):
    return direccion(cliente.get_node_from_key(clave))


def handle_de(cliente, uid):
    return cliente.hget(rs.clave_usuario(uid), "handle")


def tweet_reciente(total_tweets):
    """Los tweets nuevos reciben más likes que los viejos."""
    return max(1, total_tweets - int(random.expovariate(1 / 200)))


def accion_like(cliente, usuarios, tweets):
    uid, tid = random.randint(1, usuarios), tweet_reciente(tweets)
    likes = rs.dar_like(cliente, uid, tid)
    resultado = f"({likes} likes)" if likes else "(ya tenía like)"
    return f"LIKE      @{handle_de(cliente, uid)} -> tweet {tid} {resultado}", rs.clave_tweet(tid)


def accion_tweet(cliente, usuarios, _tweets):
    uid = random.randint(1, usuarios)
    texto = f"{random.choice(datos.FRASES)} {random.choice(datos.HASHTAGS)}"
    tid, alcance = rs.publicar_tweet(cliente, uid, texto)
    return f"TWEET     @{handle_de(cliente, uid)} publicó el {tid}, llegó a {alcance} timelines", rs.clave_tweet(tid)


def accion_timeline(cliente, usuarios, _tweets):
    uid = random.randint(1, usuarios)
    leidos = rs.obtener_timeline(cliente, uid)
    return f"TIMELINE  @{handle_de(cliente, uid)} leyó {len(leidos)} tweets", rs.clave_usuario(uid, ":timeline")


ACCIONES = [accion_like, accion_tweet, accion_timeline]
PROBABILIDADES = [0.6, 0.15, 0.25]


def simular_en_loop(nodo, pausa):
    cliente = crear_cliente(nodo)
    inicio_falla = None
    while True:
        try:
            usuarios, tweets = rs.totales(cliente)
            if not tweets:
                print("No hay datos: correr primero cargar_datos.py")
                return
            accion = random.choices(ACCIONES, weights=PROBABILIDADES)[0]
            descripcion, clave = accion(cliente, usuarios, tweets)
            if inicio_falla is not None:
                print(f"[{hora()}] RECUPERADO tras {time.time() - inicio_falla:.1f} s")
                inicio_falla = None
            print(f"[{hora()}] {descripcion:<62} [{nodo_de(cliente, clave)}]")
        except RedisError as error:
            if inicio_falla is None:
                inicio_falla = time.time()
            print(f"[{hora()}] ERROR     {type(error).__name__}: {error}")
        time.sleep(pausa)


def main():
    parser = crear_parser(__doc__)
    parser.add_argument("--pausa", type=float, default=0.3, help="segundos entre operaciones")
    args = parser.parse_args()
    try:
        simular_en_loop(args.nodo, args.pausa)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
