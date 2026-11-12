# Recetas

Todos los comandos muestran primero un plan. Añade --apply para ejecutarlos.

```bash
# Portátil físico, Niri y tema cyberpunk
./setup.sh --desktop niri --profile generic

# Físico, Hyprland con widgets y LibreOffice; sin historial del portapapeles
./setup.sh --desktop hyprland --profile generic --addons office,widgets

# VMware, ambos escritorios, automático sin workarounds forzados
./setup.sh --desktop both --profile vmware

# VMware con el workaround DRM optativo y una resolución de esa VM
./setup.sh --desktop hyprland --profile vmware \
  --vmware-legacy-drm --resolution 1920x1080@60 --output Virtual-1

# Cambiar de equipo: no arrastrar nombres de salida ni resolución anterior
./setup.sh --desktop both --profile auto --resolution auto

# Debian mínimo sin gestor de acceso: selector greetd (no autologin)
./setup.sh --desktop niri --profile auto --login-manager greetd

# Usar paquetes ya preparados en otra distribución compatible
./setup.sh --desktop hyprland --profile generic --configure-only

# Base funcional sin widgets ni personalización neón
./setup.sh --desktop niri --profile generic --theme plain --addons none

# Desinstalar solo Hyprland dejando Niri y los recursos comunes
./uninstall.sh --desktop hyprland --purge-packages --delete-backups

# Diagnóstico; no escribe configuración
./doctor.sh

# Exportar sin caché, respaldos ni datos personales
./export.sh --output ~/cyberpunk-portable.tar.gz
```

En el destino, extrae el archivo, entra en cyberpunk-portable, verifica
`sha256sum -c SHA256SUMS` y ejecuta el comando apropiado para ese equipo.
Los paquetes se descargan desde sus repositorios; no se exporta el sistema instalado.
