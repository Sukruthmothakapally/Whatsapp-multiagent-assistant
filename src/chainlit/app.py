import chainlit as cl
import httpx
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

    # Show short-term memory
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
                json={"message": message.content, "conversation_id": client_id}
            )
            data = response.json()
            user_msg, assistant_reply = message.content, data["reply"]

            # Store both sides in memory
            add_to_memory(client_id, "user", user_msg)
            add_to_memory(client_id, "assistant", assistant_reply)

            await cl.Message(content=assistant_reply).send()

        except Exception as e:
            await cl.Message(content=f"Error: {str(e)}").send()
