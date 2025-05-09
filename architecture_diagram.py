from diagrams import Diagram, Cluster, Edge
from diagrams.custom import Custom
from diagrams.onprem.container import Docker
from diagrams.programming.framework import FastAPI

with Diagram("WhatsApp_Multi_Agent_AI_Assistant", show=False, direction="LR"):

    # Client Section
    with Cluster("Client"):
        user = Custom("User", "images/user.png")
        whatsapp = Custom("WhatsApp", "images/whatsapp.png")
        chainlit = Custom("Chainlit UI", "images/chainlit.png")

        user >> whatsapp
        user >> chainlit

    # Server Section
    with Cluster("Server"):
        fastapi = FastAPI("FastAPI")

        with Cluster("Multi-Agent System (LangGraph)"):
            router = Custom("Routing Agent\n(Grok)", "images/routing_agent.png")

            audio_agents = Custom("Audio Processing\nSTT: Whisper\nTTS: ElevenLabs", "images/stt_tts.png")
            image_agents = Custom("Image Processing\nITT: Llama\nTTI: Together AI", "images/itt_tti.png")
            task_agents = Custom("Specialized Task Agents\n(Powered by Grok)", "images/groq.png")

            router >> audio_agents
            router >> image_agents
            router >> task_agents

        # Memory Systems
        with Cluster("Memory Systems"):
            short_term = Custom("Short-Term Memory\n(SQLite)", "images/sqlite.png")
            long_term = Custom("Long-Term Memory\n(Qdrant Vector DB)", "images/qdrant.png")

            task_agents >> short_term
            task_agents >> long_term

        # Integrations Section
        with Cluster("Integrations"):
            news_api = Custom("News API", "images/news.png")

            with Cluster("Google Workspace API"):
                gmail_api = Custom("Gmail API", "images/gmail.png")
                calendar_api = Custom("Calendar API", "images/calendar.png")
                tasks_api = Custom("Tasks API", "images/tasks.png")

            task_agents >> news_api
            task_agents >> gmail_api
            task_agents >> calendar_api
            task_agents >> tasks_api

        # Data Pipeline
        with Cluster("Data Pipeline"):
            prefect = Custom("Prefect", "images/prefect_logo.png")
            etl = Custom("ETL Daily Summary", "images/etl.png")

            prefect >> etl
            etl >> task_agents
            gmail_api >> Edge(color="darkgreen") >> etl
            calendar_api >> Edge(color="darkgreen") >> etl
            tasks_api >> Edge(color="darkgreen") >> etl

    # Infrastructure
    with Cluster("Infrastructure"):
        docker = Docker("Docker & Docker Compose")
        ngrok = Custom("Ngrok\n(HTTPS Tunnel)", "images/ngrok.png")
        cron = Custom("Cron Jobs", "images/cron.png")

        docker >> fastapi
        docker >> prefect
        fastapi >> ngrok
        cron >> prefect

    # Main connections
    whatsapp >> Edge(color="darkgreen") >> ngrok
    ngrok >> Edge(color="darkgreen") >> fastapi
    chainlit >> Edge(color="darkgreen") >> fastapi

    fastapi >> Edge(color="darkgreen") >> router

    # Return path
    fastapi >> Edge(color="darkgreen", style="dashed") >> whatsapp
    fastapi >> Edge(color="darkgreen", style="dashed") >> chainlit
