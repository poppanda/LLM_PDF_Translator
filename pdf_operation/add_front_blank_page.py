from PyPDF2 import PdfReader, PdfWriter
import os
import sys

def add_blank_page(input_pdf_path: str, output_pdf_path: str, front=True, back=True):
    reader = PdfReader(input_pdf_path)
    writer = PdfWriter()
    if front:
        writer.add_blank_page(reader.pages[0].mediabox.width, reader.pages[0].mediabox.height)
    for page in reader.pages:
        writer.add_page(page)
    if back:
        writer.add_blank_page(reader.pages[0].mediabox.width, reader.pages[0].mediabox.height)
    with open(output_pdf_path, "wb") as f:
        writer.write(f)
        
if __name__ == "__main__":
    input_pdf_path = sys.argv[1]
    output_pdf_path = sys.argv[2]
    add_blank_page_at_front(input_pdf_path, output_pdf_path)