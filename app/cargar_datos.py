"""Genera una red social de ejemplo: usuarios, seguidores, tweets y likes."""

import random
import time
import unicodedata
from itertools import accumulate

from redis.cluster import RedisCluster

import datos_ejemplo as datos
import red_social as rs
from conexion import crear_cliente, crear_parser, direccion

LOTE = 2000  # comandos por pipeline


def normalizar(texto):
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sin_acentos.lower().replace(" ", "_")


def ejecutar_si_lleno(pipe):
    if len(pipe) >= LOTE:
        pipe.execute()


def reservar_ids(cliente, contador, cantidad):
    """Reserva un rango de IDs con un solo INCRBY."""
    ultimo = cliente.incrby(contador, cantidad)
    return list(range(ultimo - cantidad + 1, ultimo + 1))


def generar_perfiles(cantidad):
    """Cuentas populares primero y el resto con nombres al azar. Devuelve perfiles y pesos."""
    perfiles = [(nombre, handle, "Buenos Aires") for nombre, handle in datos.CUENTAS_POPULARES]
    pesos = [40] * len(perfiles)
    handles = {handle for _, handle, _ in perfiles}
    while len(perfiles) < cantidad:
        nombre = f"{random.choice(datos.NOMBRES)} {random.choice(datos.APELLIDOS)}"
        handle = normalizar(nombre)
        while handle in handles:
            handle = f"{normalizar(nombre)}{random.randint(1, 999)}"
        handles.add(handle)
        perfiles.append((nombre, handle, random.choice(datos.CIUDADES)))
        # Distribución de Pareto: pocos usuarios concentran muchos seguidores.
        pesos.append(random.paretovariate(1.5))
    return perfiles, list(accumulate(pesos))


def crear_usuarios(cliente, cantidad):
    perfiles, pesos_acumulados = generar_perfiles(cantidad)
    uids = reservar_ids(cliente, "ids:usuario", len(perfiles))
    pipe = cliente.pipeline()
    for uid, (nombre, handle, ciudad) in zip(uids, perfiles):
        pipe.hset(rs.clave_usuario(uid), mapping={"nombre": nombre, "handle": handle, "ciudad": ciudad})
        pipe.set(f"handle:{handle}", uid)
        ejecutar_si_lleno(pipe)
    pipe.execute()
    return uids, pesos_acumulados


def crear_seguidores(cliente, uids, pesos_acumulados):
    """Devuelve {usuario: set de seguidores}, que después se usa para armar los timelines."""
    seguidores = {uid: set() for uid in uids}
    pipe = cliente.pipeline()
    for uid in uids:
        elegidos = random.choices(uids, cum_weights=pesos_acumulados, k=random.randint(5, 40))
        for otro in set(elegidos) - {uid}:
            pipe.sadd(rs.clave_usuario(uid, ":siguiendo"), otro)
            pipe.sadd(rs.clave_usuario(otro, ":seguidores"), uid)
            seguidores[otro].add(uid)
        ejecutar_si_lleno(pipe)
    pipe.execute()
    return seguidores


def generar_texto():
    hashtags = random.sample(datos.HASHTAGS, k=random.randint(0, 2))
    return " ".join([random.choice(datos.FRASES), *hashtags])


def crear_tweets(cliente, uids, seguidores, cantidad):
    """Publica los tweets de la última semana en orden cronológico, con el mismo
    fan-out que rs.publicar_tweet pero en lotes."""
    ahora = int(time.time())
    fechas = sorted(random.randint(ahora - 7 * 86400, ahora) for _ in range(cantidad))
    autores = random.choices(uids, k=cantidad)
    tids = reservar_ids(cliente, "ids:tweet", cantidad)
    pipe = cliente.pipeline()
    for tid, autor, fecha in zip(tids, autores, fechas):
        texto = generar_texto()
        pipe.hset(rs.clave_tweet(tid), mapping={"autor": autor, "texto": texto, "fecha": fecha, "likes": 0})
        pipe.lpush(rs.clave_usuario(autor, ":tweets"), tid)
        for hashtag in rs.extraer_hashtags(texto):
            pipe.zincrby("tendencias", 1, hashtag)
        for seguidor in seguidores[autor]:
            pipe.lpush(rs.clave_usuario(seguidor, ":timeline"), tid)
        ejecutar_si_lleno(pipe)
    for uid in uids:
        pipe.ltrim(rs.clave_usuario(uid, ":timeline"), 0, rs.LIMITE_TIMELINE - 1)
    pipe.execute()
    return tids


def crear_likes(cliente, uids, tids, cantidad):
    """Pocos tweets se vuelven virales y se llevan la mayoría de los likes."""
    cantidad = min(cantidad, len(uids) * len(tids) // 4)
    viralidad = list(accumulate(random.paretovariate(2) for _ in tids))
    pares = set()
    while len(pares) < cantidad:
        tid = random.choices(tids, cum_weights=viralidad)[0]
        pares.add((random.choice(uids), tid))

    pipe = cliente.pipeline()
    for uid, tid in pares:
        pipe.sadd(rs.clave_tweet(tid, ":likes"), uid)
        pipe.hincrby(rs.clave_tweet(tid), "likes", 1)
        pipe.zincrby("ranking:likes", 1, tid)
        ejecutar_si_lleno(pipe)
    pipe.execute()
    return cantidad


def mostrar_resumen(cliente):
    usuarios, tweets = rs.totales(cliente)
    print(f"\nUsuarios: {usuarios}   Tweets: {tweets}\n")

    print("Claves por master:")
    for nodo in cliente.get_primaries():
        claves = cliente.execute_command("DBSIZE", target_nodes=nodo)
        print(f"  {direccion(nodo):<21} {claves:>7}")

    print("\nTweets con más likes:")
    for tweet in rs.top_tweets(cliente, 3):
        print(f"  {tweet['likes']:>4}  @{tweet['handle']}: {tweet['texto']}")

    print("\nTendencias:")
    for hashtag, usos in rs.tendencias(cliente, 5):
        print(f"  {hashtag:<16} {int(usos)}")

    print("\nTodo lo del usuario 1 está en el mismo nodo (hash tag {usuario:1}):")
    for sufijo in ["", ":seguidores", ":siguiendo", ":tweets", ":timeline"]:
        clave = rs.clave_usuario(1, sufijo)
        print(f"  {clave:<26} slot {cliente.keyslot(clave):>5}  ->  {direccion(cliente.get_node_from_key(clave))}")


def main():
    parser = crear_parser(__doc__)
    parser.add_argument("--usuarios", type=int, default=500)
    parser.add_argument("--tweets", type=int, default=1500)
    parser.add_argument("--likes", type=int, default=10000)
    parser.add_argument("--semilla", type=int, default=42, help="misma semilla, mismos datos")
    parser.add_argument("--limpiar", action="store_true", help="borra los datos existentes antes de cargar")
    args = parser.parse_args()

    random.seed(args.semilla)
    cliente = crear_cliente(args.nodo)
    if args.limpiar:
        cliente.flushall(target_nodes=RedisCluster.PRIMARIES)
    elif any(rs.totales(cliente)):
        print("El cluster ya tiene datos. Usar --limpiar para borrarlos y cargar de nuevo.")
        return

    inicio = time.time()
    print("Creando usuarios...")
    uids, pesos = crear_usuarios(cliente, args.usuarios)
    print("Creando seguidores...")
    seguidores = crear_seguidores(cliente, uids, pesos)
    print("Publicando tweets...")
    tids = crear_tweets(cliente, uids, seguidores, args.tweets)
    print("Dando likes...")
    crear_likes(cliente, uids, tids, args.likes)
    print(f"Listo en {time.time() - inicio:.1f} s")

    mostrar_resumen(cliente)


if __name__ == "__main__":
    main()
