from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from io import BytesIO
from docx import Document
from fpdf import FPDF
import requests
import os
import re
from dotenv import load_dotenv

# 🔐 .env laden (lokal vorhanden)
load_dotenv()

app = Flask(__name__, template_folder='templates')
CORS(app)

# 🔐 API-Keys aus Umgebungsvariablen
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # optional für spätere Features

# Debug-Ausgabe
if not GOOGLE_API_KEY:
    print("❌ GOOGLE_API_KEY wurde nicht gefunden!")
else:
    print("✅ GOOGLE_API_KEY ist gesetzt.")

@app.route('/')
def serve_html():
    return render_template('amt.html')


# 📍 Hole Koordinaten zur PLZ via OpenStreetMap
def get_coords_from_plz(plz):
    try:
        res = requests.get("https://nominatim.openstreetmap.org/search", params={
            "postalcode": plz,
            "country": "Germany",
            "format": "json",
            "limit": 1
        }, headers={"User-Agent": "AlltagsBuddy Amt-o-Mat"})
        data = res.json()
        if not data:
            return None, None
        return data[0]["lat"], data[0]["lon"]
    except Exception as e:
        print("PLZ-Koordinatenfehler:", e)
        return None, None


# 📌 Suche nächstes Amt über Google Places API
def get_amtsadresse(plz, amt):
    if not GOOGLE_API_KEY:
        return "[Kein Google API Key verfügbar]"

    lat, lon = get_coords_from_plz(plz)
    if not lat or not lon:
        return "[Ort zur PLZ nicht gefunden]"

    try:
        suchbegriff = f"{amt} {plz} Germany"
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": suchbegriff,
            "location": f"{lat},{lon}",
            "radius": 50000,
            "region": "de",
            "language": "de",
            "key": GOOGLE_API_KEY
        }
        res = requests.get(url, params=params)
        data = res.json()

        if "error_message" in data:
            return f"[Google API Fehler: {data['error_message']}]"

        if not data.get("results"):
            return "[Keine passende Behörde gefunden]"

        best = data["results"][0]
        name = best.get("name", "[Unbekanntes Amt]")
        adresse = best.get("formatted_address", "")
        return f"{name}, {adresse}"

    except Exception as e:
        return f"[Fehler bei der Google-Suche: {str(e)}]"


# 📝 Schreiben generieren
def generate_letter(behoerde, anliegen, tonfall, details, name, adresse, kundennummer):
    stil = {
        "neutral": "Sehr geehrte Damen und Herren,",
        "freundlich": "Guten Tag, ich hoffe, es geht Ihnen gut.",
        "formell": "Hiermit wende ich mich in förmlicher Weise an Sie."
    }.get(tonfall, "Sehr geehrte Damen und Herren,")

    plz_match = re.search(r'(\d{5})', adresse)
    plz = plz_match.group(1) if plz_match else ''
    amtsadresse = get_amtsadresse(plz, behoerde)

    absenderblock = f"{name}\n{adresse}\nKundennummer: {kundennummer or '-'}"

    text = (
        f"{absenderblock}\n\n"
        f"An:\n{amtsadresse}\n\n"
        f"{stil}\n\n"
        f"Ich möchte mich mit folgendem Anliegen an das {behoerde} wenden: {anliegen}.\n\n"
        f"{details}\n\n"
        f"Ich danke Ihnen im Voraus für Ihre Bearbeitung.\n\nMit freundlichen Grüßen\n{name}"
    )
    return text


# 📤 Schreiben generieren
@app.route('/api/generate', methods=['POST'])
def generate():
    data = request.get_json()
    letter = generate_letter(
        data.get('behoerde', ''),
        data.get('anliegen', ''),
        data.get('tonfall', ''),
        data.get('details', ''),
        data.get('name', '[Dein Name]'),
        data.get('adresse', '[Deine Adresse]'),
        data.get('kundennummer', '-')
    )
    return jsonify({"brieftext": letter})


# 📥 PDF Export
@app.route('/api/export/pdf', methods=['POST'])
def export_pdf():
    data = request.get_json()
    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_font("Arial", size=12)
    for line in data.get("brieftext", "").split("\n"):
        pdf.multi_cell(0, 10, line)
    buffer = BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="amtsschreiben.pdf", mimetype='application/pdf')


# 📥 DOCX Export
@app.route('/api/export/docx', methods=['POST'])
def export_docx():
    data = request.get_json()
    doc = Document()
    for line in data.get("brieftext", "").split("\n"):
        doc.add_paragraph(line)
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="amtsschreiben.docx", mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


# 🌐 Starten
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
# 🔍 Diagnose-Endpunkt zur API-Funktion (optional, für Adminzwecke)
@app.route('/test-api')
def test_google_api():
    test_plz = "10115"  # Berlin
    test_behoerde = "Bürgeramt"

    try:
        amtsadresse = get_amtsadresse(test_plz, test_behoerde)
        return jsonify({
            "status": "OK",
            "plz": test_plz,
            "behoerde": test_behoerde,
            "ergebnis": amtsadresse
        })
    except Exception as e:
        return jsonify({
            "status": "Fehler",
            "meldung": str(e)
        }), 500
