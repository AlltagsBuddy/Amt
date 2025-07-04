from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO
from docx import Document
from fpdf import FPDF
import requests
import os
import re
from dotenv import load_dotenv  # <-- NEU

# === .env laden ===
load_dotenv()

# === Initialisierung ===
app = Flask(__name__, template_folder='templates')
CORS(app)

# === API Key sicher aus .env holen ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
# OPENAI API Key
openaiapi_key = os.getenv("OPENAI_API_KEY")  

@app.route('/')
def serve_html():
    return render_template('amt.html')

# === Hilfsfunktionen ===

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
    except:
        return None, None

def get_amtsadresse(plz, amt):
    lat, lon = get_coords_from_plz(plz)
    if not lat or not lon:
        return "[Ort zur PLZ nicht gefunden]"

    try:
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": amt,
            "location": f"{lat},{lon}",
            "radius": 30000,
            "region": "de",
            "language": "de",
            "key": GOOGLE_API_KEY
        }
        res = requests.get(url, params=params)
        data = res.json()
        if not data.get("results"):
            return "[Keine passende Behörde gefunden]"

        best = data["results"][0]
        name = best.get("name", "[Unbekanntes Amt]")
        adresse = best.get("formatted_address", "")
        return f"{name}, {adresse}"

    except Exception as e:
        return f"[Fehler bei der Google-Suche: {str(e)}]"

# === Briefgenerator ===

def generate_letter(behoerde, anliegen, tonfall, details, name, adresse, kundennummer):
    anreden = {
        "neutral": "Sehr geehrte Damen und Herren,",
        "freundlich": "Guten Tag, ich hoffe, es geht Ihnen gut.",
        "formell": "Hiermit wende ich mich in förmlicher Weise an Sie."
    }
    anrede = anreden.get(tonfall, "Sehr geehrte Damen und Herren,")

    plz_match = re.search(r'\b\d{5}\b', adresse)
    plz = plz_match.group(0) if plz_match else ''
    amtsadresse = get_amtsadresse(plz, behoerde)

    absenderblock = f"{name}\n{adresse}"
    if kundennummer.strip():
        absenderblock += f"\nKundennummer: {kundennummer.strip()}"

    einleitung = (
        f"{anrede}\n\n"
        f"ich wende mich an Sie mit folgendem Anliegen in Bezug auf das {behoerde}:\n"
        f"{anliegen}.\n"
    )

    hauptteil = (
        f"{details.strip()}\n\n"
        f"Ich bitte um eine wohlwollende Prüfung und eine Rückmeldung an mich unter den oben genannten Kontaktdaten."
    )

    schluss = (
        "\n\nVielen Dank für Ihre Mühe.\n\n"
        f"Mit freundlichen Grüßen\n\n{name}"
    )

    brief = (
        f"{absenderblock}\n\n"
        f"An:\n{amtsadresse}\n\n"
        f"{einleitung}"
        f"{hauptteil}"
        f"{schluss}"
    )

    return brief

# === API-Routen ===

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

# === Start ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
