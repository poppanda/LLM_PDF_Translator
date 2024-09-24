from .LLMTranslateBase import LLMTranslateBase
from openai import OpenAI


class TranslateQwen(LLMTranslateBase):
    def init(self, cfg: dict):
        super().init(cfg)

    def init_client(self, cfg: dict) -> OpenAI:
        return OpenAI(
            api_key=cfg["api_key"],
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
