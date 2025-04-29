from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
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

@app.post("/chat")
async def chat(
    message: str = Form(None),
    conversation_id: str = Form(None),
    audio: UploadFile = File(None)
):
    """
    Flexible endpoint:
    - If audio uploaded, process audio.
    - If text provided, process text.
    """

    if audio:
        audio_bytes = await audio.read()
        reply = await route_message(audio_bytes, conversation_id)
        
        if isinstance(reply, bytes):
            return StreamingResponse(iter([reply]), media_type="audio/mpeg")
        
        return JSONResponse({"reply": reply})

    elif message:
        reply = await route_message(message, conversation_id)
        return JSONResponse({"reply": reply})

    else:
        return JSONResponse({"error": "No input provided"}, status_code=400)
