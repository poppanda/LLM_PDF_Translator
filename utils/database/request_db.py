from .base import Database
from ..api_utils import TranslateRequest

class RequestDatabase(Database):
    def __init__(
        self,
        database_name,
        table_name="pdf_translator_requests",
        table_format={
            "pdf_path": str,
            "temp_output_dir": str,
            "from_lang": str,
            "to_lang": str,
            "translate_all": bool,
            "p_from": int,
            "p_to": int,
            "output_file_path": str,
            "render_mode": str,
            "add_blank_page": bool,
        },
    ):
        super().__init__(database_name, table_name, table_format=table_format)
        
    def add_request(self, request: TranslateRequest):
        self.c.execute(
            f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(request.pdf_path),
                str(request.temp_output_dir),
                request.from_lang,
                request.to_lang,
                request.translate_all,
                request.p_from,
                request.p_to,
                str(request.output_file_path),
                request.render_mode,
                request.add_blank_page,
            ),
        )
        self.conn.commit()