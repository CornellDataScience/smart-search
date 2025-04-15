from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel
import ollama

app = FastAPI()
PROJECT_KEYWORDS = ["project", "task", "assignment"]

class QueryRequest(BaseModel):
    query: str

import json
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
import chromadb
from langchain.prompts import PromptTemplate

EMBEDDINGS = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
PERSIST_DIR = "/Users/jerometh/Projects/CDS/smart-search/tests/chroma_db"
COLLECTION_NAME = "test"

TEMPLATE = """### Task
You are to answer questions about the Cornell Data Science project team.
You specialize in answering questions about code repositories.
You will be provided with a user's question, along with snippets of code that should provide you with the context you need to answer them.

### Warning
DO NOT REFERENCE OUTSIDE INFORMATION IN YOUR RESPONSE. Answer only within the bounds of the context provided.

### User Question
{question}

### Context
{context}

### Answer
"""


def get_vdb():
    chroma_client = chromadb.PersistentClient(path=PERSIST_DIR)

    # Check if a collection exists
    existing_collections = [col.name for col in chroma_client.list_collections()]
    print(existing_collections)
    collection_name = "test"
    print("existing collections: ---------")
    print(existing_collections)

    if collection_name in existing_collections:
        print(f"Collection '{collection_name}' exists. Getting existing...")
        vectordb = Chroma(
            collection_name=collection_name,
            embedding_function=EMBEDDINGS,
            persist_directory=PERSIST_DIR
        )
        print("Retrieved.")
    else:
        print(f"Collection '{collection_name}' does not exist.")
        # vectordb = Chroma(
        #     collection_name=collection_name,
        #     embedding_function=EMBEDDINGS,
        #     persist_directory=PERSIST_DIR
        # )
        # vectordb.add_texts(texts=data['summary'], metadatas=data['metadata'], ids=data['ids'])
    return vectordb

def query(q):
    vectordb = get_vdb()
    results = vectordb.similarity_search(q)
    return results

def get_llm_prompt(q):
    docs = query(q)

    context = "\n\n".join([f"===== Snippet {i} =====\n<Summary>{doc.page_content}</Summary>\n<Raw Code>{doc.metadata['code']}</Raw Code\n<Source>{doc.metadata['context']}</Source>"
    for i, doc in enumerate(docs)])

    template = PromptTemplate(
        input_variables=["context", "question"],
        template=TEMPLATE
    )

    formatted_prompt = template.format(
        context=context,
        question=q
   )

    return {"prompt" : formatted_prompt, "sources" : [doc.metadata['context'] for doc in docs]}

@app.post("/rag-api/")
async def sample_rag_api(request: QueryRequest):
    # Mock function to simulate the API call
    # In a real implementation, this would call the actual API and return the response
    
    #simulate network delay
    res = get_llm_prompt(request.query)
    prompt = res['prompt']
    sources = res["sources"]

    #use ollama
    response = ollama.generate(
        model='llama3.1:latest',
        prompt=prompt
    )
    return {"sources" : sources, "response": response['response'], "prompt": prompt}

def is_relevant(query: str) -> bool:
    return any(word in query.lower() for word in PROJECT_KEYWORDS)

@app.post("/filter-query/")
async def filter_query(query):
    relevant = is_relevant(query)
    return {"relevant": relevant}

@app.post("/request_answer/")
async def run(request: QueryRequest):
    #call the filter_query function
    response = await filter_query(request.query)
    if not response["relevant"]:
        return JSONResponse(content={"message": "Query is not relevant"}, status_code=200)

    # Call the sample RAG API function
    response = await sample_rag_api(request.query)
    return JSONResponse(content=response, status_code=200)

'''
Installation: 
pip install "fastapi[standard]"

usage: 
1. start the server
fastapi dev api/api.py

2. post request to the server
curl -X POST "http://localhost:8000/rag-api/" \
  -H "Content-Type: application/json" \
  -d '{"query": "Where is the MathSearch vision model code?"}'
'''
