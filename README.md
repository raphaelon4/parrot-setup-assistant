# 🦜 Parrot OS Setup- & Styling-Assistent

Ein Einrichtungs-Assistent für **Parrot Security OS mit KDE Plasma 6** – mit grafischer
Oberfläche (Dark Mode) und Terminal-Modus. Er erkennt die Hardware selbst und schlägt nur
das vor, was zu diesem Rechner passt.

Schwerpunkt sind die zwei Dinge, die nach einer frischen Installation am häufigsten hängen:
das **Tastaturlayout** und der **NVIDIA-Treiber**.

---

## 🚀 Schnellstart (Terminal)

```bash
git clone https://github.com/raphaelon4/parrot-setup-assistant.git
```

```bash
cd parrot-setup-assistant && ./start.sh
```

Das war's. Der Assistent fragt das Passwort selbst ab, wenn er es braucht.

> **Wichtig: nicht mit `sudo` starten.**
> Mit `sudo` wäre das Heimatverzeichnis `/root`, und Tastatur, Designs, Akzentfarbe und
> Hintergrundbild landeten im Root-Profil – auf dem Desktop würde sich nichts ändern.
> Der Assistent bricht in dem Fall mit einem Hinweis ab.

### Weitere Aufrufarten

| Befehl | Wirkung |
|---|---|
| `./start.sh` | Grafische Oberfläche (Rückfall auf Terminal, falls `python3-tk` fehlt) |
| `./start.sh --cli` | Terminal-Modus erzwingen |
| `./start.sh --yes` | Alle Vorgaben übernehmen, nur noch nach dem Passwort fragen |
| `./start.sh --help` | Hilfe anzeigen |

Alternativ lässt sich `Parrot-Setup-Assistent.desktop` doppelklicken.

**Voraussetzung für die grafische Oberfläche:**

```bash
sudo apt install -y python3-tk
```

---

## 🛠️ Was der Assistent macht

Alles ist einzeln an- und abwählbar. Vorausgewählt wird nur, was zur erkannten Hardware passt.

### ⌨️ 1. Tastatur-Fix – das `@` auf AltGr+Q

**Problem:** Steht das Layout auf US, liegt `@` auf `Shift+2`. Auf einer deutschen Tastatur
drückt man `AltGr+Q` – und bekommt nichts.

**Lösung:** Das Layout wird an *allen vier* Stellen dauerhaft auf Deutsch gesetzt, denn eine
allein reicht nicht:

| Stelle | Wofür |
|---|---|
| `/etc/default/keyboard` | Die eigentliche Quelle der Wahrheit auf Debian/Parrot – ohne die steht nach dem Neustart wieder `us` drin. Eine Sicherung wird als `.bak-parrot-setup` angelegt. |
| `~/.config/kxkbrc` | KDE Plasma (inkl. Variante, Modell `pc105` und globalem Umschaltmodus) |
| `localectl` | Systemd-Ebene für Konsole und X11 |
| `setxkbmap` | Die laufende Sitzung – wirkt nur unter X11 |

**Unter Wayland** (Plasma-6-Standard) greift das neue Layout erst nach dem nächsten
Anmelden. Der Assistent erkennt das und sagt es ausdrücklich dazu. Zum Schluss zeigt er,
was tatsächlich hinterlegt wurde.

### 🟢 2. NVIDIA-Treiber & Werkzeuge

Installiert `nvidia-driver`, `nvidia-kernel-dkms`, `nvidia-settings`, `nvtop` und Vulkan –
und prüft vorher das, woran es erfahrungsgemäß scheitert:

* **Secure-Boot-Prüfung.** Ist Secure Boot aktiv, lädt das per DKMS gebaute, unsignierte
  Kernelmodul nicht – klassisches Ergebnis: nach dem Neustart bleibt der Bildschirm
  schwarz. Der Assistent warnt vorher deutlich, statt dich hinterher raten zu lassen.
* **Kernel-Header.** Erst passgenau zur laufenden Version, sonst generisch als Rückfall.
* **`non-free`-Paketquellen.** Werden geprüft – ohne sie gibt es kein `nvidia-driver`.
* **32-Bit-Bibliotheken.** Wird Steam mitinstalliert, kommen `nvidia-driver-libs:i386` &
  Co. dazu. Ohne die startet unter Steam kein einziges Spiel.
* **Kontrolle am Ende.** DKMS-Status und geladene Kernelmodule werden ausgegeben.

Nach der Treiberinstallation ist ein **Neustart nötig** – erst dann löst der neue Treiber
`nouveau` ab.

### 🎨 3. KDE-Designs (mitgeliefert, keine Downloads nötig)

| Bereich | Design |
|---|---|
| Plasma-Theme | Arc-Dark |
| Icons | Arc-ICONS |
| Fensterdekoration | Windows 10 Dark (Aurorae) |
| Ladebildschirm | Kuro the Cat, Casper the Morning Star |
| Anmeldebildschirm (SDDM) | KDE-Story, sddm_wynn |

### 🌸 4. Rosa Akzentfarbe & Hintergrundbild

Setzt die Plasma-Akzentfarbe auf `#e93a9a` und aktiviert das mitgelieferte Wallpaper.

Dabei wird `AccentColorFromWallpaper` abgeschaltet – sonst überschreibt Plasma die Farbe
beim nächsten Hintergrundwechsel wieder automatisch.

### ⚡ 5. AMD Ryzen

`amd64-microcode` (Stabilität für Zen-CPUs), `lm-sensors` (Temperaturen) und `gamemode`.

### 🔴 6. AMD Radeon

`firmware-amd-graphics`, Mesa-Vulkan und `radeontop` – wird nur angeboten, wenn eine
Radeon-Karte erkannt wurde.

### 🕹️ 7. Valve Steam

Aktiviert die 32-Bit-Architektur (`dpkg --add-architecture i386`) und installiert Steam aus
den Parrot-Paketquellen (`steam-installer`).

### 🔄 8. System-Updates & Parrot-Treiber

`apt update` + `full-upgrade` + Bereinigung, dazu das Metapaket `parrot-drivers` und `dkms`.

### 🤖 9. Claude Desktop *(optional)*

> **Zur Einordnung:** Anthropic bietet derzeit **kein** offizielles Claude Desktop für Linux
> an. Der Assistent bindet dafür das Community-Repository `pkg.claude-desktop-debian.dev`
> ein – also eine **fremde Paketquelle mit fremdem GPG-Schlüssel**. Das ist eine bewusste
> Entscheidung; der Assistent weist im Protokoll und in der Zusammenfassung darauf hin.
> Wer das nicht möchte, nimmt einfach das Häkchen raus.

### 🌌 10. Google Antigravity *(nicht im Paket enthalten)*

Das Archiv ist rund 164 MB groß und liegt deshalb **nicht** im Repository.

Zum Installieren `Antigravity.tar.gz` in den Ordner des Assistenten oder nach `~/Downloads`
legen und den Assistenten erneut starten – er findet es dann von selbst. Fehlt es, wird der
Punkt sauber übersprungen und in der Zusammenfassung vermerkt.

---

## 💡 Nach der Installation

* **`@` tippen:** `AltGr + Q` (die rechte Alt-Taste). Unter Wayland erst nach dem nächsten
  Anmelden.
* **Neustart:** `sudo reboot` – nötig für NVIDIA-Treiber und SDDM-Design.
* **Grafikkarte beobachten:** `nvtop` im Terminal.
* **Apps:** Steam und – falls gewählt – Claude und Antigravity liegen im Anwendungsmenü.

Am Ende zeigt der Assistent drei Blöcke: was eingerichtet wurde, welche Pakete auf diesem
System nicht verfügbar waren, und was du noch selbst erledigen musst (z. B. Secure Boot).

---

## 🔍 Wenn etwas nicht klappt

| Symptom | Ursache & Lösung |
|---|---|
| `@` geht nach dem Neustart wieder nicht | `grep XKBLAYOUT /etc/default/keyboard` – muss `"de"` zeigen. Unter Wayland einmal ab- und anmelden. |
| Schwarzer Bildschirm nach NVIDIA-Neustart | Fast immer Secure Boot. Im BIOS/UEFI abschalten oder das Modul per MOK signieren. Prüfen mit `mokutil --sb-state`. |
| Spiele starten in Steam nicht | Die 32-Bit-Treiberbibliotheken fehlen. Assistent mit Steam **und** NVIDIA zusammen nochmal laufen lassen. |
| Rosa Akzentfarbe verschwindet | Passiert, wenn `AccentColorFromWallpaper` wieder aktiviert wurde – Punkt 4 erneut ausführen. |
| Keine grafische Oberfläche | `sudo apt install -y python3-tk`, oder `./start.sh --cli` benutzen. |
| „Bitte NICHT mit sudo starten" | Genau so gemeint: `./start.sh` ohne `sudo` aufrufen. |
| Einzelne Pakete fehlen | Der Assistent listet übersprungene Pakete am Ende auf. Nicht jedes Debian-Paket existiert auch auf Parrot – der Rest wird trotzdem installiert. |

Das vollständige Protokoll läuft während der Installation im Fenster bzw. im Terminal mit.

---

## 📋 Systemvoraussetzungen

* Parrot OS (oder ein anderes Debian-basiertes System) mit KDE Plasma 6
* `python3` – für die grafische Oberfläche zusätzlich `python3-tk`
* Ein Benutzerkonto mit `sudo`-Rechten
* Internetverbindung
