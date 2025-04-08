from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from pydantic import BaseModel

app = FastAPI()
PROJECT_KEYWORDS = ["project", "task", "assignment"]

class QueryRequest(BaseModel):
    query: str


async def sample_rag_api(query):
    # Mock function to simulate the API call
    # In a real implementation, this would call the actual API and return the response
    
    #simulate network delay
    await asyncio.sleep(3)
    return {
        "response": f"Mocked response for query: {query}",
        "metadata": {"source": "mocked"}
    }

def is_relevant(query: str) -> bool:
    return any(word in query.lower() for word in PROJECT_KEYWORDS)

@app.post("/filter-query/")
async def filter_query(query):
    relevant = is_relevant(query)
    return {"relevant": relevant}

@app.post("/rag-api/")
async def rag_api(request: QueryRequest):
    """
    Endpoint to handle RAG API requests.
    """
    # Call the sample RAG API function
    response = await sample_rag_api(request.query)
    return JSONResponse(content=response, status_code=200)

