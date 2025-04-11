import logging
from agents.text_agents.groq import ask_groq, ask_routing_agent
from memory.short_term import get_memory, add_to_memory
from memory.long_term import query_qdrant, add_to_qdrant

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def is_error(response: str) -> bool:
    return not response or response.lower().startswith("error:")

async def route_message(message: str, conversation_id: str | None = None) -> str:
    conversation_id = conversation_id or "default"
    logger.info(f"📨 Message [{conversation_id}]: {message}")

    routing_context = f"""
        You are a routing agent. Your job is to determine the best memory source for answering the user's query.
        You must return only one of these responses: DIRECT, USE_SHORT_TERM, USE_LONG_TERM, or NONE.

        Use this logic:
        1. If the user is stating a fact (e.g., 'I live in New York', 'I am a student'), treat it as DIRECT.
        2. If the question includes recency indicators like 'did I just', 'did I recently', 'did I mention earlier', return USE_SHORT_TERM.
        3. If it's about past facts without recent cues (e.g., 'What is my name?', 'Where do I live?'), return USE_LONG_TERM.
        4. If the query is generic or unrelated to memory, return NONE.

        Examples:
        - 'I live in Bangalore' → DIRECT
        - 'I’m pursuing a master’s in CS' → DIRECT
        - 'Did I just tell you my degree?' → USE_SHORT_TERM
        - 'Did I mention my name earlier?' → USE_SHORT_TERM
        - 'Where do I live?' → USE_LONG_TERM
        - 'What’s my background?' → USE_LONG_TERM
        - 'Tell me a joke' → NONE

        User query: {message}
    """

    decision = ask_routing_agent(routing_context).strip().split()[0].upper()
    logger.info(f"🧭 Routing decision: {decision} → [{conversation_id}]")

    response = ""
    used_memory_type = None

    if decision == "DIRECT":
        response = ask_groq(message)
        if is_error(response):
            logger.error(f"❗ LLM error in DIRECT: {response}")
            response = "Sorry, I had trouble answering that. Could you please rephrase?"
        used_memory_type = "direct"

    elif decision == "USE_SHORT_TERM":
        memory = get_memory(conversation_id)
        if memory:
            context = "\n".join([f"{role.capitalize()}: {msg}" for role, msg in memory]) + f"\nUser: {message}"
            relevance_prompt = (
                f"You are a relevance evaluator. Return YES or NO only.\n"
                f"Does the following context help answer the user's question?\n\n"
                f"Context:\n{context}\n\nQuestion: {message}"
            )
            relevance = ask_routing_agent(relevance_prompt).strip().split()[0].upper()
            if relevance == "YES":
                response = ask_groq(context)
                if is_error(response):
                    logger.error(f"❗ LLM error in SHORT_TERM: {response}")
                    response = "Sorry, I had trouble answering that. Could you please rephrase?"
                used_memory_type = "short_term"
            else:
                logger.info(f"📭 Short-term memory exists but is not relevant. Trying long-term.")
                decision = "USE_LONG_TERM"
        else:
            logger.info(f"📭 No short-term memory found. Trying long-term.")
            decision = "USE_LONG_TERM"

    if decision == "USE_LONG_TERM":
        retrieved = query_qdrant(message)
        logger.info(f"📦 Qdrant returned context for [{conversation_id}]")
        if retrieved:
            
            context = f"{retrieved} User: {message}"
            relevance_prompt = (
                f"You are a relevance evaluator. Return YES or NO only.\n"
                f"Does the following info help answer the user's question?\n\n"
                f"Info: {retrieved}\n\nQuestion: {message}"
            )
            relevance = ask_routing_agent(relevance_prompt).strip().split()[0].upper()
            if relevance == "YES":
                response = ask_groq(context)
                if is_error(response):
                    logger.error(f"❗ LLM error in LONG_TERM: {response}")
                    response = "Sorry, I had trouble answering that. Could you please rephrase?"
                used_memory_type = "long_term"
            else:
                logger.info(f"❌ Long-term memory not relevant. Answering fresh.")
                context = "User asked something that has no relevant memory. Answer fresh.\n\nUser: " + message
                response = ask_groq(context)
                if is_error(response):
                    logger.error(f"❗ LLM error in fallback from long_term: {response}")
                    response = "Sorry, I had trouble answering that. Could you please rephrase?"
                used_memory_type = "none"
        else:
            logger.info(f"❌ No long-term memory found. Answering fresh.")
            context = "User asked something that has no relevant memory. Answer fresh.\n\nUser: " + message
            response = ask_groq(context)
            if is_error(response):
                logger.error(f"❗ LLM error in fallback from no long_term: {response}")
                response = "Sorry, I had trouble answering that. Could you please rephrase?"
            used_memory_type = "none"

    elif decision == "NONE":
        logger.info(f"🔄 No memory used. Answering fresh.")
        context = "User asked something that has no relevant memory. Answer fresh.\n\nUser: " + message
        response = ask_groq(context)
        if is_error(response):
            logger.error(f"❗ LLM error in NONE case: {response}")
            response = "Sorry, I had trouble answering that. Could you please rephrase?"
        used_memory_type = "none"

    if not response:
        logger.warning(f"⚠️ No response generated. Using fallback.")
        response = ask_groq(message)
        if is_error(response):
            logger.error(f"❗ Fallback also failed: {response}")
            response = "Sorry, something went wrong with the assistant."
        used_memory_type = "fallback"

    add_to_memory(conversation_id, "user", message)
    add_to_memory(conversation_id, "assistant", response)
    add_to_qdrant(conversation_id, message)

    logger.info(f"✅ [{conversation_id}] → Used: {used_memory_type}")
    return response
