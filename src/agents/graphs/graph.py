from functools import lru_cache
import logging

from langgraph.graph import END, START, StateGraph

from agents.graphs.edges import route_by_decision, has_response, route_by_media_type
from agents.graphs.nodes import (
    process_media_node,
    routing_decision_node,
    direct_response_node,
    short_term_memory_node,
    no_memory_node,
    fallback_node,
    update_memory_node,
    check_media_response_node,
    generate_image_node,
    generate_speech_node,
    summarize_today_node,
    news_node,
    send_email_node,
    calendar_event_node
)
from agents.graphs.state import RouterState

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def create_router_graph():
    """Create the router workflow graph."""
    graph_builder = StateGraph(RouterState)
    
    # Add all nodes
    graph_builder.add_node("process_media_node", process_media_node)
    graph_builder.add_node("routing_decision_node", routing_decision_node)
    graph_builder.add_node("direct_response_node", direct_response_node)
    graph_builder.add_node("short_term_memory_node", short_term_memory_node)
    graph_builder.add_node("no_memory_node", no_memory_node)
    graph_builder.add_node("fallback_node", fallback_node)
    graph_builder.add_node("update_memory_node", update_memory_node)
    graph_builder.add_node("check_media_response_node", check_media_response_node)
    graph_builder.add_node("generate_image_node", generate_image_node)
    graph_builder.add_node("generate_speech_node", generate_speech_node)
    graph_builder.add_node("summarize_today_node", summarize_today_node)
    graph_builder.add_node("news_node", news_node)
    graph_builder.add_node("send_email_node", send_email_node)
    graph_builder.add_node("calendar_event_node", calendar_event_node)
    graph_builder.add_node("final_node", lambda x: x)  # Identity node to end the graph
    
    # Define the flow
    # Start with processing the media
    graph_builder.add_edge(START, "process_media_node")
    
    # Then decide on the routing strategy
    graph_builder.add_edge("process_media_node", "routing_decision_node")
    
    # Route to the appropriate node based on the decision
    graph_builder.add_conditional_edges("routing_decision_node", route_by_decision)
    
    # Check if a response was generated, go to fallback if not
    graph_builder.add_conditional_edges("direct_response_node", has_response)
    graph_builder.add_conditional_edges("short_term_memory_node", has_response)
    graph_builder.add_conditional_edges("no_memory_node", has_response)
    graph_builder.add_conditional_edges("summarize_today_node", has_response)
    graph_builder.add_conditional_edges("news_node", has_response)
    graph_builder.add_conditional_edges("send_email_node", has_response)
    graph_builder.add_conditional_edges("calendar_event_node", has_response)
    
    # After memory update, check if the response should be converted to a different media type
    graph_builder.add_edge("update_memory_node", "check_media_response_node")
    graph_builder.add_edge("fallback_node", "check_media_response_node")
    
    # Route based on the response media type
    graph_builder.add_conditional_edges("check_media_response_node", route_by_media_type)
    
    # End the graph
    graph_builder.add_edge("generate_image_node", END)
    graph_builder.add_edge("generate_speech_node", END)
    graph_builder.add_edge("final_node", END)
    
    return graph_builder

# Compiled graph for use
router_graph = create_router_graph().compile()

# Main entry point function that will replace the current route_message
async def route_message(
    message: str | bytes,
    conversation_id: str | None = None,
    media_type: str = "text"
) -> str | bytes:
    """Route a message through the LangGraph workflow."""
    conversation_id = conversation_id or "default"
    logger.info(f"\n📨 [{conversation_id}] Received: {type(message).__name__} | Media type: {media_type}")
    
    # Initialize the state
    initial_state = RouterState(
        conversation_id=conversation_id,
        media_type=media_type,
        raw_input=message,
        messages=[],  # Start with empty messages, will be filled by process_media_node
    )
    
    # Execute the graph
    final_state = await router_graph.ainvoke(initial_state)
    
    # Return the appropriate response
    if "response_bytes" in final_state and final_state["response_bytes"]:
        return final_state["response_bytes"]
    else:
        return final_state.get("response_text", "Sorry, I couldn't generate a response.")

# import os
# import logging
# from langchain_core.runnables.graph import MermaidDrawMethod

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# def visualize_with_mermaid():
#     """Render and save the router graph as a PNG using Mermaid.ink API."""
#     try:
#         logger.info("🔧 Starting Mermaid graph visualization...")

#         # Compile and access internal graph
#         compiled_graph = create_router_graph().compile()
#         mermaid_graph = compiled_graph.get_graph()

#         logger.info("🧠 Compiled graph retrieved successfully.")

#         # Generate image
#         img_bytes = mermaid_graph.draw_mermaid_png(draw_method=MermaidDrawMethod.API)

#         output_path = os.path.join(os.getcwd(), "router_graph_mermaid.png")
#         with open(output_path, "wb") as f:
#             f.write(img_bytes)

#         logger.info(f"✅ Graph image saved at: {output_path}")

#     except Exception as e:
#         logger.error("❌ Error generating graph image", exc_info=True)

# # if __name__ == "__main__":
# #     visualize_with_mermaid()