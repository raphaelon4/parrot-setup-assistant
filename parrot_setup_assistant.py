#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
PARROT OS SETUP-ASSISTENT & PERSONALISIERUNG
=============================================================================
Ein interaktiver Assistent für Parrot Security OS (KDE Plasma 6):
- System-Updates (apt update & full-upgrade)
- Google Antigravity 2.0 (Grafische Desktop-UI & AI-Plattform)
- Claude Desktop (Community-Build, nicht von Anthropic)
- Valve Steam Installation (Gaming-Plattform & i386-Unterstützung)
- Tastatur-Check & Layout-Korrektur (Fix für @-Zeichen mit AltGr+Q),
  dauerhaft über /etc/default/keyboard + KDE + localectl
- NVIDIA: Secure-Boot-Prüfung, Kernel-Header, DKMS & 32-Bit-Libs für Steam
- KDE Plasma 6 Designs als Standard (Arc-Dark, Arc-ICONS, Win10-Dark, Kuro, SDDM)
- Fenster-Akzentfarbe auf Rosa / Pink (#e93a9a)
- Neues Hintergrundbild (IMG_1685.png / wallpaper.png)
- AMD Ryzen CPU Optimierungen (amd64-microcode, lm-sensors, gamemode)
- NVIDIA Treiber & Tools (nvidia-driver, nvidia-settings, nvtop, vulkan)
- AMD Radeon Treiber & Tools (firmware-amd-graphics, vulkan, radeontop)
- Parrot Treiber-Pakete (parrot-drivers, dkms)
=============================================================================
"""

import sys
import os
import subprocess
import threading
import time
import re
import queue
import platform
import shutil
import zipfile
import tarfile
import shlex
from pathlib import Path

# Tkinter wird auf Modulebene gebraucht (die GUI-Klasse nutzt tk/ttk/messagebox
# direkt). Ein Import erst in main() wäre nur dort sichtbar -> NameError.
# Fehlt python3-tk, läuft der Assistent weiterhin im Terminal-Modus.
try:
    import tkinter as tk
    from tkinter import ttk
    from tkinter import messagebox
    HAS_TK = True
except Exception:
    tk = None
    ttk = None
    messagebox = None
    HAS_TK = False


def safe_extract(archive_path, dest):
    """Entpackt ein tar/zip-Archiv nach dest.

    tarfile.extractall() ohne 'filter' warnt ab Python 3.12 und wechselt in
    3.14 selbst auf 'data'. Wir setzen es explizit, damit das Verhalten auf
    allen Parrot-Versionen gleich ist und keine Pfade ausserhalb von dest
    geschrieben werden koennen.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if str(archive_path).lower().endswith(".zip"):
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(dest)
        return
    with tarfile.open(archive_path, "r:*") as tf:
        try:
            tf.extractall(dest, filter="data")
        except TypeError:
            tf.extractall(dest)

# =============================================================================
# SYSTEM & HARDWARE DIAGNOSTICS
# =============================================================================
def get_system_info():
    script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
    info = {
        "os_name": "Linux",
        "os_version": "",
        "kernel": platform.release(),
        "arch": platform.machine(),
        "cpu_model": "Unbekannter Prozessor",
        "cpu_cores": os.cpu_count() or 1,
        "is_amd_cpu": False,
        "is_intel_cpu": False,
        "ram_gb": 0,
        "gpus": [],
        "has_nvidia": False,
        "has_amd_gpu": False,
        "has_intel_gpu": False,
        "keyboard_layout": "unknown",
        "is_keyboard_de": False,
        "local_claude_deb": None,
        "antigravity_archive": None,
        "is_antigravity_installed": shutil.which("antigravity") is not None or os.path.exists("/opt/antigravity/antigravity"),
        "steam_deb": None,
        "wallpaper_path": None,
        "themes_dir": None,
    }

    # OS Info
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        info["os_name"] = line.split("=", 1)[1].strip().strip('"')
                    elif line.startswith("VERSION_ID="):
                        info["os_version"] = line.split("=", 1)[1].strip().strip('"')
        except Exception:
            pass

    # CPU Info
    if os.path.exists("/proc/cpuinfo"):
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "model name" in line:
                        info["cpu_model"] = line.split(":", 1)[1].strip()
                        break
        except Exception:
            pass
    
    cpu_lower = info["cpu_model"].lower()
    info["is_amd_cpu"] = "amd" in cpu_lower or "ryzen" in cpu_lower
    info["is_intel_cpu"] = "intel" in cpu_lower and not info["is_amd_cpu"]

    # RAM Info
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if "MemTotal:" in line:
                        kb = int(line.split()[1])
                        info["ram_gb"] = round(kb / (1024 * 1024), 1)
                        break
        except Exception:
            pass

    # GPU Info via lspci
    try:
        p = subprocess.run(["lspci"], capture_output=True, text=True, timeout=5)
        for line in p.stdout.splitlines():
            if re.search(r"VGA|3D controller|Display controller", line, re.IGNORECASE):
                parts = line.split(": ", 1)
                gpu_name = parts[1].strip() if len(parts) > 1 else line.strip()
                info["gpus"].append(gpu_name)
                gpu_upper = gpu_name.upper()
                if "NVIDIA" in gpu_upper:
                    info["has_nvidia"] = True
                if "AMD" in gpu_upper or "RADEON" in gpu_upper or "ATI" in gpu_upper:
                    info["has_amd_gpu"] = True
                if "INTEL" in gpu_upper:
                    info["has_intel_gpu"] = True
    except Exception:
        pass

    # Keyboard Layout Check
    try:
        kp = subprocess.run(["setxkbmap", "-query"], capture_output=True, text=True, timeout=3)
        for line in kp.stdout.splitlines():
            if line.startswith("layout:"):
                info["keyboard_layout"] = line.split(":", 1)[1].strip()
                break
    except Exception:
        pass
    
    if info["keyboard_layout"] == "unknown" and os.path.exists("/etc/default/keyboard"):
        try:
            with open("/etc/default/keyboard", "r") as f:
                for line in f:
                    if line.startswith("XKBLAYOUT="):
                        info["keyboard_layout"] = line.split("=", 1)[1].strip().strip('"')
                        break
        except Exception:
            pass
    info["is_keyboard_de"] = "de" in info["keyboard_layout"].lower()

    # Search paths for assets
    # Bewusst OHNE /tmp: dort koennte ein beliebiges, fremdes .deb liegen,
    # das sonst ungefragt mitinstalliert wuerde.
    search_paths = [
        script_dir,
        Path.home() / "Downloads",
        Path.home() / "Pictures",
        Path.home(),
    ]

    # Look for local claude deb
    for sp in search_paths:
        if sp.exists():
            for deb in sp.glob("claude-desktop*.deb"):
                info["local_claude_deb"] = str(deb)
                break
        if info["local_claude_deb"]:
            break

    # Look for Antigravity archive
    for sp in search_paths:
        if sp.exists():
            for pattern in ["Antigravity*.tar.gz", "antigravity*.tar.gz"]:
                for arch in sp.glob(pattern):
                    info["antigravity_archive"] = str(arch)
                    break
                if info["antigravity_archive"]:
                    break
        if info["antigravity_archive"]:
            break

    # Look for Steam deb
    for sp in search_paths:
        if sp.exists():
            for deb in sp.glob("*steam*.deb"):
                info["steam_deb"] = str(deb)
                break
        if info["steam_deb"]:
            break

    # Wallpaper path
    candidates_wp = [
        script_dir / "wallpaper.png",
        Path.home() / "Pictures" / "IMG_1685.png",
        script_dir / "IMG_1685.png",
    ]
    for c in candidates_wp:
        if c.exists():
            info["wallpaper_path"] = str(c)
            break

    # Themes dir
    td = script_dir / "themes"
    if td.exists():
        info["themes_dir"] = str(td)

    return info

# =============================================================================
# INSTALLATION WORKER LOGIC
# =============================================================================
class InstallerWorker:
    def __init__(self, selections, password, log_callback, progress_callback, finish_callback):
        self.selections = selections
        self.password = password
        self.log_cb = log_callback
        self.prog_cb = progress_callback
        self.finish_cb = finish_callback
        self.is_running = True
        self.keep_alive_thread = None
        self.success = False
        self.installed_items = []
        self.skipped_packages = []
        self.warnings = []
        self._apt_updated = False

    def log(self, text, tag="INFO"):
        if self.log_cb:
            self.log_cb(f"[{tag}] {text}\n")

    def run_cmd(self, cmd, desc="", critical=True, use_sudo=True):
        self.log(f"▶ {desc or cmd}", tag="RUN")
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        
        if use_sudo and os.geteuid() != 0:
            # Das GESAMTE Kommando muss unter sudo laufen. Bei "sudo -n a | b"
            # oder "sudo -n a && b" bzw. "a || b" liefe nur der erste Teil als
            # root - Pipes (curl|gpg, echo|tee), Verkettungen (mkdir && tar) und
            # Fallbacks (apt X || apt Y) waeren sonst rechtelos.
            # DEBIAN_FRONTEND muss mit hinein, weil sudo die Umgebung leert.
            inner = "export DEBIAN_FRONTEND=noninteractive; " + cmd
            full_cmd = "sudo -n /bin/bash -c " + shlex.quote(inner)
        else:
            full_cmd = cmd

        p = subprocess.Popen(
            full_cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )

        for line in iter(p.stdout.readline, ''):
            if not self.is_running:
                p.terminate()
                break
            self.log_cb(line)
        p.stdout.close()
        p.wait()

        # Muss den ECHTEN Status liefern: vorher kam bei critical=False immer
        # True zurueck, dadurch lief z.B. die Abhaengigkeits-Reparatur nach
        # einem fehlgeschlagenen .deb ("apt-get install -f") nie an.
        ok = (p.returncode == 0)
        if ok:
            self.log(f"Erfolgreich: {desc or cmd}", tag="OK")
        else:
            level = "ERROR" if critical else "WARN"
            self.log(f"Befehl beendet mit Code {p.returncode}: {cmd}", tag=level)
        return ok

    # ------------------------------------------------------------------
    # Hilfsfunktionen
    # ------------------------------------------------------------------
    def apt_update_once(self):
        """apt-get update genau einmal pro Lauf, aber garantiert vor dem
        ersten Install - sonst schlaegt eine Installation fehl, wenn der
        Punkt "System-Updates" abgewaehlt wurde."""
        if self._apt_updated:
            return
        self._apt_updated = True
        self.run_cmd("apt-get update -y", "Paketlisten auffrischen", critical=False)

    def apt_install(self, packages, desc="", allow_fail_single=True):
        """Installiert Pakete moeglichst vollstaendig.

        apt bricht die GESAMTE Installation ab, sobald ein einziger Paketname
        im Repo fehlt. Auf Parrot heissen aber nicht alle Pakete wie auf Debian
        (z.B. cpupower-gui, gamemode). Darum: erst alles zusammen, bei Fehler
        Paket fuer Paket - so landen die verfuegbaren Pakete trotzdem drauf.
        """
        pkgs = [p for p in packages if p]
        if not pkgs:
            return True
        self.apt_update_once()
        joined = " ".join(pkgs)
        if self.run_cmd(f"apt-get install -y {joined}", desc or f"Installiere: {joined}", critical=False):
            return True
        if not allow_fail_single:
            return False
        self.log(f"Sammel-Installation fehlgeschlagen - versuche einzeln: {joined}", tag="WARN")
        ok_any = False
        for pkg in pkgs:
            if self.run_cmd(f"apt-get install -y {pkg}", f"Installiere Einzelpaket: {pkg}", critical=False):
                ok_any = True
            else:
                self.log(f"Paket '{pkg}' auf diesem System nicht verfuegbar - uebersprungen.", tag="WARN")
                self.skipped_packages.append(pkg)
        return ok_any

    def kwrite(self, cfg_file, group, key, value, desc, use_sudo=False):
        """kwriteconfig6 mit Fallback auf kwriteconfig5."""
        q = shlex.quote
        args = f"--file {q(cfg_file)} --group {q(group)} --key {q(key)} {q(value)}"
        return self.run_cmd(
            f"kwriteconfig6 {args} || kwriteconfig5 {args}",
            desc, use_sudo=use_sudo, critical=False
        )

    def kwin_reconfigure(self):
        self.run_cmd(
            "qdbus6 org.kde.KWin /KWin reconfigure "
            "|| qdbus org.kde.KWin /KWin reconfigure "
            "|| qdbus-qt6 org.kde.KWin /KWin reconfigure || true",
            "KWin neu konfigurieren", use_sudo=False, critical=False
        )

    def start(self):
        t = threading.Thread(target=self._execute, daemon=True)
        t.start()

    def _keep_sudo_alive(self):
        while self.is_running:
            time.sleep(40)
            if not self.is_running:
                break
            subprocess.run(["sudo", "-n", "-v"], capture_output=True)

    def _execute(self):
        try:
            # Step 0: Ensure sudo credentials if not root
            if os.geteuid() != 0:
                p = subprocess.run(
                    ["sudo", "-S", "-v"],
                    input=f"{self.password}\n",
                    text=True,
                    capture_output=True
                )
                if p.returncode != 0:
                    err = (p.stderr or "").strip()
                    # Falsches Passwort und "Benutzer darf kein sudo" sehen sonst
                    # gleich aus - das schickt einen auf die falsche Fehlersuche.
                    if "not in the sudoers" in err or "not allowed" in err:
                        msg = (f"Der Benutzer '{os.environ.get('USER', '?')}' darf kein sudo ausführen. "
                               "Ein Administrator muss ihn zur Gruppe 'sudo' hinzufügen:\n"
                               f"  usermod -aG sudo {os.environ.get('USER', 'BENUTZER')}")
                    else:
                        msg = "Das eingegebene Passwort war nicht korrekt."
                    self.log(f"Sudo fehlgeschlagen: {err or 'kein Grund gemeldet'}", tag="ERROR")
                    self.finish_cb(False, msg)
                    return
                self.keep_alive_thread = threading.Thread(target=self._keep_sudo_alive, daemon=True)
                self.keep_alive_thread.start()

            steps = []
            if self.selections.get("keyboard_fix"):
                steps.append("keyboard_fix")
            if self.selections.get("system_update"):
                steps.append("system_update")
            if self.selections.get("steam"):
                steps.append("steam")
            if self.selections.get("antigravity"):
                steps.append("antigravity")
            if self.selections.get("claude"):
                steps.append("claude")
            if self.selections.get("kde_themes"):
                steps.append("kde_themes")
            if self.selections.get("pink_accent_wallpaper"):
                steps.append("pink_accent_wallpaper")
            if self.selections.get("amd_ryzen"):
                steps.append("amd_ryzen")
            if self.selections.get("nvidia"):
                steps.append("nvidia")
            if self.selections.get("amd_radeon"):
                steps.append("amd_radeon")
            if self.selections.get("parrot_drivers"):
                steps.append("parrot_drivers")

            total_steps = len(steps)
            if total_steps == 0:
                self.finish_cb(True, "Keine Komponenten ausgewählt.")
                return

            current = 0
            script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            home = Path.home()

            # -------------------------------------------------------------
            # STEP: KEYBOARD FIX (@ Symbol / German Layout)
            # -------------------------------------------------------------
            if "keyboard_fix" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Korrigiere Tastaturlayout auf Deutsch (@-Taste)...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: TASTATUR-LAYOUT AUF DEUTSCH SETZEN (FIX FÜR '@')", tag="INFO")
                self.log("=" * 60, tag="INFO")
                
                session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()
                self.log(f"Erkannte Sitzung: {session_type or 'unbekannt'}", tag="INFO")

                # 1) Sofort in der laufenden Sitzung (nur X11 - unter Wayland
                #    hat setxkbmap keinerlei Wirkung, das macht dort KWin).
                if session_type == "x11":
                    self.run_cmd("setxkbmap -layout de -model pc105 || true",
                                 "Aktive X11-Sitzung auf deutsches Layout umstellen", use_sudo=False)
                else:
                    self.log("Wayland/unbekannt: Layout greift nach dem Ab- und Anmelden.", tag="INFO")

                # 2) KDE Plasma (kxkbrc). VariantList/DisplayNames muessen mit
                #    gesetzt werden, sonst behaelt Plasma teilweise das alte
                #    Layout in der Anzeige und schaltet zurueck.
                self.kwrite("kxkbrc", "Layout", "LayoutList", "de", "KDE: Layout-Liste auf 'de' setzen")
                self.kwrite("kxkbrc", "Layout", "VariantList", "", "KDE: Layout-Variante leeren")
                self.kwrite("kxkbrc", "Layout", "DisplayNames", "", "KDE: Anzeigenamen zuruecksetzen")
                self.kwrite("kxkbrc", "Layout", "Model", "pc105", "KDE: Tastaturmodell pc105 setzen")
                self.kwrite("kxkbrc", "Layout", "Use", "true", "KDE: eigene Layout-Einstellung aktivieren")
                self.kwrite("kxkbrc", "Layout", "SwitchMode", "Global", "KDE: Layout global (nicht pro Fenster)")
                self.kwrite("kxkbrc", "Layout", "ResetOldOptions", "true", "KDE: alte Tastaturoptionen verwerfen")

                # 3) /etc/default/keyboard ist auf Debian/Parrot die eigentliche
                #    Quelle der Wahrheit (Konsole, SDDM-Login und X11). Ohne
                #    diesen Schritt steht nach dem Neustart wieder 'us' drin.
                kb_conf = (
                    "# Gesetzt vom Parrot-Setup-Assistenten: deutsches QWERTZ-Layout\n"
                    "# ('@' liegt damit auf AltGr+Q)\n"
                    'XKBMODEL="pc105"\n'
                    'XKBLAYOUT="de"\n'
                    'XKBVARIANT=""\n'
                    'XKBOPTIONS=""\n'
                    'BACKSPACE="guess"\n'
                )
                self.run_cmd(
                    "cp -n /etc/default/keyboard /etc/default/keyboard.bak-parrot-setup 2>/dev/null || true; "
                    f"printf '%s' {shlex.quote(kb_conf)} > /etc/default/keyboard",
                    "/etc/default/keyboard dauerhaft auf 'de' setzen (ueberlebt Neustart)",
                    critical=False
                )

                # 4) systemd-Ebene fuer Konsole und X11
                self.run_cmd("localectl set-x11-keymap de pc105 '' '' || true",
                             "Systemweites X11-Tastaturlayout auf 'de' setzen", critical=False)
                self.run_cmd("localectl set-keymap de || true",
                             "Systemweites Konsolen-Layout auf 'de' setzen", critical=False)
                self.run_cmd("setupcon --save --force 2>/dev/null || true",
                             "Konsolen-Tastatur neu laden", critical=False)
                self.run_cmd("udevadm trigger --subsystem-match=input --action=change 2>/dev/null || true",
                             "Eingabegeraete neu einlesen", critical=False)

                # 5) Kontrolle: was steht jetzt wirklich drin?
                self.run_cmd(
                    "echo '--- /etc/default/keyboard ---'; grep -E '^XKB' /etc/default/keyboard || true; "
                    "echo '--- localectl ---'; localectl status 2>/dev/null | grep -iE 'keymap|layout' || true",
                    "Kontrolle: hinterlegtes Tastaturlayout", critical=False
                )

                self.installed_items.append(
                    "Tastatur-Fix: deutsches QWERTZ-Layout dauerhaft ('@' = AltGr+Q)"
                )
                if session_type != "x11":
                    self.warnings.append(
                        "Tastatur: Bitte einmal abmelden/neu starten - unter Wayland greift "
                        "das neue Layout erst in der naechsten Sitzung."
                    )

            # -------------------------------------------------------------
            # STEP: SYSTEM UPDATE
            # -------------------------------------------------------------
            if "system_update" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Aktualisiere Paketquellen & System-Updates...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: PARROT OS SYSTEM-UPDATES", tag="INFO")
                self.log("=" * 60, tag="INFO")
                self.run_cmd("apt-get update -y", "Paketlisten auffrischen")
                self.run_cmd("apt-get full-upgrade -y -o Dpkg::Options::='--force-confdef' -o Dpkg::Options::='--force-confold'", "System-Upgrade ausführen", critical=False)
                self.run_cmd("apt-get autoremove -y --purge", "Alte Pakete bereinigen", critical=False)
                self.installed_items.append("Parrot OS System-Updates")

            # -------------------------------------------------------------
            # STEP: STEAM
            # -------------------------------------------------------------
            if "steam" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere Valve Steam...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: STEAM GAMING-PLATTFORM INSTALLATION", tag="INFO")
                self.log("=" * 60, tag="INFO")
                
                self.run_cmd("dpkg --add-architecture i386", "32-Bit Architektur (i386) fuer Spiele aktivieren", critical=False)
                self._apt_updated = False          # nach add-architecture neu einlesen
                self.apt_update_once()

                steam_deb = self.selections.get("steam_deb")
                installed_steam = False
                if steam_deb and os.path.exists(steam_deb):
                    self.log(f"Installiere Steam aus .deb Paket: {steam_deb}", tag="INFO")
                    if self.run_cmd(f"apt-get install -y {shlex.quote(steam_deb)}",
                                    "Steam aus lokalem Debian-Paket installieren", critical=False):
                        installed_steam = True
                    else:
                        # Laeuft jetzt tatsaechlich an: run_cmd meldet echte Fehler.
                        self.run_cmd("apt-get install -f -y",
                                     "Fehlende Abhaengigkeiten fuer Steam nachziehen", critical=False)
                        installed_steam = self.run_cmd(
                            "dpkg -l steam steam-launcher 2>/dev/null | grep -q '^ii'",
                            "Kontrolle: ist Steam installiert?", critical=False, use_sudo=False)

                if not installed_steam:
                    self.log("Weiche auf die Paketquellen aus...", tag="INFO")
                    self.apt_install(["steam-installer", "steam-devices"],
                                     "Steam aus den Paketquellen installieren")

                self.installed_items.append("Valve Steam (Gaming-Plattform, 32-Bit aktiviert)")

            # -------------------------------------------------------------
            # STEP: GOOGLE ANTIGRAVITY 2.0 (DESKTOP-UI)
            # -------------------------------------------------------------
            if "antigravity" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere Google Antigravity 2.0 Desktop-UI...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: GOOGLE ANTIGRAVITY 2.0 (DESKTOP-UI)", tag="INFO")
                self.log("=" * 60, tag="INFO")

                arch_path = self.selections.get("antigravity_archive")
                if not arch_path or not os.path.exists(arch_path):
                    candidates = [
                        script_dir / "Antigravity.tar.gz",
                        script_dir / "antigravity.tar.gz",
                        home / "Downloads" / "Antigravity.tar.gz",
                    ]
                    for c in candidates:
                        if c.exists():
                            arch_path = str(c)
                            break

                if not (arch_path and os.path.exists(arch_path)):
                    # Das Archiv ist ~164 MB gross und daher nicht Teil des Repos.
                    # Frueher wurde der Schritt hier kommentarlos uebersprungen -
                    # man sah nur, dass Antigravity danach fehlte.
                    self.log("Antigravity-Archiv nicht gefunden - Schritt wird uebersprungen.", tag="WARN")
                    self.log("Zum Nachinstallieren 'Antigravity.tar.gz' in einen dieser Ordner legen:", tag="INFO")
                    self.log(f"   {script_dir}", tag="INFO")
                    self.log(f"   {home / 'Downloads'}", tag="INFO")
                    self.log("...und den Assistenten danach erneut starten.", tag="INFO")
                    self.warnings.append(
                        "Antigravity wurde uebersprungen: 'Antigravity.tar.gz' lag nicht vor. "
                        f"Datei nach {script_dir} kopieren und Assistent erneut starten."
                    )

                if arch_path and os.path.exists(arch_path):
                    self.log(f"Entpacke Antigravity-Archiv: {arch_path}", tag="INFO")
                    self.run_cmd("mkdir -p /opt/antigravity", "Zielverzeichnis /opt/antigravity anlegen")
                    self.run_cmd(f"tar -xzf '{arch_path}' -C /opt/antigravity --strip-components=1", "Antigravity Dateien extrahieren")
                    self.run_cmd("chmod +x /opt/antigravity/antigravity", "Ausfuehrungsrechte setzen", critical=False)
                    if not self.run_cmd("test -x /opt/antigravity/antigravity",
                                        "Kontrolle: Antigravity-Programmdatei vorhanden",
                                        critical=False, use_sudo=False):
                        self.log("/opt/antigravity/antigravity fehlt - Archivaufbau weicht ab.", tag="WARN")
                        self.warnings.append("Antigravity: Programmdatei nicht gefunden, Starter kann fehlschlagen.")
                    self.run_cmd("chown root:root /opt/antigravity/chrome-sandbox 2>/dev/null && chmod 4755 /opt/antigravity/chrome-sandbox 2>/dev/null || true", "Sandbox-Rechte konfigurieren", critical=False)
                    self.run_cmd("ln -sf /opt/antigravity/antigravity /usr/local/bin/antigravity", "Symlink /usr/local/bin/antigravity anlegen")
                    
                    user_bin = home / ".local" / "bin"
                    user_bin.mkdir(parents=True, exist_ok=True)
                    try:
                        (user_bin / "antigravity").unlink(missing_ok=True)
                        (user_bin / "antigravity").symlink_to("/opt/antigravity/antigravity")
                    except Exception:
                        pass

                    svg_source = script_dir / "antigravity.svg"
                    if svg_source.exists():
                        self.run_cmd("mkdir -p /usr/share/icons/hicolor/scalable/apps /usr/share/pixmaps", "Icon-Verzeichnisse erstellen")
                        self.run_cmd(f"cp '{svg_source}' /usr/share/icons/hicolor/scalable/apps/antigravity.svg", "Antigravity Icon in System kopieren")
                        self.run_cmd(f"cp '{svg_source}' /usr/share/pixmaps/antigravity.svg", "Antigravity Pixmap kopieren")

                    desktop_file_content = """[Desktop Entry]
Version=1.0
Type=Application
Name=Antigravity
GenericName=AI Development Platform
Comment=Google Antigravity 2.0 Desktop Environment
Exec=/opt/antigravity/antigravity %U
Icon=antigravity
Terminal=false
Categories=Development;IDE;Utility;
StartupWMClass=antigravity
MimeType=x-scheme-handler/antigravity;
"""
                    tmp_desktop = "/tmp/antigravity.desktop"
                    with open(tmp_desktop, "w") as df:
                        df.write(desktop_file_content)
                    self.run_cmd(f"cp '{tmp_desktop}' /usr/share/applications/antigravity.desktop && chmod 644 /usr/share/applications/antigravity.desktop", "Desktop-Starter installieren")

                    user_apps = home / ".local" / "share" / "applications"
                    user_apps.mkdir(parents=True, exist_ok=True)
                    try:
                        shutil.copy(tmp_desktop, user_apps / "antigravity.desktop")
                    except Exception:
                        pass

                    self.run_cmd("update-desktop-database || true", "Desktop-Datenbank aktualisieren", critical=False)
                    self.installed_items.append("Google Antigravity 2.0 (Desktop-UI)")

            # -------------------------------------------------------------
            # STEP: CLAUDE DESKTOP
            # -------------------------------------------------------------
            if "claude" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere Claude Desktop (Anthropic)...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: CLAUDE DESKTOP INSTALLATION", tag="INFO")
                self.log("=" * 60, tag="INFO")
                
                local_deb = self.selections.get("local_claude_deb")
                installed_deb = False

                if local_deb and os.path.exists(local_deb):
                    self.log(f"Verwende vorhandenes Debian-Paket: {local_deb}", tag="INFO")
                    if self.run_cmd(f"apt-get install -y {shlex.quote(local_deb)}",
                                    "Lokales Claude Desktop .deb installieren", critical=False):
                        installed_deb = True
                    else:
                        self.run_cmd("apt-get install -f -y",
                                     "Fehlende Abhaengigkeiten nachziehen", critical=False)
                        installed_deb = self.run_cmd(
                            "dpkg -l claude-desktop 2>/dev/null | grep -q '^ii'",
                            "Kontrolle: ist Claude Desktop installiert?", critical=False, use_sudo=False)

                if not installed_deb:
                    # Hinweis: Anthropic bietet (Stand jetzt) KEIN offizielles
                    # Linux-.deb an. pkg.claude-desktop-debian.dev ist ein
                    # Community-Repository - fremde Paketquelle + fremder
                    # GPG-Schluessel. Bewusste Entscheidung, daher der Hinweis.
                    self.log("Hinweis: Claude Desktop kommt aus dem Community-Repository "
                             "pkg.claude-desktop-debian.dev (nicht von Anthropic selbst).", tag="WARN")
                    self.warnings.append(
                        "Claude Desktop stammt aus dem Community-Repo "
                        "pkg.claude-desktop-debian.dev, nicht von Anthropic. "
                        "Wer das nicht moechte: Haekchen bei der Auswahl entfernen."
                    )
                    self.log("Richte das Community-Repository fuer Claude ein...", tag="INFO")
                    self.apt_install(["curl", "gpg", "ca-certificates", "libsecret-1-0", "gnome-keyring"],
                                     "Voraussetzungen fuer Claude (inkl. Schluesselbund)")
                    self.run_cmd("curl -fsSL https://pkg.claude-desktop-debian.dev/KEY.gpg | gpg --dearmor --yes -o /usr/share/keyrings/claude-desktop.gpg", "GPG-Schlüssel hinzufügen", critical=False)
                    self.run_cmd('echo "deb [signed-by=/usr/share/keyrings/claude-desktop.gpg arch=amd64,arm64] https://pkg.claude-desktop-debian.dev stable main" | tee /etc/apt/sources.list.d/claude-desktop.list', "APT Repository anlegen", critical=False)
                    self.run_cmd("apt-get update -y", "Paketliste für Claude aktualisieren", critical=False)
                    self.run_cmd("apt-get install -y claude-desktop", "Claude Desktop via Repository installieren", critical=False)

                self.run_cmd("update-desktop-database || true", "Desktop-Datenbank auffrischen", critical=False)
                self.installed_items.append("Claude Desktop (Community-Build)")

            # -------------------------------------------------------------
            # STEP: KDE DESIGNS & STYLING (STORE THEMES)
            # -------------------------------------------------------------
            if "kde_themes" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere & aktiviere KDE Store Designs...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: KDE DESIGNS (ARC-DARK, KURO, WIN10, ICONS, SDDM)", tag="INFO")
                self.log("=" * 60, tag="INFO")

                themes_dir = script_dir / "themes"
                local_share = home / ".local" / "share"
                
                # 1. Arc-ICONS
                arc_zip = themes_dir / "Arc-ICONS_1.5.7.zip"
                if arc_zip.exists():
                    icons_dir = local_share / "icons"
                    icons_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        safe_extract(arc_zip, icons_dir)
                        self.kwrite("kdeglobals", "Icons", "Theme", "Arc-ICONS",
                                    "Arc-ICONS als Standard-Icon-Theme setzen")
                        self.run_cmd("gtk-update-icon-cache -f -t ~/.local/share/icons/Arc-ICONS 2>/dev/null || true",
                                     "Icon-Cache aktualisieren", use_sudo=False, critical=False)
                    except Exception as e:
                        self.log(f"Fehler bei Arc-ICONS: {e}", tag="WARN")

                # 2. Windows 10 Dark Window Decoration
                win_tar = themes_dir / "windows10-dark.tar.xz"
                if win_tar.exists():
                    aurorae_dir = local_share / "aurorae" / "themes"
                    aurorae_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        safe_extract(win_tar, aurorae_dir)
                        self.kwrite("kwinrc", "org.kde.kdecoration2", "library", "org.kde.kwin.aurorae",
                                    "Aurorae Fensterdekoration Engine aktivieren")
                        self.kwrite("kwinrc", "org.kde.kdecoration2", "theme", "__aurorae__svg__Windows10-dark",
                                    "Windows 10 Dark als Fensterdekoration setzen")
                    except Exception as e:
                        self.log(f"Fehler bei Windows 10 Dark: {e}", tag="WARN")

                # 3. Arc-Dark Plasma Desktop Theme
                arc_dark = themes_dir / "Arc-Dark.tar.gz"
                if arc_dark.exists():
                    dt_dir = local_share / "plasma" / "desktoptheme"
                    dt_dir.mkdir(parents=True, exist_ok=True)
                    try:
                        safe_extract(arc_dark, dt_dir)
                        # plasma-apply-desktoptheme greift sofort; kwriteconfig als Rueckfall.
                        self.run_cmd("plasma-apply-desktoptheme Arc-Dark 2>/dev/null || true",
                                     "Arc-Dark sofort anwenden", use_sudo=False, critical=False)
                        self.kwrite("plasmarc", "Theme", "name", "Arc-Dark",
                                    "Arc-Dark als Plasma Desktop-Theme setzen")
                    except Exception as e:
                        self.log(f"Fehler bei Arc-Dark: {e}", tag="WARN")

                # 4. Splashscreens (Kuro the Cat & Casper)
                splash_dir = local_share / "plasma" / "look-and-feel"
                splash_dir.mkdir(parents=True, exist_ok=True)
                kuro_tar = themes_dir / "a2n.kuro.tar.gz"
                if kuro_tar.exists():
                    try:
                        safe_extract(kuro_tar, splash_dir)
                        self.kwrite("ksplashrc", "KSplash", "Engine", "KSplashQML",
                                    "QML Splashscreen Engine setzen")
                        self.kwrite("ksplashrc", "KSplash", "Theme", "a2n.kuro",
                                    "Kuro the Cat als Start-Ladebildschirm setzen")
                    except Exception as e:
                        self.log(f"Fehler bei Kuro Splash: {e}", tag="WARN")

                casper_tar = themes_dir / "CasperTheMorningStar.tar.gz"
                if casper_tar.exists():
                    casper_target = splash_dir / "CasperTheMorningStar"
                    casper_target.mkdir(parents=True, exist_ok=True)
                    try:
                        safe_extract(casper_tar, casper_target)
                    except Exception as e:
                        self.log(f"Fehler bei Casper Splash: {e}", tag="WARN")

                # 5. SDDM Themes (sddm_wynn & KDE-Story)
                self.run_cmd("mkdir -p /usr/share/sddm/themes /etc/sddm.conf.d", "SDDM Verzeichnisse anlegen")
                wynn_tar = themes_dir / "sddm_wynn-theme-1.4.tar.gz"
                if wynn_tar.exists():
                    self.run_cmd(f"tar -xzf '{wynn_tar}' -C /usr/share/sddm/themes/", "sddm_wynn Theme installieren", critical=False)
                
                kdestory_tar = themes_dir / "KDE-Story.tar.gz"
                if kdestory_tar.exists():
                    self.run_cmd(f"mkdir -p /usr/share/sddm/themes/KDE-Story && tar -xzf '{kdestory_tar}' -C /usr/share/sddm/themes/KDE-Story --strip-components=1", "KDE-Story SDDM Theme installieren", critical=False)
                    self.kwrite("/etc/sddm.conf.d/kde_settings.conf", "Theme", "Current", "KDE-Story",
                                "KDE-Story als SDDM-Anmeldethema setzen", use_sudo=True)

                self.run_cmd("kbuildsycoca6 --noincremental 2>/dev/null || kbuildsycoca5 --noincremental 2>/dev/null || true",
                             "Anwendungs-/Theme-Datenbank neu aufbauen", use_sudo=False, critical=False)
                self.kwin_reconfigure()
                self.installed_items.append("KDE Designs: Arc-Dark, Arc-ICONS, Windows10-Dark & Kuro Splash")

            # -------------------------------------------------------------
            # STEP: PINK ACCENT COLOR & WALLPAPER
            # -------------------------------------------------------------
            if "pink_accent_wallpaper" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Setze rosa Akzentfarbe & Hintergrundbild...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: ROSA FENSTER-AKZENTFARBE & WALLPAPER", tag="INFO")
                self.log("=" * 60, tag="INFO")

                # Pink Accent Color (#e93a9a -> 233,58,154)
                pink_rgb = "233,58,154"
                # MUSS zuerst kommen: steht AccentColorFromWallpaper auf true,
                # ueberschreibt Plasma die eigene Akzentfarbe beim naechsten
                # Hintergrundwechsel wieder automatisch - das Rosa waere weg.
                self.kwrite("kdeglobals", "General", "AccentColorFromWallpaper", "false",
                            "Automatische Akzentfarbe aus dem Wallpaper abschalten")
                self.kwrite("kdeglobals", "General", "AccentColor", pink_rgb,
                            "Fenster-Akzentfarbe auf Rosa setzen")
                self.kwrite("kdeglobals", "General", "LastUsedCustomAccentColor", pink_rgb,
                            "Benutzerdefinierte Akzentfarbe speichern")
                self.kwrite("kdeglobals", "Colors:Selection", "BackgroundNormal", pink_rgb,
                            "Auswahlfarbe anpassen")
                self.kwrite("kdeglobals", "Colors:Selection", "BackgroundAlternate", "240,90,170",
                            "Alternative Auswahlfarbe anpassen")

                # Wallpaper
                wp_source = self.selections.get("wallpaper_path")
                if not wp_source or not os.path.exists(wp_source):
                    wp_source = str(script_dir / "wallpaper.png")
                
                if os.path.exists(wp_source):
                    dest_wp_dir = home / "Pictures"
                    dest_wp_dir.mkdir(parents=True, exist_ok=True)
                    dest_wp = dest_wp_dir / "IMG_1685.png"
                    try:
                        shutil.copy(wp_source, dest_wp)
                    except Exception:
                        dest_wp = Path(wp_source)

                    self.run_cmd(f"plasma-apply-wallpaperimage '{dest_wp}'", f"Hintergrundbild '{dest_wp.name}' anwenden", use_sudo=False, critical=False)
                    self.installed_items.append("Rosa Fenster-Akzentfarbe (#e93a9a) & neues Hintergrundbild")
                else:
                    self.installed_items.append("Rosa Fenster-Akzentfarbe (#e93a9a)")

                self.kwin_reconfigure()

            # -------------------------------------------------------------
            # STEP: AMD RYZEN TWEAKS
            # -------------------------------------------------------------
            if "amd_ryzen" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere AMD Ryzen Optimierungen...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: AMD RYZEN TOOLS & MICROCODE", tag="INFO")
                self.log("=" * 60, tag="INFO")
                # Einzeln nachziehen, falls ein Paketname auf Parrot fehlt
                # (gamemode/cpupower-gui sind nicht in jedem Release vorhanden).
                self.apt_install(["amd64-microcode", "lm-sensors", "gamemode", "cpupower-gui"],
                                 "AMD Microcode & Tools installieren")
                self.run_cmd("sensors-detect --auto || true", "Hardware-Sensoren konfigurieren", critical=False)
                self.installed_items.append("AMD Ryzen Microcode & Sensoren (lm-sensors, gamemode)")

            # -------------------------------------------------------------
            # STEP: NVIDIA TOOLS & DRIVERS
            # -------------------------------------------------------------
            if "nvidia" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere NVIDIA Treiber & Tools...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: NVIDIA GRAFIKTREIBER & MONITOR", tag="INFO")
                self.log("=" * 60, tag="INFO")
                kernel_rel = platform.release()

                # --- Secure Boot pruefen -------------------------------------
                # Haeufigste Ursache fuer "Treiber ist installiert, aber nach dem
                # Neustart bleibt der Bildschirm schwarz": das per DKMS gebaute
                # Modul ist unsigniert und wird bei aktivem Secure Boot blockiert.
                sb_state = ""
                try:
                    sbp = subprocess.run(["mokutil", "--sb-state"],
                                         capture_output=True, text=True, timeout=5)
                    sb_state = (sbp.stdout + sbp.stderr).strip()
                except Exception:
                    sb_state = ""
                self.log(f"Secure-Boot-Status: {sb_state or 'nicht ermittelbar (mokutil fehlt)'}", tag="INFO")
                if "enabled" in sb_state.lower():
                    warn = (
                        "SECURE BOOT IST AKTIV. Der NVIDIA-Treiber wird per DKMS gebaut; "
                        "ein unsigniertes Modul laedt dann NICHT (schwarzer Bildschirm nach "
                        "Neustart). Loesung: Secure Boot im BIOS/UEFI abschalten oder das "
                        "Modul per MOK signieren."
                    )
                    for _ in range(1):
                        self.log("!" * 60, tag="WARN")
                        self.log(warn, tag="WARN")
                        self.log("!" * 60, tag="WARN")
                    self.warnings.append("NVIDIA: " + warn)

                # --- non-free Komponenten sind Pflicht fuer nvidia-driver ----
                self.run_cmd(
                    "grep -rhoE 'non-free[a-z-]*' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null "
                    "| sort -u | grep . "
                    "|| echo 'WARNUNG: keine non-free Komponente in den Paketquellen gefunden'",
                    "Kontrolle: non-free Paketquellen", critical=False
                )

                # --- Kernel-Header: erst exakt, dann generisch ---------------
                self.run_cmd(
                    f"apt-get install -y linux-headers-{kernel_rel} "
                    f"|| apt-get install -y linux-headers-$(dpkg --print-architecture) "
                    f"|| apt-get install -y linux-headers-amd64",
                    f"Kernel-Header fuer {kernel_rel} installieren", critical=False
                )
                self.apt_install(["dkms", "build-essential"], "Build-Umgebung fuer Kernelmodule")

                # --- Treiber & Werkzeuge -------------------------------------
                self.apt_install(
                    ["nvidia-driver", "nvidia-kernel-dkms", "nvidia-settings",
                     "firmware-misc-nonfree", "nvtop", "vulkan-tools", "libvulkan1"],
                    "NVIDIA Treiber, Settings, nvtop & Vulkan"
                )

                # --- 32-Bit Bibliotheken -------------------------------------
                # Ohne die startet unter Steam kein einziges Spiel ("missing
                # 32-bit OpenGL driver"). Nur sinnvoll, wenn Steam mit drauf soll.
                if self.selections.get("steam"):
                    self.run_cmd("dpkg --add-architecture i386",
                                 "32-Bit Architektur sicherstellen", critical=False)
                    self._apt_updated = False   # nach add-architecture neu einlesen
                    self.apt_install(
                        ["nvidia-driver-libs:i386", "libgl1:i386", "libvulkan1:i386"],
                        "32-Bit NVIDIA- & Vulkan-Bibliotheken fuer Steam"
                    )

                # --- Kontrolle ------------------------------------------------
                self.run_cmd(
                    "echo '--- DKMS ---'; dkms status 2>/dev/null | grep -i nvidia "
                    "|| echo 'Noch kein NVIDIA-DKMS-Modul aktiv (vor dem Neustart normal)'; "
                    "echo '--- geladene Module ---'; lsmod | grep -iE '^nvidia|^nouveau' "
                    "|| echo 'Weder nvidia noch nouveau geladen'",
                    "Kontrolle: NVIDIA-Kernelmodul", critical=False
                )

                self.installed_items.append("NVIDIA Treiber, nvidia-settings & nvtop GPU-Monitor")
                self.warnings.append(
                    "NVIDIA: Neustart noetig - erst danach loest der neue Treiber "
                    "den nouveau-Treiber ab."
                )

            # -------------------------------------------------------------
            # STEP: AMD RADEON TOOLS
            # -------------------------------------------------------------
            if "amd_radeon" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere AMD Radeon Tools...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: AMD RADEON GRAFIK FIRMWARE & TOOLS", tag="INFO")
                self.log("=" * 60, tag="INFO")
                self.apt_install(["firmware-amd-graphics", "mesa-vulkan-drivers", "vulkan-tools",
                                  "radeontop", "nvtop"], "AMD Grafik-Firmware, Vulkan & Monitoring")
                self.installed_items.append("AMD Radeon Firmware, Vulkan & nvtop")

            # -------------------------------------------------------------
            # STEP: PARROT DRIVERS & DKMS
            # -------------------------------------------------------------
            if "parrot_drivers" in steps:
                current += 1
                self.prog_cb(int((current / total_steps) * 100), "Installiere Parrot Treiber-Metapaket...")
                self.log("=" * 60, tag="INFO")
                self.log("SCHRITT: PARROT DRIVERS & BASIS-TOOLS", tag="INFO")
                self.log("=" * 60, tag="INFO")
                self.apt_install(["parrot-drivers", "build-essential", "dkms"],
                                 "Parrot Drivers Metapaket & DKMS")
                self.installed_items.append("Parrot Treiber-Paket & DKMS")

            self.prog_cb(100, "Fertig!")
            self.log("=" * 60, tag="OK")
            self.log("INSTALLATION & KONFIGURATION ERFOLGREICH BEENDET!", tag="OK")
            self.log("=" * 60, tag="OK")
            self.success = True
            self.finish_cb(True, "Alle ausgewählten Elemente wurden erfolgreich eingerichtet.")

        except Exception as e:
            self.log(f"Unerwarteter Fehler aufgetreten: {e}", tag="ERROR")
            self.finish_cb(False, str(e))
        finally:
            self.is_running = False


# =============================================================================
# MODERN TKINTER GUI WIZARD
# =============================================================================
class SetupAssistantGUI:
    def __init__(self, root, info):
        self.root = root
        self.info = info
        self.worker = None

        self.root.title("Parrot OS – Setup & Styling Assistent")
        self.root.geometry("900x700")
        self.root.minsize(840, 640)
        self.root.configure(bg="#0d1117")

        # Color Palette
        self.c_bg = "#0d1117"
        self.c_card = "#161b22"
        self.c_card_border = "#30363d"
        self.c_accent = "#00d285"       # Parrot Neon Teal/Green
        self.c_accent_hover = "#00ff9f"
        self.c_text = "#f0f6fc"
        self.c_text_muted = "#8b949e"
        self.c_nvidia = "#76b900"
        self.c_amd = "#ff7b72"
        self.c_antigravity = "#38bdf8"
        self.c_pink = "#f472b6"
        self.c_term_bg = "#030712"
        self.c_term_fg = "#4ade80"

        # Checkbox variables
        self.var_keyboard_fix = tk.BooleanVar(value=not info["is_keyboard_de"])
        self.var_pink_accent_wallpaper = tk.BooleanVar(value=True)
        self.var_kde_themes = tk.BooleanVar(value=True)
        self.var_steam = tk.BooleanVar(value=True)
        # Nur vorauswählen, wenn das Archiv wirklich vorliegt (~164 MB, liegt
        # nicht im Repo) – sonst liefe der Schritt garantiert ins Leere.
        self.var_antigravity = tk.BooleanVar(value=bool(info["antigravity_archive"]))
        self.var_claude = tk.BooleanVar(value=True)
        self.var_update = tk.BooleanVar(value=True)
        self.var_amd_ryzen = tk.BooleanVar(value=info["is_amd_cpu"])
        self.var_nvidia = tk.BooleanVar(value=info["has_nvidia"])
        self.var_amd_radeon = tk.BooleanVar(value=info["has_amd_gpu"])
        self.var_parrot_drivers = tk.BooleanVar(value=True)
        self.password_var = tk.StringVar()

        # Build Container
        self.container = tk.Frame(self.root, bg=self.c_bg)
        self.container.pack(fill="both", expand=True)

        self.pages = {}
        self._create_header()
        self._create_page_welcome()
        self._create_page_selection()
        self._create_page_password()
        self._create_page_progress()
        self._create_page_finished()

        self.show_page("welcome")

    def _create_header(self):
        header_frame = tk.Frame(self.container, bg="#161b22", height=70, bd=0)
        header_frame.pack(fill="x", side="top")

        title_box = tk.Frame(header_frame, bg="#161b22")
        title_box.pack(side="left", padx=25, pady=12)

        lbl_title = tk.Label(
            title_box,
            text="🦜 PARROT OS SETUP & STYLING ASSISTENT",
            font=("Segoe UI", 15, "bold"),
            bg="#161b22",
            fg=self.c_accent
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            title_box,
            text="System, Antigravity, Claude, Steam, KDE-Designs, Rosa Akzent & Tastatur-Fix",
            font=("Segoe UI", 9),
            bg="#161b22",
            fg=self.c_text_muted
        )
        lbl_sub.pack(anchor="w")

        self.lbl_step = tk.Label(
            header_frame,
            text="Schritt 1 von 4",
            font=("Segoe UI", 10, "bold"),
            bg="#21262d",
            fg=self.c_text,
            padx=12,
            pady=4
        )
        self.lbl_step.pack(side="right", padx=25, pady=18)

        sep = tk.Frame(self.container, bg=self.c_card_border, height=1)
        sep.pack(fill="x")

    def show_page(self, page_name):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[page_name].pack(fill="both", expand=True, padx=25, pady=12)

        step_map = {
            "welcome": "Schritt 1: Diagnose",
            "selection": "Schritt 2: Auswahl & Styling",
            "password": "Schritt 3: Bestätigung",
            "progress": "Schritt 4: Ausführung",
            "finished": "Fertiggestellt 🎉"
        }
        self.lbl_step.config(text=step_map.get(page_name, ""))

    # -------------------------------------------------------------------------
    # PAGE 1: WELCOME & HARDWARE DETECTION
    # -------------------------------------------------------------------------
    def _create_page_welcome(self):
        p = tk.Frame(self.container, bg=self.c_bg)
        self.pages["welcome"] = p

        intro_lbl = tk.Label(
            p,
            text="Hallo! Dieser Assistent richtet dein Parrot OS komplett & optimal ein.",
            font=("Segoe UI", 13, "bold"),
            bg=self.c_bg,
            fg=self.c_text
        )
        intro_lbl.pack(anchor="w", pady=(0, 2))

        desc_lbl = tk.Label(
            p,
            text="Systemanalyse und vordefinierte Einstellungen für Hardware, Styling & Apps:",
            font=("Segoe UI", 10),
            bg=self.c_bg,
            fg=self.c_text_muted
        )
        desc_lbl.pack(anchor="w", pady=(0, 8))

        # Hardware Card
        card = tk.Frame(p, bg=self.c_card, bd=1, highlightbackground=self.c_card_border, highlightthickness=1)
        card.pack(fill="x", pady=4, ipady=6, padx=2)

        # OS Row
        self._add_info_row(card, "🐧 Betriebssystem", f"{self.info['os_name']} (Kernel {self.info['kernel']})", self.c_accent)
        
        # Keyboard Check Row
        if not self.info["is_keyboard_de"]:
            kb_status = f"Aktuell '{self.info['keyboard_layout']}' ➔ FIX: Umstellung auf Deutsch (AltGr+Q für '@')"
            kb_color = "#f85149"
        else:
            kb_status = "Deutsches QWERTZ-Layout aktiv (AltGr+Q für '@' funktioniert)"
            kb_color = self.c_accent
        self._add_info_row(card, "⌨️ Tastatur-Layout", kb_status, kb_color)

        # CPU Row
        cpu_text = f"{self.info['cpu_model']} ({self.info['cpu_cores']} Kerne)"
        cpu_badge = "🔥 AMD Ryzen erkannt! Microcode & Tweaks verfügbar" if self.info["is_amd_cpu"] else "Intel Prozessor erkannt"
        self._add_info_row(card, "⚡ Prozessor (CPU)", f"{cpu_text} | {cpu_badge}", self.c_amd if self.info["is_amd_cpu"] else self.c_text)

        # GPU Row
        gpus_text = ", ".join(self.info["gpus"]) if self.info["gpus"] else "Standard VGA Controller"
        if self.info["has_nvidia"]:
            gpu_badge = "🟢 NVIDIA erkannt! Treiber & nvtop verfügbar"
            color = self.c_nvidia
        elif self.info["has_amd_gpu"]:
            gpu_badge = "🔴 AMD Radeon erkannt! Vulkan & Firmware aktiv"
            color = self.c_amd
        else:
            gpu_badge = "Standard Grafikkarte"
            color = self.c_text
        self._add_info_row(card, "🎮 Grafikkarte (GPU)", f"{gpus_text} | {gpu_badge}", color)

        # Antigravity Status
        if self.info["is_antigravity_installed"]:
            ag_status = "Bereits installiert"
            ag_color = self.c_accent
        elif self.info["antigravity_archive"]:
            ag_status = "Archiv gefunden – bereit zur Installation mit Desktop-UI & Starter"
            ag_color = self.c_antigravity
        else:
            ag_status = "Kein Archiv gefunden – 'Antigravity.tar.gz' in diesen Ordner legen"
            ag_color = self.c_text_muted
        self._add_info_row(card, "🌌 Google Antigravity", ag_status, ag_color)

        # KDE Themes & Rosa Accent
        self._add_info_row(card, "🎨 KDE Themes & Rosa", "Arc-Dark, Arc-ICONS, Win10-Dark, Kuro the Cat, SDDM & Rosa Akzent bereit", self.c_pink)

        # Steam Status
        self._add_info_row(card, "🕹️ Valve Steam", "Steam-Paket & 32-Bit Spiele-Bibliotheken bereit", self.c_accent)

        # Bottom Button
        btn_frame = tk.Frame(p, bg=self.c_bg)
        btn_frame.pack(fill="x", side="bottom", pady=8)

        btn_next = tk.Button(
            btn_frame,
            text="Weiter zur Auswahl & Anpassung  ➔",
            font=("Segoe UI", 11, "bold"),
            bg=self.c_accent,
            fg="#0b1015",
            activebackground=self.c_accent_hover,
            activeforeground="#0b1015",
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2",
            command=lambda: self.show_page("selection")
        )
        btn_next.pack(side="right")

    def _add_info_row(self, parent, label, val, val_color):
        row = tk.Frame(parent, bg=self.c_card)
        row.pack(fill="x", padx=16, pady=4)
        
        lbl = tk.Label(row, text=label, font=("Segoe UI", 10, "bold"), bg=self.c_card, fg=self.c_text, width=22, anchor="w")
        lbl.pack(side="left")

        val_lbl = tk.Label(row, text=val, font=("Segoe UI", 9), bg=self.c_card, fg=val_color, justify="left", anchor="w")
        val_lbl.pack(side="left", fill="x", expand=True)

    # -------------------------------------------------------------------------
    # PAGE 2: SELECTION & PACKAGES
    # -------------------------------------------------------------------------
    def _create_page_selection(self):
        p = tk.Frame(self.container, bg=self.c_bg)
        self.pages["selection"] = p

        intro_lbl = tk.Label(
            p,
            text="Wähle die gewünschten Aktionen und Anpassungen:",
            font=("Segoe UI", 12, "bold"),
            bg=self.c_bg,
            fg=self.c_text
        )
        intro_lbl.pack(anchor="w", pady=(0, 4))

        # Canvas with scrollbar for clean card list
        canvas_frame = tk.Frame(p, bg=self.c_bg)
        canvas_frame.pack(fill="both", expand=True, pady=4)

        canvas = tk.Canvas(canvas_frame, bg=self.c_bg, highlightthickness=0, bd=0)
        scrollbar = tk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scroll_content = tk.Frame(canvas, bg=self.c_card, bd=1, highlightbackground=self.c_card_border, highlightthickness=1)

        scroll_content.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scroll_content, anchor="nw", width=840)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # Checkboxes
        self._add_checkbox_item(
            scroll_content,
            self.var_keyboard_fix,
            "⌨️ Tastatur-Fix (@-Zeichen & Deutsches Layout)",
            "Stellt das Tastaturlayout dauerhaft auf Deutsch (QWERTZ) um, damit das '@'-Zeichen mit [AltGr] + [Q] einwandfrei getippt werden kann."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_pink_accent_wallpaper,
            "🌸 Fenster-Akzentfarbe auf Rosa / Pink (#e93a9a) & Wallpaper",
            "Aktiviert die moderne rosa Akzentfarbe für alle Fenster und setzt dein Hintergrundbild (IMG_1685.png) als neuen Desktop-Hintergrund."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_kde_themes,
            "🎨 KDE Plasma Designs als Standard setzen",
            "Installiert und setzt als Standard: Arc-Dark Theme, Arc-ICONS, Windows 10 Dark Fensterdekoration, Kuro the Cat Ladebildschirm & SDDM Login Themes."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_antigravity,
            "🌌 Google Antigravity 2.0 (Desktop-UI & Entwicklungsplattform)",
            "Installiert die Antigravity 2.0 Desktop-Anwendung samt Startmenü-Starter. "
            "Setzt voraus, dass 'Antigravity.tar.gz' in diesem Ordner oder in ~/Downloads liegt "
            "(nicht im Paket enthalten, ca. 164 MB)."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_claude,
            "🤖 Claude Desktop (Community-Build)",
            "Installiert Claude Desktop samt Starter im Startmenü und Schlüsselbund. "
            "Achtung: Anthropic bietet kein offizielles Linux-Paket an – die Installation "
            "bindet das fremde Repository pkg.claude-desktop-debian.dev mit eigenem "
            "GPG-Schlüssel ein. Wer das nicht möchte, lässt dieses Häkchen weg."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_steam,
            "🕹️ Valve Steam (Gaming-Plattform)",
            "Installiert Steam aus den Parrot-Paketquellen (steam-installer), aktiviert die "
            "32-Bit (i386) Spiele-Bibliotheken und richtet den Starter ein."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_update,
            "🔄 Parrot OS System-Updates (Sudo)",
            "Führt 'apt update' & 'full-upgrade' durch, behebt Sicherheitslücken und bringt alle Pakete auf den neuesten Stand."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_amd_ryzen,
            "⚡ AMD Ryzen Optimierungen (Microcode & Sensoren)",
            "Installiert 'amd64-microcode' (Stabilität für Zen-CPUs), 'lm-sensors' (Temperaturüberwachung) und 'gamemode'."
        )

        self._add_checkbox_item(
            scroll_content,
            self.var_nvidia,
            "🟢 NVIDIA Treiber & Tools (Treiber, Settings, nvtop)",
            "Offizieller proprietärer NVIDIA-Treiber, grafische Systemsteuerung 'nvidia-settings' und 'nvtop' (Live-GPU Monitor)."
        )

        if self.info["has_amd_gpu"]:
            self._add_checkbox_item(
                scroll_content,
                self.var_amd_radeon,
                "🔴 AMD Radeon Grafik-Firmware & Vulkan Tools",
                "Installiert 'firmware-amd-graphics', Vulkan 3D-Beschleuniger und 'radeontop'/'nvtop' für GPU-Statistiken."
            )

        self._add_checkbox_item(
            scroll_content,
            self.var_parrot_drivers,
            "🦜 Zusätzliche Parrot Treiber & DKMS",
            "Metapaket 'parrot-drivers' für verbesserte Hardwareunterstützung (WLAN, Bluetooth) und automatische Kernelmodul-Verwaltung."
        )

        # Buttons
        btn_frame = tk.Frame(p, bg=self.c_bg)
        btn_frame.pack(fill="x", side="bottom", pady=6)

        btn_back = tk.Button(
            btn_frame,
            text="◀  Zurück",
            font=("Segoe UI", 10),
            bg="#21262d",
            fg=self.c_text,
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=lambda: self.show_page("welcome")
        )
        btn_back.pack(side="left")

        btn_next = tk.Button(
            btn_frame,
            text="Weiter zur Bestätigung  ➔",
            font=("Segoe UI", 11, "bold"),
            bg=self.c_accent,
            fg="#0b1015",
            activebackground=self.c_accent_hover,
            activeforeground="#0b1015",
            bd=0,
            padx=20,
            pady=9,
            cursor="hand2",
            command=self._on_selection_next
        )
        btn_next.pack(side="right")

    def _add_checkbox_item(self, parent, var, title, desc):
        item_frame = tk.Frame(parent, bg=self.c_card)
        item_frame.pack(fill="x", padx=16, pady=4)

        cb = tk.Checkbutton(
            item_frame,
            text=title,
            variable=var,
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg=self.c_text,
            selectcolor="#21262d",
            activebackground=self.c_card,
            activeforeground=self.c_accent,
            bd=0,
            anchor="w"
        )
        cb.pack(anchor="w")

        desc_lbl = tk.Label(
            item_frame,
            text=desc,
            font=("Segoe UI", 9),
            bg=self.c_card,
            fg=self.c_text_muted,
            anchor="w",
            padx=25
        )
        desc_lbl.pack(anchor="w")

    def _on_selection_next(self):
        if os.geteuid() == 0:
            self.start_installation()
        else:
            self.show_page("password")

    # -------------------------------------------------------------------------
    # PAGE 3: SUDO PASSWORD CONFIRMATION
    # -------------------------------------------------------------------------
    def _create_page_password(self):
        p = tk.Frame(self.container, bg=self.c_bg)
        self.pages["password"] = p

        intro_lbl = tk.Label(
            p,
            text="🔒 Administrator-Rechte (Sudo)",
            font=("Segoe UI", 14, "bold"),
            bg=self.c_bg,
            fg=self.c_text
        )
        intro_lbl.pack(anchor="w", pady=(10, 5))

        desc_lbl = tk.Label(
            p,
            text="Für die Installation von System-Updates, Treibern und Steam wird dein Administrator-Passwort benötigt.\nDas Passwort wird ausschließlich lokal für 'sudo' verwendet.",
            font=("Segoe UI", 10),
            bg=self.c_bg,
            fg=self.c_text_muted,
            justify="left"
        )
        desc_lbl.pack(anchor="w", pady=(0, 20))

        # Password Entry Card
        card = tk.Frame(p, bg=self.c_card, bd=1, highlightbackground=self.c_card_border, highlightthickness=1)
        card.pack(fill="x", pady=10, ipady=15, padx=2)

        lbl_pass = tk.Label(
            card,
            text="Gib dein Benutzer-Passwort ein:",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_card,
            fg=self.c_text
        )
        lbl_pass.pack(anchor="w", padx=25, pady=(5, 5))

        self.ent_password = tk.Entry(
            card,
            textvariable=self.password_var,
            show="•",
            font=("Segoe UI", 12),
            bg="#0d1117",
            fg="#ffffff",
            insertbackground=self.c_accent,
            bd=1,
            relief="flat",
            highlightthickness=1,
            highlightbackground=self.c_card_border
        )
        self.ent_password.pack(fill="x", padx=25, pady=5, ipady=6)
        self.ent_password.bind("<Return>", lambda e: self._on_password_submit())

        self.lbl_pw_error = tk.Label(
            card,
            text="",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_card,
            fg="#f85149"
        )
        self.lbl_pw_error.pack(anchor="w", padx=25, pady=(5, 0))

        # Buttons
        btn_frame = tk.Frame(p, bg=self.c_bg)
        btn_frame.pack(fill="x", side="bottom", pady=15)

        btn_back = tk.Button(
            btn_frame,
            text="◀  Zurück",
            font=("Segoe UI", 10),
            bg="#21262d",
            fg=self.c_text,
            bd=0,
            padx=15,
            pady=8,
            cursor="hand2",
            command=lambda: self.show_page("selection")
        )
        btn_back.pack(side="left")

        btn_start = tk.Button(
            btn_frame,
            text="Installation jetzt starten  🚀",
            font=("Segoe UI", 11, "bold"),
            bg=self.c_accent,
            fg="#0b1015",
            activebackground=self.c_accent_hover,
            activeforeground="#0b1015",
            bd=0,
            padx=22,
            pady=10,
            cursor="hand2",
            command=self._on_password_submit
        )
        btn_start.pack(side="right")

    def _on_password_submit(self):
        pw = self.password_var.get()
        if not pw:
            self.lbl_pw_error.config(text="Bitte gib dein Passwort ein.")
            return

        p = subprocess.run(["sudo", "-S", "-v"], input=f"{pw}\n", text=True, capture_output=True)
        if p.returncode != 0:
            self.lbl_pw_error.config(text="Falsches Passwort! Bitte versuche es erneut.")
            return

        self.lbl_pw_error.config(text="")
        self.start_installation()

    # -------------------------------------------------------------------------
    # PAGE 4: LIVE INSTALLATION & LOGS
    # -------------------------------------------------------------------------
    def _create_page_progress(self):
        p = tk.Frame(self.container, bg=self.c_bg)
        self.pages["progress"] = p

        self.lbl_prog_title = tk.Label(
            p,
            text="Installation & Personalisierung wird ausgeführt...",
            font=("Segoe UI", 13, "bold"),
            bg=self.c_bg,
            fg=self.c_text
        )
        self.lbl_prog_title.pack(anchor="w", pady=(0, 4))

        self.lbl_prog_status = tk.Label(
            p,
            text="Bereite Schritte vor...",
            font=("Segoe UI", 10),
            bg=self.c_bg,
            fg=self.c_accent
        )
        self.lbl_prog_status.pack(anchor="w", pady=(0, 8))

        self.prog_bar = ttk.Progressbar(p, orient="horizontal", mode="determinate")
        self.prog_bar.pack(fill="x", pady=(0, 10), ipady=3)

        lbl_console = tk.Label(
            p,
            text="Live-Ausgabe der Installation:",
            font=("Segoe UI", 9, "bold"),
            bg=self.c_bg,
            fg=self.c_text_muted
        )
        lbl_console.pack(anchor="w", pady=(0, 4))

        term_frame = tk.Frame(p, bg=self.c_term_bg, bd=1, highlightbackground=self.c_card_border, highlightthickness=1)
        term_frame.pack(fill="both", expand=True)

        self.txt_log = tk.Text(
            term_frame,
            bg=self.c_term_bg,
            fg=self.c_term_fg,
            insertbackground=self.c_accent,
            font=("DejaVu Sans Mono", 9),
            bd=0,
            padx=10,
            pady=10,
            wrap="char"
        )
        scroll = tk.Scrollbar(term_frame, command=self.txt_log.yview, bg=self.c_card)
        self.txt_log.configure(yscrollcommand=scroll.set)

        scroll.pack(side="right", fill="y")
        self.txt_log.pack(side="left", fill="both", expand=True)

    def append_log(self, text):
        def _update():
            self.txt_log.insert(tk.END, text)
            self.txt_log.see(tk.END)
        self.root.after(0, _update)

    def update_progress(self, percent, status_text):
        def _update():
            self.prog_bar["value"] = percent
            self.lbl_prog_status.config(text=f"[{percent}%] {status_text}")
        self.root.after(0, _update)

    def start_installation(self):
        self.show_page("progress")
        selections = {
            "keyboard_fix": self.var_keyboard_fix.get(),
            "pink_accent_wallpaper": self.var_pink_accent_wallpaper.get(),
            "kde_themes": self.var_kde_themes.get(),
            "steam": self.var_steam.get(),
            "system_update": self.var_update.get(),
            "claude": self.var_claude.get(),
            "antigravity": self.var_antigravity.get(),
            "amd_ryzen": self.var_amd_ryzen.get(),
            "nvidia": self.var_nvidia.get(),
            "amd_radeon": self.var_amd_radeon.get(),
            "parrot_drivers": self.var_parrot_drivers.get(),
            "local_claude_deb": self.info["local_claude_deb"],
            "antigravity_archive": self.info["antigravity_archive"],
            "steam_deb": self.info["steam_deb"],
            "wallpaper_path": self.info["wallpaper_path"]
        }

        self.worker = InstallerWorker(
            selections=selections,
            password=self.password_var.get(),
            log_callback=self.append_log,
            progress_callback=self.update_progress,
            finish_callback=self.on_installation_finished
        )
        self.worker.start()

    # -------------------------------------------------------------------------
    # PAGE 5: FINISHED & SUMMARY
    # -------------------------------------------------------------------------
    def _create_page_finished(self):
        p = tk.Frame(self.container, bg=self.c_bg)
        self.pages["finished"] = p

        self.lbl_finish_header = tk.Label(
            p,
            text="🎉 Alles erfolgreich eingerichtet & personalisiert!",
            font=("Segoe UI", 15, "bold"),
            bg=self.c_bg,
            fg=self.c_accent
        )
        self.lbl_finish_header.pack(anchor="w", pady=(6, 2))

        self.lbl_finish_sub = tk.Label(
            p,
            text="Dein Parrot OS ist jetzt auf dem neuesten Stand, designt und voll einsatzbereit.",
            font=("Segoe UI", 10),
            bg=self.c_bg,
            fg=self.c_text_muted
        )
        self.lbl_finish_sub.pack(anchor="w", pady=(0, 8))

        # Summary Card
        card = tk.Frame(p, bg=self.c_card, bd=1, highlightbackground=self.c_card_border, highlightthickness=1)
        card.pack(fill="both", expand=True, pady=2, ipady=6, padx=2)

        self.lbl_installed_summary = tk.Label(
            card,
            text="",
            font=("Segoe UI", 9),
            bg=self.c_card,
            fg=self.c_text,
            justify="left",
            anchor="nw",
            padx=18,
            pady=6
        )
        self.lbl_installed_summary.pack(fill="both", expand=True)

        # Info Box (Tips for her)
        tips_box = tk.Frame(card, bg="#21262d", bd=0)
        tips_box.pack(fill="x", padx=15, pady=(0, 8), ipady=6)

        tips_title = tk.Label(
            tips_box,
            text="💡 Wichtige Infos für dich:",
            font=("Segoe UI", 9, "bold"),
            bg="#21262d",
            fg=self.c_pink
        )
        tips_title.pack(anchor="w", padx=12, pady=(3, 2))

        tips_text = (
            "• Tastatur-Fix: '@' funktioniert jetzt normal mit [AltGr] + [Q] (oder rechte Alt-Taste + Q).\n"
            "• Design & Styling: Arc-Dark, Windows 10 Dark Fenstertitel, Kuro-Splash & Rosa-Akzentfarbe sind aktiv.\n"
            "• Apps: Antigravity, Claude Desktop & Steam findest du sofort im Startmenü.\n"
            "• GPU-Monitor: Tippe 'nvtop' ins Terminal für eine hübsche Live-Grafikkarteanzeige.\n"
            "• Neustart: Bitte starte das System einmal neu, damit alle Treiber und SDDM-Themes voll greifen!"
        )
        tips_lbl = tk.Label(
            tips_box,
            text=tips_text,
            font=("Segoe UI", 9),
            bg="#21262d",
            fg=self.c_text,
            justify="left"
        )
        tips_lbl.pack(anchor="w", padx=12, pady=(0, 3))

        # Bottom Buttons
        btn_frame = tk.Frame(p, bg=self.c_bg)
        btn_frame.pack(fill="x", side="bottom", pady=6)

        btn_launch_ag = tk.Button(
            btn_frame,
            text="Antigravity 🌌",
            font=("Segoe UI", 9, "bold"),
            bg="#0284c7",
            fg="#ffffff",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._launch_antigravity
        )
        btn_launch_ag.pack(side="left")

        btn_launch_claude = tk.Button(
            btn_frame,
            text="Claude 🤖",
            font=("Segoe UI", 9, "bold"),
            bg="#1f6feb",
            fg="#ffffff",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._launch_claude
        )
        btn_launch_claude.pack(side="left", padx=6)

        btn_launch_steam = tk.Button(
            btn_frame,
            text="Steam 🕹️",
            font=("Segoe UI", 9, "bold"),
            bg="#475569",
            fg="#ffffff",
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._launch_steam
        )
        btn_launch_steam.pack(side="left")

        btn_reboot = tk.Button(
            btn_frame,
            text="System neu starten  🔄",
            font=("Segoe UI", 9),
            bg="#21262d",
            fg=self.c_text,
            bd=0,
            padx=12,
            pady=7,
            cursor="hand2",
            command=self._reboot_system
        )
        btn_reboot.pack(side="left", padx=6)

        btn_close = tk.Button(
            btn_frame,
            text="Schließen  ✓",
            font=("Segoe UI", 10, "bold"),
            bg=self.c_accent,
            fg="#0b1015",
            bd=0,
            padx=16,
            pady=7,
            cursor="hand2",
            command=self.root.destroy
        )
        btn_close.pack(side="right")

    def on_installation_finished(self, success, message):
        def _update():
            if success:
                items_text = "Folgende Komponenten wurden erfolgreich eingerichtet:\n\n"
                for item in self.worker.installed_items:
                    items_text += f"  ✓  {item}\n"
                if self.worker.skipped_packages:
                    items_text += "\nNicht verfügbar und übersprungen:\n"
                    for pkg in self.worker.skipped_packages:
                        items_text += f"  –  {pkg}\n"
                if self.worker.warnings:
                    items_text += "\n⚠  BITTE BEACHTEN:\n"
                    for w in self.worker.warnings:
                        items_text += f"  !  {w}\n"
                self.lbl_installed_summary.config(text=items_text)
                self.show_page("finished")
            else:
                messagebox.showerror("Fehler bei der Installation", f"Es gab ein Problem:\n\n{message}")
                self.show_page("selection")
        self.root.after(0, _update)

    def _launch_antigravity(self):
        try:
            subprocess.Popen(["/opt/antigravity/antigravity"], start_new_session=True)
        except Exception:
            try:
                subprocess.Popen(["antigravity"], start_new_session=True)
            except Exception as e:
                messagebox.showinfo("Antigravity", f"Konnte Antigravity nicht direkt aufrufen ({e}). Suche einfach im Startmenü nach 'Antigravity'.")

    def _launch_claude(self):
        try:
            subprocess.Popen(["claude-desktop"], start_new_session=True)
        except Exception:
            try:
                subprocess.Popen(["claude"], start_new_session=True)
            except Exception as e:
                messagebox.showinfo("Claude", f"Konnte Claude nicht direkt aufrufen ({e}). Suche im Startmenü nach 'Claude'.")

    def _launch_steam(self):
        try:
            subprocess.Popen(["steam"], start_new_session=True)
        except Exception as e:
            messagebox.showinfo("Steam", f"Konnte Steam nicht direkt aufrufen ({e}). Suche im Startmenü nach 'Steam'.")

    def _reboot_system(self):
        if messagebox.askyesno("Neustart bestätigen", "Möchtest du das System jetzt wirklich neu starten?"):
            subprocess.run(["systemctl", "reboot"])


# =============================================================================
# CLI / TERMINAL FALLBACK (ANSI Colors)
# =============================================================================
def run_cli_mode(info):
    c_bold = "\033[1m"
    c_green = "\033[32m"
    c_teal = "\033[36m"
    c_red = "\033[31m"
    c_yellow = "\033[33m"
    c_pink = "\033[35m"
    c_reset = "\033[0m"

    print(f"\n{c_teal}{c_bold}==================================================================={c_reset}")
    print(f"{c_teal}{c_bold}        PARROT OS SETUP & STYLING ASSISTENT (CLI MODUS)            {c_reset}")
    print(f"{c_teal}{c_bold}==================================================================={c_reset}\n")

    print(f"{c_bold}SYSTEM-DIAGNOSE:{c_reset}")
    print(f"  • Betriebssystem: {info['os_name']} (Kernel {info['kernel']})")
    print(f"  • Prozessor:      {info['cpu_model']} ({info['cpu_cores']} Kerne)")
    if info["is_amd_cpu"]:
        print(f"    {c_green}➜ AMD Ryzen erkannt! Microcode & Tweaks verfügbar.{c_reset}")
    for g in info["gpus"]:
        print(f"  • Grafikkarte:    {g}")
    if info["has_nvidia"]:
        print(f"    {c_green}➜ NVIDIA GPU erkannt! Treiber & nvtop verfügbar.{c_reset}")
    elif info["has_amd_gpu"]:
        print(f"    {c_yellow}➜ AMD Radeon GPU erkannt! Firmware & Vulkan aktiv.{c_reset}")
    if info["antigravity_archive"]:
        print(f"  • Antigravity:    Archiv gefunden ({info['antigravity_archive']})")
    elif info["is_antigravity_installed"]:
        print(f"  • Antigravity:    bereits installiert")
    else:
        print(f"  • Antigravity:    {c_yellow}kein Archiv – 'Antigravity.tar.gz' hierher legen{c_reset}")
    print(f"  • Tastatur:       Layout '{info['keyboard_layout']}'")
    if not info["is_keyboard_de"]:
        print(f"    {c_red}➜ Kein deutsches Layout! Fix für '@'-Zeichen empfohlen.{c_reset}")
    else:
        print(f"    {c_green}➜ Deutsches Layout aktiv.{c_reset}")
    print()

    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    if auto_yes:
        print(f"{c_yellow}--yes: alle Vorgaben werden uebernommen.{c_reset}\n")

    def ask_yes_no(prompt, default=True):
        suffix = "[J/n]" if default else "[j/N]"
        if auto_yes:
            print(f"{c_bold}{prompt} {suffix}: {c_reset}{'ja' if default else 'nein'}")
            return default
        try:
            ans = input(f"{c_bold}{prompt} {suffix}: {c_reset}").strip().lower()
        except (EOFError, KeyboardInterrupt):
            # Kein Terminal (z.B. per Pipe gestartet) -> Vorgabe nehmen
            print()
            return default
        if not ans:
            return default
        return ans in ["j", "ja", "y", "yes"]

    selections = {
        "keyboard_fix": ask_yes_no("Tastatur-Fix (@-Zeichen / Deutsches QWERTZ Layout)?", not info["is_keyboard_de"]),
        "pink_accent_wallpaper": ask_yes_no("Rosa Akzentfarbe & Hintergrundbild aktivieren?", True),
        "kde_themes": ask_yes_no("KDE Plasma Designs als Standard setzen (Arc, Kuro, Win10)?", True),
        "antigravity": ask_yes_no(
            "Google Antigravity 2.0 (Desktop-UI) installieren?"
            + ("" if info["antigravity_archive"] else "  [Archiv fehlt – wird übersprungen]"),
            bool(info["antigravity_archive"])),
        "claude": ask_yes_no("Claude Desktop installieren? (Community-Build, nicht von Anthropic)", True),
        "steam": ask_yes_no("Valve Steam (Gaming-Plattform) installieren?", True),
        "system_update": ask_yes_no("Parrot OS System-Updates durchführen?", True),
        "amd_ryzen": ask_yes_no("AMD Ryzen Optimierungen (Microcode & Sensoren)?", info["is_amd_cpu"]),
        "nvidia": ask_yes_no("NVIDIA Treiber, nvidia-settings & nvtop installieren?", info["has_nvidia"]),
        "amd_radeon": ask_yes_no("AMD Radeon Firmware & Vulkan Tools installieren?", info["has_amd_gpu"]),
        "parrot_drivers": ask_yes_no("Zusätzliche Parrot Treiber & DKMS installieren?", True),
        "local_claude_deb": info["local_claude_deb"],
        "antigravity_archive": info["antigravity_archive"],
        "steam_deb": info["steam_deb"],
        "wallpaper_path": info["wallpaper_path"]
    }

    password = ""
    if os.geteuid() != 0:
        import getpass
        versuche = 3
        for versuch in range(1, versuche + 1):
            try:
                password = getpass.getpass("\n🔑 Sudo-Passwort für die Installation eingeben: ")
            except (EOFError, KeyboardInterrupt):
                # Ohne Terminal (Pipe, /dev/null) gab es hier vorher einen
                # Python-Traceback statt einer verständlichen Meldung.
                print(f"\n{c_red}Abgebrochen: keine Passworteingabe möglich.{c_reset}")
                print("Der Assistent braucht ein echtes Terminal. Bitte direkt aufrufen:")
                print("  ./start.sh --cli\n")
                return
            p = subprocess.run(["sudo", "-S", "-v"], input=f"{password}\n",
                               text=True, capture_output=True)
            if p.returncode == 0:
                break
            err = (p.stderr or "").strip()
            if "not in the sudoers" in err or "not allowed" in err:
                benutzer = os.environ.get("USER", "BENUTZER")
                print(f"\n{c_red}Der Benutzer '{benutzer}' darf kein sudo ausführen.{c_reset}")
                print("Ein Administrator muss ihn zur Gruppe 'sudo' hinzufügen:")
                print(f"  usermod -aG sudo {benutzer}\n")
                return
            if versuch < versuche:
                print(f"{c_red}Falsches Passwort ({versuch}/{versuche}), bitte erneut eingeben.{c_reset}")
            else:
                print(f"\n{c_red}Dreimal falsch – abgebrochen. Es wurde nichts verändert.{c_reset}\n")
                return

    print(f"\n{c_green}{c_bold}Starte Installation & Styling... Bitte warten!{c_reset}\n")

    done_event = threading.Event()
    def cli_log(text):
        sys.stdout.write(text)
        sys.stdout.flush()

    def cli_prog(percent, status):
        print(f"\n{c_teal}>>> [{percent}%] {status}{c_reset}")

    def cli_finish(success, msg):
        done_event.set()

    worker = InstallerWorker(
        selections=selections,
        password=password,
        log_callback=cli_log,
        progress_callback=cli_prog,
        finish_callback=cli_finish
    )
    worker.start()
    done_event.wait()

    if worker.success:
        print(f"\n{c_green}{c_bold}==================================================================={c_reset}")
        print(f"{c_green}{c_bold}            INSTALLATION & STYLING ERFOLGREICH!                    {c_reset}")
        print(f"{c_green}{c_bold}==================================================================={c_reset}")
        print("Tipps:")
        print(" • Tastatur: '@' funktioniert ab sofort mit [AltGr] + [Q].")
        print(" • Designs & Rosa-Akzent sind aktiv.")
        print(" • Antigravity, Claude und Steam sind im Startmenü einsatzbereit.")
        print(" • Ein Systemneustart wird empfohlen: 'sudo reboot'\n")

        if worker.skipped_packages:
            print(f"{c_yellow}Nicht verfügbare Pakete (übersprungen):{c_reset}")
            for pkg in worker.skipped_packages:
                print(f"   – {pkg}")
            print()

        if worker.warnings:
            print(f"{c_yellow}{c_bold}BITTE BEACHTEN:{c_reset}")
            for w in worker.warnings:
                print(f"{c_yellow}   ! {w}{c_reset}")
            print()
    else:
        print(f"\n{c_red}Es ist ein Fehler aufgetreten.{c_reset}\n")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__)
        print("Aufruf:  ./start.sh [--cli] [--yes]\n")
        print("  --cli, -c   Terminal-Modus erzwingen (ohne grafische Oberflaeche)")
        print("  --yes, -y   Alle Vorgaben uebernehmen, nur noch nach dem Passwort fragen")
        print("  --help, -h  Diese Hilfe\n")
        return

    # NICHT mit sudo starten lassen: Path.home() waere dann /root und saemtliche
    # KDE-Einstellungen (Layout, Themes, Akzentfarbe, Wallpaper) landeten im
    # Root-Profil statt beim Benutzer - sichtbar waere davon nichts.
    if os.geteuid() == 0 and os.environ.get("SUDO_USER"):
        print("\n\033[31m\033[1mBitte NICHT mit sudo starten.\033[0m\n")
        print("Der Assistent fragt das Passwort selbst ab. Mit sudo landen deine")
        print("Tastatur-, Design- und Hintergrundeinstellungen im Profil von 'root'")
        print("und du siehst auf dem Desktop keinerlei Aenderung.\n")
        print("  Richtig:  ./start.sh")
        print("  Falsch:   sudo ./start.sh\n")
        sys.exit(1)

    info = get_system_info()

    force_cli = "--cli" in sys.argv or "-c" in sys.argv
    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

    if force_cli or not has_display or not HAS_TK:
        if not HAS_TK and not force_cli and has_display:
            print("Hinweis: python3-tk fehlt - starte im Terminal-Modus.")
            print("Grafische Oberflaeche nachruesten: sudo apt install -y python3-tk\n")
        run_cli_mode(info)
        return

    try:
        root = tk.Tk()
        SetupAssistantGUI(root, info)
        root.mainloop()
    except Exception as e:
        print(f"Konnte die grafische Oberflaeche nicht starten ({e}). Wechsle in den Terminal-Modus...")
        run_cli_mode(info)

if __name__ == "__main__":
    main()
