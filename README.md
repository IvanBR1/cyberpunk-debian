# Cyberpunk Desktop · kit portable

Un punto de entrada para **Niri o Hyprland**, perfiles de hardware separados y
personalización cyberpunk reutilizable. Consolidado a partir de esta instalación;
no copia tu HOME ni requiere las carpetas históricas.

**Los comandos de instalación y desinstalación muestran un plan por defecto.**
Solo `--apply` cambia el equipo. No reinician ni cierran la sesión. Al reemplazar una configuración, el compositor
puede recargarla al detectar cambios; el nuevo arranque de servicios y los ajustes
de backend requieren volver a entrar en la sesión.

## Organización

```text
cyberpunk-portable/
├── environments/          # Niri / Hyprland: configuración funcional y portales
├── hardware/              # generic / vmware: paquetes y compatibilidad exclusiva
├── themes/cyberpunk/      # apariencia común, barras por entorno, fuente y fondo
├── addons/                # office / widgets / clipboard: paquetes optativos
├── packages/             # dependencias comunes de Debian 13
├── scripts/              # composición, estado, sesión y limpieza histórica
├── docs/                 # decisiones, migración, compatibilidad y ejemplos
├── tests/                # portabilidad, restauración y protección de dependencias
├── setup.sh              # plan / instalar / configurar
├── uninstall.sh          # plan / restaurar / limpiar lo administrado
├── doctor.sh             # diagnóstico de lectura
├── export.sh             # paquete sin datos de la máquina
└── versions.json         # revisiones, serie de configuración y SHA256 de fuente
```

## Elegir entorno y equipo

Desde esta carpeta, como usuario normal, sin anteponer sudo:

```bash
# PC físico: plan de Hyprland
./setup.sh --desktop hyprland --profile generic

# VMware: plan de Niri
./setup.sh --desktop niri --profile vmware

# Ambos, detectando VMware automáticamente
./setup.sh --desktop both --profile auto

# Ejecutar la instalación elegida
./setup.sh --desktop both --profile auto --apply
```

`auto` selecciona VMware únicamente si `systemd-detect-virt` identifica `vmware`.
En otros casos selecciona `generic`, sin ajustes VMware. Las máquinas físicas
conservan sus controladores; no se instala automáticamente un driver NVIDIA.

El instalador de paquetes está dirigido a **Debian 13 con systemd**. Hyprland usa
backports oficial, con plantilla validada para **0.55.x**. Niri reutiliza un binario
existente; si falta, compila **v25.08** con Cargo.lock y commit fijado. Para exigir
una compilación usa `--niri-source build`; `--build-jobs 2` limita su paralelismo.
No se añaden sid/testing ni se ejecutan instaladores de dotfiles de Arch.

En otra distribución, instala las dependencias equivalentes con su gestor y usa:

```bash
./setup.sh --desktop hyprland --profile generic --configure-only --apply
```

Ese modo copia configuración y registra la sesión, por lo que puede solicitar
sudo; no instala paquetes, compila Niri ni descarga fuentes. Exige compositor
instalado y versión compatible. No se declara soporte universal para otras distros.

## Tema, complementos y pantalla

```bash
# Solo base funcional, sin los complementos opcionales
./setup.sh --desktop niri --profile generic --theme plain --addons none

# Cyberpunk con LibreOffice y widgets, sin historial del portapapeles
./setup.sh --desktop hyprland --profile generic --addons office,widgets

# Resolución explícita: usa el nombre real obtenido con doctor.sh
./setup.sh --desktop hyprland --profile vmware \
  --resolution 1920x1080@60 --output Virtual-1
```

Tema predeterminado: azul `#009dff`, magenta `#ff00cc`, Hack Nerd Font, fondo
Neon Horizon, transparencias, sombras y blur en Hyprland. Niri mantiene sus
capacidades propias: el tema no añade blur que el compositor no proporciona.
Super+A muestra los widgets; Super+D abre el lanzador; Super+Enter la terminal.
En Hyprland, Super+R cambia ancho de columna y Super+C centra la cinta scrolling.

Complementos predeterminados: `office,widgets,clipboard`.

- **office:** Writer, Calc y `libreoffice-gtk3`, con backend GTK3 para Wayland.
- **widgets:** reloj, calendario, CPU, RAM, uptime y controles MPRIS; sin APIs externas.
- **clipboard:** historial de texto local con cliphist; puede contener información privada.

La pantalla se almacena por separado en
`~/.config/cyberpunk-desktop/hardware/`. `--resolution preserve` conserva las reglas
locales administradas; para Hyprland también puede importar solo las líneas
`monitor =` del antiguo monitors.conf, descartando las variables AQ_.
En una máquina nueva sin reglas utiliza automático. `--resolution auto` descarta
la resolución explícita del nuevo despliegue y vuelve a automático.
No se exportan los nombres ni las resoluciones guardadas de esta máquina.
En Niri 25.08 el fragmento se integra al generar config.kdl: para cambiar el archivo
local de pantalla, vuelve a ejecutar el plan/aplicación; no se presupone soporte de include.

El perfil VMware usa cursor por software en Hyprland para evitar el puntero
invisible de vmwgfx, conservando la aceleración 3D. No se aplica a equipos físicos.

La opción VMware `--vmware-legacy-drm` pertenece exclusivamente al perfil VMware
y Hyprland. No está activada por defecto: véase [hardware](docs/HARDWARE.md).
La RAM no determina ajustes de kernel, caché, swap ni audio.

## Aplicación y respaldos

El nuevo kit guarda recursos independientes en
`~/.local/share/cyberpunk-desktop/{niri,hyprland}` y crea sesiones de acceso
**Niri (Cyberpunk)** / **Hyprland (Cyberpunk)**. Conserva los archivos reemplazados
por primera vez en `~/.local/state/cyberpunk-desktop/backups/` y registra cada ruta
administrada en `manifests/`. Las herramientas compartidas usan un registro propio.

La barra, notificaciones, bloqueo y widgets tienen servicios de usuario ligados
a la sesión. No se habilita una segunda barra global; se registra una máscara
restaurable para waybar.service. No se cambian los archivos globales de foot,
fuzzel, mako o swaylock de otros escritorios. No se modifica PAM.

Las ediciones posteriores al despliegue se detectan: si quieres reemplazarlas,
usa `--overwrite`; también se guardan esas ediciones. Los respaldos originales
permanecen disponibles para la desinstalación. La aplicación registra progreso
por archivo; si falla una dependencia o un paso posterior, no promete revertir
los paquetes ya instalados. Los registros permiten revisar y restaurar archivos.

Por defecto conserva tu gestor de inicio de sesión. En un Debian mínimo sin uno,
puedes elegir `--login-manager greetd`; instala greetd/tuigreet con selector de
sesiones. Si ya existe otro gestor, no lo reemplaza. Nunca habilita autologin.
Tras instalar, guarda tu trabajo y selecciona la sesión correspondiente al entrar.

## Desinstalación controlada

```bash
# Ver el plan: solo archivos de este kit
./uninstall.sh --desktop niri

# Restaurar originales y quitar lo que no existía antes
./uninstall.sh --desktop niri --apply

# Limpiar ambos, sus paquetes exclusivos, respaldos y caché de este kit
./uninstall.sh --desktop both --purge-packages --delete-backups \
  --remove-shared --purge-cache --apply
```

Antes de aplicar, cierra el escritorio seleccionado y entra en GNOME o una TTY.
No basta con cambiar de TTY dejando esa sesión en ejecución.

`--purge-packages` se limita a paquetes instalados exclusivos del entorno.
APT se simula y se cancela si propone eliminar otro paquete o instalar/actualizar
algo. No ejecuta autoremove: Wayland, Xwayland, audio, red, LibreOffice y bibliotecas
compartidas quedan instalados. Un Niri compilado por este kit se elimina como
archivo administrado; un Niri preexistente de otra instalación se conserva.

Los archivos modificados después se conservan por defecto. `--force` permite
restaurar sus originales de todos modos. Sus respaldos no se borran mientras quede
alguna restauración pendiente. `--remove-shared` solo es válido cuando el otro
entorno ya no tiene archivos administrados. Los repositorios de backports se
conservan para poder actualizar paquetes que puedan seguir instalados.

El desinstalador nuevo **no adivina propiedad de archivos antiguos**. Para esas
instalaciones se incluye `scripts/legacy-uninstall.sh`; véase migración.

## Exportar y verificar

```bash
./export.sh
# Llevar dist/cyberpunk-portable-1.0.tar.gz a la otra máquina
# Extraer y ejecutar desde allí:
sha256sum -c SHA256SUMS
./doctor.sh
./setup.sh --desktop niri --profile auto
```

El tar incluye scripts, plantillas, recursos, documentación y pruebas. Excluye
respaldos, cachés, compilaciones, descargas, estado instalado y datos personales.
Incluye SHA256SUMS de los archivos internos. Requiere Internet para instalar
paquetes y obtener fuentes; no es un repositorio APT ni instalador offline.

Pruebas: `python3 -m unittest discover -s tests -v`.

Consulta [la migración](docs/MIGRATION.md), [las decisiones consolidadas](docs/DECISIONS.md)
y [los ejemplos](docs/EXAMPLES.md).

## Controles opcionales para Hyprland

```bash
./setup.sh --desktop hyprland --profile generic --addons office,widgets,clipboard,controls --apply
```

`controls` añade acceso a pantallas, brillo y audio, sin servicios adicionales ni
cambios a GNOME. Los complementos indicados reemplazan la selección completa;
conserva en la lista los que quieras usar.

- Teclas de brillo: pasos de 5%, con mínimo distinto de cero.
- Brillo en la barra: rueda para ajustar el panel interno.
- Volumen en la barra: rueda para ajustar, clic para abrir pavucontrol,
  clic derecho para silenciar. Las teclas multimedia siguen disponibles.
- Super+S: dispositivos, volumen y entradas/salidas de audio (pavucontrol).
- Super+P o DISP en la barra: ordenar pantallas, resolución, escala y rotación
  (nwg-displays). Aplica y guarda para persistir entre sesiones.
- Tecla de silencio del micrófono: alternar entrada predeterminada.

nwg-displays guarda en `~/.config/hypr/monitors.conf`,
ya incluido por el compositor al activar `controls`. Funciona también al abrir
Pantallas desde el lanzador de aplicaciones. No es necesario copiar reglas.
Al activar el complemento se prioriza este archivo sobre el fragmento antiguo.
El kit conserva esas reglas con `--resolution preserve` (predeterminado).
Como son ediciones locales, una reinstalación puede pedir `--overwrite`: revisa
el plan antes de usarlo; esa opción también respalda las ediciones.
Las asignaciones de workspaces que nwg-displays pudiera escribir en su archivo
propio no se incluyen automáticamente: este complemento gestiona las pantallas.

El brillo por backlight corresponde al panel del portátil. En monitores externos
se usa normalmente el menú físico del monitor; DDC/CI requiere soporte específico
y no se activa aquí. En equipos sin backlight la barra no muestra ese módulo.

Configuración de GNOME requiere una sesión GNOME; sus pantallas dependen de
Mutter. No se cambia XDG_CURRENT_DESKTOP para forzar su apertura en Hyprland.
Se usan herramientas específicas que controlan la sesión actual y GNOME sigue
conservando sus preferencias propias.

### Abrir Foot desde el lanzador

El kit registra una entrada local de Foot que selecciona la configuración del
entorno activo (Hyprland o Niri), igual que Super+Enter. Fuera de esos entornos
abre Foot con sus preferencias habituales. No modifica el archivo de aplicación
del sistema. La entrada pertenece a los recursos compartidos y se restaura con
`--remove-shared` al desinstalar el último entorno. Ejecutar `/usr/bin/foot`
directamente sigue utilizando los valores normales de Foot.

## Bluetooth: suspensión USB optativa

Si has comprobado cortes de audio relacionados con ahorro USB, el kit incluye
la parte USB de `corregir-audio-bluetooth.sh`, sin MAC personales y sin modificar
códecs, quantum, manos libres o emparejamientos. Detecta los dispositivos USB
ancestros de `/sys/class/bluetooth/hci*`; no desactiva ahorro para hubs ni todos
los periféricos. No se aplica automáticamente al instalar un escritorio.

```bash
./bluetooth-usb.sh                         # diagnóstico y plan, sin sudo
./bluetooth-usb.sh --apply                 # temporal, como el script original
./bluetooth-usb.sh --persistent --apply    # también conservar tras reiniciar
./bluetooth-usb.sh --restore               # plan de reversión
./bluetooth-usb.sh --restore --apply       # restaurar valores y regla originales
```

Ejecuta como usuario normal; solicita sudo para escribir en sysfs y udev.
El modo persistente crea una regla por fabricante/producto del adaptador detectado
en el equipo de destino; no exporta IDs de esta máquina al kit. Puede afectar
otros adaptadores del mismo modelo. Puede aumentar consumo de batería; no es
un aumento de potencia de radio ni una garantía contra cualquier corte Bluetooth.

Respaldos y manifiesto: `~/.local/state/cyberpunk-desktop`, registro `usb-power`.
La reversión USB es independiente de la desinstalación de Niri/Hyprland: ejecuta
`--restore --apply` si quieres retirarla. Si el adaptador está desconectado al
restaurar, se retira la regla pero se conserva su respaldo temporal para reintentar.
No se reinician servicios, no se descarga `btusb` ni se borran parejas.

### Teclas multimedia

Hyprland incluye las teclas estándar Reproducir/Pausar, Pausa, Detener,
Siguiente y Anterior mediante `playerctl` y MPRIS. Funcionan en reproductores
compatibles como Spotify; las funciones disponibles dependen del reproductor.
También funcionan con la pantalla bloqueada, igual que las teclas de volumen.
Según el teclado puede ser necesario mantener Fn.
