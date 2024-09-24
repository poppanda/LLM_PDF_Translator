from abc import ABC, abstractmethod
from typing import Tuple
from utils.layout_model import Layout
import numpy as np
from enum import Enum

class RenderMode(Enum):
    SIDE_BY_SIDE = 1
    TRANSLATION_ONLY = 2
    INTERLEAVE = 3
    @staticmethod
    def get_mode(mode: str):
        if mode.lower() == "side_by_side":
            return RenderMode.SIDE_BY_SIDE
        elif mode.lower() == "translation_only":
            return RenderMode.TRANSLATION_ONLY
        elif mode.lower() == "interleave":
            return RenderMode.INTERLEAVE
    

class RenderBase(ABC):
    @abstractmethod
    def init(self, cfg: dict):
        pass


    @abstractmethod
    def get_font_info(self, image, line_cnt):
        """
        Translates a given string into another language.

        Parameters:
        - text (str): The text to be translated.

        Returns:
        - str: The translated text.

        This method needs to be implemented by subclasses.
        """
        pass


    @abstractmethod
    def get_all_fonts(self, layout):
        """
        Translates a given string into another language.

        Parameters:
        - text (str): The text to be translated.

        Returns:
        - str: The translated text.

        This method needs to be implemented by subclasses.
        """
        pass

    
    @abstractmethod
    def translate_one_page(
        self,
        image,
        result: list[Layout],
        reached_references: bool,
    ) -> Tuple[np.ndarray, np.ndarray, bool]:
        """Translate one page of the PDF file."""
        pass