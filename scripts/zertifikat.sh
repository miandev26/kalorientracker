#!/usr/bin/env bash
# Erzeugt ein TLS-Zertifikat für den LAN-Zugriff.
#
# Ohne HTTPS gibt kein Browser die Kamera frei - auch nicht im eigenen Netz,
# auch nicht über VPN. Der Browser sieht nur "http://", und das gilt als
# unsicherer Kontext.
#
# Zwei Wege:
#   mkcert   -> eigene CA, einmal am Handy installiert, danach keine Warnung
#   openssl  -> selbstsigniert, Warnung muss einmal weggeklickt werden
#
# Aufruf:  ./scripts/zertifikat.sh [hostname] [ip ...]
# Beispiel: ./scripts/zertifikat.sh minipc.local 192.168.0.42

set -euo pipefail

ZIEL="${ZERT_DIR:-./data/certs}"
HOST="${1:-$(hostname)}"
shift || true
IPS=("$@")

# Keine IP übergeben? Die LAN-Adressen des Rechners selbst nehmen.
if [ ${#IPS[@]} -eq 0 ]; then
  mapfile -t IPS < <(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^(192\.168|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)' || true)
fi

mkdir -p "$ZIEL"

NAMEN=("$HOST" "${HOST%%.*}" "${HOST%%.*}.local" "${HOST%%.*}.fritz.box" "localhost")
# Doppelte entfernen
mapfile -t NAMEN < <(printf '%s\n' "${NAMEN[@]}" | awk '!seen[$0]++')

echo "Hostnamen: ${NAMEN[*]}"
echo "IP-Adressen: ${IPS[*]:-keine gefunden}"
echo

if command -v mkcert >/dev/null 2>&1; then
  echo "mkcert gefunden - Zertifikat wird von deiner lokalen CA signiert."
  mkcert -install
  mkcert -cert-file "$ZIEL/cert.pem" -key-file "$ZIEL/key.pem" \
         "${NAMEN[@]}" "${IPS[@]}"
  echo
  echo "Root-CA liegt hier:  $(mkcert -CAROOT)/rootCA.pem"
  echo "Diese Datei aufs Handy übertragen und installieren, dann ist die App"
  echo "dort ohne jede Zertifikatswarnung erreichbar:"
  echo "  iOS      Datei öffnen -> Einstellungen -> Profil laden ->"
  echo "           danach Einstellungen -> Allgemein -> Info ->"
  echo "           Zertifikatsvertrauen -> Schalter aktivieren"
  echo "  Android  Einstellungen -> Sicherheit -> Verschlüsselung ->"
  echo "           Zertifikat installieren -> CA-Zertifikat"
else
  echo "mkcert ist nicht installiert - erzeuge ein selbstsigniertes Zertifikat."
  echo "(Empfehlung: 'apt install mkcert' oder von GitHub holen, dann"
  echo " entfällt die Browserwarnung am Handy.)"
  echo

  SAN=""
  for n in "${NAMEN[@]}"; do SAN+="DNS:$n,"; done
  for i in "${IPS[@]}"; do SAN+="IP:$i,"; done
  SAN+="IP:127.0.0.1"

  openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
    -keyout "$ZIEL/key.pem" -out "$ZIEL/cert.pem" \
    -subj "/CN=$HOST" \
    -addext "subjectAltName=$SAN" \
    -addext "basicConstraints=critical,CA:FALSE" \
    -addext "keyUsage=digitalSignature,keyEncipherment" \
    -addext "extendedKeyUsage=serverAuth" 2>/dev/null

  echo "Selbstsigniertes Zertifikat erstellt."
  echo "Beim ersten Aufruf zeigt der Browser eine Warnung. Einmal"
  echo "'Erweitert' -> 'Trotzdem fortfahren', danach ist der Kontext sicher"
  echo "und die Kamera funktioniert."
fi

chmod 600 "$ZIEL/key.pem"
echo
echo "Fertig:"
ls -l "$ZIEL"
echo
echo "Container neu starten:  docker compose restart"
echo "Aufruf am Handy:        https://${NAMEN[0]}:8443"
