from abc import ABC, abstractmethod
from tqdm import tqdm
from typing import List
from utils.layout_model import Layout
from threading import Thread

class TranslateBase(ABC):
    @abstractmethod
    def init(self, cfg: dict):
        pass

    @abstractmethod
    def get_languages(self):
        pass

    def translate_all(self, layout: List[Layout], from_lang, to_lang, multi_thread = False):
        if not multi_thread:
            for line in tqdm(layout, desc="Translating", leave=False):
                if line.text:
                    if line.type == 'list':
                        line.text = self.reformat_text(line.text)
                    line.translated_text = self.translate(line.text, from_lang, to_lang)
        else:
            threads = []
            def translate_single_layout(i):
                line = layout[i]
                if line.type == 'list':
                    line.text = self.reformat_text(line.text)
                layout[i].translated_text = self.translate(line.text, from_lang, to_lang)
            for i in range(len(layout)):
                if layout[i].text:
                    t = Thread(target=translate_single_layout, args=(i,))
                    threads.append(t)
                    t.start()
            for t in threads:
                t.join()
        return layout

    @abstractmethod
    def reformat_text(self, text: str) -> str:
        pass

    @abstractmethod
    def translate(self, text: str) -> str:
        """
        Translates a given string into another language.

        Parameters:
        - text (str): The text to be translated.

        Returns:
        - str: The translated text.

        This method needs to be implemented by subclasses.
        """
        pass
