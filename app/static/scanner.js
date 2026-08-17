/* Barcode-Scanner.
   Erst die native BarcodeDetector-API (Chrome/Android), sonst ZXing.
   Beides läuft im Browser - der Server sieht nur den fertigen EAN. */

(function () {
  var video   = document.getElementById('video');
  var box     = document.getElementById('video-box');
  var status  = document.getElementById('status');
  var ausgabe = document.getElementById('ergebnis');
  var startBtn = document.getElementById('kamera-an');
  var mahlzeit = document.getElementById('mahlzeit');

  var stream = null, laueft = false, letzterCode = '', letzteZeit = 0;
  var zxing = null;

  function melde(text, art) {
    status.textContent = text;
    status.className = 'status' + (art ? ' ' + art : '');
  }

  // --- Kamera ---------------------------------------------------
  async function starten() {
    if (!window.isSecureContext) {
      melde('Der Browser gibt die Kamera nur über HTTPS frei – auch im ' +
            'eigenen Netz. Die App stattdessen über https://…:8443 aufrufen, ' +
            'oder den Barcode unten von Hand eingeben.', 'fehler');
      return;
    }
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      melde('Dieser Browser gibt keinen Kamerazugriff frei.', 'fehler');
      return;
    }

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 } }
      });
    } catch (e) {
      melde('Kamerazugriff abgelehnt. In den Browser-Einstellungen freigeben.', 'fehler');
      return;
    }

    video.srcObject = stream;
    await video.play();
    box.hidden = false;
    startBtn.textContent = 'Kamera stoppen';
    laueft = true;
    melde('Suche Strichcode …');

    if ('BarcodeDetector' in window) {
      nativLoop();
    } else if (window.ZXing) {
      zxingLoop();
    } else {
      melde('Kein Barcode-Leser verfügbar. Bitte den Code von Hand eingeben.', 'fehler');
    }
  }

  function stoppen() {
    laueft = false;
    if (zxing && zxing.reset) { try { zxing.reset(); } catch (e) {} }
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
    box.hidden = true;
    startBtn.textContent = 'Kamera starten';
    melde('Kamera aus.');
  }

  async function nativLoop() {
    var detector = new window.BarcodeDetector({
      formats: ['ean_13', 'ean_8', 'upc_a', 'upc_e', 'code_128']
    });
    while (laueft) {
      try {
        var codes = await detector.detect(video);
        if (codes && codes.length) treffer(codes[0].rawValue);
      } catch (e) { /* einzelne Frames dürfen scheitern */ }
      await new Promise(function (r) { setTimeout(r, 180); });
    }
  }

  function zxingLoop() {
    var hints = new Map();
    hints.set(window.ZXing.DecodeHintType.POSSIBLE_FORMATS, [
      window.ZXing.BarcodeFormat.EAN_13, window.ZXing.BarcodeFormat.EAN_8,
      window.ZXing.BarcodeFormat.UPC_A, window.ZXing.BarcodeFormat.UPC_E,
      window.ZXing.BarcodeFormat.CODE_128
    ]);
    zxing = new window.ZXing.BrowserMultiFormatReader(hints, 250);
    zxing.decodeFromVideoElement(video, function (result) {
      if (result) treffer(result.getText());
    });
  }

  // --- Treffer verarbeiten --------------------------------------
  function treffer(code) {
    var jetzt = Date.now();
    if (code === letzterCode && jetzt - letzteZeit < 4000) return;
    letzterCode = code; letzteZeit = jetzt;
    if (navigator.vibrate) navigator.vibrate(40);
    nachschlagen(code);
  }

  async function nachschlagen(ean) {
    melde('Barcode ' + ean + ' – schlage nach …');
    try {
      var r = await fetch('/api/barcode/' + encodeURIComponent(ean));
      if (r.status === 404) {
        zeigeUnbekannt(ean);
        return;
      }
      var daten = await r.json();
      melde('Gefunden (' + daten.origin + ')', 'ok');
      zeigeTreffer(daten.food, ean);
    } catch (e) {
      melde('Nachschlagen fehlgeschlagen: ' + e.message, 'fehler');
    }
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function zeigeTreffer(f, ean) {
    var einheit = f.is_liquid ? 'ml' : 'g';
    var menge = Math.round(f.default_g || 100);
    var portionen = (f.portions || []).map(function (p) {
      return '<button type="button" data-g="' + p.grams + '">' +
             esc(p.label) + ' · ' + Math.round(p.grams) + ' g</button>';
    }).join('');

    ausgabe.innerHTML =
      '<details class="treffer" open>' +
        '<summary><span class="titel"><b>' + esc(f.name) + '</b><small>' +
          (f.brand ? esc(f.brand) + ' · ' : '') +
          Math.round(f.kcal_100) + ' kcal / 100 ' + einheit +
        '</small></span></summary>' +
        '<div class="treffer-body">' +
          (f.suspect ? '<div class="warnung">Die Nährwerte wirken unplausibel ' +
            '(typischer Fehler in Open Food Facts: kJ statt kcal). Bitte am Etikett prüfen.</div>' : '') +
          '<form method="post" action="/api/log">' +
            '<input type="hidden" name="food_id" value="' + f.id + '">' +
            '<input type="hidden" name="meal" value="' + esc(mahlzeit.value) + '">' +
            '<input type="hidden" name="day" value="' + esc(window.KCAL_TAG) + '">' +
            '<input type="hidden" name="input" value="barcode">' +
            '<input type="hidden" name="confidence" value="exact">' +
            '<input type="hidden" name="redirect" value="/tag/' + esc(window.KCAL_TAG) + '">' +
            '<label>Menge in ' + einheit + '</label>' +
            '<div class="reihe">' +
              '<input type="number" class="menge" name="amount_g" value="' + menge +
                '" min="1" max="5000" step="1" inputmode="numeric">' +
              '<button class="btn primaer" style="flex:0 0 auto">Eintragen</button>' +
            '</div>' +
            (portionen ? '<div class="portionen">' + portionen + '</div>' : '') +
            '<p class="vorschau"><b class="v-kcal">–</b> kcal · <span class="v-makros">–</span></p>' +
          '</form>' +
        '</div>' +
      '</details>';

    var feld = ausgabe.querySelector('.menge');
    var kOut = ausgabe.querySelector('.v-kcal');
    var mOut = ausgabe.querySelector('.v-makros');
    function neu() {
      var k = (parseFloat(feld.value) || 0) / 100;
      kOut.textContent = Math.round(f.kcal_100 * k);
      mOut.textContent = Math.round(f.protein_100 * k) + ' g Eiweiß · ' +
        Math.round(f.carbs_100 * k) + ' g KH · ' + Math.round(f.fat_100 * k) + ' g Fett';
    }
    feld.addEventListener('input', neu);
    ausgabe.querySelectorAll('.portionen button').forEach(function (b) {
      b.addEventListener('click', function () { feld.value = b.dataset.g; neu(); });
    });
    neu();
    ausgabe.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function zeigeUnbekannt(ean) {
    melde('Barcode ' + ean + ' ist weder lokal noch bei Open Food Facts hinterlegt.');
    ausgabe.innerHTML =
      '<div class="treffer"><div class="treffer-body">' +
        '<p style="margin:0 0 .7rem">Einmal die Werte vom Etikett eintippen – ' +
        'danach kennt die App das Produkt.</p>' +
        '<a class="btn primaer voll" href="/neu?ean=' + encodeURIComponent(ean) +
          '&meal=' + encodeURIComponent(mahlzeit.value) +
          '&day=' + encodeURIComponent(window.KCAL_TAG) + '">Produkt anlegen</a>' +
      '</div></div>';
  }

  // --- Verdrahtung ----------------------------------------------
  // Unsicherer Kontext: gar nicht erst die Kamera anbieten, sondern
  // direkt auf dieselbe Seite über HTTPS verlinken.
  if (!window.isSecureContext) {
    var httpsUrl = 'https://' + location.hostname + ':8443' +
                   location.pathname + location.search;
    startBtn.disabled = true;
    ausgabe.innerHTML =
      '<div class="warnung" style="margin-top:.8rem">' +
        '<b>Kamera gesperrt.</b> Browser geben sie nur über HTTPS frei – ' +
        'das gilt auch im eigenen Netz und über VPN.' +
        '<p style="margin:.7rem 0 0"><a class="btn primaer voll" href="' +
          httpsUrl + '">Seite über HTTPS öffnen</a></p>' +
        '<p style="margin:.6rem 0 0;font-size:.75rem">' +
        'Läuft dort noch nichts: <code>./scripts/zertifikat.sh</code> ' +
        'ausführen und den Container neu starten. Bis dahin funktioniert ' +
        'die manuelle Eingabe unten.</p>' +
      '</div>';
    melde('Barcode unten von Hand eingeben oder auf HTTPS wechseln.');
  }

  startBtn.addEventListener('click', function () {
    if (laueft) stoppen(); else starten();
  });

  document.getElementById('ean-suchen').addEventListener('click', function () {
    var v = document.getElementById('ean-manuell').value.replace(/\D/g, '');
    if (v) nachschlagen(v);
  });
  document.getElementById('ean-manuell').addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); document.getElementById('ean-suchen').click(); }
  });

  window.addEventListener('pagehide', stoppen);
})();
