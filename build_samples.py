"""Render sample data through the production generators and write all outputs
to ``out/``.

This stands in for the old build.py / build_insert.py one-shot scripts: run it to
regenerate the reference PDFs and eyeball them against the originals.

    python build_samples.py
"""

from pathlib import Path

from presentation import render_grace_presentation
from sample_data.bulletin_data import STANDING, WEEKLY
from sample_data.insert_data import INSERT
from render import render_bulletin_pdf, render_insert_pdf, render_large_print_pdf
from schema import normalize_blob

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(exist_ok=True)

bulletin_path = OUT / "bulletin.pdf"
insert_path = OUT / "insert.pdf"
large_print_path = OUT / "large-print-booklet.pdf"
presentation_path = OUT / "grace-presentation.pptx"

blob = normalize_blob({"weekly": WEEKLY, "standing": STANDING, "insert": INSERT})
bulletin_path.write_bytes(render_bulletin_pdf(blob["weekly"], blob["standing"]))
insert_path.write_bytes(render_insert_pdf(blob["insert"]))
large_print_path.write_bytes(
    render_large_print_pdf(blob["weekly"], blob["standing"], blob["insert"])
)
presentation_path.write_bytes(render_grace_presentation(blob))

print(f"wrote {bulletin_path} ({bulletin_path.stat().st_size:,} bytes)")
print(f"wrote {insert_path} ({insert_path.stat().st_size:,} bytes)")
print(f"wrote {large_print_path} ({large_print_path.stat().st_size:,} bytes)")
print(f"wrote {presentation_path} ({presentation_path.stat().st_size:,} bytes)")
