from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from io import BytesIO
from docx import Document
from fpdf import FPDF
import requests
import os
import re
from dotenv import load_dotenv

# === .env laden ===
load_dotenv()

# === Initialisierung ===
app = Flask(__name__, template_folder='templates', static_folder='static')
CORS(app)

# === API Keys ===
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

@app.route('/')
def serve_html():
    return render_template('amt.html')

# === Ort aus PLZ ermitteln ===
def get_ort_from_plz(plz):
    try:
        res = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "postalcode": plz,
                "country": "Germany",
                "format": "json",
                "limit": 1
            },
            headers={"User-Agent": "AlltagsBuddy Amt-o-Mat"},
            timeout=5
        )
        data = res.json()
        if not data:
            return None, None, None
        return data[0]["lat"], data[0]["lon"], data[0].get("display_name", "")
    except:
        return None, None, None

# === Google-Suche nach Behörde mit Ort und PLZ ===
def get_amtsadresse(plz, amt):
    if not GOOGLE_API_KEY:
        return "[Fehler: Kein Google API Key gefunden]"

    lat, lon, ortname = get_ort_from_plz(plz)
    if not lat or not lon:
        return "[Ort zur PLZ nicht gefunden]"

    try:
        query = f"{amt} {plz} {ortname}"
        url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
        params = {
            "query": query,
            "location": f"{lat},{lon}",
            "radius": 30000,
            "region": "de",
            "language": "de",
            "key": GOOGLE_API_KEY
        }
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        if not data.get("results"):
            return "[Keine passende Behörde gefunden]"

        best = data["results"][0]
        name = best.get("name", "[Unbekanntes Amt]")
        adresse = best.get("formatted_address", "")
        return f"{name}, {adresse}"

    except Exception as e:
        return f"[Fehler bei der Google-Suche: {str(e)}]"

# === Schreiben generieren ===
def generate_letter(behoerde, anliegen, tonfall, details, name, adresse, kundennummer):
    if not all([behoerde, anliegen, tonfall, name, adresse]):
        return "[Fehler: Unvollständige Eingaben]"

    stil = {
        "neutral": "Sehr geehrte Damen und Herren,",
        "freundlich": "Guten Tag, ich hoffe, es geht Ihnen gut.",
        "formell": "Hiermit wende ich mich in förmlicher Weise an Sie."
    }.get(tonfall, "Sehr geehrte Damen und Herren,")

    plz_match = re.search(r'\b\d{5}\b', adresse)
    plz = plz_match.group() if plz_match else ""
    amtsadresse = get_amtsadresse(plz, behoerde)

    absender = f"{name}\n{adresse}"
    if kundennummer.strip() and kundennummer != "-":
        absender += f"\nKundennummer: {kundennummer.strip()}"

    einleitung = (
        f"{stil}\n\n"
        f"Ich wende mich mit folgendem Anliegen an das {behoerde}:\n{anliegen}."
    )

    hauptteil = details if details.strip() else "Ich bitte um Unterstützung bei diesem Anliegen."

    schluss = (
        "\n\nIch danke Ihnen für Ihre Mühe und freue mich auf eine Rückmeldung.\n\n"
        f"Mit freundlichen Grüßen\n\n{name}"
    )

    return f"{absender}\n\nAn:\n{amtsadresse}\n\n{einleitung}\n\n{hauptteil}{schluss}"

# === API: Schreiben generieren ===
@app.route('/api/generate', methods=['POST'])
def generate():
    try:
        data = request.get_json()
        letter = generate_letter(
            data.get('behoerde', '').strip(),
            data.get('anliegen', '').strip(),
            data.get('tonfall', '').strip(),
            data.get('details', '').strip(),
            data.get('name', '').strip(),
            data.get('adresse', '').strip(),
            data.get('kundennummer', '').strip()
        )
        return jsonify({"brieftext": letter})
    except Exception as e:
        return jsonify({"brieftext": f"[Fehler: {str(e)}]"}), 500

# === API: PDF-Export ===
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
    pdf_output = pdf.output(dest='S').encode('latin-1')
    buffer.write(pdf_output)
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="amtsschreiben.pdf", mimetype='application/pdf')

# === API: DOCX-Export ===
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

print("Google Key geladen:", GOOGLE_API_KEY is not None)

# === App starten ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
