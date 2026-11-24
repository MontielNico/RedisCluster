#!/usr/bin/env bash
# Baja los contenedores de esta notebook y borra sus datos (incluido nodes.conf).
# Necesario si cambian las IPs o para volver a crear el cluster desde cero.
source "$(dirname "$0")/comun.sh"
cargar_env

compose --profile a --profile b --profile extra down -v
