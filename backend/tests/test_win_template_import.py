import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from xml.sax.saxutils import escape
from zipfile import ZipFile, ZIP_DEFLATED

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.routes.ai import router
from app.core.config import settings


def make_xlsx(rows):
    """Minimal OOXML fixture, with inline strings and no external dependencies."""
    stream = io.BytesIO()
    with ZipFile(stream, "w", ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Content win" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        body = ''.join(f'<row r="{i}">' + ''.join(f'<c r="{chr(65+j)}{i}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>' for j, value in enumerate(row)) + '</row>' for i, row in enumerate(rows, 1))
        archive.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' + f'<dimension ref="A1:F{len(rows)}"/><sheetData>{body}</sheetData></worksheet>')
    return stream.getvalue()


class WinFileImportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        store = patch.object(settings, "WIN_TEMPLATE_STORE_PATH", str(Path(temp.name) / "win.db"))
        store.start()
        self.addCleanup(store.stop)
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.rows = [["Tên mẫu", "Tiêu đề 2", "Tiêu đề 1", "Mô tả 1", "Ghi chú"], ["Mẫu A", "Khám Phá Ngay", "Làm Việc Hiệu Quả", "Quản lý công việc dễ dàng. Khám phá ngay.", "Lợi ích + CTA"], ["Mẫu B", "Xem Tính Năng", "Tối Ưu Công Việc", "Khám phá tính năng cho nhóm của bạn.", "CTA ngắn"]]

    def preview(self, content, filename):
        return self.client.post("/win-templates/preview", files={"file": (filename, content)})

    def test_csv_utf16_preamble_semicolon_and_numbered_order(self):
        text = io.StringIO()
        writer = csv.writer(text, delimiter=";")
        writer.writerow(["Ads report"])
        writer.writerows(self.rows)
        result = self.preview(text.getvalue().encode("utf-16"), "report.csv")
        self.assertEqual(200, result.status_code, result.text)
        drafts = result.json()["drafts"]
        self.assertEqual(2, len(drafts))
        self.assertEqual(["Làm Việc Hiệu Quả", "Khám Phá Ngay"], drafts[0]["headlines"])
        self.assertEqual([], self.client.get("/win-templates").json()["templates"])

    def test_xlsx_preview_then_atomic_save_and_reload(self):
        result = self.preview(make_xlsx(self.rows), "report.xlsx")
        self.assertEqual(200, result.status_code, result.text)
        drafts = result.json()["drafts"]
        payload = [{key: row[key] for key in ("name", "notes", "headlines", "descriptions")} for row in drafts]
        invalid = [{**payload[0], "headlines": ["x" * 31]}, payload[1]]
        self.assertEqual(422, self.client.post("/win-templates/batch", json=invalid).status_code)
        self.assertEqual([], self.client.get("/win-templates").json()["templates"])
        saved = self.client.post("/win-templates/batch", json=payload)
        self.assertEqual(201, saved.status_code, saved.text)
        self.assertEqual(2, len(self.client.get("/win-templates").json()["templates"]))

    def test_invalid_assets_stay_visible_for_correction(self):
        content = 'name,Headlines,Descriptions\nBad,"Duplicate\nDuplicate",' + 'x' * 91
        result = self.preview(content.encode(), "bad.csv")
        self.assertEqual(200, result.status_code)
        self.assertGreater(len(result.json()["drafts"][0]["issues"]), 0)
        self.assertEqual('x' * 91, result.json()["drafts"][0]["descriptions"][0])

    def test_malformed_oversized_and_excess_rows_are_rejected(self):
        for filename, content, code in [("bad.xlsx", b"not a zip", 422), ("bad.xls", b"old format", 422), ("empty.csv", b"name,cost\na,1", 422), ("big.csv", b"x" * (5 * 1024 * 1024 + 1), 413), ("many.csv", b"Headline 1,Description 1\n" + b"Title,Description\n" * 51, 422)]:
            with self.subTest(filename=filename):
                self.assertEqual(code, self.preview(content, filename).status_code)

    def test_formula_is_not_saved_as_copy(self):
        result = self.preview(b'Headline 1,Description 1\n=1+1,Example', "formula.csv")
        draft = result.json()["drafts"][0]
        self.assertTrue(draft["issues"])
        payload = {key: draft[key] for key in ("name", "notes", "headlines", "descriptions")}
        self.assertEqual(422, self.client.post("/win-templates/batch", json=[payload]).status_code)
