from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
from agents.text_agents.router import route_message
import httpx
import os
import json

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN") 
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")  
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_BUSINESS_NUMBER = os.getenv("WHATSAPP_BUSINESS_NUMBER")

# Validate env vars
if not WHATSAPP_TOKEN or not PHONE_NUMBER_ID or not WHATSAPP_VERIFY_TOKEN or not WHATSAPP_BUSINESS_NUMBER:
    raise ValueError("Missing required environment variables for WhatsApp integration.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Track active message processing to prevent loops
active_messages = set()

@app.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return JSONResponse({"error": "Verification failed"}, status_code=403)

@app.post("/webhook")
async def whatsapp_webhook(request: Request):
    try:
        payload = await request.json()
        
        # Early return for status updates
        if not payload.get("object") == "whatsapp_business_account":
            return JSONResponse({"status": "ignored non-whatsapp message"}, status_code=200)
            
        entry = payload.get("entry", [])[0]
        changes = entry.get("changes", [])[0]
        value = changes.get("value", {})
        
        # Handle statuses if present
        if "statuses" in value:
            print("📊 Received status update")
            return JSONResponse({"status": "status update received"}, status_code=200)
            
        messages = value.get("messages", [])
        if not messages:
            return JSONResponse({"status": "no message"}, status_code=200)

        message = messages[0]
        sender = message.get("from")
        message_id = message.get("id", "unknown")
        
        # Check if we're already processing this message to prevent loops
        message_key = f"{sender}:{message_id}"
        if message_key in active_messages:
            print(f"🔄 Already processing message {message_key}, ignoring")
            return JSONResponse({"status": "already processing"}, status_code=200)
            
        # Stop loop: ignore messages sent by our own number
        if sender == WHATSAPP_BUSINESS_NUMBER:
            print("🔁 Ignoring message sent by bot itself.")
            return JSONResponse({"status": "ignored self-message"}, status_code=200)

        # Show typing indicator
        await send_typing_indicator(sender)
        
        # Add to active messages
        active_messages.add(message_key)
        
        try:
            msg_type = message.get("type")
            print(f"📩 Received {msg_type} message from {sender}")

            # Handle incoming content
            if msg_type == "text":
                text = message["text"]["body"]
                reply = await route_message(text, sender, media_type="text")
            elif msg_type == "audio":
                media_id = message["audio"]["id"]
                audio_bytes = await download_whatsapp_media(media_id)
                reply = await route_message(audio_bytes, sender, media_type="audio")
            elif msg_type == "image":
                media_id = message["image"]["id"]
                image_bytes = await download_whatsapp_media(media_id)
                
                # Check if there's a caption with the image
                caption = message.get("image", {}).get("caption", "")
                
                if caption:
                    # If there's a caption, pass both the image and text
                    reply = await route_message(
                        {"image": image_bytes, "caption": caption}, 
                        sender, 
                        media_type="image_with_caption"
                    )
                else:
                    reply = await route_message(image_bytes, sender, media_type="image")
            else:
                # Remove from active messages
                active_messages.discard(message_key)
                return JSONResponse({"status": f"unsupported message type: {msg_type}"}, status_code=200)

            # Send back the response
            await send_whatsapp_response(sender, reply)
            print(f"✅ Completed processing for {message_key}")
            
            return JSONResponse({"status": "message processed"}, status_code=200)
        finally:
            # Always remove from active messages when done
            active_messages.discard(message_key)

    except Exception as e:
        print(f"❌ Error in webhook: {str(e)}")
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
    
    
async def send_typing_indicator(to: str):
    """Send typing indicator to WhatsApp"""
    url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "typing",
        "typing": {
            "on": True
        }
    }
    
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, headers=headers, json=payload)
            print(f"✏️ Sent typing indicator to {to}")
        except Exception as e:
            print(f"❌ Failed to send typing indicator: {str(e)}")

async def send_whatsapp_response(to: str, reply: str | bytes):
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"}
    
    # Determine response type
    if isinstance(reply, str):
        # TEXT response
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"body": reply}
        }
        media_type = "text"
    else:
        # Try to detect if it's audio or image based on file signature
        if reply.startswith(b'\xFF\xFB') or reply.startswith(b'ID3') or reply.startswith(b'RIFF'):
            # Likely audio (MP3 or WAV)
            upload_type = "audio"
            mime_type = "audio/mpeg"
        else:
            # Default to image 
            upload_type = "image"
            mime_type = "image/png"
            
        # Upload the media first
        media_type = upload_type
        upload_url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/media"
        
        async with httpx.AsyncClient() as client:
            upload_resp = await client.post(
                upload_url,
                headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
                files={
                    "file": (
                        f"response.{upload_type}",
                        reply,
                        mime_type
                    ),
                    "type": (None, upload_type),
                    "messaging_product": (None, "whatsapp")
                }
            )
            
            if upload_resp.status_code != 200:
                print(f"❌ Failed to upload media: {upload_resp.status_code} - {upload_resp.text}")
                # Fallback to text
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": "text",
                    "text": {"body": "Sorry, I couldn't send the media response."}
                }
            else:
                media_id = upload_resp.json().get("id")
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": upload_type,
                    upload_type: {"id": media_id}
                }

    # Send the response
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=payload
        )
        
        if resp.status_code != 200:
            print(f"❌ Failed to send {media_type} message: {resp.status_code} - {resp.text}")
        else:
            print(f"✅ Sent {media_type} response to {to}")

async def download_whatsapp_media(media_id: str) -> bytes:
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    
    # Get media URL
    meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(meta_url, headers=headers)
        meta_resp.raise_for_status()
        media_url = meta_resp.json().get("url")
        
    # Download the file
    async with httpx.AsyncClient() as client:
        file_resp = await client.get(media_url, headers=headers)
        file_resp.raise_for_status()
        return file_resp.content