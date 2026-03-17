from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
SWISS_CANTONS = {
    "AG": "Aargau",
    "AI": "Appenzell Innerrhoden",
    "AR": "Appenzell Ausserrhoden",
    "BE": "Bern",
    "BL": "Basel-Landschaft",
    "BS": "Basel-Stadt",
    "FR": "Freiburg",
    "GE": "Genf",
    "GL": "Glarus",
    "GR": "Graubuenden",
    "JU": "Jura",
    "LU": "Luzern",
    "NE": "Neuenburg",
    "NW": "Nidwalden",
    "OW": "Obwalden",
    "SG": "St. Gallen",
    "SH": "Schaffhausen",
    "SO": "Solothurn",
    "SZ": "Schwyz",
    "TG": "Thurgau",
    "TI": "Tessin",
    "UR": "Uri",
    "VD": "Waadt",
    "VS": "Wallis",
    "ZG": "Zug",
    "ZH": "Zuerich",
}

NO_SPACE_BEFORE = {
    ".",
    ",",
    ";",
    ":",
    "!",
    "?",
    ")",
    "]",
    "}",
    "»",
    "”",
    "›",
    "%",
    "...",
}
NO_SPACE_AFTER = {"(", "[", "{", "«", "\"", "„", "‚", "‹"}
TERMINAL_END = (".", "!", "?", "…")
STARTS_WITH_CLOSER = ("»", "”", "’", ")", "]", "}", ",", ";", ":")
ABBREV_ENDINGS = ("geb.", "gest.", "vgl.", "ca.", "u.a.", "etc.")


def detokenize(tokens: list[str]) -> str:
    parts: list[str] = []
    for token in tokens:
        tok = token.strip()
        if not tok:
            continue
        if not parts:
            parts.append(tok)
            continue

        prev = parts[-1]
        if tok in NO_SPACE_BEFORE or tok.startswith("'"):
            parts[-1] = f"{prev}{tok}"
        elif prev and prev[-1] in NO_SPACE_AFTER:
            parts[-1] = f"{prev}{tok}"
        else:
            parts.append(tok)

    return " ".join(parts)


def norm_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def first_text(root: ET.Element, paths: list[str]) -> str:
    for path in paths:
        node = root.find(path, NS)
        if node is not None:
            text = norm_text("".join(node.itertext()))
            if text:
                return text
    return ""


def infer_year(root: ET.Element) -> str:
    year = first_text(
        root,
        [
            ".//tei:date[@type='publication_year']",
            ".//tei:date[@type='first_published']",
        ],
    )
    if year:
        m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", year)
        if m:
            return m.group(1)

    bibl_text = first_text(root, [".//tei:sourceDesc/tei:bibl"])
    m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", bibl_text)
    return m.group(1) if m else ""


def infer_canton(root: ET.Element) -> tuple[str, str, str]:
    canton_name = first_text(
        root,
        [
            ".//tei:noteGrp[@type='dialect_canton']/tei:note[@type='name']",
        ],
    )
    canton_code = first_text(
        root,
        [
            ".//tei:noteGrp[@type='dialect_canton']/tei:note[@type='chmk-id']",
        ],
    )
    region_name = first_text(
        root,
        [
            ".//tei:noteGrp[@type='dialect_region']/tei:note[@type='name']",
        ],
    )

    if not canton_code:
        region_code = first_text(
            root,
            [
                ".//tei:noteGrp[@type='dialect_region']/tei:note[@type='chmk-id']",
            ],
        )
        if region_code and "-" in region_code:
            maybe = region_code.split("-", 1)[0]
            if maybe in SWISS_CANTONS:
                canton_code = maybe

    if not canton_name and canton_code in SWISS_CANTONS:
        canton_name = SWISS_CANTONS[canton_code]

    if not canton_name:
        canton_name = "Unknown"

    return canton_name, canton_code, region_name


def extract_metadata(root: ET.Element, xml_file: Path) -> dict[str, str]:
    source = first_text(
        root,
        [
            ".//tei:title[@type='abbreviated']",
            ".//tei:title[@type='main']",
            ".//tei:titleStmt/tei:title",
        ],
    )
    if not source:
        source = xml_file.stem

    file_id = first_text(root, [".//tei:msDesc/tei:msIdentifier/tei:idno"]) or xml_file.stem.split("_", 1)[0]
    year = infer_year(root)
    canton_name, canton_code, region_name = infer_canton(root)
    return {
        "xml_file": str(xml_file),
        "file_id": file_id,
        "source": source,
        "year": year,
        "canton": canton_name,
        "canton_code": canton_code,
        "region": region_name,
    }


def sentence_rows(xml_file: Path) -> list[dict[str, str]]:
    tree = ET.parse(xml_file)
    root = tree.getroot()
    metadata = extract_metadata(root, xml_file)

    rows: list[dict[str, str]] = []
    s_nodes = root.findall(".//tei:text/tei:body//tei:s", NS)
    if s_nodes:
        for idx, s in enumerate(s_nodes, start=1):
            tokens = [norm_text("".join(w.itertext())) for w in s.findall(".//tei:w", NS)]
            tokens = [t for t in tokens if t]
            text = detokenize(tokens)
            if not text:
                text = norm_text("".join(s.itertext()))
            if not text:
                continue

            rows.append(
                {
                    **metadata,
                    "sentence_id": str(idx),
                    "lang": s.attrib.get("{http://www.w3.org/XML/1998/namespace}lang", ""),
                    "sentence": text,
                }
            )
        return rows

    paragraphs = root.findall(".//tei:text/tei:body//tei:p", NS)
    for idx, p in enumerate(paragraphs, start=1):
        tokens = [norm_text("".join(w.itertext())) for w in p.findall(".//tei:w", NS)]
        tokens = [t for t in tokens if t]
        text = detokenize(tokens)
        if not text:
            text = norm_text("".join(p.itertext()))
        if not text:
            continue

        rows.append(
            {
                **metadata,
                "sentence_id": f"p{idx}",
                "lang": "",
                "sentence": text,
            }
        )

    return rows


def should_merge(prev_sentence: str, current_sentence: str) -> bool:
    prev = prev_sentence.strip()
    cur = current_sentence.strip()
    if not prev or not cur:
        return False

    if cur.startswith(STARTS_WITH_CLOSER):
        return True

    if prev.endswith((",", ";", ":")):
        return True

    if prev.endswith(ABBREV_ENDINGS):
        return True

    if re.match(r"^[0-9][0-9\s,.;:]*$", cur):
        return True

    if not prev.endswith(TERMINAL_END):
        first = cur[0]
        if first.islower() or first in ("'", "\"", "«", "„"):
            return True

    return False


def merge_sentence_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return rows

    merged: list[dict[str, str]] = []
    current = dict(rows[0])
    start_id = current["sentence_id"]
    end_id = current["sentence_id"]

    for row in rows[1:]:
        if should_merge(current["sentence"], row["sentence"]):
            current["sentence"] = f"{current['sentence']} {row['sentence']}".strip()
            end_id = row["sentence_id"]
            continue

        if end_id != start_id:
            current["sentence_id"] = f"{start_id}-{end_id}"
        merged.append(current)
        current = dict(row)
        start_id = current["sentence_id"]
        end_id = current["sentence_id"]

    if end_id != start_id:
        current["sentence_id"] = f"{start_id}-{end_id}"
    merged.append(current)
    return merged


def year_sort_key(value: str) -> tuple[int, str]:
    if value and value.isdigit():
        return (0, f"{int(value):04d}")
    return (1, value)


def sentence_id_sort_key(value: str) -> tuple[int, int, str]:
    m = re.match(r"^(?:p)?(\d+)", value)
    if not m:
        return (1, 0, value)
    prefix_penalty = 1 if value.startswith("p") else 0
    return (0, prefix_penalty, int(m.group(1)))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_overview(documents: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        documents,
        key=lambda d: (
            year_sort_key(d["year"]),
            d["source"],
            d["file_id"],
            d["xml_file"],
        ),
    )


def run(input_dir: Path, output_dir: Path) -> tuple[int, int]:
    xml_files = sorted(input_dir.glob("*.xml"))
    xml_files = [p for p in xml_files if not p.name.endswith("_index.xml")]

    all_rows: list[dict[str, str]] = []
    documents: list[dict[str, str]] = []
    for xml_file in xml_files:
        try:
            rows = merge_sentence_rows(sentence_rows(xml_file))
            all_rows.extend(rows)

            if rows:
                base = {k: rows[0][k] for k in ["xml_file", "file_id", "source", "year", "canton", "canton_code", "region"]}
            else:
                root = ET.parse(xml_file).getroot()
                base = extract_metadata(root, xml_file)
            documents.append({**base, "sentence_count": str(len(rows))})
        except ET.ParseError as e:
            print(f"[warn] Failed to parse {xml_file}: {e}")

    all_rows = sorted(
        all_rows,
        key=lambda r: (
            year_sort_key(r["year"]),
            r["source"],
            r["file_id"],
            sentence_id_sort_key(r["sentence_id"]),
        ),
    )

    sentence_csv = output_dir / "chmk_sentences.csv"
    overview_csv = output_dir / "chmk_overview.csv"

    write_csv(
        sentence_csv,
        [
            "file_id",
            "source",
            "year",
            "canton",
            "canton_code",
            "region",
            "sentence_id",
            "lang",
            "sentence",
            "xml_file",
        ],
        all_rows,
    )

    overview_rows = build_overview(documents)
    write_csv(
        overview_csv,
        ["xml_file", "file_id", "source", "year", "canton", "canton_code", "region", "sentence_count"],
        overview_rows,
    )

    return len(overview_rows), len(all_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert CHMK XML files to readable CSV files.")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("data/unpacked/XML-CHMK_v2.2_free_subcorpus"),
        help="Directory containing extracted CHMK XML files.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where CSV files will be written.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    files_count, sentences_count = run(args.input_dir, args.output_dir)
    print(f"Wrote {sentences_count} sentence rows across {files_count} sources.")
    print(f"- {args.output_dir / 'chmk_sentences.csv'}")
    print(f"- {args.output_dir / 'chmk_overview.csv'}")


if __name__ == "__main__":
    main()
