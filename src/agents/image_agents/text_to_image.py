# src/agents/image_agents/text_to_image.py

import base64
import logging
import os
from typing import Optional

from together import Together

class TextToImageError(Exception):
    pass

class TextToImage:
    """A class to handle text-to-image generation using Together AI."""

    REQUIRED_ENV_VARS = ["TOGETHER_API_KEY"]

    def __init__(self):
        self._validate_env_vars()
        self._together_client: Optional[Together] = None
        self.logger = logging.getLogger(__name__)

    def _validate_env_vars(self) -> None:
        missing = [v for v in self.REQUIRED_ENV_VARS if not os.getenv(v)]
        if missing:
            raise EnvironmentError(f"Missing environment vars: {', '.join(missing)}")

    @property
    def client(self) -> Together:
        if self._together_client is None:
            self._together_client = Together(api_key=os.getenv("TOGETHER_API_KEY"))
        return self._together_client

    async def generate_image(self, prompt: str, output_path: str = "") -> bytes:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        try:
            self.logger.info(f"🖌️ Generating image for prompt: {prompt.strip()[:100]}")

            response = self.client.images.generate(
                prompt=prompt,
                model="black-forest-labs/FLUX.1-schnell-Free",
                width=1024,
                height=768,
                steps=4,
                n=1,
                response_format="b64_json"
            )

            image_data = base64.b64decode(response.data[0].b64_json)

            if output_path:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(image_data)
                self.logger.info(f"📁 Saved image to {output_path}")

            return image_data

        except Exception as e:
            raise TextToImageError(f"Failed to generate image: {e}") from e
