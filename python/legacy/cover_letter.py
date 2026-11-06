"""Cover letter helpers.

The LETTER TEXT is written by the agent using the gerald-voice skill —
this module handles rendering to PDF and file naming.
Cover letters live in cover_letters/YYYY-MM-DD_company_role.{md,pdf}
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fpdf import FPDF

from common import COVER_LETTERS, cover_letter_name, register_cover_letter


def slug(text: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return s[:maxlen]


class LetterPDF(FPDF):
    def footer(self):
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(150)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def render_pdf(letter_text: str, out_path: Path, applicant: dict) -> Path:
    pdf = LetterPDF(format="A4", unit="mm")
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.set_margins(25, 25, 25)
    pdf.add_page()

    # Sender block
    pdf.set_font("helvetica", "", 10)
    contact = (
        f"{applicant['full_name']}\n{applicant['city']}, Germany\n"
        f"{applicant['email']}\n{applicant['phone']}"
    )
    pdf.multi_cell(0, 5, contact)
    pdf.ln(4)
    pdf.cell(
        0, 5, datetime.now().strftime("%d.%m.%Y"),
        align="R", new_x="LMARGIN", new_y="NEXT",
    )
    pdf.ln(6)

    pdf.set_font("helvetica", "", 11)
    # latin-1 covers German umlauts/ß; replace anything outside it
    safe = letter_text.encode("latin-1", "replace").decode("latin-1")
    pdf.multi_cell(0, 6, safe)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(out_path))
    return out_path


def save_letter(company: str, role: str, letter_text: str, applicant: dict,
                job_id: str = "") -> tuple[Path, Path]:
    base = cover_letter_name(company, role)
    if job_id:
        register_cover_letter(job_id, base)
    md_path = COVER_LETTERS / f"{base}.md"
    pdf_path = COVER_LETTERS / f"{base}.pdf"
    md_path.write_text(letter_text)
    render_pdf(letter_text, pdf_path, applicant)
    return md_path, pdf_path
