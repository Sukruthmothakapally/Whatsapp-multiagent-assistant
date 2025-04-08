import httpx
import uuid
from server.config import settings
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

HEADERS = {
    "api-key": settings.qdrant_api_key,
    "Content-Type": "application/json"
}

COLLECTION_NAME = "chainlit_memory"
VECTOR_DIM = 384

def embed_text(text: str) -> list[float]:
    return model.encode(text).tolist()

def ensure_collection_exists():
    schema = {
        "vectors": {
            "size": VECTOR_DIM,
            "distance": "Cosine"
        }
    }

    try:
        response = httpx.put(
            f"{settings.qdrant_url}/collections/{COLLECTION_NAME}",
            headers=HEADERS,
            json=schema
        )
        if response.status_code not in (200, 201, 409):
            print(f"⚠️ Qdrant collection create failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception while creating Qdrant collection: {e}")

def add_to_qdrant(conversation_id: str, message: str):
    ensure_collection_exists()
    vector = embed_text(message)

    point_id = str(uuid.uuid4())

    payload = {
        "points": [
            {
                "id": point_id,
                "vector": vector,
                "payload": {
                    "conversation_id": conversation_id,
                    "message": message
                }
            }
        ]
    }

    try:
        response = httpx.put(
            f"{settings.qdrant_url}/collections/{COLLECTION_NAME}/points?wait=true",
            json=payload,
            headers=HEADERS
        )
        if response.status_code not in (200, 201):
            print(f"⚠️ Failed to add point to Qdrant: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception while adding to Qdrant: {e}")

def query_qdrant(query: str) -> str:
    vector = embed_text(query)
    payload = {
        "vector": vector,
        "top": 1,
        "with_payload": True
    }

    try:
        response = httpx.post(
            f"{settings.qdrant_url}/collections/{COLLECTION_NAME}/points/search",
            json=payload,
            headers=HEADERS
        )
        if response.status_code == 200:
            hits = response.json().get("result", [])
            if hits:
                message = hits[0]["payload"].get("message", "")
                print(f"🔁 Retrieved from Qdrant: {message}")
                return message
        else:
            print(f"⚠️ Qdrant search failed: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Exception during Qdrant search: {e}")

    return ""
