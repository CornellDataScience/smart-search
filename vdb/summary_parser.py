from langchain.schema import Document
import json

def extract_documents(node):
    # Extracts LangChain Documents from nested JSON data
    
    documents = []
    name = node.get("name", "")
    
    # Final summary for file or directory
    final = node.get("final_summary")
    if final and final.get("summary") is not None:
        documents.append(Document(
            page_content=final["summary"],
            metadata={
                "type": node.get("type"),
                "name": final.get("name", ""),
                "path": node.get("path"),
                "code": final.get("code", ""),
                "summary" : final["summary"]
            }
        ))

    # Function-level summaries inside PYTHON_FILE
    if node.get("type") == "PYTHON_FILE":
        curr_path = node['path']
        for func in node.get("summaries", []):
            documents.append(Document(
                page_content=f"{func['summary']}\n\n{func['code']}",
                metadata={
                    "type": "FUNCTION",
                    "name": func["name"],
                    "path": curr_path,
                    "code": func['code'],
                    "summary": func['summary'],
                }
            ))

    for child in node.get("children", []):
        documents.extend(extract_documents(child))

    return documents



def test_conversion(filepath):
    with open(filepath, "r") as f:
        data = json.load(f)
        
    documents = extract_documents(data)

    serializable_docs = [
        {"page_content": doc.page_content, "metadata": doc.metadata}
        for doc in documents
    ]

    with open("data/langchain_docs.json", "w", encoding="utf-8") as f:
        json.dump(serializable_docs, f, indent=2)
        
    
test_conversion("../summary_output.json")