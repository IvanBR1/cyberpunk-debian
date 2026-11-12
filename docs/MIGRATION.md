# Migración de las carpetas históricas

El kit nuevo no depende de `cyberpunk-niri-legacy` ni `cyberpunk-hyprland-legacy`. Estas se
conservaron en la máquina de origen para poder revisar o revertir el trabajo;
**no se incluyen en la exportación**. El kit está preparado y verificado, pero
no se ha aplicado sobre tu sesión actual.

1. Desde cyberpunk-portable ejecuta `./doctor.sh`.
2. Elige entorno, perfil y complementos. Ejecuta setup.sh sin --apply y revisa el plan.
3. Ejecuta el mismo comando con --apply. Usará binarios Niri preexistentes si hay
   uno, pero no adoptará su propiedad ni los borrará al desinstalar.
4. El despliegue respalda niri/config.kdl y/o hypr/hyprland.conf si existían. Conserva
   los archivos de herramientas globales anteriores y usa sus propios recursos.
5. Guarda tu trabajo, cierra sesión y selecciona el nombre acabado en (Cyberpunk).
6. Tras comprobarlo, decide si deseas retirar los proyectos históricos.

No ejecutes el desinstalador histórico sobre el entorno después de aplicar el
nuevo: no conoce sus manifiestos y podría borrar la nueva configuración principal.
Para una limpieza histórica completa, hazla **antes** de aplicar el kit nuevo,
desde GNOME/TTY, o revisa su plan archivo por archivo. El nuevo no borra los
respaldos antiguos por asociación de nombres. Su limpieza es una acción separada.

`scripts/legacy-uninstall.sh niri|hyprland|both` es la herramienta histórica
incluida para revisión. Sin --apply no modifica nada. Con --delete-projects puede
borrar las carpetas originales y sus respaldos; es irreversible. No forma parte
del flujo normal de instalación/desinstalación del nuevo kit.

El cambio PAM aplicado anteriormente puede seguir en /etc/pam.d/swaylock. Este
kit no lo revierte ni lo vuelve a editar: conservar las políticas del equipo es
más seguro que deducir el archivo original al importar una configuración.
