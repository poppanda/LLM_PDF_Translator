import sys
import os
from threading import Thread
from multiprocessing import Pool
import tempfile
from pathlib import Path
from typing import List, Tuple, Union
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from typing import Optional
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import time
import asyncio
# from starlette.middleware.wsgi import WSGIMiddleware
from pdf2image import convert_from_bytes, convert_from_path
from PIL import Image
from pydantic import BaseModel, Field
from modules.render.base import RenderMode
from modules.render.simple import SimpleRender
from modules.render.reportlab import ReportLabRender
from tqdm import tqdm
import gradio as gr
from loguru import logger
from concurrent.futures import ThreadPoolExecutor
from utils.layout_model import Layout
from utils.database.file_db import FileDatabase, FileStatus
from utils.api_utils import TranslateRequest
from threading import Thread

logger.remove()
logger.add(sys.stderr, level="INFO")


from utils import create_gradio_app, load_config
from modules import (
    load_translator,
    load_layout_engine,
    load_ocr_engine,
    load_render_engine,
)


cfg = load_config("config.yaml", "config.dev.yaml")
translator = load_translator(cfg["translator"])
logger.info(f"Got translator {translator}")
render_engine = load_render_engine(cfg["render"])


class InputPdf(BaseModel):
    """Input PDF file."""

    input_pdf: UploadFile = Field(..., title="Input PDF file")

def layout_and_ocr_process(cfg: dict, pdf_images: list):
    """Process the layout and OCR for the PDF images.
    Restart the Ollama container if it is provided.(For lower vram usage)
    Input:
        cfg: dict: Configurations
        pdf_images: list: List of PDF images
        ollama_container: str: Ollama container name
    """
    if (
        cfg["translator"].get("restart_container") is not None
        and cfg["translator"]["restart_container"]
    ):
        ollama_container = cfg["translator"]["container_name"]
        logger.info(f"\tRestarting the Ollama container: {ollama_container}")
        os.system(f"docker restart {ollama_container}")
    # Initialize the layout engine / OCR engine
    layout_engine = load_layout_engine(cfg["layout"])
    ocr_engine = load_ocr_engine(cfg["ocr"])
    results = []
    for i, image in tqdm(enumerate(pdf_images), desc="Getting layout and texts"):
        result = layout_engine.get_single_layout(image)
        result = ocr_engine.get_all_text(result)
        results.append(result)
    return results


class TranslateApi:
    """Translator API class.

    Attributes
    ----------
    app: FastAPI
        FastAPI instance
    temp_dir: tempfile.TemporaryDirectory
        Temporary directory for storing translated PDF files
    temp_dir_name: Path
        Path to the temporary directory
    layout_model: PPStructure
        Layout model for detecting text blocks
    ocr_model: PaddleOCR
        OCR model for detecting text in the text blocks
    translate_model: MarianMTModel
        Translation model for translating text
    translate_tokenizer: MarianTokenizer
        Tokenizer for the translation model
    """

    DPI = 200

    def __init__(
        self,
        model_root_dir: Path = Path("/app/models/"),
        database_neme: str = "pdf_translator_files.db",
        enable_api: bool = False,
        enable_gui: bool = False,
    ):
        # The database
        self.database_name = database_neme
        self.file_db = FileDatabase(database_neme)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_name = Path(self.temp_dir.name)

        self.use_multi_thread = cfg["multi_thread"]["enable"]
        
        self.pending_requests: list[TranslateRequest] = []

        self.translate_thread = Thread(target=self.scan_and_translate)
        self.translate_thread.start()

        if enable_api or enable_gui:
            self.app = FastAPI()
            self.app.add_api_route(
                "/translate_pdf/",
                self.translate_pdf,
                methods=["POST"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/clear_temp_dir/",
                self.clear_temp_dir,
                methods=["GET"],
            )
            logger.info("GETFILES API ENABLED")
            self.app.add_api_route(
                "/get_files/",
                self.get_files,
                methods=["POST"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/download_file/",
                self.download_file,
                methods=["POST"],
                response_class=FileResponse,
            )

        if enable_gui:
            gradioapp = create_gradio_app(translator.get_languages())
            gr.mount_gradio_app(self.app, gradioapp, "/")

    def run(self):
        """Run the API server"""
        uvicorn.run(self.app, host="0.0.0.0", port=8765)
        
    def scan_and_translate(self):
        """Scan the pending requests and translate them."""
        file_db = FileDatabase(self.database_name)
        while True:
            time.sleep(1)
            # logger.info(f"Scanning the pending requests, there are {len(self.pending_requests)} requests")
            if len(self.pending_requests) > 0:
                req = self.pending_requests.pop(0)
                file_db.set_translating(str(req.pdf_path).split("/")[-1])
                self._translate_pdf(req)
                file_db.set_translated(str(req.pdf_path).split("/")[-1])

    async def translate_pdf(
        self,
        input_pdf: UploadFile = File(None),
        input_pdf_path: str = Form(None),
        from_lang: str = Form(...),
        to_lang: str = Form(...),
        translate_all: bool = Form(...),
        p_from: int = Form(...),
        p_to: int = Form(...),
        render_mode: str = Form(...),
        output_file_path: str = Form(None),
        add_blank_page: bool = Form(...),
    ) -> FileResponse:
        """API endpoint for translating PDF files."""
        logger.info(
            f"Got request to translate PDF, the args are:\nfrom_lang: {from_lang} to_lang: {to_lang}\ntranslate_all: {translate_all} p_from: {p_from}, p_to: {p_to}\nrender_mode: {render_mode}\noutput_file_path: {output_file_path}\ninput_pdf_path: {input_pdf_path}\nadd_blank_page: {add_blank_page}\ninput_pdf: {input_pdf is None}"
        )

        if input_pdf:
            # conver to Path
            input_pdf_data = await input_pdf.read()
            input_pdf_data = BytesIO(input_pdf_data)
            # input_pdf_data = PdfReader(input_pdf_data)
            # save the PDF file
            logger.info(f"The filename is {input_pdf.filename}")
            if input_pdf_path is None:
                input_pdf_path = self.temp_dir_name / input_pdf.filename
                output_file_path = self.temp_dir_name / input_pdf.filename.replace(".pdf", "_translated.pdf")
            else:
                input_pdf_path = Path(input_pdf_path)
            with open(input_pdf_path, "wb") as f:
                writer = PdfWriter()
                writer.append(input_pdf_data)
                writer.write(f)
            input_pdf_data = Path(input_pdf_path)
        elif input_pdf_path:
            input_pdf_data = Path(input_pdf_path)
        else:
            raise ValueError("No input PDF file provided")
        response: str = self._submit(
            input_pdf_data,
            self.temp_dir_name,
            from_lang,
            to_lang,
            translate_all,
            p_from,
            p_to,
            output_file_path=output_file_path,
            render_mode=render_mode,
            add_blank_page=add_blank_page,
        )
        return JSONResponse(content={"message": response})

    def _submit(
        self,
        pdf_path: Path,
        temp_output_dir: Path,
        from_lang: str,
        to_lang: str,
        translate_all: bool,
        p_from: int,
        p_to: int,
        output_file_path: Optional[Path | str] = None,
        render_mode: Optional[str] = None,
        add_blank_page: bool = False,
    ) -> None:
        """Submit a translation request."""
        req = TranslateRequest(
            pdf_path=pdf_path,
            temp_output_dir=temp_output_dir,
            from_lang=from_lang,
            to_lang=to_lang,
            translate_all=translate_all,
            p_from=p_from,
            p_to=p_to,
            output_file_path=output_file_path,
            render_mode=render_mode,
            add_blank_page=add_blank_page,
        )
        # self.req_db.add_request(req)
        # self.lock.acquire()
        self.pending_requests.append(req)
        # self.lock.release()
        self.file_db.add_file(
            str(req.pdf_path).split("/")[-1], 
            str(req.pdf_path), 
            str(req.output_file_path),
            FileStatus.NOT_TRANSLATED
        )
        if len(self.pending_requests) == 1:
            return "Request submitted, translating..."
        else:
            return f"Request submitted, there are {len(self.pending_requests) - 1} requests before."

    async def get_files(self, target_status: Optional[FileStatus]=Form(None)):
        logger.info(f"Getting files with status {target_status}")
        file_status: list[tuple] = self.file_db.get_files(target_status)
        ret_status = []
        for file, src_path, target_path, status in file_status:
            target_file_disappeared = status == FileStatus.TRANSLATED.value and not os.path.exists(target_path)
            src_path_disappeared = status == FileStatus.NOT_TRANSLATED.value and not os.path.exists(src_path)
            if target_file_disappeared or src_path_disappeared:
                self.file_db.remove_file(file)
                continue
            status = {
                "file": file,
                "src_path": src_path,
                "target_path": target_path,
                "status": status,
            }
            ret_status.append(status)
        return JSONResponse(content=ret_status)
    
    async def download_file(self, file_path: str=Form(...)):
        logger.info(f"Downloading file {file_path}")
        if not os.path.exists(file_path):
            return JSONResponse(content={"message": "File not found"})
        return FileResponse(file_path)

    async def clear_temp_dir(self):
        """API endpoint for clearing the temporary directory."""
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_name = Path(self.temp_dir.name)
        return {"message": "temp dir cleared"}

    def _init_translation(
        self,
        pdf_path: Path,
        render_mode: Optional[str],
        p_from: int,
        p_to: int,
        translate_all: bool,
    ) -> Tuple[List[Image.Image], Optional[RenderMode]]:
        # Check if the input is a file or bytes
        if isinstance(pdf_path, str):
            pdf_path = Path(pdf_path)
            # check if the path is a file
            assert pdf_path.is_file(), f"{pdf_path} is not a file"

        if isinstance(pdf_path, Path):
            pdf_images = convert_from_path(pdf_path, dpi=self.DPI)
        else:
            raise ValueError("Invalid input type")

        # Get the render mode of the output file
        if isinstance(render_mode, str):
            render_mode = RenderMode.get_mode(render_mode)
        else:
            render_mode = None

        total_pages = len(pdf_images)
        if translate_all:
            p_from = 0
            p_to = total_pages
        elif p_to > p_from:
            total_pages = p_to - p_from
        else:
            logger.error("Invalid page range, the range will be [from_page, to_page)")
            raise ValueError(
                "Invalid page range, the range will be [from_page, to_page)"
            )
        pdf_images = pdf_images[p_from:p_to]
        logger.info(
            f"Total pages: {total_pages} / Translating pages: from {p_from} to {p_to} / Translate all: {translate_all}"
        )

        return pdf_images, render_mode

    def _translate_pdf(
        self,
        req: TranslateRequest,
    ) -> None:
        """Backend function for translating PDF files.

        Translation is performed in the following steps:
            1. Getting the layout and text
                1.1 Convert the PDF file to images
                1.2 Detect text blocks in the images (layout detection)
                1.3 For each text block, detect text (ocr)
            2. translate the text
            3. Setting the render font, render each page with the translated text
            4. Merge all PDF files into one PDF file

        At 3, this function does not translate the text after
        the references section. Instead, saves the image as it is.

        Parameters
        ----------
        pdf_path: Path
            Path to the input PDF file or bytes of the input PDF file
        temp_output_dir: Path
            Path to the output directory for temporal files
        from_lang: str
            The source language
        to_lang: str
            The target language
        translate_all: bool
            Translate all the pages
        p_from: int
            (Won't take effect when translate_all is True) The begin index of the range of translation
        p_to: int
            (Won't take effect when translate_all is True) The end index of the range of translation
        output_file_path: Optional[Path | str] = None
            The path of output file
        render_mode: Optional[str] = None,
            The render mode
        add_blank_page: bool = False,
            Add blank page at the begining and the end of the pdf, only take effects when the render mode is RenderMode.INTERLEAVE and the render backend is ReportLab
        """
        # 0. Initialize
        logger.info(f"Translate PDF: {req.pdf_path}")
        pdf_path, temp_output_dir, from_lang, to_lang, translate_all, p_from, p_to, output_file_path, render_mode, add_blank_page = req.extract()
        pdf_images, render_mode = self._init_translation(
            pdf_path, render_mode, p_from, p_to, translate_all
        )
        logger.info(f"Translate from {from_lang} to {to_lang}")

        pdf_files = []
        total_pages = len(pdf_images)
        logger.info(f"Step 1/2: processing {total_pages} pages")

        if isinstance(output_file_path, str):
            if Path(output_file_path).is_dir():
                output_file_path = os.path.join(output_file_path, pdf_path.name.replace(".pdf", "_translated.pdf"))
            output_file_path = Path(output_file_path)
        if isinstance(render_engine, SimpleRender):
            render_engine.init_pdf()
        elif isinstance(render_engine, ReportLabRender):
            render_engine.init_pdf(output_file_path, self.temp_dir_name)

        results, threads = [], []
        logger.info(f"Getting layout and texts")

        def translate_one_page(i, layouts):
            results[i] = translator.translate_all(
                layouts, from_lang, to_lang, multi_thread=True
            )

        # 1. Getting layout and text
        if not self.use_multi_thread:
            # Use multi-processing to control the vram usage
            # This will free the vram after each page is processed
            # On 3090, the vram usage is around 5GB
            logger.info(f"\tUsing single-threading")
            self.pool = Pool(1)
            res = self.pool.apply_async(layout_and_ocr_process, args=(cfg, pdf_images))
            self.pool.close()
            self.pool.join()
            results = res.get()
        else:
            # Initialize the layout engine / OCR engine
            layout_engine = load_layout_engine(cfg["layout"])
            ocr_engine = load_ocr_engine(cfg["ocr"])

            for i, image in enumerate(
                zip(range(p_to - p_from), pdf_images), desc="Getting layout and texts"
            ):
                result: list[Layout] = layout_engine.get_single_layout(
                    image
                )  # Getting layout
                result = ocr_engine.get_all_text(result)  # Getting text
                results.append(result)
                # translate the text in parallel
                t = Thread(target=translate_one_page, args=(i, result))
                threads.append(t)
                t.start()

        # 2. Translate the text
        logger.info(f"Translating pages")
        if self.use_multi_thread:
            logger.info(f"\tUsing multi-threading")
            for t in threads:
                t.join()
        else:
            # translate the text sequentially
            for i, result in tqdm(
                enumerate(results), leave=False, desc="Translating pages"
            ):
                result = translator.translate_all(result, from_lang, to_lang)
                results[i] = result

        # 3. Setting render font and render each page
        logger.info(f"Render the pages")
        for i, (image, result) in tqdm(
            enumerate(zip(pdf_images, results)), leave=False, desc="Setting render font"
        ):
            result = render_engine.get_all_fonts(result)
            output_path = temp_output_dir / f"{i:03}.pdf"

            if isinstance(render_engine, SimpleRender):
                if not render_engine.reached_references:
                    render_engine.translate_one_page(image=image, result=result)
                render_engine.post_process(image, render_mode, output_path, self.DPI)
                pdf_files.append(str(output_path))
            elif isinstance(render_engine, ReportLabRender):
                render_engine.translate_one_page(image=image, result=result)
                render_engine.post_process()
            else:
                raise NotImplementedError("Font engine not implemented")

        # 4. Merge the result and save the PDF
        logger.info("Step 2/2: Merging PDF files")
        if isinstance(render_engine, SimpleRender):
            render_engine.merge_pdfs(pdf_files, output_file_path, self.temp_dir_name)
        elif isinstance(render_engine, ReportLabRender):
            if render_mode is None:
                render_mode = render_engine.render_mode
            render_engine.save_pdf(
                render_mode, pdf_path, p_from, add_blank_page
            )
        else:
            raise NotImplementedError("Render engine not implemented")

if __name__ == "__main__":
    translate_api = TranslateApi(enable_gui=True)
    translate_api.run()
