#!/bin/bash
# =============================================================================
# PARROT INSTALLER  –  Discord & AnyDesk
# =============================================================================
# Installiert Discord und AnyDesk und legt für beide ein Symbol auf dem
# Desktop an. Ein Aufruf, einmal das Passwort – danach läuft alles allein.
#
#   ./discord-anydesk-installer.sh
#
# Optionen:  --nur-discord   --nur-anydesk   --ohne-symbole   --help
# =============================================================================
set -euo pipefail

rot=$'\e[31m'; gruen=$'\e[32m'; gelb=$'\e[33m'; blau=$'\e[36m'; fett=$'\e[1m'; aus=$'\e[0m'

WILL_DISCORD=1
WILL_ANYDESK=1
WILL_SYMBOLE=1

for arg in "$@"; do
    case "$arg" in
        --nur-discord)  WILL_ANYDESK=0 ;;
        --nur-anydesk)  WILL_DISCORD=0 ;;
        --ohne-symbole) WILL_SYMBOLE=0 ;;
        -h|--help)
            cat <<'HILFE'
Parrot Installer – Discord & AnyDesk

  ./discord-anydesk-installer.sh              Beides installieren + Desktop-Symbole
  ./discord-anydesk-installer.sh --nur-discord
  ./discord-anydesk-installer.sh --nur-anydesk
  ./discord-anydesk-installer.sh --ohne-symbole   Nur installieren, kein Desktop-Symbol

Das Passwort wird genau einmal abgefragt (von sudo selbst).
HILFE
            exit 0 ;;
        *)
            echo "${rot}Unbekannte Option: $arg${aus}  (--help zeigt die Hilfe)"
            exit 1 ;;
    esac
done

# --- Ausgabe -----------------------------------------------------------------
SCHRITT_NR=0
SCHRITTE_GESAMT=$(( 2 + WILL_DISCORD + WILL_ANYDESK + WILL_SYMBOLE ))

schritt()  { SCHRITT_NR=$((SCHRITT_NR+1)); printf '\n%s[%d/%d] %s%s\n' "$blau$fett" "$SCHRITT_NR" "$SCHRITTE_GESAMT" "$1" "$aus"; }
info()     { printf '      %s\n' "$1"; }
ok()       { printf '      %s✔ %s%s\n' "$gruen" "$1" "$aus"; }
warnung()  { printf '      %s! %s%s\n' "$gelb" "$1" "$aus"; }
fehler()   { printf '      %s✘ %s%s\n' "$rot" "$1" "$aus"; }

# --- Aufräumen ---------------------------------------------------------------
TMP=""
KEEPALIVE_PID=""
aufraeumen() {
    [ -n "$KEEPALIVE_PID" ] && kill "$KEEPALIVE_PID" 2>/dev/null || true
    [ -n "$TMP" ] && rm -rf "$TMP" 2>/dev/null || true
}
trap aufraeumen EXIT

TMP="$(mktemp -d)"
chmod 755 "$TMP"   # der Zielbenutzer muss die Dateien darin lesen können

# =============================================================================
# 1. Wer bekommt die Desktop-Symbole?
# =============================================================================
# Der Installer funktioniert in beide Richtungen: normal gestartet (dann holt er
# sich sudo selbst) oder mit sudo gestartet (dann muss er den echten Benutzer
# hinter SUDO_USER finden – sonst landen die Symbole auf dem Desktop von root,
# den niemand je zu sehen bekommt).
if [ "$(id -u)" -eq 0 ]; then
    ZIEL_USER="${SUDO_USER:-}"
    [ -z "$ZIEL_USER" ] && ZIEL_USER="$(logname 2>/dev/null || true)"
    if [ -z "$ZIEL_USER" ] || [ "$ZIEL_USER" = "root" ]; then
        ZIEL_USER="$(awk -F: '$3>=1000 && $3<65534 {print $1; exit}' /etc/passwd || true)"
    fi
else
    ZIEL_USER="$(id -un)"
fi

if [ -z "$ZIEL_USER" ]; then
    echo "${rot}Kein normaler Benutzer gefunden – ohne den weiß ich nicht, auf welchen Desktop die Symbole sollen.${aus}"
    exit 1
fi
ZIEL_HOME="$(getent passwd "$ZIEL_USER" | cut -d: -f6)"

SUDO_N="-n"   # wird zurueckgesetzt, falls sudo die Freigabe nicht zwischenspeichert
als_root() {
    if [ "$(id -u)" -eq 0 ]; then
        DEBIAN_FRONTEND=noninteractive bash -c "$1"
    else
        sudo $SUDO_N DEBIAN_FRONTEND=noninteractive bash -c "$1"
    fi
}
als_user() {
    if [ "$(id -u)" -eq 0 ] && [ "$ZIEL_USER" != "root" ]; then
        sudo -u "$ZIEL_USER" -H bash -c "$1"
    else
        bash -c "$1"
    fi
}

# =============================================================================
# 2. Vorbereitung: Rechte, Architektur, Werkzeuge
# =============================================================================
schritt "Vorbereitung"

ARCH="$(dpkg --print-architecture)"
info "Benutzer: $ZIEL_USER   Architektur: $ARCH"

if [ "$ARCH" != "amd64" ] && [ "$ARCH" != "i386" ]; then
    fehler "Discord und AnyDesk gibt es nur für amd64/i386, dieser Rechner ist '$ARCH'."
    exit 1
fi
if [ "$WILL_DISCORD" -eq 1 ] && [ "$ARCH" != "amd64" ]; then
    warnung "Discord gibt es nur für amd64 – wird auf $ARCH übersprungen."
    WILL_DISCORD=0
    SCHRITTE_GESAMT=$((SCHRITTE_GESAMT-1))
fi

# Passwort genau einmal – abgefragt von sudo selbst, nicht von diesem Skript.
if [ "$(id -u)" -ne 0 ]; then
    if ! sudo -v; then
        fehler "Ohne Administratorrechte lässt sich nichts installieren."
        exit 1
    fi
    # Manche sudo-Konfigurationen merken sich die Freigabe nicht (timestamp_timeout=0).
    # Dann darf "-n" nicht verwendet werden, sonst scheitert jeder Befehl sofort.
    if ! sudo -n true 2>/dev/null; then
        SUDO_N=""
        warnung "sudo merkt sich die Freigabe nicht – es kann erneut nach dem Passwort fragen."
    else
        # sudo-Freigabe wachhalten, damit lange apt-Läufe nicht mittendrin
        # erneut nach dem Passwort fragen.
        ( while kill -0 "$$" 2>/dev/null; do sudo -n true 2>/dev/null || true; sleep 50; done ) &
        KEEPALIVE_PID=$!
    fi
fi

APT="apt-get -y -o DPkg::Lock::Timeout=600 -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold"

info "Paketlisten auffrischen ..."
als_root "$APT update" >/dev/null 2>&1 || warnung "apt update meldete Fehler – wird trotzdem versucht."
als_root "$APT install curl ca-certificates gnupg" >/dev/null 2>&1 || true
ok "System bereit"

DISCORD_OK=0
ANYDESK_OK=0

# =============================================================================
# 3. Discord
# =============================================================================
if [ "$WILL_DISCORD" -eq 1 ]; then
    schritt "Discord installieren"

    # Offizieller Download-Link von Discord. Er leitet immer auf die aktuelle
    # Version weiter – deshalb keine fest eingetragene Versionsnummer, die nach
    # ein paar Wochen ins Leere liefe.
    info "Aktuelle Version herunterladen ..."
    if curl -fL --retry 3 --retry-delay 2 --connect-timeout 20 \
            -o "$TMP/discord.deb" \
            "https://discord.com/api/download?platform=linux&format=deb" 2>/dev/null \
       && [ -s "$TMP/discord.deb" ]; then
        chmod 644 "$TMP/discord.deb"
        info "Paket einspielen (Abhängigkeiten kommen automatisch mit) ..."
        if als_root "$APT install '$TMP/discord.deb'"; then
            DISCORD_OK=1
        else
            # apt ist an einer Abhängigkeit gescheitert: hart mit dpkg setzen
            # und apt hinterher die Lücken schließen lassen.
            warnung "Erster Versuch fehlgeschlagen – repariere Abhängigkeiten ..."
            als_root "dpkg -i '$TMP/discord.deb'" || true
            if als_root "$APT install -f"; then
                DISCORD_OK=1
            fi
        fi
    else
        fehler "Download fehlgeschlagen – ist die Internetverbindung in Ordnung?"
    fi

    if [ "$DISCORD_OK" -eq 1 ] && command -v discord >/dev/null 2>&1; then
        ok "Discord $(dpkg-query -W -f='${Version}' discord 2>/dev/null || echo '') installiert"
    else
        DISCORD_OK=0
        fehler "Discord konnte nicht installiert werden."
    fi
fi

# =============================================================================
# 4. AnyDesk
# =============================================================================
if [ "$WILL_ANYDESK" -eq 1 ]; then
    schritt "AnyDesk installieren"

    # Über das offizielle Repository, nicht über ein einzelnes .deb: so bekommt
    # AnyDesk künftige Updates ganz normal über "apt upgrade" mit.
    info "Signaturschlüssel und Paketquelle eintragen ..."
    als_root "install -d -m 0755 /etc/apt/keyrings" || true
    if als_root "curl -fsSL https://keys.anydesk.com/repos/DEB-GPG-KEY | gpg --dearmor --yes -o /etc/apt/keyrings/anydesk.gpg && chmod 644 /etc/apt/keyrings/anydesk.gpg"; then
        als_root "echo 'deb [signed-by=/etc/apt/keyrings/anydesk.gpg] http://deb.anydesk.com/ all main' > /etc/apt/sources.list.d/anydesk.list"
        als_root "$APT update" >/dev/null 2>&1 || true
        if als_root "$APT install anydesk"; then
            ANYDESK_OK=1
        fi
    else
        warnung "Schlüssel von keys.anydesk.com nicht erreichbar."
    fi

    # Rückfallweg: Paketliste des Repos direkt lesen und das .deb von Hand
    # holen. Greift auch dann, wenn apt die Quelle (z.B. wegen GPG) ablehnt.
    if [ "$ANYDESK_OK" -eq 0 ]; then
        warnung "Repository-Weg fehlgeschlagen – lade das Paket direkt ..."
        DEB_PFAD="$(curl -fsSL --connect-timeout 20 "http://deb.anydesk.com/dists/all/main/binary-${ARCH}/Packages" 2>/dev/null \
                    | awk '/^Filename:/ {print $2; exit}' || true)"
        if [ -n "$DEB_PFAD" ] \
           && curl -fL --retry 3 --connect-timeout 20 -o "$TMP/anydesk.deb" "http://deb.anydesk.com/$DEB_PFAD" 2>/dev/null \
           && [ -s "$TMP/anydesk.deb" ]; then
            chmod 644 "$TMP/anydesk.deb"
            if als_root "$APT install '$TMP/anydesk.deb'"; then
                ANYDESK_OK=1
            else
                als_root "dpkg -i '$TMP/anydesk.deb'" || true
                als_root "$APT install -f" && ANYDESK_OK=1 || true
            fi
        else
            fehler "Auch der direkte Download hat nicht geklappt."
        fi
    fi

    if [ "$ANYDESK_OK" -eq 1 ] && command -v anydesk >/dev/null 2>&1; then
        ok "AnyDesk $(dpkg-query -W -f='${Version}' anydesk 2>/dev/null || echo '') installiert"
    else
        ANYDESK_OK=0
        fehler "AnyDesk konnte nicht installiert werden."
    fi
fi

# =============================================================================
# 5. Desktop-Symbole
# =============================================================================
DESKTOP_DIR=""
SYMBOL_DISCORD=""
SYMBOL_ANYDESK=""

if [ "$WILL_SYMBOLE" -eq 1 ]; then
    schritt "Symbole auf den Desktop legen"

    # Der Ordner heißt je nach Sprache "Desktop" oder "Schreibtisch" – deshalb
    # fragen wir xdg-user-dir statt einen Namen zu raten.
    KANDIDAT="$(als_user 'xdg-user-dir DESKTOP 2>/dev/null' || true)"
    if [ -n "$KANDIDAT" ] && [ "$KANDIDAT" != "$ZIEL_HOME" ] && [ -d "$KANDIDAT" ]; then
        DESKTOP_DIR="$KANDIDAT"
    else
        for kand in "$ZIEL_HOME/Desktop" "$ZIEL_HOME/Schreibtisch"; do
            [ -d "$kand" ] && DESKTOP_DIR="$kand" && break
        done
    fi
    if [ -z "$DESKTOP_DIR" ]; then
        DESKTOP_DIR="$ZIEL_HOME/Desktop"
        als_user "mkdir -p '$DESKTOP_DIR'" || true
        info "Desktop-Ordner neu angelegt: $DESKTOP_DIR"
    fi
    info "Desktop-Ordner: $DESKTOP_DIR"

    # $1 Paketname/Basisname  $2 Anzeigename  $3 Befehl  $4 Icon  $5 Kategorien
    # Ergebnis steht danach in SYMBOL_PFAD (leer = nicht angelegt).
    symbol_anlegen() {
        SYMBOL_PFAD=""
        local basis="$1" name="$2" befehl="$3" icon="$4" kat="$5"
        local ziel="$DESKTOP_DIR/${basis}.desktop"
        local quelle="/usr/share/applications/${basis}.desktop"
        local vorlage="$TMP/${basis}.desktop"

        if [ -f "$quelle" ]; then
            # Der Starter aus dem Paket ist immer der genaueste (richtiger
            # Pfad, richtige WM-Klasse, Sprachversionen des Namens).
            cp "$quelle" "$vorlage"
        else
            cat > "$vorlage" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=$name
Exec=$befehl
Icon=$icon
Terminal=false
Categories=$kat
StartupNotify=true
EOF
        fi
        chmod 644 "$vorlage"

        if als_user "cp '$vorlage' '$ziel' && chmod +x '$ziel'"; then
            # KDE und GNOME starten einen Desktop-Starter erst, wenn er als
            # vertrauenswürdig gilt: ausführbar (KDE) bzw. mit gesetztem
            # metadata::trusted (GNOME/Nautilus). Beides setzen, dann fragt
            # beim Doppelklick nichts mehr nach.
            als_user "gio set -t string '$ziel' metadata::trusted true 2>/dev/null" || true
            SYMBOL_PFAD="$ziel"
            ok "$name liegt auf dem Desktop"
            return 0
        fi
        fehler "Symbol für $name konnte nicht angelegt werden."
        return 1
    }

    if [ "$DISCORD_OK" -eq 1 ]; then
        symbol_anlegen discord "Discord" "/usr/bin/discord" "discord" "Network;InstantMessaging;" || true
        SYMBOL_DISCORD="$SYMBOL_PFAD"
    fi
    if [ "$ANYDESK_OK" -eq 1 ]; then
        symbol_anlegen anydesk "AnyDesk" "/usr/bin/anydesk" "anydesk" "Network;RemoteAccess;" || true
        SYMBOL_ANYDESK="$SYMBOL_PFAD"
    fi

    als_root "update-desktop-database /usr/share/applications" >/dev/null 2>&1 || true

    # Plasma zeigt Desktop-Symbole nur an, wenn der Desktop auf "Ordneransicht"
    # steht. Steht er auf "Arbeitsfläche", liegen die Dateien zwar richtig, sind
    # aber unsichtbar – das wäre sonst ein rätselhafter Fehlschlag.
    APPLETSRC="$ZIEL_HOME/.config/plasma-org.kde.plasma.desktop-appletsrc"
    ORDNERANSICHT_FEHLT=0
    if [ -f "$APPLETSRC" ] && ! grep -q "org.kde.plasma.folder" "$APPLETSRC" 2>/dev/null; then
        ORDNERANSICHT_FEHLT=1
    fi
fi

# =============================================================================
# 6. Ergebnis
# =============================================================================
schritt "Fertig"

FEHLGESCHLAGEN=0
if [ "$WILL_DISCORD" -eq 1 ]; then
    if [ "$DISCORD_OK" -eq 1 ]; then ok "Discord  – Startmenü${SYMBOL_DISCORD:+ und Desktop}"
    else fehler "Discord  – nicht installiert"; FEHLGESCHLAGEN=1; fi
fi
if [ "$WILL_ANYDESK" -eq 1 ]; then
    if [ "$ANYDESK_OK" -eq 1 ]; then ok "AnyDesk  – Startmenü${SYMBOL_ANYDESK:+ und Desktop}"
    else fehler "AnyDesk  – nicht installiert"; FEHLGESCHLAGEN=1; fi
fi

if [ "${ORDNERANSICHT_FEHLT:-0}" -eq 1 ]; then
    echo
    warnung "Dein Plasma-Desktop steht auf 'Arbeitsfläche' – der zeigt grundsätzlich"
    warnung "keine Symbole an. Die Dateien liegen richtig in $DESKTOP_DIR."
    warnung "Sichtbar werden sie so: Rechtsklick auf den Desktop →"
    warnung "'Arbeitsflächen-Einstellungen' → Layout auf 'Ordneransicht' stellen."
    echo
    warnung "Bis dahin: Discord und AnyDesk stehen im Startmenü unter 'Internet'."
fi

echo
if [ "$FEHLGESCHLAGEN" -eq 0 ]; then
    printf '%s%sAlles erledigt.%s\n' "$gruen" "$fett" "$aus"
    exit 0
fi
printf '%s%sMit Fehlern beendet – siehe oben.%s\n' "$rot" "$fett" "$aus"
exit 1
