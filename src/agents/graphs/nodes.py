import logging
from typing import Dict, Any
from langchain_core.messages import HumanMessage, AIMessage

from agents.text_agents.groq import ask_groq, ask_routing_agent
from memory.short_term import get_memory, add_to_memory
from memory.long_term import query_qdrant, add_to_qdrant
from agents.audio_agents.speech_to_text import SpeechToText
from agents.audio_agents.text_to_speech import TextToSpeech
from agents.image_agents.image_to_text import ImageToText
from agents.image_agents.text_to_image import TextToImage

logger = logging.getLogger(__name__)

def is_error(response: str) -> bool:
    """Check if a response indicates an error."""
    return not response or response.lower().startswith("error:")

async def process_media_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Process different media types into text."""
    raw_input = state.get("raw_input")
    media_type = state.get("media_type")
    
    if media_type == "audio":
        logger.info("🎧 Detected audio input, invoking STT...")
        stt = SpeechToText()
        try:
            text = await stt.transcribe(raw_input)
            logger.info(f"✅ Transcribed to text: {text}")
            return {
                "messages": [HumanMessage(content=text)]
            }
        except Exception as e:
            logger.error(f"❗ STT error: {e}")
            error_msg = f"Sorry, I couldn't understand the audio: {e}"
            return {
                "messages": [HumanMessage(content="[Audio transcription failed]")],
                "response_text": error_msg,
                "routing_decision": "NONE"
            }

    elif media_type == "image":
        logger.info("🖼️ Detected image input, invoking ITT...")
        try:
            itt = ImageToText()
            text = await itt.analyze_image(raw_input)
            logger.info(f"✅ Image described as: {text}")
            return {
                "messages": [HumanMessage(content=text)]
            }
        except Exception as e:
            logger.error(f"❗ ITT error: {e}")
            error_msg = f"Sorry, I couldn't understand the image: {e}"
            return {
                "messages": [HumanMessage(content="[Image analysis failed]")],
                "response_text": error_msg,
                "routing_decision": "NONE"
            }
    
    # For text, just pass through
    return {
        "messages": [HumanMessage(content=raw_input)]
    }

async def routing_decision_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Determine routing strategy for the message."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    routing_context = f"""
        You are a routing agent. Your job is to determine the best memory source for answering the user's query.
        You must return only one of these responses: DIRECT, USE_SHORT_TERM, or NONE. 

        Use this logic:
        1. If the user is stating a fact (e.g., 'I live in New York', 'I am a student'), treat it as DIRECT.
        2. If the question includes recency indicators like ('did I just', 'did I recently', 'did I mention earlier'),
           or if it's about past facts without recent cues (e.g., 'What is my name?', 'Where do I live?') return USE_SHORT_TERM.
        3. If the query is generic or unrelated to memory, return NONE.

        Examples:
        - 'I live in Bangalore' → DIRECT
        - 'I'm pursuing a master's in CS' → DIRECT
        - 'Did I just tell you my degree?' → USE_SHORT_TERM
        - 'Tell me a joke' → NONE

        User query: {message}
    """

    decision = ask_routing_agent(routing_context).strip().split()[0].upper()
    logger.info(f"🧭 Routing decision: {decision}")
    
    return {"routing_decision": decision}

async def direct_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a direct response without memory."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    response = ask_groq(message)
    logger.info("📗 DIRECT → LLM called")
    
    if is_error(response):
        logger.error(f"❗ LLM error in DIRECT: {response}")
        response = "Sorry, I had trouble answering that. Could you please rephrase?"
    
    return {
        "response_text": response,
        "memory_used": "direct",
        "messages": state["messages"] + [AIMessage(content=response)]
    }

async def short_term_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a response using short-term memory."""
    # Get the most recent message
    message = state["messages"][-1].content
    conversation_id = state.get("conversation_id", "default")
    
    memory = get_memory(conversation_id)
    if memory:
        context = "\n".join([f"{role.capitalize()}: {msg}" for role, msg in memory]) + f"\nUser: {message}"
        relevance_prompt = (
            f"You are a relevance evaluator. Return YES or NO only.\n"
            f"Does the following context help answer the user's question?\n\n"
            f"Context:\n{context}\n\nQuestion: {message}"
        )
        relevance = ask_routing_agent(relevance_prompt).strip().split()[0].upper()
        logger.info(f"📘 SHORT_TERM → Relevant: {relevance}")
        
        if relevance == "YES":
            response = ask_groq(context)
            if is_error(response):
                logger.error(f"❗ LLM error in SHORT_TERM: {response}")
                response = "Sorry, I had trouble answering that. Could you please rephrase?"
            
            return {
                "response_text": response,
                "memory_used": "short_term",
                "messages": state["messages"] + [AIMessage(content=response)]
            }
    
    # Fallback to direct if memory not useful
    logger.info("📙 SHORT_TERM → No relevant memory, falling back to direct.")
    return await direct_response_node(state)

async def no_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a response without using memory."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    logger.info("🔄 NONE → Answering fresh without memory.")
    context = "User asked something that has no relevant memory. Answer fresh.\n\nUser: " + message
    response = ask_groq(context)
    
    if is_error(response):
        logger.error(f"❗ LLM error in NONE case: {response}")
        response = "Sorry, I had trouble answering that. Could you please rephrase?"
    
    return {
        "response_text": response,
        "memory_used": "none",
        "messages": state["messages"] + [AIMessage(content=response)]
    }

async def fallback_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a fallback response when other methods fail."""
    # Get the most recent message
    message = state["messages"][-1].content
    
    logger.warning("⚠️ No response generated. Using fallback.")
    response = ask_groq(message)
    
    if is_error(response):
        logger.error(f"❗ Fallback also failed: {response}")
        response = "Sorry, something went wrong with the assistant."
    
    return {
        "response_text": response,
        "memory_used": "fallback",
        "messages": state["messages"] + [AIMessage(content=response)]
    }

async def update_memory_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Update memory with the conversation."""
    conversation_id = state.get("conversation_id", "default")
    
    # Get the last two messages (user and assistant)
    if len(state["messages"]) >= 2:
        user_message = state["messages"][-2].content
        assistant_message = state["messages"][-1].content
        
        add_to_memory(conversation_id, "user", user_message)
        add_to_memory(conversation_id, "assistant", assistant_message)
        add_to_qdrant(conversation_id, user_message)
        
        logger.info(f"✅ Final → Memory Updated: {conversation_id}")
    
    return {}

async def check_media_response_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Check if the response should be converted to a different media type."""
    # If there's no response text, skip this node
    if not state.get("response_text"):
        return {"response_media_type": "text"}
    
    response = state["response_text"]
    media_type = state.get("media_type")
    
    # Check if this should be an image
    tti_routing_prompt = f"""
        You are an intelligent router. The user or assistant has responded with:
        "{response}"
        Should this be treated as a prompt to generate an image? 
        Only return YES or NO.
        """
    
    is_tti = ask_routing_agent(tti_routing_prompt).strip().split()[0].upper() == "YES"
    
    if is_tti:
        return {"response_media_type": "image"}
    elif media_type == "audio":
        return {"response_media_type": "audio"}
    else:
        return {"response_media_type": "text"}

async def generate_image_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate an image based on the response."""
    response = state["response_text"]
    
    try:
        logger.info(f"🖌️ LLM router says generate image → invoking TTI for: {response}")
        tti = TextToImage()
        image_bytes = await tti.generate_image(response)
        logger.info("✅ TTI image generated successfully")
        
        return {"response_bytes": image_bytes}
    except Exception as e:
        logger.error(f"❗ TTI error: {e}")
        return {"response_media_type": "text"}  # Fall back to text

async def generate_speech_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """Generate speech based on the response."""
    response = state["response_text"]
    
    logger.info("🔈 Detected original audio input — converting reply to speech...")
    tts = TextToSpeech()
    try:
        audio_bytes = await tts.synthesize(response)
        logger.info("✅ Audio synthesis complete")
        
        return {"response_bytes": audio_bytes}
    except Exception as e:
        logger.error(f"❗ TTS error: {e}")
        return {"response_media_type": "text"} 