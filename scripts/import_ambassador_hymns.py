#!/usr/bin/env python3
"""Build the browser hymn library from the Ambassador lyrics source.

The supplied RTF uses page breaks as positional hymn separators.  macOS
``textutil`` performs the RTF-to-Unicode conversion; a previously converted
UTF-8 text file is also accepted so the structural parsing is platform-neutral.

The source has one known layout defect: position 254 is blank, while the next
position contains hymns 254 and 255 together.  ``build_library`` repairs that
defect explicitly and rejects any unexpected change to the source structure.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


HYMN_COUNT = 634
HYMNS_254_255_MARKER = "Print Thine image, pure and holy,"


def _normalize_block(block: str) -> str:
    lines = [line.rstrip() for line in block.replace("\r\n", "\n").split("\n")]
    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def build_library(text: str) -> dict[str, str]:
    """Return the validated ``{"1": lyrics, ..., "634": lyrics}`` mapping."""
    blocks = [_normalize_block(block) for block in text.split("\f")]
    if len(blocks) != HYMN_COUNT:
        raise ValueError(
            f"expected {HYMN_COUNT} positional blocks, found {len(blocks)}"
        )
    if blocks[253]:
        raise ValueError("expected the known blank source position 254")

    combined = blocks[254]
    marker = "\n" + HYMNS_254_255_MARKER
    if combined.count(marker) != 1:
        raise ValueError("could not split the combined source hymns 254 and 255")
    hymn_254, hymn_255_tail = combined.split(marker, 1)
    hymn_254 = _normalize_block(hymn_254)
    hymn_255 = _normalize_block(HYMNS_254_255_MARKER + hymn_255_tail)

    library: dict[str, str] = {}
    for number in range(1, HYMN_COUNT + 1):
        if number == 254:
            lyrics = hymn_254
        elif number == 255:
            lyrics = hymn_255
        else:
            lyrics = blocks[number - 1]
        if not lyrics:
            raise ValueError(f"hymn {number} has no lyrics after source repair")
        library[str(number)] = lyrics

    # Stable sentinels make accidental reordering or a different source edition
    # fail during import rather than silently producing a misnumbered library.
    sentinels = {
        "1": "1 Lift up your heads, ye mighty gates,",
        "254": "1 Abide in grace, Lord Jesus,",
        "255": HYMNS_254_255_MARKER,
        "256": "1 The day Thou gavest, Lord, is ended,",
        "634": "1 O Canada! our home and native land!",
    }
    for number, first_line in sentinels.items():
        if not library[number].startswith(first_line):
            raise ValueError(f"hymn {number} does not match its expected first line")

    return library


def source_text(path: Path) -> str:
    if path.suffix.lower() != ".rtf":
        return path.read_text(encoding="utf-8")
    try:
        converted = subprocess.run(
            ["textutil", "-convert", "txt", "-stdout", str(path)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "textutil is required for RTF input; convert the file to UTF-8 text "
            "first when running on another platform"
        ) from exc
    return converted.stdout.decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Ambassador lyrics .rtf or UTF-8 .txt")
    parser.add_argument("output", type=Path, help="generated hymn-library JSON")
    args = parser.parse_args()

    library = build_library(source_text(args.source))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(library, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(library)} hymns to {args.output}")


if __name__ == "__main__":
    main()
