import csv
from io import StringIO, BytesIO
from openpyxl import Workbook

def export_csv(rows: list[dict]) -> bytes:
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=["art_nr", "name", "beschreibung"])
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return buf.getvalue().encode("utf-8")

def export_xlsx(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "export"
    ws.append(["art_nr", "name", "beschreibung"])
    for r in rows:
        ws.append([r["art_nr"], r["name"], r["beschreibung"]])
    out = BytesIO()
    wb.save(out)
    return out.getvalue()