#!/usr/bin/env bash
# Extra opcional del host para VMware Workstation.
set -euo pipefail
case "${1:-}" in
    -h|--help) echo "Uso: $0 [--apply]"; exit 0 ;;
    --apply|'') ;;
    *) echo "Uso: $0 [--apply]" >&2; exit 2 ;;
esac
(( $# <= 1 )) || exit 2
command -v vmware >/dev/null && command -v vmware-modconfig >/dev/null || {
    echo "Este extra requiere VMware Workstation instalado en el host." >&2
    exit 1
}
source /etc/os-release
kernel=$(uname -r)
case "$ID" in
    debian|ubuntu) install=(apt-get --no-remove install "linux-headers-$kernel" build-essential) ;;
    fedora) install=(dnf install "kernel-devel-$kernel" gcc make perl elfutils-libelf-devel) ;;
    *) echo "Distribución sin receta: $ID" >&2; exit 1 ;;
esac
printf 'Kernel activo: %s\n' "$kernel"
printf '%q ' sudo "${install[@]}"
printf '\nsudo vmware-modconfig --console --install-all\n'
[[ ${1:-} == --apply ]] || exit 0
sudo "${install[@]}"
sudo vmware-modconfig --console --install-all
