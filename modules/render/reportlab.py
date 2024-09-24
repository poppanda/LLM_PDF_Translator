import re
from loguru import logger
import numpy as np
from tqdm import tqdm
from .base import RenderBase, RenderMode
from utils.layout_model import Layout
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.utils import ImageReader
from typing import Tuple, Optional
from PIL import Image
from pathlib import Path
import io
from PyPDF2 import PdfReader, PdfWriter, Transformation
import sys
from loguru import logger

sys.setrecursionlimit(100000000)


class ReportLabRender(RenderBase):
    FONT_SIZE = 29

    def init(self, cfg: dict):
        self.cfg = cfg
        self.font_path = cfg["font_path"]
        self.font_name = cfg["font_name"]
        pdfmetrics.registerFont(TTFont(self.font_name, self.font_path))
        self.render_mode = RenderMode.get_mode(cfg["render_mode"])
        logger.info(f"Render mode: {self.render_mode}")
        self.pdf: Optional[Canvas] = None

    def init_pdf(self, output_dir, temp_dir_name: Path):
        output_file = output_dir if output_dir else (temp_dir_name / "translated.pdf")
        if isinstance(output_file, Path):
            output_file = str(output_file)
        self.output_dir = output_file
        self.packet = io.BytesIO()
        self.pdf = Canvas(self.packet, pagesize=(1000, 1000))
        # self.pdf.setFont(self.font_name, self.FONT_SIZE)
        self.reached_references = False

    def get_all_fonts(self, layout: list[Layout]):
        for line in tqdm(
            layout, desc="Getting font info", leave=False, dynamic_ncols=True
        ):
            if line.type in ["text", "list", "title"]:
                # update this so image is created from images and layout bbox info
                image = line.image
                height = line.bbox[3] - line.bbox[1]
                width = line.bbox[2] - line.bbox[0]
                temp_canvas = Canvas("temp.pdf", pagesize=(width, height))
                family, font_size, ygain, processed_text = self.get_font_info(
                    line, temp_canvas
                )
                line.font = {"family": family, "size": font_size, "ygain": ygain}
                line.processed_text = processed_text

        return layout

    def get_font_info(self, line: Layout, draw: Canvas):
        logger.debug(f"Getting font info for text:\n{line.text}")
        if line.translated_text is None:
            return "SourceHanSerifSC-Medium.otf", self.FONT_SIZE, 30, ""
        font_family = "SourceHanSerifSC-Medium.otf"
        text = line.translated_text.strip()
        height = line.bbox[3] - line.bbox[1]
        width = line.bbox[2] - line.bbox[0]

        def split_text(text: str, width: int, fontsize: int):
            logger.debug(f"Splitting text with width {width}/text: \n{text}")
            lines = []
            while text:
                # logger.debug(f"Remaining text for width {width}: \n{text}")
                initial_indent = 40 if len(lines) == 0 else 0
                index = 0
                if text[0] == "\n":
                    text = text[1:]
                    lines.append("\n")
                    continue
                while (
                    (index < len(text))
                    and (text[index] != "\n")
                    and (
                        initial_indent
                        + draw.stringWidth(
                            text[0 : index + 1],
                            fontName=self.font_name,
                            fontSize=fontsize,
                        )
                        < width
                    )
                ):
                    index += 1
                # logger.debug(f"Index: {index} / Text: {text[0:index]}")
                lines.append(text[0:index])
                text = text[index:]
            return lines

        font_size = self.FONT_SIZE
        processed_text = None

        while True:
            logger.debug(f"Try Font size: {font_size}")
            if font_size < 4:
                logger.error("Font size too small!")
                break
            text_s = split_text(text, width, font_size)
            text_l = split_text(text, width, font_size + 1)
            height_s = len(text_s) * 1.1 * font_size
            height_l = len(text_l) * 1.1 * (font_size + 1)
            if height_s < height and height_l >= height:
                # logger.debug(f"Width {width} / Render width {bbox_s[2] - bbox_s[0]}")
                processed_text = text_s
                break
            elif height_s >= height:
                logger.debug(f"Decreasing font size from {font_size}")
                font_size -= 1
            else:
                assert (
                    height_s < height and height_l < height
                ), f"Font size too large! S:{height_s} L:{height_l} Height:{height}, condition 1: {height_s < height and height_l >= height}"
                if text_s.count("\n") == 0:
                    processed_text = text_s
                    break
                logger.debug(
                    f"Increasing font size from {font_size}, count newline:"
                    + str(text_s.count("\n"))
                )
                font_size += 1

        ygain = int(font_size * 1.1)

        # return 'TimesNewRoman.ttf', font_size, ygain
        return "SourceHanSerifSC-Medium.otf", font_size, ygain, processed_text

    def fill_unrendered_region(self, image: np.ndarray):
        radius = self.FONT_SIZE // 2
        if len(image.shape) == 3:
            not_white = np.any(image != 255, axis=-1)
        else:
            not_white = image != 255
        vis = np.zeros_like(not_white, dtype=bool)

        def dfs(x, y, res):
            if vis[x, y]:
                return res
            if not_white[x, y]:
                vis[x, y] = True
            for nx in range(x - radius, x + radius):
                for ny in range(y - radius, y + radius):
                    if (
                        nx >= 0
                        and nx < image.shape[0]
                        and ny >= 0
                        and ny < image.shape[1]
                        and not_white[nx, ny]
                        and not vis[nx, ny]
                    ):
                        res[0] = min(res[0], nx)
                        res[1] = max(res[1], nx)
                        res[2] = min(res[2], ny)
                        res[3] = max(res[3], ny)
                        res = dfs(nx, ny, res)
            return res

        for i in range(image.shape[0]):
            for j in range(image.shape[1]):
                if not_white[i, j] and not vis[i, j]:
                    (x_min, x_max, y_min, y_max) = dfs(i, j, np.array([i, i, j, j]))
                    if x_max - x_min > 0 and y_max - y_min > 0:
                        img_to_render = Image.fromarray(image[x_min:x_max, y_min:y_max])
                        self.pdf.drawImage(
                            ImageReader(img_to_render),
                            y_min,
                            image.shape[0] - x_max,
                            y_max - y_min,
                            x_max - x_min,
                        )

    def translate_one_page(
        self, image, result: list[Layout]
    ) -> Tuple[np.ndarray, np.ndarray, bool]:
        """Translate one page of the PDF file."""
        image = np.array(image, dtype=np.uint8)
        # white out all the recognized region
        for line in result:
            image[
                max(0, line.bbox[1] - 3) : line.bbox[3] + 3,
                max(0, line.bbox[0] - 3) : line.bbox[2] + 3,
            ] = 255
            line.bbox[1], line.bbox[3] = (
                image.shape[0] - line.bbox[3],
                image.shape[0] - line.bbox[1],
            )

        self.pdf.setPageSize((image.shape[1], image.shape[0]))
        self.pdf.setFont(self.font_name, self.FONT_SIZE)

        self.fill_unrendered_region(image)
        # self.pdf.drawImage(ImageReader(Image.fromarray(image)), 0, 0, image.shape[1], image.shape[0])

        for line in result:
            if line.type in ["text", "list"]:
                logger.debug(f"Rendering text: {line.text}")
                if len(line.text) > 0 and (
                    line.processed_text is not None and len(line.processed_text) > 0
                ):
                    x, y = line.bbox[0], line.bbox[3] - line.font["ygain"]

                    processed_text = line.processed_text
                    self.pdf.setFont(self.font_name, line.font["size"])

                    # copy over original image
                    offset = 40
                    for render_line in processed_text:
                        if render_line != "\n":
                            self.pdf.drawString(x + offset, y, render_line)
                        y -= line.font["ygain"]
                        offset = 0
                else:
                    self.pdf.drawImage(
                        ImageReader(Image.fromarray(line.image)),
                        line.bbox[0],
                        line.bbox[1],
                        line.bbox[2] - line.bbox[0],
                        line.bbox[3] - line.bbox[1],
                    )

            elif line.type == "title":
                title = line.text
                self.pdf.drawImage(
                    ImageReader(Image.fromarray(line.image)),
                    line.bbox[0],
                    line.bbox[1],
                    line.bbox[2] - line.bbox[0],
                    line.bbox[3] - line.bbox[1],
                )
                if title.lower() == "references" or title.lower() == "reference":
                    self.reached_references = True
            elif line.type == "figure":
                self.pdf.drawImage(
                    ImageReader(Image.fromarray(line.image)),
                    line.bbox[0],
                    line.bbox[1],
                    line.bbox[2] - line.bbox[0],
                    line.bbox[3] - line.bbox[1],
                )
            else:
                # TODO: add list, table and image translation support
                self.pdf.drawImage(
                    ImageReader(Image.fromarray(line.image)),
                    line.bbox[0],
                    line.bbox[1],
                    line.bbox[2] - line.bbox[0],
                    line.bbox[3] - line.bbox[1],
                )
                logger.warning(f"Unknown type: {line.type}")
        self.pdf.showPage()
        # self.pdf.save()

    def post_process(self):
        pass

    def save_pdf(
        self,
        render_mode: RenderMode,
        src_pdf_path: Optional[str | bytes] = None,
        p_from: Optional[int] = None,
        add_blank_page: bool = False,
    ):
        self.pdf.save()
        self.packet.seek(0)
        new_pdf = PdfReader(self.packet)
        if (render_mode is RenderMode.SIDE_BY_SIDE) or (
            render_mode is RenderMode.INTERLEAVE
        ):
            if isinstance(src_pdf_path, bytes):
                src_pdf = PdfReader(io.BytesIO(src_pdf_path))
            else:
                src_pdf = PdfReader(open(src_pdf_path, "rb"))

        # existing_pdf = PdfReader(open("samplePDF.pdf", "rb"))
        output = PdfWriter()

        width, height = new_pdf.pages[0].mediabox.width, new_pdf.pages[0].mediabox.height

        if render_mode is RenderMode.INTERLEAVE and add_blank_page:
            output.add_blank_page(width, height)

        for i, page in enumerate(new_pdf.pages):
            if render_mode is RenderMode.SIDE_BY_SIDE:
                src_page = src_pdf.pages[i + p_from]
                src_page.scale_to(width, height)
                page.add_transformation(
                    Transformation().translate(width, 0), expand=True
                )
                page.merge_page(src_page, True)
            elif render_mode is RenderMode.INTERLEAVE:
                src_page = src_pdf.pages[i + p_from]
                src_page.scale_to(width, height)
                output.add_page(src_page)
            logger.debug(
                f"Merging {i} / {len(new_pdf.pages)}, page is None: {page is None}"
            )
            output.add_page(page)

        if render_mode is RenderMode.INTERLEAVE and add_blank_page:
            output.add_blank_page(width, height)

        outputStream = open(self.output_dir, "wb")
        output.write(outputStream)
        outputStream.close()
