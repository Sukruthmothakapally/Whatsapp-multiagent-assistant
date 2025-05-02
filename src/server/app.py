from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from agents.text_agents.router import route_message
import httpx
import os

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN") 
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")  
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    else:
        return JSONResponse({"error": "Verification failed"}, status_code=403)


@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    try:
        payload = await request.json()
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        messages = value.get("messages", [])
        if not messages:
            return JSONResponse({"status": "no message"}, status_code=200)

        message = messages[0]
        sender = message.get("from")
        msg_id = message.get("id")
        is_from_business = message.get("from") == value.get("metadata", {}).get("display_phone_number")

        # Prevent bot from responding to its own message
        if is_from_business:
            print("🔁 Ignoring message from self")
            return JSONResponse({"status": "ignored self-message"}, status_code=200)

        msg_type = message.get("type")

        # --- Handle text ---
        if msg_type == "text":
            text = message["text"]["body"]
            reply = await route_message(text, sender, media_type="text")
            await send_whatsapp_response(sender, reply)

        # --- Handle audio ---
        elif msg_type == "audio":
            media_id = message["audio"]["id"]
            audio_bytes = await download_whatsapp_media(media_id)
            reply = await route_message(audio_bytes, sender, media_type="audio")
            await send_whatsapp_response(sender, reply)

        # --- Handle image ---
        elif msg_type == "image":
            media_id = message["image"]["id"]
            image_bytes = await download_whatsapp_media(media_id)
            reply = await route_message(image_bytes, sender, media_type="image")
            await send_whatsapp_response(sender, reply)

        else:
            return JSONResponse({"status": f"unsupported message type: {msg_type}"}, status_code=200)

        return JSONResponse({"status": "message processed"}, status_code=200)

    except Exception as e:
        return JSONResponse({"error": f"Webhook handler failed: {str(e)}"}, status_code=500)


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


async def send_whatsapp_response(to: str, reply: str | bytes):
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    if isinstance(reply, str):
        # Text response
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": reply}
        }
    elif isinstance(reply, bytes):
        # Upload media first
        async with httpx.AsyncClient() as client:
            upload_url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/media"
            form = httpx.MultipartWriter()
            form.add_part(reply, filename="response.png", content_type="image/png")

            upload_resp = await client.post(
                upload_url + f"?messaging_product=whatsapp&type=image",
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
                content=reply
            )
            upload_resp.raise_for_status()
            media_id = upload_resp.json()["id"]

        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "image",  # or "audio" depending on your use case
            "image": {"id": media_id}
        }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=payload
        )
        if resp.status_code != 200:
            print(f"❌ Failed to send message: {resp.status_code} - {resp.text}")
        else:
            print(f"✅ Sent response to {to}")


async def download_whatsapp_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}

    # Step 1: Get media URL
    meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(meta_url, headers=headers)
        meta_resp.raise_for_status()
        media_url = meta_resp.json().get("url")

    # Step 2: Download actual file
    async with httpx.AsyncClient() as client:
        file_resp = await client.get(media_url, headers=headers)
        file_resp.raise_for_status()
        return file_resp.content