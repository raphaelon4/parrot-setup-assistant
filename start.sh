#!/bin/bash
# =============================================================================
# Starter für den Parrot OS Setup-Assistenten
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/parrot_setup_assistant.py"

rot=$'\e[31m'; gruen=$'\e[32m'; gelb=$'\e[33m'; fett=$'\e[1m'; aus=$'\e[0m'

# --- Nicht als root starten ---------------------------------------------------
# Mit sudo wäre $HOME = /root und alle KDE-Einstellungen (Tastatur, Themes,
# Akzentfarbe, Hintergrundbild) landeten im Root-Profil statt im Benutzerprofil.
# Der Assistent fragt das Passwort selbst ab, sobald er es braucht.
if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
    echo "${rot}${fett}Bitte NICHT mit sudo starten.${aus}"
    echo
    echo "Sonst landen Tastatur-, Design- und Hintergrundeinstellungen im Profil"
    echo "von 'root' und auf deinem Desktop ändert sich nichts."
    echo
    echo "  Richtig:  ${gruen}./start.sh${aus}"
    echo "  Falsch:   ${rot}sudo ./start.sh${aus}"
    exit 1
fi

# --- Python vorhanden? --------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    echo "${rot}Fehler: python3 ist nicht installiert.${aus}"
    echo "Nachinstallieren mit:"
    echo "  sudo apt update && sudo apt install -y python3 python3-tk"
    exit 1
fi

if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "${rot}Fehler: parrot_setup_assistant.py liegt nicht neben start.sh.${aus}"
    echo "Erwartet in: $SCRIPT_DIR"
    exit 1
fi

chmod +x "$PYTHON_SCRIPT" 2>/dev/null || true

# --- Grafische Oberfläche verfügbar? -----------------------------------------
# Ohne python3-tk fällt der Assistent auf den Terminal-Modus zurück. Läuft er
# dann per Doppelklick ohne sichtbares Terminal, sähe man gar nichts – deshalb
# in dem Fall ein Hinweisfenster statt eines stillen Fehlschlags.
if ! python3 -c "import tkinter" >/dev/null 2>&1; then
    if [ -t 1 ]; then
        echo "${gelb}Hinweis: python3-tk fehlt – der Assistent läuft im Terminal-Modus.${aus}"
        echo "${gelb}Grafische Oberfläche nachrüsten: sudo apt install -y python3-tk${aus}"
        echo
    else
        hinweis="Für die grafische Oberfläche fehlt das Paket python3-tk.

Bitte im Terminal ausführen:
  sudo apt install -y python3-tk

Oder den Assistenten direkt im Terminal starten:
  ./start.sh --cli"
        if command -v kdialog >/dev/null 2>&1; then
            kdialog --title "Parrot Setup-Assistent" --sorry "$hinweis"
        elif command -v zenity >/dev/null 2>&1; then
            zenity --warning --title="Parrot Setup-Assistent" --text="$hinweis"
        fi
        exit 1
    fi
fi

exec python3 "$PYTHON_SCRIPT" "$@"
