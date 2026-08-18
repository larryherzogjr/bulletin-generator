"""Generate the Grace worship PowerPoint from a saved weekly data blob."""

from __future__ import annotations

import json
import io
import os
import posixpath
import shutil
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
BUILDER = BASE_DIR / "scripts" / "generate_grace_presentation.mjs"
TEMPLATE_DIR = BASE_DIR / "presentation_templates"
TEMPLATES = (
    TEMPLATE_DIR / "empty-root.pptx",
    TEMPLATE_DIR / "normal-apostles.pptx",
    TEMPLATE_DIR / "normal-apostles-baptism.pptx",
    TEMPLATE_DIR / "normal-apostles-communion.pptx",
    TEMPLATE_DIR / "normal-nicene.pptx",
    TEMPLATE_DIR / "normal-athanasian.pptx",
)
PACKAGE_RELATIONSHIP = (
    "{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"
)


class PresentationGenerationError(RuntimeError):
    """Raised when the Grace PowerPoint cannot be generated safely."""


def _node_executable() -> str:
    configured = os.environ.get("BULLETIN_NODE", "").strip()
    if configured:
        return configured
    node = shutil.which("node")
    if node:
        return node
    raise PresentationGenerationError(
        "PowerPoint generation is unavailable because Node.js is not installed."
    )


def render_grace_presentation(data: dict) -> bytes:
    """Return an editable Grace worship presentation as PPTX bytes."""
    if not BUILDER.is_file() or any(not template.is_file() for template in TEMPLATES):
        raise PresentationGenerationError(
            "PowerPoint generation is unavailable because its templates are missing."
        )

    timeout = int(os.environ.get("BULLETIN_PRESENTATION_TIMEOUT", "120"))
    with tempfile.TemporaryDirectory(prefix="grace-presentation-") as temp_dir:
        output = Path(temp_dir) / "grace-presentation.pptx"
        try:
            result = subprocess.run(
                [_node_executable(), str(BUILDER), "--output", str(output)],
                cwd=BASE_DIR,
                input=json.dumps(data, ensure_ascii=False),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PresentationGenerationError(
                "PowerPoint generation timed out. Try again or shorten unusually long text."
            ) from exc
        except OSError as exc:
            raise PresentationGenerationError(
                "PowerPoint generation could not start."
            ) from exc

        if result.returncode != 0:
            detail = result.stderr.strip().splitlines()
            message = detail[0] if detail else "PowerPoint generation failed."
            if message.startswith("Error: "):
                message = message[7:]
            raise PresentationGenerationError(message)

        try:
            pptx = output.read_bytes()
        except OSError as exc:
            raise PresentationGenerationError(
                "PowerPoint generation completed without producing a readable file."
            ) from exc
        if len(pptx) < 4 or pptx[:2] != b"PK":
            raise PresentationGenerationError(
                "PowerPoint generation produced an invalid file."
            )
        try:
            with zipfile.ZipFile(io.BytesIO(pptx)) as archive:
                members = set(archive.namelist())
                if "[Content_Types].xml" not in members or "ppt/presentation.xml" not in members:
                    raise PresentationGenerationError(
                        "PowerPoint generation produced an incomplete file."
                    )
                for member in members:
                    if not member.endswith((".xml", ".rels")):
                        continue
                    try:
                        root = ET.fromstring(archive.read(member))
                    except ET.ParseError as exc:
                        raise PresentationGenerationError(
                            "PowerPoint generation produced malformed XML."
                        ) from exc
                    if not member.endswith(".rels"):
                        continue
                    if member == "_rels/.rels":
                        source_dir = ""
                    else:
                        rels_dir, rels_name = posixpath.split(member)
                        source_part = posixpath.join(
                            posixpath.dirname(rels_dir), rels_name[:-5]
                        )
                        source_dir = posixpath.dirname(source_part)
                    for relationship in root.findall(PACKAGE_RELATIONSHIP):
                        if relationship.attrib.get("TargetMode") == "External":
                            continue
                        target = relationship.attrib.get("Target", "")
                        resolved = posixpath.normpath(
                            posixpath.join(source_dir, target)
                        ).lstrip("/")
                        if resolved not in members:
                            raise PresentationGenerationError(
                                "PowerPoint generation produced an incomplete relationship."
                            )
        except zipfile.BadZipFile as exc:
            raise PresentationGenerationError(
                "PowerPoint generation produced an invalid file."
            ) from exc
        return pptx
