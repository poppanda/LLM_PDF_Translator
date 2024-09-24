from .LLMTranslateBase import LLMTranslateBase
from openai import OpenAI


class TranslateOllama(LLMTranslateBase):
    def init(self, cfg: dict):
        super().init(cfg)

    def init_client(self, cfg: dict) -> OpenAI:
        return OpenAI(
            base_url="http://localhost:11434/v1/",
            # required but ignored
            api_key="ollama",
        )
