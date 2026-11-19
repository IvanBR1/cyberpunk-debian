#!/usr/bin/env bash
set -euo pipefail
source /etc/os-release
if [[ $ID != ubuntu && ${1:-} != --help ]]; then
    echo "Este instalador requiere ubuntu. Sistema detectado: $ID" >&2
    exit 1
fi
exec "$(dirname -- "$0")/../setup.sh" "$@"
