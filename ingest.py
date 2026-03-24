import os
from pypdf import PdfReader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.schema import Document

DATA_FOLDER = "data"
VECTOR_FOLDER = "vectorstore"

documents = []

for filename in os.listdir(DATA_FOLDER):
    if filename.endswith(".pdf"):
        reader = PdfReader(os.path.join(DATA_FOLDER, filename))
        text = ""

        for page in reader.pages:
            content = page.extract_text()
            if content:
                text += content + "\n"

        if text.strip():
            documents.append(Document(page_content=text))

if not documents:
    print("No readable documents found.")
    exit()

# Better splitting
splitter = RecursiveCharacterTextSplitter(
    chunk_size=700,
    chunk_overlap=150
)

docs = splitter.split_documents(documents)

embeddings = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2"
)

db = FAISS.from_documents(docs, embeddings)
db.save_local(VECTOR_FOLDER)

print("Vectorstore recreated successfully.")
