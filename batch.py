import warnings

warnings.filterwarnings("ignore")
import server
import os
from pathlib import Path
import tempfile
from loguru import logger
import sys

if __name__ == "__main__":
    translator = server.TranslateApi()
    pdf_dirs = sys.argv[1:]
    try:
        files = []
        for pdf_dir in pdf_dirs:
            files.extend(list(os.scandir(pdf_dir)))
    except Exception as e:
        print(e)
        exit(1)
    for file in files:
        if file.is_dir():
            files.extend(list(os.scandir(file.path)))
        elif file.is_file() and file.name.endswith(".pdf"):
            if file.name.endswith("_translated.pdf") or os.path.exists(
                file.path.replace(".pdf", "_translated.pdf")
            ):
                logger.info(f"Skip {file.path}")
                continue
            logger.info(f"Translating {file.path}")
            response = translator._translate_pdf(
                pdf_path_or_bytes=file.path,
                output_dir=translator.temp_dir_name,
                from_lang="English",
                to_lang="Chinese",
                translate_all=True,
                p_from=0,
                p_to=0,
                output_file_path=file.path.replace(".pdf", "_translated.pdf"),
            )
