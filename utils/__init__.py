import os
from .textwrap_local import fw_fill, fw_wrap
from .ocr_model import OCRModel
from .layout_model import LayoutAnalyzer
from .gui import create_gradio_app
from PIL import Image, ImageDraw, ImageFont
from loguru import logger

import yaml

__all__ = ["fw_fill", "fw_wrap", "OCRModel", "LayoutAnalyzer"]

def load_config(base_config_path, override_config_path):
    with open(base_config_path, 'r') as base_file:
        base_config = yaml.safe_load(base_file)
    
    final_config = base_config

    if os.path.exists(override_config_path):
        with open(override_config_path, 'r') as override_file:
            override_config = yaml.safe_load(override_file)
            final_config = update(base_config, override_config)
    
    # Update the base config with the override config
    # This recursively updates nested dictionaries
    def update(d, u):
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = update(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    return final_config


def draw_text(draw: ImageDraw.ImageDraw, processed_text, current_fnt, font_size, width, ygain):
    y = 0
    if isinstance(processed_text, str):
        processed_text = processed_text.split('\n')
    first = len(processed_text) > 1
    for l in processed_text:
        words = l.split(" ")
        words_length = sum(draw.textlength(w, font=current_fnt) for w in words)
        if first: words_length += 40
        space_length = (width - words_length) / (len(words))
        if (space_length > 40):
            logger.debug(f"Space length too wide, Setting to : {space_length}")
            space_length = font_size/2.4
        elif space_length < 0:
            space_length = 0
        x = 0
        if first: x+= 40
        for word in words:
            logger.debug(f"Drawing word at {x}, {y}: \n {word}")
            draw.text((x, y), word, font=current_fnt, fill="black")
            x += draw.textlength(word, font=current_fnt) + space_length
        y += ygain
        first = False