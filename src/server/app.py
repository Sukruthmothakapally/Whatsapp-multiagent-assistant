from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from server.models import MessageRequest, MessageResponse
from agents.text_agents.router import route_message

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat", response_model=MessageResponse)
async def chat(req: MessageRequest):
    reply = await route_message(req.message, req.conversation_id)
    return {"reply": reply}
