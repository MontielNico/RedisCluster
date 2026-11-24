#!/usr/bin/env bash
# Funciones compartidas por los scripts. No se ejecuta directamente.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cargar_env() {
  if [[ ! -f "$RAIZ/.env" ]]; then
    echo "Falta $RAIZ/.env (copiar .env.ejemplo y completar HOST_IP)"
    exit 1
  fi
  source "$RAIZ/.env"
}

# Usa docker compose (v2) o docker-compose (v1), el que esté instalado.
compose() {
  if docker compose version >/dev/null 2>&1; then
    docker compose --project-directory "$RAIZ" "$@"
  else
    (cd "$RAIZ" && docker-compose "$@")
  fi
}

# Ejecuta redis-cli dentro de cualquier contenedor redis local que esté corriendo.
cli() {
  local contenedor
  contenedor=$(docker ps --filter "name=^redis-70" --filter status=running --format '{{.Names}}' | head -n1)
  if [[ -z "$contenedor" ]]; then
    echo "No hay contenedores redis corriendo en esta notebook" >&2
    exit 1
  fi
  docker exec -i "$contenedor" redis-cli "$@"
}

# Uso: esperar_nodo IP PUERTO
esperar_nodo() {
  until cli -h "$1" -p "$2" ping 2>/dev/null | grep -q PONG; do
    echo "Esperando a $1:$2 ..."
    sleep 1
  done
}

# Espera a que todos los nodos coincidan en la configuración del cluster.
# Uso: esperar_convergencia IP:PUERTO
esperar_convergencia() {
  until cli --cluster check "$1" >/dev/null 2>&1; do
    sleep 1
  done
}

# Uso: obtener_id IP PUERTO
obtener_id() {
  cli -h "$1" -p "$2" cluster myid | tr -d '\r'
}
