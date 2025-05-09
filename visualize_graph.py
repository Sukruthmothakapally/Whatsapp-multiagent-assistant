#!/usr/bin/env python3
import os
import logging
import requests
import base64
import re
from urllib.parse import quote

# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def extract_graph_structure():
    """Extract graph structure from the hardcoded graph definition."""
    logger.info("📄 Extracting graph structure from hardcoded definition...")
    
    try:
        # This is the graph definition from the message
        content = """from functools import lru_cache
import logging

from langgraph.graph import END, START, StateGraph

from agents.graphs.edges import route_by_decision, has_response, route_by_media_type
from agents.graphs.nodes import (
    process_media_node,
    routing_decision_node,
    direct_response_node,
    short_term_memory_node,
    long_term_memory_node,
    no_memory_node,
    fallback_node,
    update_memory_node,
    check_media_response_node,
    generate_image_node,
    generate_speech_node,
    summarize_today_node,
    news_node,
    send_email_node,
    calendar_event_node,
    task_node
)
from agents.graphs.state import RouterState

logger = logging.getLogger(__name__)

@lru_cache(maxsize=1)
def create_router_graph():
    \"\"\"Create the router workflow graph.\"\"\"
    graph_builder = StateGraph(RouterState)
    
    # Add all nodes
    graph_builder.add_node("process_media_node", process_media_node)
    graph_builder.add_node("routing_decision_node", routing_decision_node)
    graph_builder.add_node("direct_response_node", direct_response_node)
    graph_builder.add_node("short_term_memory_node", short_term_memory_node)
    graph_builder.add_node("long_term_memory_node", long_term_memory_node)
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
    graph_builder.add_node("task_node", task_node)
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
    graph_builder.add_conditional_edges("long_term_memory_node", has_response)
    graph_builder.add_conditional_edges("no_memory_node", has_response)
    graph_builder.add_conditional_edges("summarize_today_node", has_response)
    graph_builder.add_conditional_edges("news_node", has_response)
    graph_builder.add_conditional_edges("send_email_node", has_response)
    graph_builder.add_conditional_edges("calendar_event_node", has_response)
    graph_builder.add_conditional_edges("task_node", has_response)
    
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
"""
        
        # Extract nodes from add_node calls
        nodes = re.findall(r'graph_builder\.add_node\("([^"]+)"', content)
        logger.info(f"Found {len(nodes)} nodes")
        
        # Extract edges
        edges = []
        # Standard edges
        standard_edges = re.findall(r'graph_builder\.add_edge\(([^,]+),\s*"([^"]+)"\)', content)
        for src, dest in standard_edges:
            if src == "START":
                edges.append(("START", dest))
            elif dest == "END":
                edges.append((src, "END"))
            else:
                edges.append((src.strip('"'), dest))
        
        # Conditional edges with route functions
        conditional_edge_sections = re.findall(r'graph_builder\.add_conditional_edges\("([^"]+)",\s*([^)]+)\)', content)
        for src, route_func in conditional_edge_sections:
            route_func = route_func.strip()
            
            # Find the routing function and extract destinations
            if route_func == "route_by_decision":
                # From the code, determine possible destinations by examining node names
                decision_destinations = [
                    "direct_response_node", "short_term_memory_node", "long_term_memory_node", "no_memory_node",
                    "summarize_today_node", "news_node", "send_email_node", 
                    "calendar_event_node", "task_node"
                ]
                for dest in decision_destinations:
                    if dest in nodes:
                        edges.append((src, dest))
            
            elif route_func == "has_response":
                # This routes to either update_memory_node or fallback_node
                edges.append((src, "update_memory_node"))
                edges.append((src, "fallback_node"))
            
            elif route_func == "route_by_media_type":
                # This routes to generate_image_node, generate_speech_node, or final_node
                edges.append((src, "generate_image_node"))
                edges.append((src, "generate_speech_node"))
                edges.append((src, "final_node"))
        
        logger.info(f"Found {len(edges)} edges")
        return nodes, edges
    
    except Exception as e:
        logger.error(f"❌ Error extracting graph structure: {str(e)}")
        return [], []

def generate_mermaid_diagram(nodes, edges):
    """Generate Mermaid diagram syntax from nodes and edges."""
    logger.info("🔧 Generating Mermaid diagram...")
    
    mermaid_code = ["graph TD;"]
    
    # Add nodes with styling
    for node in nodes:
        node_id = node.replace("_node", "")
        mermaid_code.append(f'    {node_id}["{node}"];')
    
    # Add special nodes
    mermaid_code.append('    START((Start));')
    mermaid_code.append('    END((End));')
    
    # Add edges
    for src, dest in edges:
        src_id = src.replace("_node", "") if src != "START" and src != "END" else src
        dest_id = dest.replace("_node", "") if dest != "START" and dest != "END" else dest
        mermaid_code.append(f'    {src_id} --> {dest_id};')
    
    # Styling for the diagram
    mermaid_code.append('    classDef default fill:#f9f9f9,stroke:#333,stroke-width:1px;')
    mermaid_code.append('    classDef special fill:#ffd700,stroke:#333,stroke-width:2px;')
    mermaid_code.append('    class START,END special;')
    
    return "\n".join(mermaid_code)

def render_mermaid_diagram(mermaid_code):
    """Render the Mermaid diagram as PNG using the Mermaid.ink API."""
    logger.info("🎨 Rendering diagram using Mermaid.ink API...")
    
    try:
        # Encode the Mermaid code for the URL
        encoded_diagram = quote(mermaid_code)
        
        # Create the API URL
        api_url = f"https://mermaid.ink/img/{encoded_diagram}"
        
        # Get the PNG image
        response = requests.get(api_url)
        
        if response.status_code == 200:
            return response.content
        else:
            # For larger diagrams, use the POST endpoint with JSON
            logger.info("Using alternative method for larger diagram...")
            encoded_base64 = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
            json_payload = {"mermaid": mermaid_code}
            
            response = requests.post(
                "https://mermaid.ink/img",
                json=json_payload
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"❌ API returned status code: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
    
    except Exception as e:
        logger.error(f"❌ Error rendering diagram: {str(e)}")
        return None

def visualize_with_mermaid():
    """Render and save the router graph as a PNG using Mermaid.ink API."""
    try:
        logger.info("🔧 Starting Mermaid graph visualization...")
        
        # Extract graph structure directly from the hardcoded definition
        nodes, edges = extract_graph_structure()
        
        if not nodes or not edges:
            logger.error("❌ Failed to extract graph structure")
            return
        
        # Generate Mermaid diagram code
        mermaid_code = generate_mermaid_diagram(nodes, edges)
        
        # Render the diagram
        img_bytes = render_mermaid_diagram(mermaid_code)
        
        if img_bytes:
            # Save the image
            output_path = os.path.join(os.getcwd(), "router_graph_mermaid.png")
            with open(output_path, "wb") as f:
                f.write(img_bytes)
            
            logger.info(f"✅ Graph image saved at: {output_path}")
        else:
            # Alternative: Save the Mermaid code to a file for manual rendering
            logger.warning("⚠️ Could not render image directly, saving Mermaid code instead")
            output_path = os.path.join(os.getcwd(), "router_graph_mermaid.md")
            with open(output_path, "w") as f:
                f.write("```mermaid\n")
                f.write(mermaid_code)
                f.write("\n```")
            
            logger.info(f"✅ Mermaid code saved at: {output_path}")
            logger.info("You can render this manually at https://mermaid.live")
    
    except Exception as e:
        logger.error("❌ Error generating graph image", exc_info=True)

if __name__ == "__main__":
    visualize_with_mermaid()