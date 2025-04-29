from dotenv import load_dotenv
load_dotenv()

import os
from typing import Optional
from elevenlabs import ElevenLabs, Voice, VoiceSettings

class TextToSpeechError(Exception):
    """Raised when TTS fails."""
    pass

class TextToSpeech:
    """Handle text-to-speech conversion using ElevenLabs."""

    REQUIRED_ENV_VARS = ["ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID"]

    def __init__(self):
        missing = [v for v in self.REQUIRED_ENV_VARS if not os.getenv(v)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        self._client: Optional[ElevenLabs] = None

    @property
    def client(self) -> ElevenLabs:
        if self._client is None:
            self._client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
        return self._client

    async def synthesize(self, text: str) -> bytes:
        """
        Convert text to speech.
        Args:
            text: The input text (max ~5000 chars)
        Returns:
            Raw audio bytes.
        Raises:
            ValueError: if text is empty or too long
            TextToSpeechError: on any synthesis failure
        """
        if not text.strip():
            raise ValueError("Input text cannot be empty")
        if len(text) > 5000:
            raise ValueError("Input text exceeds maximum length of 5000 characters")

        try:
            audio_iter = self.client.generate(
                text=text,
                voice=Voice(
                    voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
                    settings=VoiceSettings(stability=0.5, similarity_boost=0.5),
                )
            )
            audio_bytes = b"".join(audio_iter)
            if not audio_bytes:
                raise TextToSpeechError("Generated audio is empty")
            return audio_bytes

        except TextToSpeechError:
            raise
        except Exception as e:
            raise TextToSpeechError(f"Text-to-speech conversion failed: {e}") from e
