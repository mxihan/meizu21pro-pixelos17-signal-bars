#!/system/bin/sh
# Sourced by the KernelSU module installer.
[ "$KSU" = true ] || abort "This module requires KernelSU."
[ "$API" = 37 ] || abort "This version supports SDK 37 only."
[ "$(getprop ro.product.device)" = meizu21Pro ] || abort "This version supports meizu21Pro only."
[ -d /data/adb/metamodule ] || abort "A mounting metamodule is required."
[ ! -e /data/adb/metamodule/disable ] && [ ! -e /data/adb/metamodule/remove ] || abort "Enable the mounting metamodule first."
[ -f /data/adb/metamodule/metamount.sh ] || abort "The metamodule does not provide filesystem mounting."
sha256sum -c "$MODPATH/baseline.sha256" >/dev/null 2>&1 || abort "ROM overlay hashes differ from the audited PixelOS build. Refusing to replace carrier settings."
set_perm_recursive "$MODPATH" 0 0 0755 0644
set_perm "$MODPATH/post-fs-data.sh" 0 0 0755
set_perm "$MODPATH/action.sh" 0 0 0755
set_perm "$MODPATH/uninstall.sh" 0 0 0755
ui_print "NR: -125 / -115 / -105 / -95 dBm"
ui_print "Wi-Fi: -88 / -77 / -66 / -55 dBm"
ui_print "LTE, IMS and radio mode settings preserved."
ui_print "Reboot to load the two resource overlays."
