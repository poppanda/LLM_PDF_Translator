# create a database to save (file, path, status)
# file: the name of the file
# path: the path of the file
# status: the status of the file (translated, not translated) -> True, False
import sqlite3

class Database:
    def __init__(self, database_name, table_name, table_format: dict):
        self.database = database_name
        self.conn = sqlite3.connect(self.database)
        self.c = self.conn.cursor()
        self.table_name = table_name
        self.table_format = ""
        for key, value in table_format.items():
            if value == str:
                self.table_format += f"{key} text, "
            elif value == bool:
                self.table_format += f"{key} boolean, "
            elif value == int:
                self.table_format += f"{key} integer, "
            elif value == float:
                self.table_format += f"{key} real, "
            elif value == bytes:
                self.table_format += f"{key} blob, "
            else:
                print("Invalid data type")

    def check_table(self):
        # Check if the table exists
        self.c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (self.table_name,),
        )
        if self.c.fetchone() is None:
            self.c.execute(
                f"""CREATE TABLE {self.table_name} ({self.table_format[:-2]})"""
            )
            self.conn.commit()

    def delete_db(self):
        self.c.execute(f"DROP TABLE {self.table_name}")
        self.conn.commit()

    def recreate_db(
        self,
    ):
        # Check if the table exists
        self.c.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='files'"
        )
        if self.c.fetchone() is not None:
            self.c.execute("DROP TABLE files")
        self.c.execute(
            """CREATE TABLE files
                        (file text, src_path text, target_path text, status boolean)"""
        )
        self.conn.commit()
