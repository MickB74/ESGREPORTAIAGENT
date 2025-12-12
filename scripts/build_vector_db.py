import os
import sys
from langchain_community.document_loaders import PyMuPDFLoader, DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

DOCS_DIR = "rag_docs"
DB_DIR = "chroma_db"

def build_db():
    print(f"Loading PDFs from {DOCS_DIR}...")
    
    # 1. Load PDFs
    if not os.path.exists(DOCS_DIR):
        print(f"Error: Directory {DOCS_DIR} not found.")
        return

    # Use DirectoryLoader with PyMuPDF
    loader = DirectoryLoader(DOCS_DIR, glob="./*.pdf", loader_cls=PyMuPDFLoader)
    documents = loader.load()
    
    if not documents:
        print("No documents found to index.")
        return
        
    print(f"Loaded {len(documents)} pages.")
    
    # 2. Split Text (Chunking)
    print("Splitting text...")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_documents(documents)
    print(f"Created {len(chunks)} text chunks.")
    
    # 3. Create Embeddings
    print("Initializing Embeddings (all-MiniLM-L6-v2)...")
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    
    # 4. Create/Update Vector DB
    print(f"Building/Updating Vector DB in {DB_DIR}...")
    # persist_directory is automatic in newer chroma, but good to specify path logic if handled by wrapper
    # LangChain's Chroma wrapper handles persistence if persist_directory is passed
    db = Chroma.from_documents(
        documents=chunks, 
        embedding=embedding_model, 
        persist_directory=DB_DIR
    )
    
    # Force persist (older versions) or just letting it autosave
    # db.persist() # Deprecated in newer Chroma, but harmless if suppressed
    
    print("✅ RAG Index created successfully!")

if __name__ == "__main__":
    build_db()
