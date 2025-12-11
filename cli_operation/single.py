import warnings

warnings.filterwarnings("ignore")
import server
import os
from pathlib import Path
import tempfile
from loguru import logger
import sys
import argparse

if __name__ == "__main__":
    translator = server.TranslateApi()
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", type=str, help="PDF file to translate")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite the existing translated file",
    )
    parser.add_argument(
        "--suffix",
        type=str,
        default="_translated",
        help="Suffix for the translated file (without .pdf)",
    )
    # get the arguments
    args = parser.parse_args()
    file: str = args.file # source file
    suffix = args.suffix + ".pdf" # suffix for the translated file
    overwrite_flag: bool = args.overwrite # overwrite the existing translated file

    # make sure the file exists and is a PDF file
    assert os.path.exists(file) and file.endswith(
        ".pdf"
    ), "Please provide a valid PDF file"

    # make sure the translation action should be done
    file: Path = Path(file)
    is_translated_file = file.name.endswith(suffix)
    has_translated_file = os.path.exists(file.as_posix().replace(".pdf", suffix))
    if is_translated_file or (has_translated_file and not overwrite_flag):
        logger.info(f"Skip {file.as_posix()}")
        exit(0)
        
    # start translation
    logger.info(f"Translating {file.as_posix()}")
    response = translator._translate_pdf(
        pdf_path_or_bytes=file.as_posix(),
        output_dir=translator.temp_dir_name,
        from_lang="English",
        to_lang="Chinese",
        translate_all=True,
        p_from=0,
        p_to=0,
        output_file_path=file.as_posix().replace(".pdf", suffix),
    )
