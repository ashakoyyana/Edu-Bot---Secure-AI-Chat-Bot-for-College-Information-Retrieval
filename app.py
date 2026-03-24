from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import os
import ollama

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

app = Flask(__name__)
app.secret_key = "harathi_secret"

DB = "users.db"
DATA_FOLDER = "data"
VECTOR_FOLDER = "vectorstore"

# ================= DATABASE =================

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    cur.execute("SELECT * FROM users WHERE role='admin'")
    admin = cur.fetchone()

    if not admin:
        cur.execute(
            "INSERT INTO users (username,password,role) VALUES (?,?,?)",
            ("admin", generate_password_hash("admin123"), "admin")
        )

    conn.commit()
    conn.close()

init_db()

# ================= PROCESS DOCUMENTS =================

@app.route("/process")
def process_documents():
    documents = []

    for filename in os.listdir(DATA_FOLDER):
        if filename.endswith(".pdf"):
            loader = PyPDFLoader(os.path.join(DATA_FOLDER, filename))
            documents.extend(loader.load())

    if not documents:
        return "No documents found in data folder."

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100
    )

    docs = splitter.split_documents(documents)

    embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    db = FAISS.from_documents(docs, embeddings)
    db.save_local(VECTOR_FOLDER)

    return "Documents processed successfully!"

# ================= LOAD VECTORSTORE ONCE =================

embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

if os.path.exists(VECTOR_FOLDER):
    vector_db = FAISS.load_local(
        VECTOR_FOLDER,
        embeddings,
        allow_dangerous_deserialization=True
    )
else:
    vector_db = None

# ================= LOGIN =================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute("SELECT username,password,role FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()

        if user and check_password_hash(user[1], password):
            session["user"] = user[0]
            session["role"] = user[2]

            if user[2] == "admin":
                return redirect("/admin")
            else:
                return redirect("/chatbot")
        else:
            return render_template("login.html", error="Invalid Credentials")

    return render_template("login.html")

# ================= REGISTER =================

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = generate_password_hash(request.form["password"])
        role = request.form["role"]

        try:
            conn = sqlite3.connect(DB)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username,password,role) VALUES (?,?,?)",
                (username,password,role)
            )
            conn.commit()
            conn.close()
            return redirect("/")
        except:
            return render_template("register.html", error="User already exists")

    return render_template("register.html")

# ================= ADMIN =================

@app.route("/admin")
def admin():
    if "user" not in session or session["role"] != "admin":
        return redirect("/")
    return render_template("admin.html")

# ================= CHATBOT PAGE =================

@app.route("/chatbot")
def chatbot():
    if "user" not in session:
        return redirect("/")
    return render_template("chatbot.html")

# ================= CHAT ROUTE =================
import ollama
import traceback

@app.route("/chat", methods=["POST"])
def chat():
    try:

        # ---------- GET INPUT ----------
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"response": "Invalid request."})

        user_message = data.get("message","").strip()

        if user_message == "":
            return jsonify({"response":"Please enter a question."})

        # ---------- CHECK VECTORSTORE ----------
        if not os.path.exists("vectorstore/index.faiss"):
            return jsonify({"response":"No documents uploaded by admin."})

        # ---------- LOAD VECTOR DB ----------
        embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2"
        )

        db = FAISS.load_local(
            "vectorstore",
            embeddings,
            allow_dangerous_deserialization=True
        )

        docs = db.similarity_search(user_message, k=2)

        if not docs:
            return jsonify({
                "response":"This is not a college related information. Please ask college related questions only."
            })

        context = "\n".join([d.page_content for d in docs])

        # ---------- STRICT PROMPT ----------
        prompt = f"""
You are a college assistant.

Rules:
- Answer only from context.
- Give short direct answer.
- No explanation.
- If answer not found, reply exactly:

This is not a college related information. Please ask college related questions only.

Context:
{context}

Question:
{user_message}

Answer:
"""

        # ---------- OLLAMA CALL ----------
        result = ollama.chat(
            model="mistral:latest",   # IMPORTANT
            messages=[
                {"role":"user","content":prompt}
            ]
        )

        answer = result["message"]["content"].strip()

        if answer == "":
            answer = "No proper answer found."

        return jsonify({"response": answer})

    except Exception as e:
        print("\n===== REAL ERROR START =====")
        traceback.print_exc()
        print("===== REAL ERROR END =====\n")

        return jsonify({"response":"Server Error. Check terminal."})

# ================= LOGOUT =================

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    app.run(debug=True)
