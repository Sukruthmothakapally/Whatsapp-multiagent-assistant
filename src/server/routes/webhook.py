from fastapi import APIRouter, Request, Response
from fastapi.responses import JSONResponse
import os
from server.services.whatsapp import send_typing_indicator, send_whatsapp_response
from server.services.media import download_whatsapp_media
from agents.text_agents.router import route_message

router = APIRouter()

# Track active message processing to prevent loops
active_messages = set()

# Get environment variables
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_BUSINESS_NUMBER = os.getenv("WHATSAPP_BUSINESS_NUMBER")

@router.get("/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
        return Response(content=challenge, media_type="text/plain")
    return JSONResponse({"error": "Verification failed"}, status_code=403)

@router.post("/webhook")
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