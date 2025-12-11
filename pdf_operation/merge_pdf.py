# merge the pdf files in the output_dir
from PyPDF2 import PdfFileMerger, PdfReader, PdfWriter
import sys
import os

if __name__ == "__main__":
    scan_dir = sys.argv[1]
    writer = PdfWriter()
    for file in os.listdir(scan_dir):
        if file.endswith(".pdf"):
            pdf_path = os.path.join(scan_dir, file)
            pdf = PdfReader(pdf_path)
            for page in pdf.pages:
                writer.add_page(page)
            writer.add_blank_page()
    with open("output.pdf", "wb") as f:
        writer.write(f)
        