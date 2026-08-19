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


def _shape_text(root, shape_name):
    for shape in root.findall(f".//{{{P_NS}}}sp"):
        properties = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
        if properties is not None and properties.attrib.get("name") == shape_name:
            return "".join(
                node.text or "" for node in shape.iter(f"{{{A_NS}}}t")
            )
    return ""


def _shape_font_sizes(root, shape_name):
    for shape in root.findall(f".//{{{P_NS}}}sp"):
        properties = shape.find(f"{{{P_NS}}}nvSpPr/{{{P_NS}}}cNvPr")
        if properties is None or properties.attrib.get("name") != shape_name:
            continue
        return {
            int(node.attrib["sz"])
            for node in shape.iter()
            if node.tag in {
                f"{{{A_NS}}}rPr",
                f"{{{A_NS}}}defRPr",
                f"{{{A_NS}}}endParaRPr",
            }
            and "sz" in node.attrib
        }
    return set()


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

    assert len(parts) == 63
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

    scripture_bodies = [
        (_shape_text(root, "Content Placeholder 2"), root)
        for root in roots
        if _shape_text(root, "Content Placeholder 2").startswith(
            ("Peter, standing", "Then the eleven disciples")
        )
    ]
    assert len(scripture_bodies) == 2
    assert all("<sup>" not in text for text, _root in scripture_bodies)
    assert all(not text.startswith(("14", "16")) for text, _root in scripture_bodies)
    assert all(
        _shape_font_sizes(root, "Content Placeholder 2") == {3400}
        for _text, root in scripture_bodies
    )


def test_food_at_grace_appends_table_prayer_between_blank_slides(sample_blob):
    without_food = deepcopy(sample_blob)
    without_food["weekly"]["food_at_grace"] = False
    without_pptx = render_grace_presentation(without_food)
    without_archive, _presentation, without_parts = _ordered_slides(without_pptx)
    without_texts = [
        _normalized_slide_text(ET.fromstring(without_archive.read(part)))
        for part in without_parts
    ]

    with_food = deepcopy(sample_blob)
    with_food["weekly"]["food_at_grace"] = True
    with_pptx = render_grace_presentation(with_food)
    with_archive, _presentation, with_parts = _ordered_slides(with_pptx)
    with_roots = [ET.fromstring(with_archive.read(part)) for part in with_parts]
    with_texts = [_normalized_slide_text(root) for root in with_roots]

    assert len(with_parts) == len(without_parts) + 2
    assert not any("Be present at our table" in text for text in without_texts)
    assert with_texts[-3] == ""
    assert with_texts[-2] == (
        "Be present at our table, Lord; be here and ev'rywhere adored; "
        "These mercies bless, and grant that we May feast in paradise with Thee. Amen."
    )
    assert with_texts[-1] == ""
    assert _shape_font_sizes(with_roots[-2], "Title 1") == {4000}


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
        'import { hymnSlideFontSize, splitHymnSlideTexts } '
        'from "./scripts/generate_grace_presentation.mjs";'
        f"const chunks = splitHymnSlideTexts({json.dumps(stanza)});"
        "console.log(JSON.stringify({ chunks, sizes: chunks.map(hymnSlideFontSize) }));"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    output = json.loads(result.stdout)
    chunks = output["chunks"]

    assert len(chunks) > 1
    assert all(len(chunk) <= 650 for chunk in chunks)
    assert all(size >= 26 for size in output["sizes"])
    assert " ".join("\n".join(chunks).split()) == " ".join(stanza.split())


def test_readable_hymn_stanza_stays_on_one_slide():
    stanza = "\n".join(
        ["1 A readable hymn line."]
        + [f"Another readable hymn line {line}." for line in range(2, 17)]
    )
    script = (
        'import { hymnSlideFontSize, splitHymnSlideTexts } '
        'from "./scripts/generate_grace_presentation.mjs";'
        f"const slides = splitHymnSlideTexts({json.dumps(stanza)});"
        "console.log(JSON.stringify({ slides, sizes: slides.map(hymnSlideFontSize) }));"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    output = json.loads(result.stdout)

    assert output["slides"] == [stanza]
    assert output["sizes"] == [26]


def test_hymn_split_rebalances_a_single_line_continuation():
    stanza = "\n".join(f"Line {line}" for line in range(1, 11))
    script = (
        'import { splitHymnSlideTexts } from "./scripts/generate_grace_presentation.mjs";'
        f"console.log(JSON.stringify(splitHymnSlideTexts({json.dumps(stanza)}, 240, 9)));"
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

    assert [len(chunk.splitlines()) for chunk in chunks] == [8, 2]
    assert " ".join("\n".join(chunks).split()) == " ".join(stanza.split())


def test_have_thine_own_way_keeps_each_eight_line_verse_on_one_slide():
    script = """
import fs from "node:fs";
import { hymnSlideFontSize, splitHymnSlideTexts } from "./scripts/generate_grace_presentation.mjs";
const library = JSON.parse(fs.readFileSync("static/data/ambassador_hymns.json", "utf8"));
const slides = splitHymnSlideTexts(library["460"]);
console.log(JSON.stringify({ slides, sizes: slides.map(hymnSlideFontSize) }));
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    output = json.loads(result.stdout)

    assert len(output["slides"]) == 4
    assert all(len(slide.splitlines()) == 8 for slide in output["slides"])
    assert output["sizes"] == [36, 36, 36, 36]
    assert output["slides"][1].endswith("As in Thy presence\nHumbly I bow.")
    assert output["slides"][2].endswith("Touch me and heal me,\nSavior divine!")


def test_hymn_refrain_is_repeated_after_every_verse():
    hymn = (
        "Refrain:\nSing the whole refrain,\nSing it once again.\n\n"
        "1 This is the first verse,\nWith its second line.\n\n"
        "2 This is the second verse,\nWith another line."
    )
    script = (
        'import { splitHymnSlideTexts } from "./scripts/generate_grace_presentation.mjs";'
        f"console.log(JSON.stringify(splitHymnSlideTexts({json.dumps(hymn)})));"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    slides = json.loads(result.stdout)

    assert len(slides) == 2
    assert slides[0].startswith("1 This is the first verse")
    assert slides[1].startswith("2 This is the second verse")
    assert all(slide.count("Refrain:") == 1 for slide in slides)
    assert all("Sing the whole refrain,\nSing it once again." in slide for slide in slides)
    assert all(slide.index("Refrain:") > slide.index("verse") for slide in slides)


def test_every_ambassador_refrain_is_present_on_each_generated_hymn_slide():
    script = """
import fs from "node:fs";
import { splitHymnSlideTexts } from "./scripts/generate_grace_presentation.mjs";
const library = JSON.parse(fs.readFileSync("static/data/ambassador_hymns.json", "utf8"));
const results = Object.entries(library)
  .filter(([_number, text]) => /(?:^|\\n)Refrain:/i.test(text))
  .map(([number, text]) => {
    const slides = splitHymnSlideTexts(text);
    return {
      number,
      slideCount: slides.length,
      allRepeatRefrain: slides.every((slide) => slide.includes("Refrain:")),
    };
  });
console.log(JSON.stringify(results));
"""
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    results = json.loads(result.stdout)

    assert results
    assert all(result["slideCount"] > 0 for result in results)
    assert all(result["allRepeatRefrain"] for result in results)


def test_generated_hymn_slides_repeat_refrain_and_fit_the_font(sample_blob):
    blob = deepcopy(sample_blob)
    blob["weekly"]["large_print"]["opening_hymn_text"] = (
        "Refrain:\nSing the whole refrain,\nSing it once again.\n\n"
        "1 This is the first verse,\nWith its second line.\n\n"
        "2 This is the second verse,\nWith another line."
    )

    pptx = render_grace_presentation(blob)
    archive, _presentation, parts = _ordered_slides(pptx)
    roots = [ET.fromstring(archive.read(part)) for part in parts]
    hymn_slides = [
        root for root in roots if "Sing the whole refrain" in _shape_text(root, "Title 1")
    ]

    assert len(hymn_slides) == 2
    assert all(_shape_text(root, "Title 1").count("Refrain:") == 1 for root in hymn_slides)
    assert all("Sing it once again." in _shape_text(root, "Title 1") for root in hymn_slides)
    assert all(_shape_font_sizes(root, "Title 1") == {3200} for root in hymn_slides)


def test_scripture_slides_keep_whole_verses_hide_numbers_and_adjust_font():
    long_verse = " ".join(["Alpha"] * 70)
    second_verse = "Beta remains a complete verse."
    third_verse = "Gamma also remains complete."
    scripture = (
        f"<sup>1</sup>{long_verse} "
        f"<sup>2</sup>{second_verse} "
        f"<sup>3</sup>{third_verse}"
    )
    script = (
        'import { splitScriptureSlideTexts } from "./scripts/generate_grace_presentation.mjs";'
        f"console.log(JSON.stringify(splitScriptureSlideTexts({json.dumps(scripture)})));"
    )
    result = subprocess.run(
        [shutil.which("node"), "--input-type=module", "-e", script],
        cwd=BASE_DIR,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    slides = json.loads(result.stdout)

    assert [slide["text"] for slide in slides] == [
        long_verse,
        f"{second_verse} {third_verse}",
    ]
    assert slides[0]["fontSize"] < 40
    assert all("<sup>" not in slide["text"] for slide in slides)
    assert " ".join(slide["text"] for slide in slides) == (
        f"{long_verse} {second_verse} {third_verse}"
    )
