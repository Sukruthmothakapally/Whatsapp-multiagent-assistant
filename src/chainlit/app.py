import chainlit as cl
import httpx

API_URL = "http://localhost:8000/chat"

@cl.on_message
async def on_message(message: cl.Message):
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                API_URL,
                json={"message": message.content}
            )
            data = response.json()
            await cl.Message(content=data["reply"]).send()
        except Exception as e:
            await cl.Message(content=f"Error: {str(e)}").send()
