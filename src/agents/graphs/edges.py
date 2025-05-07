from typing import Literal, Dict, Any

def route_by_decision(state: Dict[str, Any]) -> Literal["direct_response_node", "short_term_memory_node", "no_memory_node", "summarize_today_node", "news_node"]:
    """Route based on the decision from the routing agent."""
    # If routing_decision is already set by a previous node, use it
    if "routing_decision" in state and state["routing_decision"]:
        decision = state["routing_decision"]
    else:
        decision = "DIRECT"  # Default to direct
        
    if decision == "DIRECT":
        return "direct_response_node"
    elif decision == "USE_SHORT_TERM":
        return "short_term_memory_node"
    elif decision == "SUMMARIZE_TODAY":
        return "summarize_today_node"
    elif decision == "NEWS":
        return "news_node"
    elif decision == "NONE":
        return "no_memory_node"
    else:
        # Fallback to direct if decision is unknown
        return "direct_response_node"

def has_response(state: Dict[str, Any]) -> Literal["update_memory_node", "fallback_node"]:
    """Check if a response text was generated."""
    if state.get("response_text"):
        return "update_memory_node"
    else:
        return "fallback_node"

def route_by_media_type(state: Dict[str, Any]) -> Literal["generate_image_node", "generate_speech_node", "final_node"]:
    """Route based on the response media type."""
    media_type = state.get("response_media_type", "text")
    
    if media_type == "image":
        return "generate_image_node"
    elif media_type == "audio":
        return "generate_speech_node"
    else:
        return "final_node"