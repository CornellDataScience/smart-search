import json
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
import chromadb
from langchain.prompts import PromptTemplate

data = None
with open("test_dataset.json", 'r') as json_file:
    data = json.load(json_file)
    json_file.close()


EMBEDDINGS = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)
PERSIST_DIR = "./chroma_db"
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
    existing_collections = chroma_client.list_collections()
    print(existing_collections)
    collection_name = "test"

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
        vectordb = Chroma(
            collection_name=collection_name,
            embedding_function=EMBEDDINGS,
            persist_directory=PERSIST_DIR
        )
        vectordb.add_texts(texts=data['summary'], metadatas=data['metadata'], ids=data['ids'])
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
        question="Can you summarize the mathematical features of MathSearch?"
    )

    return formatted_prompt