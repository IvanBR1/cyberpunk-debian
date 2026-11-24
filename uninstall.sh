#!/usr/bin/env bash
set -Eeuo pipefail
BASE=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
for ((i=1;i<=$#;i++)); do
    next=$((i+1))
    if [[ ${!i} == --desktop=driftwm || ( ${!i} == --desktop && ${!next:-} == driftwm ) ]]; then
        exec python3 "$BASE/scripts/drift_profile.py" uninstall "$@"
    fi
done
exec python3 "$BASE/scripts/manage.py" uninstall "$@"
