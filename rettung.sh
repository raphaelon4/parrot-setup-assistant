#!/bin/bash
# =============================================================================
# Rettung: grafischer Anmeldebildschirm startet nicht (Landung in der Konsole)
#
# Bekannte Ursache: Die SDDM-Themes "KDE-Story" und "sddm_wynn" stammen aus der
# Qt5-Zeit und importieren QtGraphicalEffects. Dieses Modul gibt es in Qt6 nicht
# mehr. Plasma 6 bringt SDDM auf Qt6 mit -> der Greeter kann das Theme nicht
# laden, faellt auf ein Ersatz-Theme zurueck, das ebenfalls scheitert, und es
# erscheint gar kein Anmeldebildschirm.
# =============================================================================
set -uo pipefail

rot=$'\e[31m'; gruen=$'\e[32m'; gelb=$'\e[33m'; fett=$'\e[1m'; aus=$'\e[0m'
nur_pruefen=0
[ "${1:-}" = "--nur-pruefen" ] && nur_pruefen=1

echo "${fett}=============================================${aus}"
echo "${fett}  Parrot Setup-Assistent – Rettung${aus}"
echo "${fett}=============================================${aus}"
echo

# ---------------------------------------------------------------- Diagnose ---
echo "${fett}1) Anmeldedienst (SDDM)${aus}"
systemctl is-enabled sddm 2>/dev/null | sed 's/^/   aktiviert: /'
systemctl is-active  sddm 2>/dev/null | sed 's/^/   laeuft:    /'
echo

echo "${fett}2) Eingestelltes Anmelde-Theme${aus}"
theme_aktuell=""
for f in /etc/sddm.conf /etc/sddm.conf.d/*.conf; do
    [ -f "$f" ] || continue
    t=$(grep -oP '^\s*Current\s*=\s*\K.*' "$f" 2>/dev/null | tail -1)
    [ -n "$t" ] && { theme_aktuell="$t"; echo "   $f  ->  Current=$t"; }
done
[ -z "$theme_aktuell" ] && echo "   kein Theme gesetzt (Standard)"
echo

echo "${fett}3) Qt-Version des Anmeldebildschirms${aus}"
qt_major="?"
if command -v sddm >/dev/null 2>&1; then
    if ldd "$(command -v sddm)" 2>/dev/null | grep -q libQt6Core; then
        qt_major=6
    elif ldd "$(command -v sddm)" 2>/dev/null | grep -q libQt5Core; then
        qt_major=5
    fi
fi
echo "   SDDM laeuft auf Qt$qt_major"
if [ "$qt_major" = "6" ] && [ ! -d /usr/lib/x86_64-linux-gnu/qt6/qml/QtGraphicalEffects ]; then
    echo "   QtGraphicalEffects ist unter Qt6 ${rot}nicht vorhanden${aus} (so gehoert es sich)"
fi
echo

echo "${fett}4) Ist das eingestellte Theme mit Qt6 vertraeglich?${aus}"
theme_defekt=0
if [ -n "$theme_aktuell" ] && [ -d "/usr/share/sddm/themes/$theme_aktuell" ]; then
    if [ "$qt_major" = "6" ] && grep -rqs "QtGraphicalEffects" "/usr/share/sddm/themes/$theme_aktuell"; then
        theme_defekt=1
        echo "   ${rot}NEIN – '$theme_aktuell' importiert QtGraphicalEffects (nur Qt5).${aus}"
        echo "   ${rot}Das ist die Ursache: der Anmeldebildschirm kann nicht laden.${aus}"
    else
        echo "   ${gruen}ja, sieht vertraeglich aus${aus}"
    fi
else
    echo "   Theme-Ordner nicht gefunden – auch das laesst SDDM scheitern."
    [ -n "$theme_aktuell" ] && theme_defekt=1
fi
echo

echo "${fett}5) Grafiktreiber${aus}"
if lsmod | grep -q '^nvidia'; then
    echo "   ${gruen}NVIDIA-Kernelmodul ist geladen${aus}"
elif lspci 2>/dev/null | grep -qi nvidia; then
    echo "   ${gelb}NVIDIA-Karte vorhanden, aber Modul NICHT geladen${aus}"
    dkms status 2>/dev/null | grep -i nvidia | sed 's/^/   DKMS: /' || echo "   DKMS: kein NVIDIA-Modul gebaut"
    sb=$(mokutil --sb-state 2>/dev/null | head -1)
    echo "   Secure Boot: ${sb:-nicht ermittelbar}"
    case "$sb" in *enabled*)
        echo "   ${rot}-> Secure Boot ist an. Das unsignierte Modul wird blockiert.${aus}"
        echo "   ${rot}   Im BIOS/UEFI abschalten oder das Modul per MOK signieren.${aus}" ;;
    esac
else
    echo "   keine NVIDIA-Karte erkannt"
fi
echo

# ------------------------------------------------------------------ Fix ------
if [ "$theme_defekt" -eq 0 ]; then
    echo "${gruen}Das Anmelde-Theme ist nicht die Ursache.${aus}"
    echo "Letzte 25 Zeilen aus dem SDDM-Protokoll:"
    journalctl -b -u sddm --no-pager 2>/dev/null | tail -25
    exit 0
fi

if [ "$nur_pruefen" -eq 1 ]; then
    echo "${gelb}Nur-Pruefen-Modus – es wurde nichts geaendert.${aus}"
    exit 0
fi

echo "${fett}=============================================${aus}"
echo "${fett}  Reparatur${aus}"
echo "${fett}=============================================${aus}"
echo "Das Anmelde-Theme wird auf 'breeze' zurueckgesetzt (Qt6-tauglich,"
echo "gehoert zu Plasma). Deine Desktop-Designs, die Tastatur und die"
echo "Akzentfarbe bleiben unangetastet – nur der Anmeldebildschirm."
echo
read -r -p "Jetzt reparieren? [J/n]: " antwort
case "${antwort,,}" in n|nein) echo "Abgebrochen."; exit 0 ;; esac

ziel="/etc/sddm.conf.d/kde_settings.conf"
[ -f "$ziel" ] || ziel=$(grep -rl '^\s*Current\s*=' /etc/sddm.conf /etc/sddm.conf.d/ 2>/dev/null | head -1)
[ -n "$ziel" ] || ziel="/etc/sddm.conf.d/kde_settings.conf"

echo
echo "-> Sicherung anlegen"
sudo cp -a "$ziel" "$ziel.bak-rettung-$(date +%Y%m%d%H%M%S)" 2>/dev/null || true

echo "-> Theme auf 'breeze' setzen"
if command -v kwriteconfig6 >/dev/null 2>&1; then
    sudo kwriteconfig6 --file "$ziel" --group Theme --key Current breeze
else
    sudo sed -i 's/^\(\s*Current\s*=\).*/\1breeze/' "$ziel"
fi
grep -A2 '^\[Theme\]' "$ziel" | sed 's/^/   /'

echo
echo "-> Anmeldedienst neu starten"
sudo systemctl restart sddm

echo
echo "${gruen}${fett}Fertig.${aus} Der Anmeldebildschirm sollte jetzt erscheinen."
echo "Falls nicht, hier das Protokoll:"
echo "   journalctl -b -u sddm --no-pager | tail -30"
