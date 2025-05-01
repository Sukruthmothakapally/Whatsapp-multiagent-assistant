# # visual_graph.py

# from graph import create_router_graph  # Adjust the import path if needed
# from langchain_core.runnables.graph import MermaidDrawMethod
# from IPython.display import Image, display

# def visualize_router_graph_mermaid():
#     # Get the graph object from LangGraph
#     graph = create_router_graph().get_graph()

#     # Render to PNG using Mermaid.ink API
#     img = graph.draw_mermaid_png(
#         draw_method=MermaidDrawMethod.API
#     )

#     # Save to file
#     with open("router_graph_mermaid.png", "wb") as f:
#         f.write(img)

#     print("✅ Mermaid-based graph saved as router_graph_mermaid.png")

# if __name__ == "__main__":
#     visualize_router_graph_mermaid()
