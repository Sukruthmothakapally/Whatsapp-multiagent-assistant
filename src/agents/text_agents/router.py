from agents.text_agents.groq import ask_groq
from memory.short_term import get_memory, add_to_memory
from memory.long_term import query_qdrant, add_to_qdrant

async def route_message(message: str, conversation_id: str | None = None) -> str:
    conversation_id = conversation_id or "default"
    memory = get_memory(conversation_id)

    if memory:
        context = "\n".join(memory) + "\n" + message
        response = ask_groq(context)
    else:
        retrieved = query_qdrant(message)
        context = retrieved + "\n" + message if retrieved else message
        response = ask_groq(context)

    add_to_memory(conversation_id, message)
    add_to_qdrant(conversation_id, message)
    return response
