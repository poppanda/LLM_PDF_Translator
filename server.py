#!/usr/bin/env python3
"""
PDF Translator Server with Pure HTML Frontend
This version uses a static HTML/CSS/JS frontend instead of Gradio.
"""

import sys
import os
from threading import Thread
from multiprocessing import Pool
import tempfile
from pathlib import Path
from typing import List, Tuple
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
from PyPDF2 import PdfReader, PdfWriter
from io import BytesIO
import time
from pdf2image import convert_from_bytes, convert_from_path
from PIL import Image
from pydantic import BaseModel, Field
from modules.render.base import RenderMode
from modules.render.simple import SimpleRender
from modules.render.reportlab import ReportLabRender
from tqdm import tqdm
from loguru import logger
from concurrent.futures import ThreadPoolExecutor
from utils.layout_model import Layout
from utils.database.file_db import FileDatabase, FileStatus
from utils.api_utils import TranslateRequest
from threading import Thread

logger.remove()
logger.add(sys.stderr, level="INFO")


from utils import load_config
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
    """Translator API class with HTML frontend."""

    DPI = 200

    def __init__(
        self,
        model_root_dir: Path = Path("/app/models/"),
        enable_api: bool = True,
    ):
        # The database
        self.database_name = cfg.get("gui", {}).get(
            "database_name", "pdf_translator_files.db"
        )
        self.file_db = FileDatabase(self.database_name)
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_name = Path(self.temp_dir.name)

        self.use_multi_thread = cfg["multi_thread"]["enable"]

        self.pending_requests: list[TranslateRequest] = []

        self.translate_thread = Thread(target=self.scan_and_translate)
        self.translate_thread.start()

        if enable_api:
            self.app = FastAPI(title="PDF Translator API")

            # Mount static files for HTML frontend
            static_dir = Path("static")
            if static_dir.exists():
                self.app.mount(
                    "/static", StaticFiles(directory="static"), name="static"
                )
                logger.info("Static files mounted at /static")

            # Add API routes
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

            # File system management APIs
            self.app.add_api_route(
                "/browse_directory/",
                self.browse_directory,
                methods=["POST"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/create_directory/",
                self.create_directory,
                methods=["POST"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/delete_directory/",
                self.delete_directory,
                methods=["POST"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/get_config/",
                self.get_config,
                methods=["GET"],
                response_class=JSONResponse,
            )

            # Model configuration APIs
            self.app.add_api_route(
                "/get_translator_config/",
                self.get_translator_config,
                methods=["GET"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/set_translator_config/",
                self.set_translator_config,
                methods=["POST"],
                response_class=JSONResponse,
            )
            self.app.add_api_route(
                "/fetch_models/",
                self.fetch_models,
                methods=["POST"],
                response_class=JSONResponse,
            )

            # Add root route for HTML frontend
            @self.app.get("/", response_class=HTMLResponse)
            async def root():
                html_path = Path("static/index.html")
                if html_path.exists():
                    with open(html_path, "r", encoding="utf-8") as f:
                        return f.read()
                return "<h1>PDF Translator</h1><p>Frontend not found. Please ensure static/index.html exists.</p>"

            logger.info("HTML Frontend enabled at http://localhost:8765")

    def run(self):
        """Run the API server"""
        logger.info("Starting PDF Translator Server with HTML Frontend")
        logger.info("Access the web interface at: http://localhost:8765")
        uvicorn.run(self.app, host="0.0.0.0", port=8765)

    def scan_and_translate(self):
        """Scan the pending requests and translate them."""
        file_db = FileDatabase(self.database_name)
        while True:
            time.sleep(1)
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
    ) -> JSONResponse:
        """API endpoint for translating PDF files."""
        logger.info(
            f"Got request to translate PDF, the args are:\nfrom_lang: {from_lang} to_lang: {to_lang}\ntranslate_all: {translate_all} p_from: {p_from}, p_to: {p_to}\nrender_mode: {render_mode}\noutput_file_path: {output_file_path}\ninput_pdf_path: {input_pdf_path}\nadd_blank_page: {add_blank_page}\ninput_pdf: {input_pdf is None}"
        )

        if input_pdf:
            # conver to Path
            input_pdf_data = await input_pdf.read()
            input_pdf_data = BytesIO(input_pdf_data)
            # save the PDF file
            logger.info(f"The filename is {input_pdf.filename}")
            if input_pdf_path is None:
                input_pdf_path = self.temp_dir_name / input_pdf.filename
                output_file_path = self.temp_dir_name / input_pdf.filename.replace(
                    ".pdf", "_translated.pdf"
                )
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
            return JSONResponse(
                content={"message": "No input PDF file provided"}, status_code=400
            )

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
    ) -> str:
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
        self.pending_requests.append(req)
        self.file_db.add_file(
            str(req.pdf_path).split("/")[-1],
            str(req.pdf_path),
            str(req.output_file_path),
            FileStatus.NOT_TRANSLATED,
        )
        if len(self.pending_requests) == 1:
            return "Request submitted, translating..."
        else:
            return f"Request submitted, there are {len(self.pending_requests) - 1} requests before."

    async def get_files(self, target_status: Optional[FileStatus] = Form(None)):
        logger.info(f"Getting files with status {target_status}")
        file_status: list[tuple] = self.file_db.get_files(target_status)
        ret_status = []
        for file, src_path, target_path, status in file_status:
            target_file_disappeared = (
                status == FileStatus.TRANSLATED.value
                and not os.path.exists(target_path)
            )
            src_path_disappeared = (
                status == FileStatus.NOT_TRANSLATED.value
                and not os.path.exists(src_path)
            )
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

    async def download_file(self, file_path: str = Form(...)):
        logger.info(f"Downloading file {file_path}")
        if not os.path.exists(file_path):
            return JSONResponse(content={"message": "File not found"}, status_code=404)
        return FileResponse(file_path)

    async def clear_temp_dir(self):
        """API endpoint for clearing the temporary directory."""
        self.temp_dir.cleanup()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_dir_name = Path(self.temp_dir.name)
        return {"message": "temp dir cleared"}

    async def get_config(self):
        """Get configuration including default paths."""
        try:
            # Get project root directory (where server.py is located)
            project_root = Path(__file__).parent.resolve()

            download_folder = cfg.get("gui", {}).get(
                "download_folder", str(project_root / "download")
            )
            translate_folder = cfg.get("gui", {}).get(
                "translate_folder", str(project_root / "translate")
            )

            # Resolve paths to absolute paths
            # If path is relative, resolve it relative to project root
            download_path = Path(download_folder)
            if not download_path.is_absolute():
                download_path = project_root / download_folder
            download_folder = str(download_path.resolve())

            translate_path = Path(translate_folder)
            if not translate_path.is_absolute():
                translate_path = project_root / translate_folder
            translate_folder = str(translate_path.resolve())

            return JSONResponse(
                content={
                    "download_folder": download_folder,
                    "translate_folder": translate_folder,
                    "temp_dir": str(self.temp_dir_name),
                }
            )
        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def get_translator_config(self):
        """Get current translator configuration."""
        try:
            translator_cfg = cfg.get("translator", {})
            return JSONResponse(
                content={
                    "type": translator_cfg.get("type", "ollama"),
                    "api_key": translator_cfg.get("api_key", ""),
                    "base_url": translator_cfg.get("base_url", ""),
                    "model": translator_cfg.get("model", ""),
                }
            )
        except Exception as e:
            logger.error(f"Error getting translator config: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def set_translator_config(
        self,
        provider: str = Form(...),
        api_key: str = Form(""),
        base_url: str = Form(""),
        model: str = Form(""),
    ):
        """Update translator configuration and reinitialize translator."""
        global translator, cfg
        try:
            # Update config
            cfg["translator"]["type"] = provider
            cfg["translator"]["api_key"] = api_key
            cfg["translator"]["model"] = model
            if base_url:
                cfg["translator"]["base_url"] = base_url

            # Reinitialize translator
            translator = load_translator(cfg["translator"])
            logger.info(f"Translator updated to {provider} with model {model}")

            return JSONResponse(
                content={
                    "success": True,
                    "message": f"Translator updated to {provider} with model {model}",
                }
            )
        except Exception as e:
            logger.error(f"Error setting translator config: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def fetch_models(
        self,
        provider: str = Form(...),
        api_key: str = Form(""),
        base_url: str = Form(""),
    ):
        """Fetch available models from the provider API."""
        try:
            from openai import OpenAI

            # Set up client based on provider
            if provider == "ollama":
                client = OpenAI(
                    base_url=base_url or "http://localhost:11434/v1/",
                    api_key="ollama",
                )
            elif provider == "openai":
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url or "https://api.openai.com/v1",
                )
            elif provider == "qwen":
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url
                    or "https://dashscope.aliyuncs.com/compatible-mode/v1",
                )
            elif provider == "claude":
                # Claude uses different API, return preset models
                return JSONResponse(
                    content={
                        "models": [
                            "claude-3-opus-20240229",
                            "claude-3-sonnet-20240229",
                            "claude-3-haiku-20240307",
                            "claude-3-5-sonnet-20241022",
                        ]
                    }
                )
            elif provider == "deepseek":
                client = OpenAI(
                    api_key=api_key,
                    base_url=base_url or "https://api.deepseek.com/v1",
                )
            else:
                # Generic OpenAI-compatible provider
                client = OpenAI(
                    api_key=api_key or "none",
                    base_url=base_url,
                )

            # Fetch models
            models_response = client.models.list()
            models = [model.id for model in models_response.data]
            models.sort()

            return JSONResponse(content={"models": models})
        except Exception as e:
            logger.error(f"Error fetching models: {e}")
            return JSONResponse(
                content={"error": str(e), "models": []}, status_code=200
            )

    async def browse_directory(self, path: str = Form(None)):
        """Browse directory contents."""
        try:
            # If no path provided, use project root
            if path is None or path == "":
                path = str(Path(__file__).parent.resolve())

            # Security: prevent path traversal attacks
            target_path = Path(path).resolve()

            # Check if path exists and is a directory
            if not target_path.exists():
                return JSONResponse(
                    content={"error": "Path does not exist"}, status_code=404
                )

            if not target_path.is_dir():
                return JSONResponse(
                    content={"error": "Path is not a directory"}, status_code=400
                )

            # Get directory contents
            items = []
            try:
                for item in sorted(target_path.iterdir()):
                    try:
                        is_dir = item.is_dir()
                        items.append(
                            {
                                "name": item.name,
                                "path": str(item),
                                "is_directory": is_dir,
                                "size": item.stat().st_size if not is_dir else 0,
                                "modified": item.stat().st_mtime,
                            }
                        )
                    except PermissionError:
                        continue  # Skip items we can't access
            except PermissionError:
                return JSONResponse(
                    content={"error": "Permission denied"}, status_code=403
                )

            # Get parent directory
            parent = (
                str(target_path.parent) if target_path.parent != target_path else None
            )

            return JSONResponse(
                content={
                    "current_path": str(target_path),
                    "parent_path": parent,
                    "items": items,
                }
            )

        except Exception as e:
            logger.error(f"Error browsing directory: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def create_directory(self, path: str = Form(...), name: str = Form(...)):
        """Create a new directory."""
        try:
            parent_path = Path(path).resolve()
            new_dir = parent_path / name

            # Check if parent exists
            if not parent_path.exists() or not parent_path.is_dir():
                return JSONResponse(
                    content={"error": "Parent directory does not exist"},
                    status_code=404,
                )

            # Check if directory already exists
            if new_dir.exists():
                return JSONResponse(
                    content={"error": "Directory already exists"}, status_code=400
                )

            # Create directory
            new_dir.mkdir(parents=False, exist_ok=False)
            logger.info(f"Created directory: {new_dir}")

            return JSONResponse(
                content={
                    "message": "Directory created successfully",
                    "path": str(new_dir),
                }
            )

        except PermissionError:
            return JSONResponse(content={"error": "Permission denied"}, status_code=403)
        except Exception as e:
            logger.error(f"Error creating directory: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

    async def delete_directory(self, path: str = Form(...)):
        """Delete an empty directory."""
        try:
            target_path = Path(path).resolve()

            # Check if path exists
            if not target_path.exists():
                return JSONResponse(
                    content={"error": "Directory does not exist"}, status_code=404
                )

            # Check if it's a directory
            if not target_path.is_dir():
                return JSONResponse(
                    content={"error": "Path is not a directory"}, status_code=400
                )

            # Check if directory is empty
            if any(target_path.iterdir()):
                return JSONResponse(
                    content={"error": "Directory is not empty"}, status_code=400
                )

            # Delete directory
            target_path.rmdir()
            logger.info(f"Deleted directory: {target_path}")

            return JSONResponse(content={"message": "Directory deleted successfully"})

        except PermissionError:
            return JSONResponse(content={"error": "Permission denied"}, status_code=403)
        except Exception as e:
            logger.error(f"Error deleting directory: {e}")
            return JSONResponse(content={"error": str(e)}, status_code=500)

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
        """Backend function for translating PDF files."""
        logger.info(f"Translate PDF: {req.pdf_path}")
        (
            pdf_path,
            temp_output_dir,
            from_lang,
            to_lang,
            translate_all,
            p_from,
            p_to,
            output_file_path,
            render_mode,
            add_blank_page,
        ) = req.extract()
        pdf_images, render_mode = self._init_translation(
            pdf_path, render_mode, p_from, p_to, translate_all
        )
        logger.info(f"Translate from {from_lang} to {to_lang}")

        pdf_files = []
        total_pages = len(pdf_images)
        logger.info(f"Step 1/2: processing {total_pages} pages")

        if isinstance(output_file_path, str):
            if Path(output_file_path).is_dir():
                output_file_path = os.path.join(
                    output_file_path, pdf_path.name.replace(".pdf", "_translated.pdf")
                )
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

            for i, image in enumerate(zip(range(p_to - p_from), pdf_images)):
                result: list[Layout] = layout_engine.get_single_layout(image)
                result = ocr_engine.get_all_text(result)
                results.append(result)
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
            render_engine.save_pdf(render_mode, pdf_path, p_from, add_blank_page)
        else:
            raise NotImplementedError("Render engine not implemented")


if __name__ == "__main__":
    translate_api = TranslateApi(enable_api=True)
    translate_api.run()
