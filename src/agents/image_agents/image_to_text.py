# src/agents/image_agents/image_to_text.py

import base64
import logging
import os
from typing import Optional, Union

from groq import Groq

class ImageToTextError(Exception):
    pass

class ImageToText:
    """A class to handle image-to-text conversion using Groq's vision API."""

    REQUIRED_ENV_VARS = ["GROQ_API_KEY"]

    def __init__(self):
        self._validate_env_vars()
        self._client: Optional[Groq] = None
        self.logger = logging.getLogger(__name__)

    def _validate_env_vars(self):
        missing = [v for v in self.REQUIRED_ENV_VARS if not os.getenv(v)]
        if missing:
            raise EnvironmentError(f"Missing environment vars: {', '.join(missing)}")

    @property
    def client(self) -> Groq:
        if self._client is None:
            self._client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        return self._client

    async def analyze_image(self, image_data: Union[str, bytes], prompt: str = "") -> str:
        try:
            if isinstance(image_data, str):
                if not os.path.exists(image_data):
                    raise ValueError(f"Image path not found: {image_data}")
                with open(image_data, "rb") as f:
                    image_bytes = f.read()
            else:
                image_bytes = image_data

            if not image_bytes:
                raise ValueError("Image data is empty.")

            base64_image = base64.b64encode(image_bytes).decode("utf-8")
            prompt = prompt or "Please describe what you see in this image."

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ]

            response = self.client.chat.completions.create(
                model="meta-llama/llama-4-scout-17b-16e-instruct",
                messages=messages,
                max_tokens=1000,
            )

            if not response.choices:
                raise ImageToTextError("No response from Groq vision model.")

            result = response.choices[0].message.content
            self.logger.info(f"🧠 ITT result: {result.strip()[:100]}...")
            return result

        except Exception as e:
            raise ImageToTextError(f"Failed to analyze image: {e}") from e
