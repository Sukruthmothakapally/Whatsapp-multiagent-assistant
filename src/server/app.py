from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
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
    audio: UploadFile = File(None),
    image: UploadFile = File(None)
):
    """
    Flexible endpoint:
    - If audio uploaded: process with STT.
    - If image uploaded: process with ITT.
    - If message provided: use as text.
    - If image generated (via TTI), return image bytes.
    """

    try:
        # --- AUDIO INPUT ---
        if audio:
            audio_bytes = await audio.read()
            reply = await route_message(audio_bytes, conversation_id, media_type="audio")

            if isinstance(reply, bytes):
                return StreamingResponse(iter([reply]), media_type="audio/mpeg")
            return JSONResponse({"reply": reply})

        # --- IMAGE INPUT ---
        elif image:
            image_bytes = await image.read()
            reply = await route_message(image_bytes, conversation_id, media_type="image")

            if isinstance(reply, bytes):
                return Response(content=reply, media_type="image/png")
            return JSONResponse({"reply": reply})

        # --- TEXT INPUT ---
        elif message:
            reply = await route_message(message, conversation_id, media_type="text")

            if isinstance(reply, bytes):
                return Response(content=reply, media_type="image/png")
            return JSONResponse({"reply": reply})

        else:
            return JSONResponse({"error": "No input provided"}, status_code=400)

    except Exception as e:
        return JSONResponse({"error": f"Internal Server Error: {str(e)}"}, status_code=500)