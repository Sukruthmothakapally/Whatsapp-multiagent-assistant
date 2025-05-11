import httpx
import os

# Get environment variables
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")

# async def send_typing_indicator(to: str):
#     """Send typing indicator to WhatsApp"""
#     url = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}/messages"
#     headers = {
#         "Authorization": f"Bearer {WHATSAPP_TOKEN}",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         "messaging_product": "whatsapp",
#         "to": to,
#         "type": "typing",
#         "typing": {
#             "on": True
#         }
#     }
    
#     async with httpx.AsyncClient() as client:
#         try:
#             await client.post(url, headers=headers, json=payload)
#         except Exception as e:

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
            print(f"✅ Sent {media_type} response")