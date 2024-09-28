from .base import Database
from enum import Enum
from typing import Optional
from loguru import logger

# database_name = "pdf_translator_files.db"

class FileStatus(Enum):
    NOT_TRANSLATED = 0
    TRANSLATING = 1
    TRANSLATED = 2

class FileDatabase(Database):
    def __init__(
        self,
        database_name,
        table_name="pdf_translator_files",
        table_format={
            "file": str,
            "src_path": str,
            "target_path": str,
            "status": int,
        },
    ):
        super().__init__(database_name, table_name, table_format=table_format)
        self.check_table()
        self.clear_unfinished_files()

    def clear_unfinished_files(self):
        self.c.execute(
            f"DELETE FROM {self.table_name} WHERE status = ?", (FileStatus.TRANSLATING.value,)
        )
        self.conn.commit()
        # delete NOT_TRANSLATED files
        self.c.execute(
            f"DELETE FROM {self.table_name} WHERE status = ?", (FileStatus.NOT_TRANSLATED.value,)
        )
        self.conn.commit()
        
    def set_translating_to_not_translated(self):
        self.c.execute(
            f"UPDATE {self.table_name} SET status = ? WHERE status = ?",
            (FileStatus.NOT_TRANSLATED.value, FileStatus.TRANSLATING.value),
        )
        self.conn.commit()
        
    def set_translating(self, file: str):
        self.c.execute(
            f"UPDATE {self.table_name} SET status = ? WHERE file = ?",
            (FileStatus.TRANSLATING.value, file),
        )
        self.conn.commit()
        
    def set_translated(self, file: str):
        self.c.execute(
            f"UPDATE {self.table_name} SET status = ? WHERE file = ?",
            (FileStatus.TRANSLATED.value, file),
        )
        self.conn.commit()

    def add_file(self, file, src_path, target_path, status: FileStatus | int):
        if isinstance(status, FileStatus):
            status = status.value
        self.c.execute(
            f"INSERT INTO {self.table_name} VALUES (?, ?, ?, ?)",
            (file, src_path, target_path, status),
        )
        self.conn.commit()
    
    def remove_file(self, file):
        self.c.execute(f"DELETE FROM {self.table_name} WHERE file = ?", (file,))
        self.conn.commit()

    def update_file_status(self, file, status):
        self.c.execute(
            f"UPDATE {self.table_name} SET status = ? WHERE file = ?", (status, file)
        )
        self.conn.commit()
    
    def get_files(self, status: Optional[FileStatus]):
        if status is None:
            self.c.execute(f"SELECT * FROM {self.table_name}")
        else:
            self.c.execute(f"SELECT * FROM {self.table_name} WHERE status = ?", (status.value,))
        return self.c.fetchall()
    
    def check_file_exists(self, file):
        self.c.execute(f"SELECT * FROM {self.table_name} WHERE file = ?", (file,))
        return self.c.fetchone() is not None