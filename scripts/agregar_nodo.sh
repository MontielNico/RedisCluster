#!/usr/bin/env bash
# Escalado en caliente: suma el nodo 7006 como master y le mueve 4096 slots.
# Antes: levantar el nodo con el profile "extra".
# Uso: ./scripts/agregar_nodo.sh [IP:PUERTO de un nodo del cluster]
source "$(dirname "$0")/comun.sh"
cargar_env

NUEVO=$HOST_IP:7006
ENTRADA=${1:-$HOST_IP:7000}

agregar_master() {
  esperar_nodo "$HOST_IP" 7006
  cli --cluster add-node "$NUEVO" "$ENTRADA"
}

mover_slots() {
  local id_nuevo
  esperar_convergencia "$ENTRADA"
  id_nuevo=$(obtener_id "$HOST_IP" 7006)
  cli --cluster reshard "$ENTRADA" --cluster-from all --cluster-to "$id_nuevo" \
    --cluster-slots 4096 --cluster-yes
}

agregar_master
mover_slots
esperar_convergencia "$ENTRADA"

echo
"$(dirname "$0")/estado.sh" "$ENTRADA"
