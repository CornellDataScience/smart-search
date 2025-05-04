import json
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import Chroma
import chromadb
from langchain.prompts import PromptTemplate
from langchain.schema import Document


# data = None
# with open("vdb/data/vdb_formatted_summaries3.json", 'r') as json_file:
#     data = json.load(json_file)
#     json_file.close()

data = None
with open("data/langchain_docs.json", 'r') as json_file:
    data = json.load(json_file)
    json_file.close()
data = [
    Document(page_content=doc["page_content"], metadata=doc["metadata"])
    for doc in data
]


EMBEDDINGS = HuggingFaceEmbeddings(
    # model_name="HIT-TMG/KaLM-embedding-multilingual-mini-v1"
    model_name = "ibm-granite/granite-embedding-125m-english"
)
# PERSIST_DIR = "./vdb/chroma_db:v2"
PERSIST_DIR = "./chroma_db:demo"

COLLECTION_NAME = "test"

TEMPLATE = """### Task
You are to answer questions about the Cornell Data Science project team.
You specialize in answering questions about code repositories.
You will be provided with a user's question, along with directory, file, or code descriptions in XML format.

### Warning
Use only the provided XML information to answer the user's question. Answer only within the bounds of the context provided.

### User Question
{question}

### Context
{context}

### Answer
"""


def get_vdb(with_documents = True):
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
        
        # In the case that the data has already been converted to LangChain Documents
        if with_documents:
            vectordb.add_documents(data)
        else:
            vectordb.add_texts(texts=data['summary'], metadatas=data['metadata'], ids=data['ids'])
            
        vectordb.persist()
        print("Collection persisted.")
        
    return vectordb

def query(q):
    vectordb = get_vdb()
    results = vectordb.similarity_search(q)
    return results

def document_to_xml(doc):
    meta = doc.metadata
    return f"""
  <document>
    <file>
      <name>{meta.get("name", "")}</name>
      <path>{meta.get("path", "")}</path>
      <type>{meta.get("type", "")}</type>
    </file>
    <summary>{meta.get("summary", "")}</summary>
    <code><![CDATA[
{meta.get("code", "").strip()}
    ]]></code>
  </document>
""".strip()

def format_docs(docs):
    return "<documents>\n" + "\n".join(document_to_xml(d) for d in docs) + "\n</documents>"


def get_llm_prompt(q):
    docs = query(q)
        
    # context = "\n\n".join([f"===== Snippet {i} =====\n<Summary>{doc.page_content}</Summary>\n<Raw Code>{doc.metadata['code']}</Raw Code\n<Source>{doc.metadata['context']}</Source>"
    # for i, doc in enumerate(docs)])

    context = format_docs(docs)

    template = PromptTemplate(
        input_variables=["context", "question"],
        template=TEMPLATE
    )

    formatted_prompt = template.format(
        context=context,
        question="Can you summarize the mathematical features of MathSearch?"
    )

    return formatted_prompt


if __name__ == "__main__":
    get_vdb()