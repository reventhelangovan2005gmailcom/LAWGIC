import os
import sqlite3
import pandas as pd
from flask import Flask, render_template, request, make_response
from sentence_transformers import SentenceTransformer, util
from PIL import Image
import pytesseract
import shutil
from fpdf import FPDF
import datetime
import requests

app = Flask(__name__)

# ---------------- DATABASE ---------------- #
def get_db_connection():
    conn = sqlite3.connect("lawgic.db")
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- LOAD EMBEDDING MODEL ---------------- #
print("Loading Embedding Model...")
model = SentenceTransformer("all-MiniLM-L6-v2")

conn = get_db_connection()
df = pd.read_sql_query("SELECT * FROM laws", conn)
conn.close()

df["combined_text"] = df["section"] + ": " + df["description"]
law_embeddings = model.encode(df["combined_text"].tolist(), convert_to_tensor=True)

print("Indexed", len(df), "BNS Sections")

# ---------------- OCR ---------------- #
pytesseract.pytesseract.tesseract_cmd = "/opt/homebrew/bin/tesseract"

def extract_text_from_image(image_file):
    try:
        img = Image.open(image_file.stream).convert("RGB")
        text = pytesseract.image_to_string(img)
        return text.strip()
    except Exception as e:
        print("OCR Error:", e)
        return ""

# ---------------- LOCAL LLM CALL (OLLAMA) ---------------- #
def call_local_llm(prompt):

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "llama3",
            "prompt": prompt,
            "stream": False
        }
    )

    return response.json()["response"]

# ---------------- FULL LEGAL ANALYSIS ---------------- #
def full_case_analysis(case_text):

    query_embedding = model.encode(case_text, convert_to_tensor=True)
    hits = util.semantic_search(query_embedding, law_embeddings, top_k=5)

    retrieved_laws = []
    for hit in hits[0]:
        idx = hit["corpus_id"]
        row = df.iloc[idx]
        retrieved_laws.append(
            f"{row['section']}:\n{row['description']}"
        )

    law_context = "\n\n".join(retrieved_laws)

    prompt = f"""
You are a senior Indian Criminal Court Judge.
Strictly follow Bharatiya Nyaya Sanhita (BNS), 2023.

CASE DETAILS:
{case_text}

AVAILABLE BNS SECTIONS:
{law_context}

Provide structured legal analysis:

Case Summary:
Legal Ingredients Identified:
Applicable BNS Sections:
Legal Reasoning:
Possible Punishment:
Aggravating Factors:
Mitigating Factors:
Final Legal Opinion:
Confidence Level (0-100%):
"""

    return call_local_llm(prompt)

# ---------------- ROUTES ---------------- #

@app.route("/", methods=["GET", "POST"])
def index():

    analysis = None
    input_text = ""

    if request.method == "POST":

        # Get typed text
        input_text = request.form.get("case_description", "").strip()

        # Get uploaded image
        file = request.files.get("fir_file")

        if file and file.filename != "":
            print("Image uploaded. Running OCR...")
            extracted = extract_text_from_image(file)
            print("OCR Extracted Text:", extracted)
            input_text = input_text + " " + extracted

        # Final validation
        if len(input_text.strip()) > 5:
            print("Running Legal Analysis...")
            analysis = full_case_analysis(input_text)
            analysis = analysis.replace("**", "")
        else:
            analysis = "Please provide case description or upload a valid image."

    return render_template(
        "index.html",
        analysis=analysis,
        input_text=input_text
    )

# ---------------- PDF ---------------- #
@app.route("/download_report", methods=["POST"])
def download_report():

    analysis = request.form["analysis"]
    user_case = request.form["user_case"]

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.set_font("Arial", size=11)

    pdf.cell(0, 10, "LAWGIC - Offline Legal Report", ln=True)
    pdf.cell(0, 8, f"Generated: {datetime.datetime.now()}", ln=True)
    pdf.ln(5)

    pdf.multi_cell(0, 8, "Complete Case Description:")
    pdf.multi_cell(0, 8, user_case)
    pdf.ln(5)

    pdf.multi_cell(0, 8, "AI Legal Analysis:")
    pdf.multi_cell(0, 8, analysis)

    pdf_output = pdf.output(dest="S")
    clean_pdf_output = pdf_output.encode("latin-1", "ignore")

    response = make_response(clean_pdf_output)
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = "attachment; filename=lawgic_offline_report.pdf"

    return response

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)