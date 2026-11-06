"""Bounded spreadsheet import using only the Python standard library."""
import base64
import binascii
import csv
import io
import json
import struct
import re
import zipfile
from xml.etree import ElementTree as ET

COLUMNS = ("campaign_type", "product_name", "facts", "price", "promo", "channels", "image_filename")
TYPES = ("baru_buka", "daftar_produk", "produk_unggulan", "promo")
MAX_FILE = 5_000_000
NS = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def decode_file(encoded):
    if not isinstance(encoded, str) or len(encoded) > 6_700_000:
        raise ValueError("Use a file no larger than 5 MB.")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Invalid attachment encoding.")
    if not raw or len(raw) > MAX_FILE:
        raise ValueError("Use a non-empty file no larger than 5 MB.")
    return raw


def xml(raw):
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("XML declarations with entities are not supported.")
    return ET.fromstring(raw)


def spreadsheet_rows(raw, name):
    if name.lower().endswith(".csv"):
        return list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    if not name.lower().endswith(".xlsx"):
        raise ValueError("Use .xlsx or UTF-8 .csv. Legacy .xls and macros are not supported.")
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        info = archive.infolist()
        if len(info) > 150 or sum(i.file_size for i in info) > 12_000_000:
            raise ValueError("Spreadsheet expands beyond the import limit.")
        names = archive.namelist()
        if any("vbaproject" in n.lower() for n in names):
            raise ValueError("Macro-enabled workbooks are not supported.")
        shared = []
        if "xl/sharedStrings.xml" in names:
            shared = ["".join(t.text or "" for t in e.findall(".//s:t", NS)) for e in xml(archive.read("xl/sharedStrings.xml")).findall("s:si", NS)]
        sheets = [n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")]
        if len(sheets) != 1:
            raise ValueError("Use one worksheet per catalog file.")
        result = []
        for row in xml(archive.read(sheets[0])).findall("s:sheetData/s:row", NS):
            values = [""] * len(COLUMNS)
            for cell in row.findall("s:c", NS):
                if cell.find("s:f", NS) is not None:
                    raise ValueError("Replace formulas with plain values before importing.")
                ref = cell.get("r", "")
                letters = "".join(c for c in ref if c.isalpha())
                index = 0
                for c in letters.upper():
                    index = index * 26 + ord(c) - 64
                if not 1 <= index <= len(COLUMNS):
                    if "".join(cell.itertext()).strip():
                        raise ValueError("Only the seven template columns are supported.")
                    continue
                value = cell.findtext("s:v", default="", namespaces=NS)
                if cell.get("t") == "s":
                    value = shared[int(value)]
                elif cell.get("t") == "inlineStr":
                    inline = cell.find("s:is", NS)
                    value = "".join(t.text or "" for t in inline.findall(".//s:t", NS)) if inline is not None else ""
                values[index - 1] = value
            result.append(values)
        return result


def parse_catalog(raw, name):
    try:
        rows = spreadsheet_rows(raw, name)
    except (zipfile.BadZipFile, KeyError, IndexError, ET.ParseError, UnicodeError, RuntimeError, NotImplementedError) as exc:
        raise ValueError("Cannot read this spreadsheet. Use the template and plain cell values.") from exc
    first = next((index for index, row in enumerate(rows) if any(v.strip() for v in row)), None)
    if first is None:
        raise ValueError("Spreadsheet is empty. Add column headers and product rows.")
    headers = [re.sub(r"[\s-]+", "_", value.replace("\ufeff", "").strip().lower()) for value in rows[first]]
    active = [value for value in headers if value]
    missing = [key for key in ("campaign_type", "product_name", "facts") if key not in active]
    unknown = [value for value in active if value not in COLUMNS]
    if missing or unknown or len(set(active)) != len(active):
        details = []
        if missing:
            details.append("missing headers: " + ", ".join(missing))
        if unknown:
            details.append("unrecognized headers: " + ", ".join(unknown))
        if len(set(active)) != len(active):
            details.append("duplicate column headers")
        raise ValueError("Catalog headers: " + "; ".join(details) + ". Use the template; required columns may be in any order.")
    groups = {}
    count = 0
    for line, values in enumerate(rows[first+1:], first+2):
        if not any(v.strip() for v in values):
            continue
        if len(values) > len(COLUMNS):
            raise ValueError(f"Row {line}: too many columns.")
        item = {key: "" for key in COLUMNS}
        for index, value in enumerate(values):
            key = headers[index] if index < len(headers) else ""
            if value.strip() and not key:
                raise ValueError(f"Row {line}: a value has no column header.")
            if key:
                item[key] = value.strip()
        if any(len(v) > 2000 for v in item.values()):
            raise ValueError(f"Row {line}: keep each cell within 2,000 characters.")
        missing_values = [key for key in ("campaign_type", "product_name", "facts") if not item[key]]
        if missing_values:
            raise ValueError(f"Row {line}: fill " + ", ".join(missing_values) + ".")
        if len(item["campaign_type"]) > 120:
            raise ValueError(f"Row {line}: keep campaign_type within 120 characters; its value is free text.")
        placeholders = [key for key, value in item.items() if value in ("PRODUCT_NAME", "REPLACE_WITH_SUPPORTED_FACTS")]
        if placeholders:
            raise ValueError(f"Row {line}: replace template placeholders in " + ", ".join(placeholders) + " with your product information, or delete the unused row.")
        groups.setdefault(item["campaign_type"], []).append(item)
        count += 1
        if count > 200:
            raise ValueError("Import at most 200 rows per file.")
    if not count:
        raise ValueError("Add at least one catalog row.")
    for kind, items in groups.items():
        if len(json.dumps({"campaign_type": kind, "items": items}, ensure_ascii=False)) > 12000:
            raise ValueError(f"Group {kind} is too large for the current source context. Split it into smaller catalogs; no rows were saved.")
    return {"rows": count, "groups": [{"campaign_type": kind, "items": items} for kind, items in groups.items()]}


def template_csv():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(COLUMNS)
    writer.writerow(["produk_unggulan", "PRODUCT_NAME", "REPLACE_WITH_SUPPORTED_FACTS", "", "", "Instagram", "product.jpg"])
    return output.getvalue().encode("utf-8-sig")


def template_xlsx():
    from xml.sax.saxutils import escape
    output = io.BytesIO()
    rows = [list(COLUMNS)] + [[kind, "PRODUCT_NAME", "REPLACE_WITH_SUPPORTED_FACTS", "", "", "Instagram", "product.jpg"] for kind in TYPES]
    sheet_rows = []
    for number, row in enumerate(rows, 1):
        cells = ''.join(f'<c r="{chr(65+i)}{number}" t="inlineStr"><is><t>{escape(value)}</t></is></c>' for i, value in enumerate(row))
        sheet_rows.append(f'<row r="{number}">{cells}</row>')
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Catalog" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><cols><col min="1" max="7" width="26" customWidth="1"/></cols><sheetData>' + ''.join(sheet_rows) + '</sheetData></worksheet>')
    return output.getvalue()


def image_dimensions(raw, media):
    if media == "image/png":
        width, height = struct.unpack(">II", raw[16:24])
    else:
        position = 2
        width = height = 0
        while position + 4 <= len(raw):
            if raw[position] != 255:
                break
            while position < len(raw) and raw[position] == 255:
                position += 1
            if position >= len(raw):
                break
            marker = raw[position]
            position += 1
            if marker in (0xD9, 0xDA):
                break
            if marker == 0x01 or 0xD0 <= marker <= 0xD8:
                continue
            if position + 2 > len(raw):
                break
            length = int.from_bytes(raw[position:position+2], "big")
            if length < 2 or position + length > len(raw):
                break
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF) and length >= 8:
                height = int.from_bytes(raw[position+3:position+5], "big")
                width = int.from_bytes(raw[position+5:position+7], "big")
                break
            position += length
    if not width or not height or width > 10000 or height > 10000 or width * height > 25_000_000:
        raise ValueError("Use a readable image up to 25 megapixels and 10,000 pixels per side.")
    return width, height
