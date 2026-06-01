"""Milestone-1 confirmation: render the sample data through the render functions
and write the two PDFs to ``out/``.

This stands in for the old build.py / build_insert.py one-shot scripts: run it to
regenerate the reference PDFs and eyeball them against the originals.

    python build_samples.py
"""

from pathlib import Path

from sample_data.bulletin_data import STANDING, WEEKLY
from sample_data.insert_data import INSERT
from render import render_bulletin_pdf, render_insert_pdf

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

bulletin_path = OUT / "bulletin.pdf"
insert_path = OUT / "insert.pdf"

bulletin_path.write_bytes(render_bulletin_pdf(WEEKLY, STANDING))
insert_path.write_bytes(render_insert_pdf(INSERT))

print(f"wrote {bulletin_path} ({bulletin_path.stat().st_size:,} bytes)")
print(f"wrote {insert_path} ({insert_path.stat().st_size:,} bytes)")
