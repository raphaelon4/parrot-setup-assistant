#!/bin/bash
# =============================================================================
# Diagnose: nach dem Neustart erscheint kein grafischer Anmeldebildschirm
#
# Ermittelt erst die Fakten und benennt dann die Ursache. Es wird NICHTS
# veraendert, solange nicht ausdruecklich zugestimmt wird.
# =============================================================================
set -uo pipefail

rot=$'\e[31m'; gruen=$'\e[32m'; gelb=$'\e[33m'; fett=$'\e[1m'; aus=$'\e[0m'
befund=""
merke() { befund="${befund}$1"$'\n'; }

echo "${fett}==================================================${aus}"
echo "${fett}  Kein Anmeldebildschirm – Diagnose${aus}"
echo "${fett}==================================================${aus}"
echo

# ------------------------------------------------------------- 1) Zielzustand
echo "${fett}1) Startziel des Systems${aus}"
ziel=$(systemctl get-default 2>/dev/null)
echo "   $ziel"
if [ "$ziel" != "graphical.target" ]; then
    echo "   ${rot}Das System startet absichtlich OHNE Grafik.${aus}"
    merke "URSACHE: Startziel steht auf '$ziel' statt graphical.target."
    merke "  FIX: sudo systemctl set-default graphical.target && sudo reboot"
fi
echo

# --------------------------------------------------- 2) Welcher Anmeldedienst
echo "${fett}2) Anmeldedienst${aus}"
konfiguriert=$(cat /etc/X11/default-display-manager 2>/dev/null)
echo "   eingetragen: ${konfiguriert:-keiner}"
aktiver_dm=""
for dm in lightdm sddm gdm3 lxdm; do
    dpkg -l "$dm" >/dev/null 2>&1 || continue
    en=$(systemctl is-enabled "$dm" 2>/dev/null)
    ac=$(systemctl is-active  "$dm" 2>/dev/null)
    printf "   %-9s enabled=%-9s active=%s\n" "$dm" "$en" "$ac"
    [ "$ac" = "active" ] && aktiver_dm="$dm"
    [ -z "$aktiver_dm" ] && [ "$en" = "enabled" ] && aktiver_dm="$dm"
done
if [ -z "$aktiver_dm" ]; then
    echo "   ${rot}Kein Anmeldedienst laeuft oder ist aktiviert.${aus}"
    basis=$(basename "${konfiguriert:-lightdm}")
    merke "URSACHE: Anmeldedienst '$basis' ist nicht aktiv."
    merke "  FIX: sudo systemctl enable --now $basis"
fi
echo

# ------------------------------------------------- 3) Warum scheitert er?
if [ -n "$aktiver_dm" ]; then
    echo "${fett}3) Protokoll von $aktiver_dm (letzte Fehler)${aus}"
    journalctl -b -u "$aktiver_dm" -p warning --no-pager 2>/dev/null | tail -12 | sed 's/^/   /'
    [ -z "$(journalctl -b -u "$aktiver_dm" -p warning --no-pager 2>/dev/null)" ] && echo "   keine Warnungen/Fehler"
    echo
fi

# ---------------------------------------------------------- 4) Grafiktreiber
echo "${fett}4) Grafiktreiber${aus}"
hat_nvidia=0
lspci 2>/dev/null | grep -qi 'nvidia' && hat_nvidia=1
if [ "$hat_nvidia" -eq 1 ]; then
    echo "   NVIDIA-Karte vorhanden"
    if lsmod | grep -q '^nvidia'; then
        echo "   ${gruen}Kernelmodul 'nvidia' ist geladen${aus}"
    else
        echo "   ${rot}Kernelmodul 'nvidia' ist NICHT geladen${aus}"
        merke "URSACHE (wahrscheinlich): NVIDIA-Treiber installiert, Modul laedt nicht."

        echo "   --- DKMS ---"
        dkms status 2>/dev/null | sed 's/^/     /' | head -5
        dkms status 2>/dev/null | grep -qi nvidia || echo "     kein NVIDIA-Modul gebaut"

        sb=$(mokutil --sb-state 2>/dev/null | head -1)
        echo "   --- Secure Boot: ${sb:-nicht ermittelbar} ---"
        case "$sb" in *[Ee]nabled*)
            echo "     ${rot}Secure Boot blockiert das unsignierte Modul.${aus}"
            merke "  -> Secure Boot ist AN. Im BIOS/UEFI abschalten, dann neu starten." ;;
        esac

        log=$(ls -t /var/lib/dkms/nvidia/*/build/make.log 2>/dev/null | head -1)
        if [ -n "$log" ]; then
            echo "   --- Bau-Protokoll (letzte Fehler) ---"
            grep -iE 'error|fehler' "$log" 2>/dev/null | tail -5 | sed 's/^/     /'
        fi
        echo "   --- ist nouveau blockiert? ---"
        grep -rhs 'nouveau' /etc/modprobe.d/ 2>/dev/null | head -3 | sed 's/^/     /'
        merke "  FIX (Desktop sofort zurueck): ./rettung.sh --nvidia-zurueck"
    fi
else
    echo "   keine NVIDIA-Karte"
    lsmod | grep -qE '^amdgpu|^i915|^nouveau' && echo "   ${gruen}freier Treiber geladen${aus}"
fi
echo

# ------------------------------------------------ 5) Xorg-Fehler (falls X11)
echo "${fett}5) Letzte Xorg-Fehler${aus}"
xlog=$(ls -t /var/log/Xorg.0.log ~/.local/share/xorg/Xorg.0.log 2>/dev/null | head -1)
if [ -n "$xlog" ]; then
    grep -E '^\[.*\] \(EE\)' "$xlog" 2>/dev/null | tail -8 | sed 's/^/   /'
    grep -qE '^\[.*\] \(EE\)' "$xlog" 2>/dev/null || echo "   keine (EE)-Fehler"
else
    echo "   kein Xorg-Protokoll gefunden (Wayland-Sitzung oder X nie gestartet)"
fi
echo

# ----------------------------------------------------------------- Befund ---
echo "${fett}==================================================${aus}"
if [ -z "$befund" ]; then
    echo "${gelb}Keine eindeutige Ursache gefunden.${aus}"
    echo "Bitte diese Ausgabe abfotografieren und weitergeben:"
    echo
    journalctl -b -p err --no-pager 2>/dev/null | tail -20
else
    echo "${fett}BEFUND${aus}"
    echo "$befund"
fi
echo "${fett}==================================================${aus}"

# ---------------------------- Desktop-Designs auf Standard zuruecksetzen -----
# Fuer den Fall: Anmeldung klappt, danach schwarzer Bildschirm. Dann startet
# die Plasma-Sitzung nicht. Haeufigste Ursache sind alte Plasma-5-Designs
# (Desktop-Theme, Splash, Fensterdekoration), an denen plasmashell scheitert.
# Das Tastaturlayout bleibt dabei ausdruecklich erhalten.
if [ "${1:-}" = "--desktop-standard" ]; then
    echo
    echo "${fett}Desktop-Designs auf den Plasma-Standard zuruecksetzen${aus}"
    echo "Betroffen: Desktop-Theme, Ladebildschirm, Symbole, Fensterrahmen."
    echo "${gruen}Dein Tastaturlayout bleibt unveraendert.${aus}"
    echo

    kw() {
        kwriteconfig6 --file "$1" --group "$2" --key "$3" "$4" 2>/dev/null \
        || kwriteconfig5 --file "$1" --group "$2" --key "$3" "$4" 2>/dev/null
        echo "   $1 [$2] $3 = $4"
    }

    for f in plasmarc ksplashrc kdeglobals kwinrc; do
        [ -f "$HOME/.config/$f" ] && cp -n "$HOME/.config/$f" "$HOME/.config/$f.bak-rettung" 2>/dev/null
    done
    echo "   (Sicherungen als *.bak-rettung abgelegt)"
    echo

    kw plasmarc   Theme                     name    default
    kw ksplashrc  KSplash                   Engine  none
    kw ksplashrc  KSplash                   Theme   None
    kw kdeglobals Icons                     Theme   breeze
    kw kwinrc     org.kde.kdecoration2      library org.kde.breeze
    kw kwinrc     org.kde.kdecoration2      theme   Breeze
    kw kwinrc     org.kde.kdecoration3      library org.kde.breeze
    kw kwinrc     org.kde.kdecoration3      theme   Breeze

    echo
    echo "${gruen}${fett}Fertig.${aus} Jetzt neu starten:"
    echo "   sudo reboot"
    echo
    echo "Kommt der Desktop danach hoch, lag es an den Designs."
    echo "Bleibt es schwarz, lag es woanders – dann melde dich nochmal."
    exit 0
fi

# ------------------------------------------- Optionaler NVIDIA-Rueckbau -----
if [ "${1:-}" = "--nvidia-zurueck" ]; then
    echo
    echo "${gelb}${fett}NVIDIA-Treiber entfernen und auf den freien Treiber zurueck${aus}"
    echo "Danach hast du wieder einen Desktop – ohne die proprietaeren"
    echo "NVIDIA-Funktionen. Der Treiber laesst sich spaeter neu einrichten,"
    echo "sobald Secure Boot aus ist."
    echo
    read -r -p "Wirklich entfernen? [j/N]: " a
    case "${a,,}" in j|ja)
        sudo apt-get remove --purge -y 'nvidia-*' 'libnvidia-*' 2>/dev/null
        sudo apt-get autoremove -y
        sudo rm -f /etc/modprobe.d/nvidia*.conf
        sudo update-initramfs -u
        echo
        echo "${gruen}Fertig. Jetzt neu starten: sudo reboot${aus}" ;;
    *) echo "Abgebrochen." ;;
    esac
fi
