import time
import logging

from openai import OpenAI, AuthenticationError, RateLimitError, APIError
from core.config import settings

logger = logging.getLogger(__name__)


class NIMClient:
    def __init__(self):
        self._client: OpenAI | None = None
        self._request_times: list[float] = []
        self._model = settings.NIM_MODEL
        self._max_retries = 3

    def _get_client(self) -> OpenAI:
        if self._client is None:
            if not settings.NIM_API_KEY:
                raise ValueError(
                    "NIM_API_KEY is not set. Add it to your .env file or environment variables."
                )
            self._client = OpenAI(
                base_url=settings.NIM_BASE_URL,
                api_key=settings.NIM_API_KEY,
                timeout=120.0,
            )
        return self._client

    def set_model(self, model: str) -> None:
        self._model = model

    @property
    def model(self) -> str:
        return self._model

    def list_models(self) -> list[str]:
        client = self._get_client()
        try:
            models = client.models.list()
            return sorted(m.id for m in models.data)
        except Exception as e:
            logger.warning(f"Failed to fetch model list from NIM: {e}")
            return []

    def chat(self, system: str, user: str, temperature: float = 0.3, max_tokens: int = 4096) -> str:
        return self._call_with_retry(system, user, temperature, max_tokens, use_json=False)

    def chat_json(self, system: str, user: str, temperature: float = 0.3) -> str:
        return self._call_with_retry(system, user, temperature, max_tokens=4096, use_json=True)

    def _call_with_retry(self, system: str, user: str, temperature: float,
                         max_tokens: int, use_json: bool) -> str:
        last_error = None
        for attempt in range(self._max_retries):
            try:
                self._rate_limit_wait()
                kwargs = {
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if use_json:
                    kwargs["response_format"] = {"type": "json_object"}

                client = self._get_client()
                response = client.chat.completions.create(**kwargs)
                self._request_times.append(time.time())
                content = response.choices[0].message.content or ("{}" if use_json else "")
                return content

            except AuthenticationError:
                raise
            except (RateLimitError, APIError) as e:
                last_error = e
                wait = 2 ** attempt
                logger.warning(f"NIM API transient error (attempt {attempt + 1}): {e}. Retrying in {wait}s")
                time.sleep(wait)
            except Exception as e:
                last_error = e
                logger.error(f"NIM API unexpected error: {e}")
                if attempt == self._max_retries - 1:
                    break
                time.sleep(2 ** attempt)

        raise last_error or RuntimeError("NIM API call failed after all retries")

    def _rate_limit_wait(self):
        self._request_times = [t for t in self._request_times if time.time() - t < 60]
        if len(self._request_times) >= settings.NIM_RPM:
            sleep_time = 60 - (time.time() - self._request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
            self._request_times = self._request_times[1:]


nim = NIMClient()
