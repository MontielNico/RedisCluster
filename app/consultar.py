"""Consultas sobre la red social. Cada una indica en qué nodo están los datos.

Ejemplos:
  consultar.py usuario noticias_ya
  consultar.py timeline noticias_ya -n 5
  consultar.py tweet 120
  consultar.py top
  consultar.py tendencias
"""

import argparse
from datetime import datetime

import red_social as rs
from conexion import crear_cliente, crear_parser, direccion


def ubicacion(cliente, clave):
    return f"{clave} -> slot {cliente.keyslot(clave)}, nodo {direccion(cliente.get_node_from_key(clave))}"


def mostrar_tweets(tweets):
    for t in tweets:
        fecha = datetime.fromtimestamp(int(t["fecha"])).strftime("%d/%m %H:%M")
        print(f"  [{t['id']:>5}] {fecha}  @{t['handle']}: {t['texto']}  ({t['likes']} likes)")


def obtener_uid(cliente, handle):
    uid = rs.buscar_usuario(cliente, handle)
    if uid is None:
        raise SystemExit(f"No existe el usuario {handle}")
    return uid


def consultar_usuario(cliente, args):
    uid = obtener_uid(cliente, args.handle)
    u = rs.obtener_usuario(cliente, uid)
    print(f"@{u['handle']} - {u['nombre']} ({u['ciudad']})")
    print(f"  {u['seguidores']} seguidores, {u['siguiendo']} seguidos, {u['tweets']} tweets")
    print(f"  {ubicacion(cliente, rs.clave_usuario(uid))}")
    print("Últimos tweets:")
    ids = cliente.lrange(rs.clave_usuario(uid, ":tweets"), 0, 4)
    mostrar_tweets(rs.obtener_tweets(cliente, ids))


def consultar_timeline(cliente, args):
    uid = obtener_uid(cliente, args.handle)
    print(f"Timeline de @{args.handle.lstrip('@')}")
    print(f"  {ubicacion(cliente, rs.clave_usuario(uid, ':timeline'))}")
    mostrar_tweets(rs.obtener_timeline(cliente, uid, args.n))


def consultar_tweet(cliente, args):
    tweets = rs.obtener_tweets(cliente, [args.id])
    if not tweets:
        raise SystemExit(f"No existe el tweet {args.id}")
    mostrar_tweets(tweets)
    print(f"  {ubicacion(cliente, rs.clave_tweet(args.id))}")


def consultar_top(cliente, args):
    print("Tweets con más likes")
    print(f"  {ubicacion(cliente, 'ranking:likes')}")
    mostrar_tweets(rs.top_tweets(cliente, args.n))


def consultar_tendencias(cliente, args):
    print("Tendencias")
    print(f"  {ubicacion(cliente, 'tendencias')}")
    for hashtag, usos in rs.tendencias(cliente, args.n):
        print(f"  {hashtag:<16} {int(usos)}")


def main():
    parser = crear_parser(__doc__)
    parser.formatter_class = argparse.RawDescriptionHelpFormatter
    sub = parser.add_subparsers(dest="consulta", required=True)

    for nombre, funcion in [("usuario", consultar_usuario), ("timeline", consultar_timeline)]:
        p = sub.add_parser(nombre)
        p.add_argument("handle")
        p.add_argument("-n", type=int, default=10)
        p.set_defaults(funcion=funcion)

    p = sub.add_parser("tweet")
    p.add_argument("id", type=int)
    p.set_defaults(funcion=consultar_tweet)

    for nombre, funcion in [("top", consultar_top), ("tendencias", consultar_tendencias)]:
        p = sub.add_parser(nombre)
        p.add_argument("-n", type=int, default=10)
        p.set_defaults(funcion=funcion)

    args = parser.parse_args()
    args.funcion(crear_cliente(args.nodo), args)


if __name__ == "__main__":
    main()
