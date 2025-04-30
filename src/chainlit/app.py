import chainlit as cl
import httpx
import traceback
from io import BytesIO
from memory.short_term import get_memory, clear_memory, add_to_memory

API_URL = "http://localhost:8000/chat"
DEFAULT_TIMEOUT = 90.0 

@cl.on_chat_start
async def on_chat_start():
    client_id = cl.user_session.get("id") or cl.context.session.id
    cl.user_session.set("id", client_id)

    await cl.Message(
        content="Welcome! Type your message, upload an image 🖼️, or click 🎤 to record voice!",
    ).send()

    for role, msg in get_memory(client_id):
        prefix = "You" if role == "user" else "Assistant"
        await cl.Message(content=f"**{prefix}:** {msg}").send()

@cl.action_callback("reset")
async def on_reset(action: cl.Action):
    client_id = cl.user_session.get("id")
    clear_memory(client_id)
    await cl.Message(content="✅ Chat history cleared!").send()

@cl.on_message
async def on_message(message: cl.Message):
    client_id = cl.user_session.get("id")

    try:
        audio_elems = [e for e in getattr(message, "elements", []) if getattr(e, "mime", "").startswith("audio")]
        image_elems = [e for e in getattr(message, "elements", []) if getattr(e, "mime", "").startswith("image")]

        async with httpx.AsyncClient() as client:
            if audio_elems:
                audio = audio_elems[0]
                audio_bytes = await audio.read()
                resp = await client.post(
                    API_URL,
                    files={"audio": (audio.name or "voice.wav", audio_bytes, audio.mime)},
                    data={"conversation_id": client_id},
                    timeout=DEFAULT_TIMEOUT
                )

            elif image_elems:
                image = image_elems[0]
                with open(image.path, "rb") as f:
                    image_bytes = f.read()

                form_data = {
                    "conversation_id": client_id,
                }
                if message.content:
                    form_data["message"] = message.content

                resp = await client.post(
                    API_URL,
                    files={"image": (image.name or "image.png", image_bytes, image.mime)},
                    data=form_data,
                    timeout=DEFAULT_TIMEOUT
                )


            else:
                # Plain text
                resp = await client.post(
                    API_URL,
                    data={"message": message.content, "conversation_id": client_id},
                    timeout=DEFAULT_TIMEOUT
                )

        if resp.status_code != 200:
            raise ValueError(f"Non-200 response: {resp.status_code} - {resp.text}")

        ctype = resp.headers.get("Content-Type", "")

        if "application/json" in ctype:
            data = resp.json()
            reply = data.get("reply")
            if not isinstance(reply, str):
                raise ValueError(f"Missing or invalid 'reply' in response: {data}")

            add_to_memory(client_id, "user", message.content or "media input")
            add_to_memory(client_id, "assistant", reply)
            await cl.Message(content=reply).send()

        elif ctype.startswith("audio/"):
            await cl.Message(
                author="Assistant",
                content="",
                elements=[cl.Audio(name="Response Audio", content=resp.content, mime_type=ctype, auto_play=True)]
            ).send()

        elif ctype.startswith("image/"):
            await cl.Message(
                author="Assistant",
                content="",
                elements=[cl.Image(name="Generated Image", content=resp.content, mime_type=ctype)]
            ).send()

        else:
            raise ValueError(f"Unsupported Content-Type: {ctype}")

    except Exception as e:
        cl.logger.error("Exception in on_message:\n" + traceback.format_exc())
        await cl.Message(content=f"Error: {e}").send()

@cl.on_audio_chunk
async def on_audio_chunk(chunk: cl.AudioChunk):
    if chunk.isStart:
        buffer = BytesIO()
        buffer.name = f"input_audio.{chunk.mimeType.split('/')[1]}"
        cl.user_session.set("audio_buffer", buffer)
        cl.user_session.set("audio_mime_type", chunk.mimeType)

    cl.user_session.get("audio_buffer").write(chunk.data)

@cl.on_audio_end
async def on_audio_end(elements):
    client_id = cl.user_session.get("id")
    audio_buffer = cl.user_session.get("audio_buffer")
    audio_buffer.seek(0)
    audio_data = audio_buffer.read()

    input_audio_el = cl.Audio(mime="audio/mpeg3", content=audio_data)
    await cl.Message(author="You", content="", elements=[input_audio_el, *elements]).send()

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                API_URL,
                files={"audio": ("input_audio.wav", audio_data, "audio/wav")},
                data={"conversation_id": client_id},
                timeout=DEFAULT_TIMEOUT
            )

        if resp.status_code != 200:
            raise ValueError(f"Audio POST failed: {resp.status_code}")

        ctype = resp.headers.get("Content-Type", "")

        if "application/json" in ctype:
            data = resp.json()
            reply = data.get("reply")
            if not isinstance(reply, str):
                raise ValueError(f"Missing reply: {data}")
            await cl.Message(content=reply).send()

        elif ctype.startswith("audio/"):
            await cl.Message(
                author="Assistant",
                content="",
                elements=[cl.Audio(name="Response Audio", content=resp.content, mime_type=ctype, auto_play=True)]
            ).send()

        elif ctype.startswith("image/"):
            await cl.Message(
                author="Assistant",
                content="",
                elements=[cl.Image(name="Generated Image", content=resp.content, mime_type=ctype)]
            ).send()

        else:
            raise ValueError(f"Unsupported Content-Type: {ctype}")

    except Exception as e:
        cl.logger.error("Exception in on_audio_end:\n" + traceback.format_exc())
        await cl.Message(content=f"Error: {e}").send()