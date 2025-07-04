from flask import Flask, request, jsonify, send_file, render_template
from flask_cors import CORS
from io import BytesIO
from docx import Document
from fpdf import FPDF
import requests
import os
import re
from dotenv import load_dotenv
import openai

# 🔐 .env laden (lokal)
load_dotenv()

# 🌍 Flask-App einrichten
app = Flask(__name__, template_folder='templates')
CORS(app)

# 🔐 API Keys aus Umgebungsvariablen
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.json

    name = data.get("name", "")
    adresse = data.get("adresse", "")
    kundennummer = data.get("kundennummer", "")
    behoerde = data.get("behoerde", "")
    behoerde_sonstig = data.get("behoerdeSonstig", "")
    anliegen = data.get("anliegen", "")
    anliegen_sonstig = data.get("anliegenSonstig", "")
    tonfall = data.get("tonfall", "neutral")
    details = data.get("details", "")

    # Fallback auf "Sonstiges"-Felder
    behoerde_final = behoerde_sonstig if behoerde == "Sonstiges" else behoerde
    anliegen_final = anliegen_sonstig if anliegen == "Sonstiges" else anliegen

    # Beispielhafte Behördenadresse (hier später durch Lookup ersetzen)
    behoerden_adressen = {
        "Jobcenter": "Jobcenter Musterstadt\nHauptstraße 1\n12345 Musterstadt",
        "Bürgeramt": "Bürgeramt Musterstadt\nAm Rathaus 2\n12345 Musterstadt",
        "Agentur für Arbeit": "Agentur für Arbeit Musterstadt\nArbeitsweg 4\n12345 Musterstadt",
        "Familienkasse": "Familienkasse Musterstadt\nKinderweg 7\n12345 Musterstadt",
        "Stadtverwaltung": "Stadtverwaltung Musterstadt\nVerwaltungsplatz 8\n12345 Musterstadt"
    }

    behoerde_adresse = behoerden_adressen.get(behoerde_final, behoerde_final)

    # Prompt vorbereiten
    prompt = f"""
    Erstelle ein offizielles, gut lesbares und verständliches Schreiben an folgende Behörde:
    {behoerde_adresse}

    Art des Schreibens: {anliegen_final}
    Tonfall: {tonfall}
    Absender: {name}, {adresse}
    {"Kundennummer: " + kundennummer if kundennummer else ""}
    Details zum Anliegen: {details}

    Beginne mit einer passenden Anrede, formuliere den Text gemäß deutschem Behördenstil und schließe mit einem höflichen Abschluss und vollständiger Absenderangabe.
    """

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=800
        )
        output_text = response['choices'][0]['message']['content']
        return jsonify({
            "output": output_text,
            "behoerdeAdresse": behoerde_adresse
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
