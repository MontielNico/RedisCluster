# Redis Cluster distribuido

Cluster de Redis con 6 nodos (3 masters y 3 réplicas) repartidos entre dos notebooks con Docker. Cada réplica está en la notebook opuesta a su master.

```
Notebook A                     Notebook B
  7000  master   <-------->    7004  réplica de 7000
  7001  master   <-------->    7005  réplica de 7001
  7002  réplica de 7003 <--->  7003  master
```

## Estructura

```
docker-compose.yml   nodos de Redis (profiles: a, b, extra)
.env.ejemplo         plantilla con la IP de la notebook
config/redis.conf    configuración común de los nodos
scripts/             creación, estado, escalado y reset del cluster (bash, notebook A)
app/                 scripts en Python para la demo
docs/guion_demo.md   pasos de la demo
```

## Requisitos

- Docker con Docker Compose (en Windows, Docker Desktop).
- Python 3.9 o superior, solo en la notebook que corre la app.
- Ambas notebooks en la misma red. Se recomienda el hotspot de un celular: muchas redes WiFi institucionales bloquean el tráfico entre dispositivos.

## 1. Red y firewall

Cada notebook necesita abiertos los puertos 7000-7006 (clientes) y 17000-17006 (bus del cluster).

Windows (PowerShell como administrador):

```powershell
New-NetFirewallRule -DisplayName "Redis Cluster" -Direction Inbound -Protocol TCP -LocalPort 7000-7006,17000-17006 -Action Allow
```

Además, la red WiFi tiene que estar configurada como "Privada".

Linux, solo si `ufw` está activo:

```bash
sudo ufw allow 7000:7006/tcp
sudo ufw allow 17000:17006/tcp
```

## 2. Configurar la IP

En cada notebook, copiar `.env.ejemplo` a `.env` y poner la IP de esa notebook en la red compartida.

- Linux: `ip a`
- Windows: `ipconfig`, la IP del adaptador WiFi (no la de `vEthernet (WSL)`).

```
HOST_IP=192.168.1.10
```

## 3. Levantar los nodos

Notebook A:

```bash
docker compose --profile a up -d
```

Notebook B:

```bash
docker compose --profile b up -d
```

Con Docker Compose v1 el comando es `docker-compose` en lugar de `docker compose`.

Probar la conexión desde A hacia B:

```bash
docker exec redis-7000 redis-cli -h IP_B -p 7003 ping
```

Tiene que responder `PONG`.

## 4. Crear el cluster

Una sola vez, desde la notebook A:

```bash
./scripts/crear_cluster.sh IP_A IP_B
```

Ver el estado en cualquier momento:

```bash
./scripts/estado.sh
```

## 5. Aplicación de prueba

Una red social estilo Twitter (usuarios, seguidores, tweets, likes, timelines y tendencias) guardada en el cluster. El modelo de claves está en `app/red_social.py`.

```bash
python3 -m venv .venv
.venv/bin/pip install -r app/requirements.txt

.venv/bin/python app/cargar_datos.py --nodo IP_A:7000          # genera la red social y muestra el reparto
.venv/bin/python app/consultar.py --nodo IP_A:7000 top         # consultas (usuario, timeline, tweet, top, tendencias)
.venv/bin/python app/actividad.py --nodo IP_A:7000             # usuarios simulados en vivo, muestra el failover
.venv/bin/python app/monitor.py --nodo IP_A:7000               # estado de cada nodo en vivo
```

`cargar_datos.py --limpiar` borra los datos y los vuelve a generar.

En Windows se usa `.venv\Scripts\python` en lugar de `.venv/bin/python`.

La demo completa está en [docs/guion_demo.md](docs/guion_demo.md).

## Plan B: todo en una sola notebook

Si la red falla, se puede correr el cluster completo en una notebook:

```bash
docker compose --profile a --profile b up -d
./scripts/crear_cluster.sh IP IP
```

Usar la IP de la notebook en ambos argumentos.

## Reset

Si cambian las IPs (por ejemplo, otra red WiFi) hay que borrar los datos y volver a crear el cluster, porque cada nodo guarda la topología en su volumen.

Notebook A:

```bash
./scripts/reset.sh
```

Notebook B:

```bash
docker compose --profile b down -v
```
