import os.path
import time

from llama_index.core import (
    VectorStoreIndex,
    SimpleDirectoryReader,
    StorageContext,
    load_index_from_storage,
    Settings
)
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding


def run_smart_local_rag() -> None:
    """
    Runs a local RAG pipeline with error handling for missing storage files
    and automatic index updates.
    """
    PERSIST_DIR = "./storage"
    DATA_DIR = "./docs"

    # Path to a core file that MUST exist for a valid index
    INDEX_FILE = os.path.join(PERSIST_DIR, "docstore.json")

    Settings.llm = Ollama(model="qwen3:4b", request_timeout=600.0)
    Settings.embed_model = OllamaEmbedding(model_name="qwen3-embedding")

    # Check if the index file exists, not just the directory
    if not os.path.exists(INDEX_FILE):
        print("Index not found. Initializing from scratch...")
        documents = SimpleDirectoryReader(DATA_DIR).load_data()
        index = VectorStoreIndex.from_documents(documents)
        index.storage_context.persist(persist_dir=PERSIST_DIR)
    else:
        print("Loading and syncing existing index...")
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)

        # Sync new files - TODO: fix this diff updating
        # new_docs = SimpleDirectoryReader(DATA_DIR).load_data()
        # refreshed_docs = index.refresh_ref_docs(new_docs)

        # if any(refreshed_docs):
        #     print("Changes detected. Saving updates...")
        #     index.storage_context.persist(persist_dir=PERSIST_DIR)

    chat_engine = index.as_chat_engine()

    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # Start Timer
        start_time = time.perf_counter()
        response = chat_engine.chat(user_input)

        # End Timer
        end_time = time.perf_counter()
        duration = end_time - start_time

        print(f"AI (took: {duration:.2f}s): {response}\n")


if __name__ == "__main__":
    run_smart_local_rag()
