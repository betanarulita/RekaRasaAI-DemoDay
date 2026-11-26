"""Bounded Campaign Brief parsing and template generation."""
from __future__ import annotations

import io
import re
import struct
import unicodedata
import zipfile
from datetime import date, timedelta
import zlib
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

from catalog_import import spreadsheet_rows

COLUMNS = (
    "content_request",
    "product_project_name",
    "product_description",
    "product_facts",
    "product_variants",
    "price",
    "promotion",
    "content_idea",
    "objective",
    "key_message",
    "channels",
    "supporting_information",
    "additional_notes",
    "folder_name",
    "deadline",
)
MAX_REQUESTS = 3
MAX_DATA_ROWS = 200
MAX_CELL_CHARS = 2000
MAX_ROW_CHARS = 10_000
MAX_COLUMNS = 50

ALIASES = {
    "content_request": {
        "content_request", "content request", "permintaan_konten", "permintaan konten",
        "request_konten", "request konten", "content_brief", "brief_konten",
    },
    "product_project_name": {
        "product_project_name", "nama_produk", "nama produk", "product_name", "product name",
        "nama_project", "nama project", "nama_proyek", "nama proyek", "project_name", "project name",
        "product", "produk",
    },
    "product_description": {"product_description", "deskripsi_produk", "deskripsi produk", "description", "deskripsi"},
    "product_facts": {"product_facts", "fakta_produk", "fakta produk", "facts", "fakta", "product_features", "fitur_produk"},
    "product_variants": {"product_variants", "variants", "varian", "variasi", "varian_produk"},
    "price": {"price", "harga", "harga_produk", "harga produk"},
    "promotion": {"promotion", "promo", "promosi", "penawaran", "offer"},
    "content_idea": {"content_idea", "ide_konten", "ide konten", "content idea", "konsep_konten"},
    "objective": {"objective", "tujuan", "tujuan_konten", "tujuan konten"},
    "key_message": {
        "key_message", "pesan_utama", "pesan utama", "key_message_promo", "key_message_promotion",
        "pesan_promosi", "pesan promosi",
    },
    "channels": {"channels", "channel", "platform", "platforms", "kanal", "saluran", "media"},
    "supporting_information": {
        "supporting_information", "supporting_info", "informasi_pendukung", "informasi pendukung",
        "info_pendukung", "info pendukung", "catatan_pendukung",
    },
    "additional_notes": {"additional_notes", "additional notes", "notes", "catatan_tambahan", "catatan tambahan", "catatan_lain"},
    "folder_name": {"folder_name", "folder name", "project_folder", "project folder", "nama_folder", "nama folder", "nama_folder_proyek", "nama folder proyek", "folder", "folder_tujuan", "folder tujuan"},
    "deadline": {"deadline", "due_date", "due date", "tanggal_deadline", "tanggal deadline", "tanggal_tenggat", "tanggal tenggat", "deadline_produksi", "deadline produksi", "tenggat"},
}
HEADER_TO_FIELD = {alias: field for field, aliases in ALIASES.items() for alias in aliases}
SHEET_COLUMNS = tuple(f"column_{index}" for index in range(MAX_COLUMNS))


class NotCampaignBrief(ValueError):
    """Raised when a spreadsheet is valid but has no recognizable brief headers."""


def normalize_header(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value).replace("\ufeff", "").strip().casefold())
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def field_for_header(value: str) -> str:
    normalized = normalize_header(value)
    return HEADER_TO_FIELD.get(normalized, "")


def is_legacy_catalog_headers(headers: list[str]) -> bool:
    normalized = {normalize_header(value) for value in headers if str(value).strip()}
    return "content_request" not in {field_for_header(value) for value in headers} and {
        "campaign_type", "product_name", "facts"
    }.issubset(normalized)


def _read_rows(raw: bytes, name: str) -> list[list[str]]:
    if not isinstance(name, str) or not name.lower().endswith((".xlsx", ".csv")):
        raise ValueError("Use an .xlsx Campaign Brief workbook or a UTF-8 .csv file.")
    if not isinstance(raw, bytes) or not raw or len(raw) > 5_000_000:
        raise ValueError("Use a non-empty Campaign Brief file no larger than 5 MB.")
    try:
        rows = spreadsheet_rows(raw, name, SHEET_COLUMNS, "Campaign Brief")
    except ValueError:
        raise
    except (zipfile.BadZipFile, zipfile.LargeZipFile, ET.ParseError, struct.error, KeyError,
            IndexError, UnicodeError, RuntimeError, NotImplementedError, EOFError, zlib.error) as exc:
        raise ValueError("Cannot read this Campaign Brief. Use one valid worksheet and plain cell values.") from exc
    if any(len(row) > MAX_COLUMNS for row in rows):
        raise ValueError(f"Campaign Briefs support at most {MAX_COLUMNS} columns.")
    return rows


def campaign_brief_headers(raw: bytes, name: str) -> list[str]:
    rows = _read_rows(raw, name)
    header_index = next((index for index, row in enumerate(rows) if any(str(value).strip() for value in row)), None)
    if header_index is None:
        raise ValueError("Campaign Brief is empty. Add headers and at least one request or reference row.")
    headers = [str(value).strip() for value in rows[header_index]]
    while headers and not headers[-1]:
        headers.pop()
    return headers


def _row_fields(headers: list[str], values: list[str], line_number: int) -> tuple[dict, dict]:
    fields = {column: "" for column in COLUMNS}
    extra_fields = {}
    for index, raw_value in enumerate(values):
        text = str(raw_value).strip()
        if not text:
            continue
        header = headers[index] if index < len(headers) else ""
        if not header:
            raise ValueError(f"Row {line_number}: a value has no column header.")
        field = field_for_header(header)
        if field:
            if fields[field]:
                raise ValueError(f"Row {line_number}: more than one header maps to '{field}'. Keep one of those columns.")
            if field == "deadline":
                text = _normalize_deadline(text, line_number)
            if field == "folder_name" and len(text) > 100:
                raise ValueError(f"Row {line_number}: keep folder_name within 100 characters.")
            fields[field] = text
        else:
            label = re.sub(r"\s+", " ", header).strip()[:80]
            extra_fields[label] = text
    too_long = [column for column, value in fields.items() if len(value) > MAX_CELL_CHARS]
    too_long.extend(label for label, value in extra_fields.items() if len(value) > MAX_CELL_CHARS)
    if too_long:
        raise ValueError(f"Row {line_number}: keep each cell within {MAX_CELL_CHARS:,} characters ({', '.join(too_long)}).")
    if sum(map(len, fields.values())) + sum(len(value) for value in extra_fields.values()) > MAX_ROW_CHARS:
        raise ValueError(f"Row {line_number}: keep the combined row within {MAX_ROW_CHARS:,} characters.")
    return fields, extra_fields


def _normalize_deadline(value: str, line_number: int) -> str:
    """Accept an ISO date or an Excel date serial and store YYYY-MM-DD."""
    if not value:
        return ""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            pass
    if re.fullmatch(r"\d{1,6}", value):
        serial = int(value)
        if 1 <= serial <= 2_958_465:
            return (date(1899, 12, 30) + timedelta(days=serial)).isoformat()
    raise ValueError(f"Row {line_number}: enter deadline as YYYY-MM-DD (for example 2026-12-15).")


def parse_campaign_brief(raw: bytes, name: str) -> dict:
    """Normalize request rows and reference-only rows without mixing their roles."""
    rows = _read_rows(raw, name)
    header_index = next((index for index, row in enumerate(rows) if any(str(value).strip() for value in row)), None)
    if header_index is None:
        raise ValueError("Campaign Brief is empty. Add headers and at least one request or reference row.")

    headers = [str(value).strip() for value in rows[header_index]]
    while headers and not headers[-1]:
        headers.pop()
    mapped = [field_for_header(header) if header else "" for header in headers]
    if not any(mapped):
        raise NotCampaignBrief("No Campaign Brief headers were recognized.")
    duplicates = sorted({field for field in mapped if field and mapped.count(field) > 1})
    if duplicates:
        raise ValueError("Campaign Brief has duplicate or ambiguous headers for: " + ", ".join(duplicates) + ". Keep one column for each field.")

    requests = []
    reference_rows = []
    for line_number, values in enumerate(rows[header_index + 1 :], header_index + 2):
        if not any(str(value).strip() for value in values):
            continue
        fields, extra_fields = _row_fields(headers, values, line_number)
        row = {"row_number": line_number, "fields": fields, "extra_fields": extra_fields}
        if fields["content_request"]:
            requests.append(row)
            if len(requests) > MAX_REQUESTS:
                raise ValueError(f"Campaign Briefs support at most {MAX_REQUESTS} content requests.")
        else:
            reference_rows.append(row)
        if len(requests) + len(reference_rows) > MAX_DATA_ROWS:
            raise ValueError(f"Campaign Briefs support at most {MAX_DATA_ROWS} non-empty rows.")

    if not requests and not reference_rows:
        raise ValueError("Add at least one content request or product/project reference row.")
    return {
        "rows": len(requests),
        "requests": requests,
        "reference_rows": reference_rows,
        "reference_text": campaign_reference_text(name, reference_rows),
    }


def campaign_reference_text(name: str, rows: list[dict]) -> str:
    if not rows:
        return ""
    lines = [f"Reference-only information from Campaign Brief workbook: {name}.", "These rows provide supporting context, not separate content-generation requests."]
    for row in rows:
        entries = []
        for field, value in row.get("fields", {}).items():
            if field in ("folder_name", "deadline"):
                continue
            if value:
                entries.append(f"{field}: {value}")
        entries.extend(f"{header}: {value}" for header, value in row.get("extra_fields", {}).items())
        if entries:
            lines.append(f"Row {row['row_number']}: " + " | ".join(entries))
    return "\n".join(lines)


def template_campaign_brief_xlsx() -> bytes:
    """Create a brief template with optional product facts and reference rows."""
    output = io.BytesIO()
    last_column = chr(64 + len(COLUMNS))
    header_cells = "".join(
        f'<c r="{chr(65 + index)}1" t="inlineStr"><is><t>{escape(column)}</t></is></c>'
        for index, column in enumerate(COLUMNS)
    )
    rows = [f'<row r="1">{header_cells}</row>'] + [f'<row r="{number}"></row>' for number in range(2, MAX_REQUESTS + 2)]
    widths = "".join(f'<col min="{index}" max="{index}" width="24" customWidth="1"/>' for index in range(1, len(COLUMNS) + 1))
    prompt = (
        "Each content_request row creates a plan (max 3); other rows are references. "
        "folder_name routes to a project folder; empty values go to Inbox and new folder names are created automatically. "
        "deadline uses YYYY-MM-DD and means production deadline, not promotion date. Indonesian headers are supported."
    )
    validation = (
        '<dataValidations count="1"><dataValidation type="textLength" operator="lessThanOrEqual" '
        'allowBlank="1" showInputMessage="1" promptTitle="Campaign Brief" '
        f'prompt="{escape(prompt, {chr(34): "&quot;"})}" sqref="A2:{last_column}{MAX_REQUESTS + 1}"><formula1>{MAX_CELL_CHARS}</formula1>'
        '</dataValidation></dataValidations>'
    )
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr("_rels/.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Campaign Brief" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr("xl/worksheets/sheet1.xml", '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols>' + widths + '</cols><sheetData>' + "".join(rows) + '</sheetData>' + validation + '</worksheet>')
    return output.getvalue()
