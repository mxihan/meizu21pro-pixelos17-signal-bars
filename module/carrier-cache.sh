#!/system/bin/sh
# Remove only rebuildable default CarrierConfig bundles. Preserve override and other packages.
clear_platform_carrier_cache() {
    CACHE_DIRECTORY=$1
    [ -d "$CACHE_DIRECTORY" ] || return 0
    for CACHE_FILE in "$CACHE_DIRECTORY"/carrierconfig-com.android.carrierconfig-*.xml; do
        [ -f "$CACHE_FILE" ] || continue
        case "${CACHE_FILE##*/}" in
            carrierconfig-com.android.carrierconfig-override-*) continue ;;
        esac
        rm -f "$CACHE_FILE" || return 1
    done
}
