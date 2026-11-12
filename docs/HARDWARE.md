# Hardware separado de los escritorios

## Generic

No instala VMware Tools, no exporta AQ_NO_ATOMIC ni fuerza Virtual-1, 1920×1080,
dispositivos DRM o drivers propietarios. Detectar una GPU es distinto de configurar
su controlador. En un equipo físico el controlador debe estar correctamente instalado.
`auto` usa generic también para virtualizadores distintos de VMware; no pretende
ofrecer un perfil específico para VirtualBox/KVM.

## VMware

Incluye `open-vm-tools` y `open-vm-tools-desktop`; habilita el servicio del sistema
sin reiniciarlo en medio de tu sesión. La aceleración 3D y la memoria de vídeo
se ajustan en el hipervisor. No se añade vmware-user a ciegas como autostart Wayland:
las capacidades de integración dependen del compositor y de VMware Tools.

Pantalla, tematización y workaround gráfico son opciones distintas:

1. Por defecto el perfil no fija resolución; respeta la política local de pantalla.
2. `--resolution ANCHOxALTO@HZ --output SALIDA` crea una regla explícita por máquina.
3. `--vmware-legacy-drm` exporta AQ_NO_ATOMIC=1 en el launcher de Hyprland antes de
   inicializar Aquamarine. Exige perfil vmware y Hyprland. Requiere sesión nueva.

Este último ajuste se preparó porque en esta VM aparecía:
`atomic drm request: failed to commit: Invalid argument` y el compositor volvía
a 1280×800 tras solicitar 1920×1080. La sesión inspeccionada seguía en 1280×800;
**no se confirmó que el workaround lo resolviera**. No se convierte en valor
predeterminado ni se aplica a Niri. Upstream desaconseja desactivar atomic de modo
general. Para retirarlo vuelve a generar el perfil sin esa opción y entra de nuevo.

Ejemplo optativo y específico, primero solo plan:

```bash
./setup.sh --desktop hyprland --profile vmware \
  --resolution 1920x1080@60 --output Virtual-1 --vmware-legacy-drm
```

No se habilitan automáticamente AQ_NO_MODIFIERS, render por software, cambios de
kernel, opciones de GRUB, swappiness ni límites de RAM. Blur y resolución pueden
cargar la GPU; baja blur antes de atribuir tirones a memoria. Los problemas de
audio se diagnostican por separado, sin convertirlos en cambios de render.

Fuentes:
- https://wiki.hypr.land/0.55.0/Hypr-Ecosystem/aquamarine/
- https://wiki.hypr.land/0.54.0/Configuring/Monitors/

## Puntero invisible en VMware/Hyprland

El perfil VMware fuerza `cursor.no_hardware_cursors = 1`: dibuja el puntero por
software sin desactivar la aceleración 3D de las ventanas. No se aplica al perfil
generic ni a Niri. Se puede recargar durante la sesión. En esta VM se verificó
que hardwareCursorsInUse pasó a false y la pantalla permaneció a 1920×1080.
La comprobación visual de que el puntero volvió corresponde al usuario.

En esta revisión también se observó la sesión en modo DRM legacy a 1920×1080,
a diferencia de la inspección anterior; el ajuste sigue siendo específico de
esta VM y no se convierte en un valor universal.

Referencia del mismo síntoma en vmwgfx:
https://github.com/omacom/omarchy/issues/7918
