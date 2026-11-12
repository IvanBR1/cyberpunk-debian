# Experiencia consolidada

| Situación observada | Decisión establecida |
| --- | --- |
| GNOME activo aunque Niri estaba instalado | Registrar sesiones en /usr/share/wayland-sessions y nombrarlas claramente |
| Dos barras por exec y servicio global | Un inicio por rol, lock y servicios ligados al ciclo de sesión; máscara restaurable para waybar.service |
| Teclado inicial US | latam por defecto, configurable por parámetro |
| LibreOffice sin plugin GTK3 y Niri sin satellite | Complemento office incluye GTK3 y selecciona ese backend; no confundir esto con soporte X11 completo |
| Aviso de guiutils | Hyprland incluye hyprland-guiutils en su lista de paquetes |
| Rutas ~ dentro de opciones no se expandían | Generar rutas para el usuario de destino y usar un launcher común |
| Bloqueo oscuro confundido con fallo | Indicador siempre visible, distribución, Caps Lock e instrucciones; conservar autenticación PAM del sistema |
| Se cambió PAM por un diagnóstico insuficiente | No repetir ese cambio automáticamente ni afirmar que era necesario |
| Animaciones desactivadas por tirones de audio | Animaciones activas; audio, CPU, RAM y GPU se diagnostican por separado |
| Cambiar tema reseteaba pantalla | Reglas de pantalla por máquina fuera del tema |
| VMware rechazaba modos DRM | Workaround opcional y marcado pendiente de confirmar, no una regla universal |
| Riesgo de desinstalar dependencias comunes | Manifiestos de archivos propios y lista exclusiva de paquetes con simulación APT obligatoria |
| Se quiere mover a otra máquina | Plantillas sin HOME de origen, sin respaldos/export de estado; detección de hardware al destino |

La instalación de Niri no promete compatibilidad X11 completa. Para aplicaciones
exclusivamente X11 sigue haciendo falta xwayland-satellite compatible con Niri
25.08 o posterior. Los repositorios consultados no lo ofrecen; este kit no lo
compila silenciosamente ni pone un DISPLAY fijo. LibreOffice usa GTK3/Wayland.

Niri 25.08 y Hyprland 0.55.x son las versiones de referencia de esta experiencia.
El validador de Hyprland rechaza otras series para no instalarles sintaxis antigua
por accidente. Las dependencias de Debian pueden recibir actualizaciones;
versions.json no convierte APT en un snapshot reproducible byte por byte.

Referencias:
- https://niri-wm.github.io/niri/Important-Software.html
- https://niri-wm.github.io/niri/Getting-Started.html
- https://packages.debian.org/trixie/libreoffice-gtk3
- https://packages.debian.org/trixie-backports/hyprland
- https://github.com/HyDE-Project/HyDE
- https://github.com/end-4/dots-hyprland
- https://github.com/caelestia-dots/shell

El wallpaper y widgets del tema son implementaciones propias. Los proyectos de
rice se utilizaron como referencia visual; no se ejecutan sus instaladores.
Se incluye la licencia upstream de los pequeños recursos de sesión de Niri.
