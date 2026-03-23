import os

import docx
from pdfminer.high_level import extract_text as pdf_extract_text


def read_resume_text(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in [".pdf"]:
        return (pdf_extract_text(file_path) or "").strip()
    if ext in [".docx"]:
        d = docx.Document(file_path)
        return "\n".join(p.text for p in d.paragraphs).strip()
    # .doc (legacy) not supported out of the box
    return ""

