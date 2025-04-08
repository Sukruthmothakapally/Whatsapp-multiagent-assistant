from agents.text_agents.groq import ask_groq
from memory.short_term import get_memory, add_to_memory
from memory.long_term import query_qdrant, add_to_qdrant

async def route_message(message: str, conversation_id: str | None = None) -> str:
    conversation_id = conversation_id or "default"
    memory = get_memory(conversation_id)

    if memory:
        context = "\n".join([f"{role.capitalize()}: {msg}" for role, msg in memory]) + f"\nUser: {message}"
        response = ask_groq(context)
    else:
        retrieved = query_qdrant(message)
        context = retrieved + "\n" + message if retrieved else message
        response = ask_groq(context)

    add_to_memory(conversation_id, "user", message)
    add_to_memory(conversation_id, "assistant", response)
    add_to_qdrant(conversation_id, message)
    return response
