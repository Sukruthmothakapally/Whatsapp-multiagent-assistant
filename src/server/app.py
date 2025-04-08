from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.models import MessageRequest, MessageResponse
from agents.text_agents.groq import ask_groq

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev. Lock down in prod.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=MessageResponse)
async def chat(req: MessageRequest):
    reply = ask_groq(req.message, req.conversation_id)
    return {"reply": reply}
