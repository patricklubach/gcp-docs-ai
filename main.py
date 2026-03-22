"""
Source: https://github.com/techwithtim/LocalAIAgentWithRAG/blob/main/main.py
"""
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate

from database import retriever
from manifest import check_for_changes

check_for_changes("./data")

model = OllamaLLM(model="qwen3:4b")

template = """
You are an exeprt in answering questions about Google Cloud.

Here are some relevant reviews: {reviews}

Here is the question to answer as precise as possible: {question}

When responding, always provide the source for your answers.
"""
prompt = ChatPromptTemplate.from_template(template)
chain = prompt | model

while True:
    print("\n\n-------------------------------")
    question = input("Ask your question (q to quit): ")
    print("\n\n")
    if question == "q":
        break

    reviews = retriever.invoke(question)
    result = chain.invoke({"reviews": reviews, "question": question})
    print(result)