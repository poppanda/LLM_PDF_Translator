import re
import PyPDF2
from loguru import logger
import numpy as np
from tqdm import tqdm
from .base import RenderBase, RenderMode
from utils.layout_model import Layout
from PIL import Image, ImageFont
from PIL.ImageFont import FreeTypeFont
from PIL import ImageDraw
from typing import List, Optional, Tuple
from utils import draw_text
import matplotlib.pyplot as plt

class SimpleRender(RenderBase):
    FONT_SIZE = 29

    def init(self, cfg: dict):
        self.cfg = cfg
    
    def init_pdf(self):
        self.reached_references = False

    def get_all_fonts(self, layout: list[Layout]):
        for line in tqdm(layout, desc="Getting font info", leave=False, dynamic_ncols=True):
            if line.type in ["text", "list", "title"]:
                # update this so image is created from images and layout bbox info
                image = line.image
                height = line.bbox[3] - line.bbox[1]
                width = line.bbox[2] - line.bbox[0]
                new_block = Image.new("RGB", (width, height), color=(255, 255, 255))
                draw = ImageDraw.ImageDraw(new_block)
                family, font_size, ygain, processed_text = self.get_font_info(line, draw)
                line.font = {"family": family, "size": font_size, "ygain": ygain}
                line.processed_text = processed_text

        return layout

    def get_font_info(self, 
                      line: Layout,
                      draw: ImageDraw.ImageDraw):
        logger.debug(f"Getting font info for text:\n{line.text}")
        if line.translated_text is None:
            return "SourceHanSerifSC-Medium.otf", self.FONT_SIZE, 30, ""
        font_family = "SourceHanSerifSC-Medium.otf"
        image, text, line_cnt = line.image, line.translated_text.strip(), line.line_cnt
        # if image.ndim == 3:  # If the image has channels (e.g., RGB)
        #     height, width, _ = image.shape
        # else:  # For a 2D image (grayscale)
        #     height, width = image.shape
        height = line.bbox[3] - line.bbox[1]
        width = line.bbox[2] - line.bbox[0]

        def split_text(text: str, width: int, fnt: FreeTypeFont):
            logger.debug(f"Splitting text with width {width}/text: \n{text}")
            lines = []
            while text:
                # logger.debug(f"Remaining text for width {width}: \n{text}")
                initial_indent = 40 if len(lines) == 0 else 0
                index = 0
                if text[0] == '\n':
                    text = text[1:]
                    continue
                while (index < len(text)) and \
                      (text[index] != '\n') and \
                      (initial_indent + draw.textlength(text[0:index + 1], font=fnt) < width):
                    index += 1
                # logger.debug(f"Index: {index} / Text: {text[0:index]}")
                lines.append(text[0:index])
                text = text[index:]
            return '\n'.join(lines)

        font_size = self.FONT_SIZE
        processed_text = None
        render_dict = {}

        while True:
            logger.debug(f"Try Font size: {font_size}")
            if(font_size < 4):
                logger.error("Font size too small!")
                break
            fnt_s = ImageFont.truetype(f"fonts/{font_family}", font_size)
            fnt_l = ImageFont.truetype(f"fonts/{font_family}", font_size + 1)
            text_s = split_text(text, width, fnt_s)
            text_l = split_text(text, width, fnt_l)
            bbox_s = draw.textbbox((0, 0), text_s, font=fnt_s)
            bbox_l = draw.textbbox((0, 0), text_l, font=fnt_l)
            if bbox_s[3] < height and bbox_l[3] >= height:
                logger.debug(f"Width {width} / Render width {bbox_s[2] - bbox_s[0]}")
                processed_text = text_s
                break
            elif bbox_s[3] >= height:
                logger.debug(f"Decreasing font size from {font_size}")
                font_size -= 1
            else:
                assert (bbox_s[3] < height and bbox_l[3] < height), f"Font size too large! S:{bbox_s[3]} L:{bbox_l[3]} Height:{height}, condition 1: {bbox_s[3] < height and bbox_l[3] >= height}"
                if text_s.count('\n') == 0:
                    processed_text = text_s
                    break
                logger.debug(f"Increasing font size from {font_size}, count newline:"+str(text_s.count('\n')))
                font_size += 1
                
        ygain = int(font_size * 1.1)

        # return 'TimesNewRoman.ttf', font_size, ygain
        return "SourceHanSerifSC-Medium.otf", font_size, ygain, processed_text

    def translate_one_page(
        self,
        image,
        result: list[Layout],
    ) -> Tuple[np.ndarray, np.ndarray, bool]:
        """Translate one page of the PDF file."""
        img = np.array(image, dtype=np.uint8)
        for line in result:
            if line.type in ["text", "list"]:
                if line.text:
                    height = line.bbox[3] - line.bbox[1]
                    width = line.bbox[2] - line.bbox[0]

                    # calculate text wrapping
                    processed_text = line.processed_text

                    fnt = ImageFont.truetype(
                        "fonts/" + line.font["family"], line.font["size"]
                    )
                    # create new image block with new text
                    new_block = Image.new("RGB", (width, height), color=(255, 255, 255))
                    draw = ImageDraw.Draw(new_block)
                    draw_text(
                        draw,
                        processed_text,
                        fnt,
                        line.font["size"],
                        width,
                        line.font["ygain"],
                    )

                    # copy over original image

                    new_block = np.array(new_block)
                    img[
                        int(line.bbox[1]) : int(line.bbox[3]),
                        int(line.bbox[0]) : int(line.bbox[2]),
                    ] = new_block

            elif line.type == "title":
                title = line.text
                if title.lower() == "references" or title.lower() == "reference":
                    self.reached_references = True
            elif line.type == "figure":
                continue
            else:
                # TODO: add list, table and image translation support
                # print(f"\n\n\nunknown: {line.type}")
                logger.warning(f"Unknown type: {line.type}")
        self.one_page_img = img
    
    def post_process(self, image, render_mode: RenderMode, output_path: str, DPI: int):
        if self.reached_references:
            (
                image.convert("RGB")
                .resize((int(1400 / image.size[1] * image.size[0]), 1400))
                .save(output_path, format="pdf")
            )
        else:
            if render_mode is RenderMode.SIDE_BY_SIDE:
                fig, ax = plt.subplots(1, 2, figsize=(20, 14))
                ax[0].imshow(image)
                ax[1].imshow(self.one_page_img)
                ax[0].axis("off")
                ax[1].axis("off")
            else:
                fig, ax = plt.subplots(1, 1, figsize=(10, 14))
                ax.imshow(self.one_page_img)
                ax.axis("off")
            plt.tight_layout()
            plt.savefig(output_path, format="pdf", dpi=DPI)
            plt.close(fig)
            
    def merge_pdfs(self, pdf_files: List[str], output_dir: Optional[str] = None, temp_dir_name=None) -> None:
        """Merge translated PDF files into one file.

        Merged file will be stored in the temp directory
        as "translated.pdf".

        Parameters
        ----------
        pdf_files: List[str]
            List of paths to translated PDF files stored in
            the temp directory.
        """
        pdf_merger = PyPDF2.PdfMerger()

        for pdf_file in sorted(pdf_files):
            pdf_merger.append(pdf_file)
        if output_dir:
            pdf_merger.write(output_dir)
        else:
            pdf_merger.write(temp_dir_name / "translated.pdf")