from openai import OpenAI
from server.config import settings

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=settings.groq_api_key
)

def ask_groq(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Give responses in just one line always"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"

def ask_routing_agent(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": "You are a precise routing agent. Return only one of these valid responses: DIRECT, USE_SHORT_TERM, USE_LONG_TERM, NONE, YES, or NO. Never explain. Never justify. Just reply with the keyword."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"Error: {str(e)}"
