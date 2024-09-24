from .LLMTranslateBase import LLMTranslateBase
from openai import OpenAI

class TranslateOpenAIGPT(LLMTranslateBase):
    def init(self, cfg: dict):
        super().init(cfg)
        
    def init_client(self, cfg: dict) -> OpenAI:
        return OpenAI(api_key=cfg["api_key"])