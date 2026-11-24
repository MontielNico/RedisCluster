#!/usr/bin/env bash
# Crea el cluster con una topología fija:
#   masters:  A:7000  A:7001  B:7003
#   réplicas: B:7004 -> A:7000   B:7005 -> A:7001   A:7002 -> B:7003
# Cada réplica queda en la notebook opuesta a su master.
# Uso: ./scripts/crear_cluster.sh IP_A IP_B
source "$(dirname "$0")/comun.sh"

if [[ $# -ne 2 ]]; then
  echo "Uso: $0 IP_A IP_B"
  exit 1
fi
IP_A=$1
IP_B=$2

esperar_nodos() {
  for puerto in 7000 7001 7002; do esperar_nodo "$IP_A" "$puerto"; done
  for puerto in 7003 7004 7005; do esperar_nodo "$IP_B" "$puerto"; done
}

crear_masters() {
  cli --cluster create "$IP_A:7000" "$IP_A:7001" "$IP_B:7003" \
    --cluster-replicas 0 --cluster-yes
}

# Uso: agregar_replica IP PUERTO IP_MASTER PUERTO_MASTER
agregar_replica() {
  local id_master
  id_master=$(obtener_id "$3" "$4")
  esperar_convergencia "$3:$4"
  echo ">> $1:$2 como réplica de $3:$4"
  cli --cluster add-node "$1:$2" "$3:$4" --cluster-slave --cluster-master-id "$id_master"
}

# Espera a que el cambio de rol de las réplicas se propague por gossip.
esperar_replicas() {
  until [[ $(cli -h "$IP_A" -p 7000 cluster nodes | grep -c slave) -ge 3 ]]; do
    sleep 1
  done
}

esperar_nodos
crear_masters
agregar_replica "$IP_B" 7004 "$IP_A" 7000
agregar_replica "$IP_B" 7005 "$IP_A" 7001
agregar_replica "$IP_A" 7002 "$IP_B" 7003
esperar_replicas

echo
"$(dirname "$0")/estado.sh" "$IP_A:7000"
