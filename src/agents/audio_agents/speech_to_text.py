from dotenv import load_dotenv
load_dotenv()

import os
import tempfile
from typing import Optional
from groq import Groq

class SpeechToTextError(Exception):
    """Raised when STT fails."""
    pass

class SpeechToText:
    """Handle speech-to-text conversion using Groq's Whisper model."""

    REQUIRED_ENV_VARS = ["GROQ_API_KEY"]

    def __init__(self):
        missing = [v for v in self.REQUIRED_ENV_VARS if not os.getenv(v)]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        self._client: Optional[Groq] = None

    @property
    def client(self) -> Groq:
        if self._client is None:
            self._client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        return self._client

    async def transcribe(self, audio_data: bytes) -> str:
        """
        Convert speech to text.
        Args:
            audio_data: Raw audio bytes (e.g. .wav)
        Returns:
            The transcription as text.
        Raises:
            ValueError: if audio_data is empty
            SpeechToTextError: on any failure
        """
        if not audio_data:
            raise ValueError("Audio data cannot be empty")

        try:
            # write to temp .wav file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(audio_data)
                tmp_path = tmp.name

            try:
                with open(tmp_path, "rb") as audio_file:
                    result = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model="whisper-large-v3-turbo",
                        language="en",
                        response_format="text",
                    )
                if not result:
                    raise SpeechToTextError("Transcription result is empty")
                return result

            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except SpeechToTextError:
            raise
        except Exception as e:
            raise SpeechToTextError(f"Speech-to-text conversion failed: {e}") from e
