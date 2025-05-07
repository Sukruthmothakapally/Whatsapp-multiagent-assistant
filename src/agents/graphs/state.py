from langgraph.graph import MessagesState
from typing import Optional, Literal

class RouterState(MessagesState):
    """State class for the router workflow.
    
    Extends MessagesState to track conversation history.
    
    Additional attributes:
        conversation_id (str): The ID of the current conversation
        media_type (str): The type of media being processed ('text', 'audio', 'image')
        raw_input (bytes | str): The raw input before processing
        routing_decision (str): The routing decision from the routing agent
        memory_used (str): Type of memory used for the response
        response_text (str): The text response
        response_media_type (str): The media type of the response ('text', 'audio', 'image')
        response_bytes (bytes): The response as bytes (for audio or image)
    """
    
    # Additional state properties
    conversation_id: str = "default"
    media_type: Literal["text", "audio", "image"] = "text"
    raw_input: Optional[bytes | str] = None
    routing_decision: Optional[Literal["DIRECT", "USE_SHORT_TERM", "NONE", "SUMMARIZE_TODAY"]] = None
    memory_used: Optional[Literal["direct", "short_term", "none", "fallback", "summary"]] = None
    response_text: Optional[str] = None
    response_media_type: Optional[Literal["text", "audio", "image"]] = "text"
    response_bytes: Optional[bytes] = None