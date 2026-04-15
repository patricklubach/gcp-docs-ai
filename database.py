import os

from langchain_ollama import OllamaEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from markdown_doc import MarkdownDocument

md_path = "./data/buckets.md"
md_documment = MarkdownDocument(md_path)
embeddings = OllamaEmbeddings(model="mxbai-embed-large")

db_location = "./chroma_langchain_db"
add_documents = not os.path.exists(db_location)

document_id = 1

documents = []
ids = []

if add_documents:
    for item in md_documment.items:
        for section in item.sections:
          document = Document(
              page_content=item.title + " " + section,
              metadata={"title": item.title, "path": md_path},
              id=str(document_id)
          )
          ids.append(str(document_id))
          documents.append(document)
          document_id += 1

vector_store = Chroma(
    collection_name="google_cloud_docs",
    persist_directory=db_location,
    embedding_function=embeddings
)

if add_documents:
    vector_store.add_documents(documents=documents, ids=ids)

retriever = vector_store.as_retriever(
    search_kwargs={"k": 5}
)
