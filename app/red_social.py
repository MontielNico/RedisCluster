"""Modelo de una red social estilo Twitter sobre Redis Cluster.

Claves. Lo que va entre llaves es el hash tag: solo eso se usa para calcular
el slot, así todos los datos de un usuario (o de un tweet) quedan en el mismo nodo.

  {usuario:ID}              hash    nombre, handle, ciudad
  {usuario:ID}:seguidores   set     IDs que lo siguen
  {usuario:ID}:siguiendo    set     IDs a los que sigue
  {usuario:ID}:tweets       lista   sus tweets, el más nuevo primero
  {usuario:ID}:timeline     lista   tweets de quienes sigue (máx. 800)
  {tweet:ID}                hash    autor, texto, fecha, likes
  {tweet:ID}:likes          set     IDs de usuarios que dieron like
  handle:NOMBRE             string  ID del usuario
  ids:usuario, ids:tweet    string  contadores para generar IDs
  tendencias                zset    hashtags por cantidad de usos
  ranking:likes             zset    tweets por cantidad de likes
"""

import re
import time

LIMITE_TIMELINE = 800

# SADD + HINCRBY atómicos. Funciona porque ambas claves comparten el hash tag
# {tweet:ID}; con claves de slots distintos Redis Cluster lo rechaza (CROSSSLOT).
SCRIPT_LIKE = """
if redis.call('SADD', KEYS[2], ARGV[1]) == 1 then
  return redis.call('HINCRBY', KEYS[1], 'likes', 1)
end
return false
"""


def clave_usuario(uid, sufijo=""):
    return f"{{usuario:{uid}}}{sufijo}"


def clave_tweet(tid, sufijo=""):
    return f"{{tweet:{tid}}}{sufijo}"


def extraer_hashtags(texto):
    return [h.lower() for h in re.findall(r"#\w+", texto)]


# --- Escritura ---

def crear_usuario(cliente, nombre, handle, ciudad):
    uid = cliente.incr("ids:usuario")
    cliente.hset(clave_usuario(uid), mapping={"nombre": nombre, "handle": handle, "ciudad": ciudad})
    cliente.set(f"handle:{handle}", uid)
    return uid


def seguir(cliente, uid, otro):
    """Toca dos usuarios, que pueden estar en nodos distintos: no es atómico."""
    cliente.sadd(clave_usuario(uid, ":siguiendo"), otro)
    cliente.sadd(clave_usuario(otro, ":seguidores"), uid)


def publicar_tweet(cliente, autor, texto, fecha=None):
    """Guarda el tweet y lo copia al timeline de cada seguidor (fan-out en escritura).
    Devuelve el ID y a cuántos timelines llegó."""
    tid = cliente.incr("ids:tweet")
    pipe = cliente.pipeline()
    pipe.hset(clave_tweet(tid), mapping={
        "autor": autor, "texto": texto, "fecha": fecha or int(time.time()), "likes": 0,
    })
    pipe.lpush(clave_usuario(autor, ":tweets"), tid)
    for hashtag in extraer_hashtags(texto):
        pipe.zincrby("tendencias", 1, hashtag)
    pipe.execute()
    return tid, repartir_en_timelines(cliente, autor, tid)


def repartir_en_timelines(cliente, autor, tid):
    seguidores = cliente.smembers(clave_usuario(autor, ":seguidores"))
    pipe = cliente.pipeline()
    for seguidor in seguidores:
        timeline = clave_usuario(seguidor, ":timeline")
        pipe.lpush(timeline, tid)
        pipe.ltrim(timeline, 0, LIMITE_TIMELINE - 1)
    pipe.execute()
    return len(seguidores)


def dar_like(cliente, uid, tid):
    """Devuelve la nueva cantidad de likes, o None si ya le había dado like."""
    likes = cliente.eval(SCRIPT_LIKE, 2, clave_tweet(tid), clave_tweet(tid, ":likes"), uid)
    if likes:
        # El ranking vive en otro slot: se actualiza aparte (no atómico).
        cliente.zincrby("ranking:likes", 1, tid)
    return likes


# --- Lectura ---

def buscar_usuario(cliente, handle):
    uid = cliente.get(f"handle:{handle.lstrip('@')}")
    return int(uid) if uid else None


def obtener_usuario(cliente, uid):
    pipe = cliente.pipeline()
    pipe.hgetall(clave_usuario(uid))
    pipe.scard(clave_usuario(uid, ":seguidores"))
    pipe.scard(clave_usuario(uid, ":siguiendo"))
    pipe.llen(clave_usuario(uid, ":tweets"))
    datos, seguidores, siguiendo, tweets = pipe.execute()
    return {**datos, "id": uid, "seguidores": seguidores, "siguiendo": siguiendo, "tweets": tweets}


def obtener_tweets(cliente, ids):
    """Trae varios tweets (pueden estar repartidos en todos los nodos) con el handle del autor."""
    pipe = cliente.pipeline()
    for tid in ids:
        pipe.hgetall(clave_tweet(tid))
    tweets = [{**datos, "id": int(tid)} for tid, datos in zip(ids, pipe.execute()) if datos]
    pipe = cliente.pipeline()
    for tweet in tweets:
        pipe.hget(clave_usuario(tweet["autor"]), "handle")
    for tweet, handle in zip(tweets, pipe.execute()):
        tweet["handle"] = handle
    return tweets


def obtener_timeline(cliente, uid, cantidad=10):
    ids = cliente.lrange(clave_usuario(uid, ":timeline"), 0, cantidad - 1)
    return obtener_tweets(cliente, ids)


def top_tweets(cliente, cantidad=10):
    ids = cliente.zrevrange("ranking:likes", 0, cantidad - 1)
    return obtener_tweets(cliente, ids)


def tendencias(cliente, cantidad=10):
    return cliente.zrevrange("tendencias", 0, cantidad - 1, withscores=True)


def totales(cliente):
    return int(cliente.get("ids:usuario") or 0), int(cliente.get("ids:tweet") or 0)
