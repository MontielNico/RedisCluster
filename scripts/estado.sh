#!/usr/bin/env bash
# Muestra el estado del cluster visto desde un nodo.
# Uso: ./scripts/estado.sh [IP:PUERTO]   (por defecto HOST_IP:7000)
source "$(dirname "$0")/comun.sh"
cargar_env

NODO=${1:-$HOST_IP:7000}
IP=${NODO%:*}
PUERTO=${NODO#*:}

mostrar_info() {
  cli -h "$IP" -p "$PUERTO" cluster info | tr -d '\r' \
    | grep -E '^cluster_(state|size|known_nodes)'
}

# Una fila por nodo: id corto, dirección, flags, master (si es réplica) y slots.
mostrar_nodos() {
  printf '\n%-9s %-21s %-20s %-9s %s\n' ID NODO FLAGS MASTER SLOTS
  cli -h "$IP" -p "$PUERTO" cluster nodes | tr -d '\r' | awk '{
    split($2, dir, "@")
    master = ($4 == "-") ? "" : substr($4, 1, 8)
    slots = ""
    for (i = 9; i <= NF; i++) slots = slots " " $i
    printf "%-9s %-21s %-20s %-9s%s\n", substr($1, 1, 8), dir[1], $3, master, slots
  }' | sort -k2
}

mostrar_info
mostrar_nodos
