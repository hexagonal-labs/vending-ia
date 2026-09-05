"""Escritor XLSX pequeño, determinista y sin dependencias de runtime.

La fase 2 no requiere fórmulas ni edición de libros de terceros: todos los
libros son propiedad del bridge y se reconstruyen desde el índice JSON. Esto
permite usar el formato XLSX abierto sin introducir una dependencia adicional.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from tempfile import NamedTemporaryFile
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


@dataclass(frozen=True, slots=True)
class WorkbookSheet:
    name: str
    headers: tuple[str, ...]
    rows: tuple[tuple[object, ...], ...] = ()


def write_workbook(path: Path, sheets: tuple[WorkbookSheet, ...]) -> None:
    if not sheets:
        raise ValueError("Un libro XLSX requiere al menos una hoja")
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        with ZipFile(temporary_path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("[Content_Types].xml", _content_types(len(sheets)))
            archive.writestr("_rels/.rels", _root_relationships())
            archive.writestr("xl/workbook.xml", _workbook_xml(sheets))
            archive.writestr("xl/_rels/workbook.xml.rels", _workbook_relationships(len(sheets)))
            archive.writestr("xl/styles.xml", _styles_xml())
            for position, sheet in enumerate(sheets, start=1):
                archive.writestr(f"xl/worksheets/sheet{position}.xml", _sheet_xml(sheet))
        temporary_path.replace(path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _content_types(sheet_count: int) -> str:
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{number}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for number in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        f"{overrides}</Types>"
    )


def _root_relationships() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        '</Relationships>'
    )


def _workbook_xml(sheets: tuple[WorkbookSheet, ...]) -> str:
    sheet_entries = "".join(
        f'<sheet name="{escape(sheet.name)}" sheetId="{number}" r:id="rId{number}"/>'
        for number, sheet in enumerate(sheets, start=1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheet_entries}</sheets></workbook>"
    )


def _workbook_relationships(sheet_count: int) -> str:
    sheet_relationships = "".join(
        f'<Relationship Id="rId{number}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{number}.xml"/>'
        for number in range(1, sheet_count + 1)
    )
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        f"{sheet_relationships}"
        f'<Relationship Id="rId{sheet_count + 1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        '</Relationships>'
    )


def _styles_xml() -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="2"><numFmt numFmtId="164" formatCode="&quot;€&quot;#,##0.00"/>'
        '<numFmt numFmtId="165" formatCode="yyyy-mm-dd hh:mm"/></numFmts>'
        '<fonts count="2"><font><sz val="11"/><name val="Arial"/></font>'
        '<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="Arial"/></font></fonts>'
        '<fills count="2"><fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FF1F4E78"/>'
        '<bgColor indexed="64"/></patternFill></fill></fills>'
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="4">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="1" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
        '</cellXfs></styleSheet>'
    )


def _sheet_xml(sheet: WorkbookSheet) -> str:
    rows = [sheet.headers, *sheet.rows]
    widths = _column_widths(rows)
    columns = "".join(
        f'<col min="{number}" max="{number}" width="{width}" customWidth="1"/>'
        for number, width in enumerate(widths, start=1)
    )
    row_xml = "".join(_row_xml(row_number, row) for row_number, row in enumerate(rows, start=1))
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" '
        'activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f"<cols>{columns}</cols><sheetData>{row_xml}</sheetData></worksheet>"
    )


def _cell_xml(row: int, column: int, value: object, is_header: bool) -> str:
    reference = f"{_column_name(column)}{row}"
    if value is None:
        return ""
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"><v>{int(value)}</v></c>'
    if isinstance(value, datetime):
        serial = (value.astimezone(UTC) - datetime(1899, 12, 30, tzinfo=UTC)).total_seconds() / 86400
        return f'<c r="{reference}" s="3"><v>{serial:.10f}</v></c>'
    if isinstance(value, Decimal):
        return f'<c r="{reference}" s="2"><v>{value}</v></c>'
    if isinstance(value, (int, float)):
        return f'<c r="{reference}"><v>{value}</v></c>'
    style = ' s="1"' if is_header else ""
    return f'<c r="{reference}" t="inlineStr"{style}><is><t>{escape(str(value))}</t></is></c>'


def _row_xml(row_number: int, row: tuple[object, ...]) -> str:
    cells = "".join(
        _cell_xml(row_number, column, value, row_number == 1) for column, value in enumerate(row, start=1)
    )
    return f'<row r="{row_number}">{cells}</row>'


def _column_widths(rows: list[tuple[object, ...]]) -> list[int]:
    count = max((len(row) for row in rows), default=1)
    widths: list[int] = []
    for index in range(count):
        widest = max(
            (len(str(row[index])) if index < len(row) and row[index] is not None else 0 for row in rows),
            default=0,
        )
        widths.append(min(max(widest, 10) + 2, 42))
    return widths


def _column_name(column: int) -> str:
    name = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        name = chr(65 + remainder) + name
    return name
