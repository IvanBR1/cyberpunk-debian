#!/usr/bin/env bash
set -euo pipefail
source /etc/os-release
if [[ $ID != fedora && ${1:-} != --help ]]; then
    echo "Este instalador requiere fedora. Sistema detectado: $ID" >&2
    exit 1
fi
exec "$(dirname -- "$0")/../setup.sh" "$@"
