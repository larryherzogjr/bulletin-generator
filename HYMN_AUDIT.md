# Hymn transcription review — September 6, 2026

Scanned all 634 entries in `static/data/ambassador_hymns.json` for unexpected
digits in lyrics, repeated words, malformed punctuation, unusual spellings,
and verse-number sequences. Reviewed the flagged lines in context and checked
selected passages against published hymn texts. This was a targeted error
scan, not a line-by-line comparison with the printed Ambassador Hymnal.

## Corrections

The scan produced 16 additional corrections across 14 hymns, after the initial
user-reported correction to #578. Exact replacements are also retained in
`scripts/import_ambassador_hymns.py` so future imports preserve them.

| Hymn | Original fragment | Corrected fragment |
| --- | --- | --- |
| 2 | O come, O come. Emmanuel | O come, O come, Emmanuel |
| 4 | Ye saints. who | Ye saints, who |
| 23 | Christ. the Savior | Christ, the Savior |
| 152 | Nature’s wonder Jesus’ wisdom | Nature’s wonder, Jesus’ wisdom |
| 152 | Treasure. too You | Treasure, too, You |
| 179 | Shall pray. and pray aright | Shall pray, and pray aright |
| 184 | Thine angels adore Thee. all veiling | Thine angels adore Thee, all veiling |
| 196 | Behold our need. and hear our cry | Behold our need, and hear our cry |
| 306 | Offring | Off’ring |
| 336 | Jesus. alas! | Jesus, alas! |
| 386 | O perfect Love. all human thought | O perfect Love, all human thought |
| 468 | Draw me. my Savior | Draw me, my Savior |
| 480 | O resurrection day!. | O resurrection day! |
| 501 | No turning back, no turning back!. (twice) | No turning back, no turning back! |
| 578 (previous fix) | Amazing grace, 1 sweet | Amazing grace, how sweet |
| 604 | 2 1 know | 2 I know |

## Reference checks

- [Evangelical Lutheran Synod hymn sheet](https://els.org/wp-content/download/Heritage-Hymns-of-the-Month.pdf) confirms the wording in #604.
- [Church of Scotland hymn listing](https://music.churchofscotland.org.uk/hymn/273-o-come-o-come-emmanuel) supports #2.
- [Hymnary text listing](https://www.hymnary.org/text/ye_saints_who_here_in_patience) supports #4.
- [Saint Benedict’s service bulletin](https://www.saintbenedicts.org/wp-content/uploads/2024/03/Bulletin-Mar-16-and-Mar-17-2024-The-Fifth-Sunday-in-Lent.pdf) supports the punctuation repairs in #152.
- [CPWI Hymnal text](https://www.hymnary.org/hymn/CPWI2010/490) supports #179.
- [Lutheran Service Book concordance](https://www.lutheranmusic.com/samples/LutheranMusic%24LSB-Concordance%24SAMPLE.pdf) supports #184.
- [Grace Lutheran service bulletin](https://gracelutheranescondido.org/wp-content/uploads/2024/05/May-26-2024-final.pdf) supports the contraction in #306.
- [Evangelical Lutheran Hymnary concordance](https://www.lutheranmusic.com/samples/LutheranMusic%24ELH-Concordance%24SAMPLE.pdf) supports #336.
- [New English Hymnal text](https://hymnary.org/hymn/NEH1985/320a) supports #386.
- [SDA Hymnal text](https://www.sdahymnal.org/Hymn?no=301) supports #468.

The other changes repair plainly misplaced punctuation. These references
support individual repairs; they are not substitutes for the Ambassador edition.

## Left unchanged

- #94 and #554 use verse-specific refrain labels; their apparent repeated
  verse numbers are intentional.
- Archaic spellings, poetic contractions, and foreign-language verses were
  preserved instead of applying blanket dictionary corrections.
- #480 has the unusual punctuation “I’ll joyful, cast my golden crown,”;
  #613 has “Kuniassaan” in its Finnish text. These merit comparison with the
  printed edition before further editing.

## Validation

The hymn tests cover import structure, all 634 entries, browser delivery,
correction of corrupted source text, importing already-corrected source text,
and preservation of verse-specific refrain labels and poetic contractions.
