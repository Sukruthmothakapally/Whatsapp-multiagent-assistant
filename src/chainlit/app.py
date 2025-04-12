import chainlit as cl
import httpx
import traceback
from memory.short_term import get_memory, clear_memory, add_to_memory

API_URL = "http://localhost:8000/chat"

@cl.on_chat_start
async def on_chat_start():
    client_id = cl.user_session.get("id") or cl.context.session.id
    cl.user_session.set("id", client_id)

    await cl.Message(
        content="Welcome! Click below to reset chat memory if needed.",
        actions=[cl.Action(name="reset", label="🔄 Reset Chat", payload={})]
    ).send()

    memory = get_memory(client_id)
    for role, msg in memory:
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

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                API_URL,
                json={"message": message.content, "conversation_id": client_id},
                timeout=10.0
            )

            cl.logger.debug(f"Response status: {response.status_code}")
            cl.logger.debug(f"Response body: {response.text}")

            if response.status_code != 200:
                raise ValueError(f"Non-200 response: {response.status_code} - {response.text}")

            try:
                data = response.json()
            except Exception as parse_error:
                raise ValueError(f"JSON parse error: {parse_error} | Response: {response.text}")

            reply = data.get("reply")
            if not reply or not isinstance(reply, str):
                raise ValueError(f"Missing or invalid 'reply' in response: {data}")

            add_to_memory(client_id, "user", message.content)
            add_to_memory(client_id, "assistant", reply)

            await cl.Message(content=reply).send()

        except Exception as e:
            cl.logger.error("Exception occurred in on_message:")
            cl.logger.error(traceback.format_exc())
            await cl.Message(content=f"Error: {str(e)}").send()
