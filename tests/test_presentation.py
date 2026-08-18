from copy import deepcopy
import io
import json
import posixpath
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

import pytest

from presentation import render_grace_presentation


BASE_DIR = Path(__file__).resolve().parents[1]
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _ordered_slides(pptx: bytes):
    archive = zipfile.ZipFile(io.BytesIO(pptx))
    presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
    relationships = ET.fromstring(
        archive.read("ppt/_rels/presentation.xml.rels")
    )
    targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships.findall(f"{{{PKG_REL_NS}}}Relationship")
    }
    slide_list = presentation.find(f"{{{P_NS}}}sldIdLst")
    parts = [
        posixpath.normpath(
            posixpath.join("ppt", targets[slide.attrib[f"{{{R_NS}}}id"]])
        )
        for slide in slide_list
    ]
    return archive, presentation, parts


def _normalized_slide_text(root):
    text = "".join(node.text or "" for node in root.iter(f"{{{A_NS}}}t"))
    return " ".join(text.split())


def _assert_internal_relationship_targets_exist(archive):
    members = set(archive.namelist())
    for member in members:
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
        root = ET.fromstring(archive.read(member))
        for relationship in root.findall(f"{{{PKG_REL_NS}}}Relationship"):
            if relationship.attrib.get("TargetMode") == "External":
                continue
            target = relationship.attrib.get("Target", "")
            resolved = posixpath.normpath(
                posixpath.join(source_dir, target)
            ).lstrip("/")
            assert resolved in members, (member, target, resolved)


def test_combined_athanasian_baptism_and_communion_deck(sample_blob):
    blob = deepcopy(sample_blob)
    weekly = blob["weekly"]
    weekly["confession_of_faith"] = "Athanasian Creed"
    weekly["baptism"] = {"enabled": True, "text": "Alora Grace"}
    weekly["communion"] = {"enabled": True, "grace": True, "zion": False}
    weekly["special_music"] = "This weekly value must not appear"

    pptx = render_grace_presentation(blob)
    archive, presentation, parts = _ordered_slides(pptx)
    for member in archive.namelist():
        if member.endswith((".xml", ".rels")):
            ET.fromstring(archive.read(member))
    _assert_internal_relationship_targets_exist(archive)
    roots = [ET.fromstring(archive.read(part)) for part in parts]
    texts = [_normalized_slide_text(root) for root in roots]

    assert len(parts) == 65
    assert all(root.find(f".//{{{P_NS}}}fade") is not None for root in roots)
    assert all(part in archive.namelist() for part in parts)

    size = presentation.find(f"{{{P_NS}}}sldSz")
    assert int(size.attrib["cx"]) * 3 == int(size.attrib["cy"]) * 4

    baptism = next(
        index
        for index, text in enumerate(texts)
        if "Baptism" in text and "Alora Grace" in text
    )
    confession = next(index for index, text in enumerate(texts) if "The Confession of Sin" in text)
    communion = next(index for index, text in enumerate(texts) if text == "Holy Communion")
    doxology = next(index for index, text in enumerate(texts) if text.startswith("Praise God from Whom"))
    assert baptism < confession
    assert communion < doxology

    joined = "\n".join(texts)
    assert "Whoever wishes to be saved" in joined
    assert "Memory Verse: 1 Peter 5:6-7" in joined
    memory_body = next(text for text in texts if "Humble yourselves" in text)
    assert "6Humble" not in memory_body
    assert "7casting" not in memory_body
    assert "New Testament Lesson: Acts 2:14a, 22-36" in joined
    assert "Gospel Lesson: Matthew 28:16-20" in joined
    assert "Special Music and Offering" in joined
    assert "This weekly value must not appear" not in joined
    assert "Genesis 1:1-2:4a" in joined
    assert "G-pg 1" not in joined


@pytest.mark.parametrize(
    ("creed", "expected", "excluded"),
    [
        (
            "Apostles' Creed",
            "I believe in God the Father Almighty",
            "I believe in one God, the Father Almighty",
        ),
        (
            "Nicene Creed",
            "I believe in one God, the Father Almighty",
            "Whoever wishes to be saved",
        ),
    ],
)
def test_selected_creed_uses_its_static_template(sample_blob, creed, expected, excluded):
    blob = deepcopy(sample_blob)
    blob["weekly"]["confession_of_faith"] = creed
    pptx = render_grace_presentation(blob)
    archive, _presentation, parts = _ordered_slides(pptx)
    text = "\n".join(
        _normalized_slide_text(ET.fromstring(archive.read(part))) for part in parts
    )

    assert expected in text
    assert excluded not in text


def test_lesson_heading_rules_cover_all_four_categories():
    references = [
        "Genesis 1:1",
        "Psalm 8",
        "Matthew 28:16-20",
        "John 3:16",
        "Romans 8:1",
        "1 John 4:8",
        "Acts 2:1",
        "Revelation 21:1",
    ]
    script = (
        'import { lessonHeading } from "./scripts/generate_grace_presentation.mjs";'
        f"console.log(JSON.stringify({json.dumps(references)}.map(lessonHeading)));"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )

    assert json.loads(result.stdout) == [
        "Old Testament Lesson",
        "Old Testament Lesson",
        "Gospel Lesson",
        "Gospel Lesson",
        "Epistle Lesson",
        "Epistle Lesson",
        "New Testament Lesson",
        "New Testament Lesson",
    ]


def test_long_hymn_stanzas_are_split_without_losing_text():
    stanza = "\n".join(
        f"{line} This is a deliberately long hymn line for projection."
        for line in range(1, 13)
    )
    script = (
        'import { splitHymnSlideTexts } from "./scripts/generate_grace_presentation.mjs";'
        f"console.log(JSON.stringify(splitHymnSlideTexts({json.dumps(stanza)})));"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    chunks = json.loads(result.stdout)

    assert len(chunks) > 1
    assert all(len(chunk) <= 240 for chunk in chunks)
    assert " ".join("\n".join(chunks).split()) == " ".join(stanza.split())
