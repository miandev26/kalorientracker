#!/bin/bash
# Startet die App. HTTP läuft immer, HTTPS zusätzlich, sobald unter
# /data/certs ein Zertifikat liegt. Zwei uvicorn-Prozesse auf derselben
# SQLite-Datei sind unkritisch, solange WAL aktiv ist - und das ist es.

set -e

ZERT=/data/certs/cert.pem
KEY=/data/certs/key.pem

uvicorn app.main:app --host 0.0.0.0 --port 8101 &
HTTP_PID=$!
echo "HTTP  auf Port 8101"

if [ -f "$ZERT" ] && [ -f "$KEY" ]; then
  uvicorn app.main:app --host 0.0.0.0 --port 8443 \
          --ssl-certfile "$ZERT" --ssl-keyfile "$KEY" &
  HTTPS_PID=$!
  echo "HTTPS auf Port 8443 - Kamera funktioniert nur über diesen Port"
else
  HTTPS_PID=""
  echo "HTTPS aus: kein Zertifikat unter /data/certs."
  echo "  -> ./scripts/zertifikat.sh ausführen, danach docker compose restart"
  echo "  -> ohne HTTPS bleibt der Scanner aus, die manuelle Eingabe geht"
fi

# Fällt einer der Prozesse aus, soll der Container sterben und neu starten.
trap 'kill $HTTP_PID $HTTPS_PID 2>/dev/null' TERM INT
wait -n $HTTP_PID $HTTPS_PID 2>/dev/null || wait $HTTP_PID
exit $?
