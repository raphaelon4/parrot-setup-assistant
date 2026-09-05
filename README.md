# 🦜 Parrot Installer – Discord & AnyDesk

Ein Installer für **Parrot Security OS** (und alles andere auf Debian-Basis), der
**Discord** und **AnyDesk** installiert und für beide ein **Symbol auf den Desktop** legt.

Einmal starten, einmal das Passwort – danach läuft alles allein durch.

---

## 🚀 Schnellstart

```bash
git clone https://github.com/raphaelon4/parrot-setup-assistant.git
```

```bash
cd parrot-setup-assistant && ./discord-anydesk-installer.sh
```

Alternativ `Discord-AnyDesk-Installer.desktop` doppelklicken.

Das Passwort fragt `sudo` selbst ab – das Skript sieht es nie und speichert es nirgends.

---

## 🛠️ Was passiert

| Schritt | |
|---|---|
| 1 | Architektur prüfen, `curl`/`gnupg` sicherstellen, Paketlisten auffrischen |
| 2 | **Discord** herunterladen und installieren |
| 3 | **AnyDesk** über sein offizielles Repository installieren |
| 4 | Für beide ein **Desktop-Symbol** anlegen |
| 5 | Ergebnis zusammenfassen – inklusive dem, was *nicht* geklappt hat |

### Aufrufarten

| Befehl | Wirkung |
|---|---|
| `./discord-anydesk-installer.sh` | Beides installieren + Desktop-Symbole |
| `./discord-anydesk-installer.sh --nur-discord` | Nur Discord |
| `./discord-anydesk-installer.sh --nur-anydesk` | Nur AnyDesk |
| `./discord-anydesk-installer.sh --ohne-symbole` | Nur installieren, kein Desktop-Symbol |
| `./discord-anydesk-installer.sh --help` | Hilfe anzeigen |

---

## 📦 Woher die Pakete kommen

| Programm | Quelle | Künftige Updates |
|---|---|---|
| **Discord** | offizieller Download-Link von `discord.com` | über Discords eigene Update-Abfrage |
| **AnyDesk** | offizielles AnyDesk-Repository, Schlüssel in `/etc/apt/keyrings/anydesk.gpg` | ganz normal über `sudo apt upgrade` |

Beim Discord-Link steht **keine feste Versionsnummer** im Skript – er zeigt immer auf die
aktuelle Version. Ein fest eingetragener Link wäre nach ein paar Wochen tot.

AnyDesk läuft bewusst über das Repository und nicht über ein einzelnes `.deb`: nur so kommen
Updates später automatisch mit. Ist das Repository nicht erreichbar, liest der Installer
dessen Paketliste aus und holt das `.deb` direkt – Ergebnis gleich, nur ohne Auto-Updates.

---

## 🖥️ Zu den Desktop-Symbolen

* Der Zielordner wird über `xdg-user-dir` bestimmt – heißt also je nach Sprache
  `Desktop` oder `Schreibtisch`, ohne Raterei.
* Existiert der Ordner nicht, wird er angelegt.
* Ist das Programm mit einem eigenen Starter gekommen, wird **dieser** kopiert (richtige
  Pfade, richtige Fensterklasse, übersetzte Namen). Nur falls keiner da ist, schreibt der
  Installer selbst einen.
* Die Starter werden **ausführbar** gemacht und als **vertrauenswürdig** markiert – so
  fragt KDE beim Doppelklick nicht „Anwendungsstarter nicht vertrauenswürdig" nach.

**Falls trotzdem keine Symbole zu sehen sind:** Dann steht der Plasma-Desktop auf dem Layout
„Arbeitsfläche", und das zeigt grundsätzlich keine Symbole an. Der Installer erkennt das und
sagt es am Ende ausdrücklich, statt scheinbar wirkungslos durchzulaufen. Umstellen:
Rechtsklick auf den Desktop → *Arbeitsflächen-Einstellungen* → Layout auf **Ordneransicht**.

---

## 🔍 Wenn etwas nicht klappt

| Meldung | Ursache & Lösung |
|---|---|
| `Download fehlgeschlagen` | Keine Internetverbindung, oder ein Proxy blockt. Verbindung prüfen, neu starten. |
| `Erster Versuch fehlgeschlagen – repariere Abhängigkeiten` | Normal. Der Installer setzt das Paket mit `dpkg` und lässt `apt` die Lücken schließen. |
| `Schlüssel von keys.anydesk.com nicht erreichbar` | Der Installer weicht automatisch auf den direkten Download aus. |
| `sudo merkt sich die Freigabe nicht` | Deine sudo-Konfiguration hat `timestamp_timeout=0`. Es kann erneut nach dem Passwort fragen – sonst ändert sich nichts. |
| Nur amd64/i386 | Discord und AnyDesk gibt es für ARM nicht. |

Der Installer bricht **nicht** beim ersten Fehler ab: schlägt eines der beiden Programme
fehl, wird das andere trotzdem fertig installiert. Am Ende steht schwarz auf weiß, was
durchging und was nicht, und der Rückgabewert ist entsprechend 0 oder 1.

---

## 📋 Voraussetzungen

* Debian-basiertes System (Parrot OS, Debian, Ubuntu, Kali …)
* Architektur **amd64** (AnyDesk läuft auch auf i386)
* Ein Benutzerkonto mit `sudo`-Recht
* Internetverbindung

Mit `sudo` gestartet funktioniert der Installer genauso wie ohne: er sucht dann den echten
Benutzer hinter `SUDO_USER`, damit die Symbole nicht im Desktop von `root` verschwinden.
