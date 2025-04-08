import httpx
from server.config import settings
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

HEADERS = {
    "api-key": settings.qdrant_api_key,
    "Content-Type": "application/json"
}

def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()

def add_to_qdrant(conversation_id: str, message: str):
    vector = embed_text(message)
    payload = {
        "points": [
            {
                "id": conversation_id + "_" + str(hash(message)),
                "vector": vector,
                "payload": {"conversation_id": conversation_id, "message": message}
            }
        ]
    }
    httpx.put(
        f"{settings.qdrant_url}/collections/chainlit_memory/points?wait=true",
        json=payload,
        headers=HEADERS
    )

def query_qdrant(query: str) -> str:
    vector = embed_text(query)
    payload = {
        "vector": vector,
        "top": 1,
        "with_payload": True
    }
    response = httpx.post(
        f"{settings.qdrant_url}/collections/chainlit_memory/points/search",
        json=payload,
        headers=HEADERS
    )
    if response.status_code == 200:
        hits = response.json().get("result", [])
        if hits:
            return hits[0]["payload"]["message"]
    return ""
