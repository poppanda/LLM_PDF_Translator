from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass
class TranslateRequest:
    pdf_path: Path
    temp_output_dir: Path
    from_lang: str
    to_lang: str
    translate_all: bool
    p_from: int
    p_to: int
    output_file_path: Optional[Path | str] = None,
    render_mode: Optional[str] = None,
    add_blank_page: bool = False,
    def extract(self):
        if isinstance(self.pdf_path, str):
            self.pdf_path = Path(self.pdf_path)
        return (
            self.pdf_path,
            self.temp_output_dir,
            self.from_lang,
            self.to_lang,
            self.translate_all,
            self.p_from,
            self.p_to,
            self.output_file_path,
            self.render_mode,
            self.add_blank_page,
        )