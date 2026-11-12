# -*- coding: utf-8 -*-
"""Regression tests shared by CPython 3 and pyRevit's actual IronPython 2.7 engine."""
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

from revitauto.sheets import SheetSpec, _text, csv_text, for_views, read_csv_text, read_csv_file, write_csv_file


class UnicodeRuntimeTests(unittest.TestCase):
    def test_korean_import_preserves_codepoints(self):
        plan = read_csv_text('Number,Name\r\nA101,1층 평면도\r\nA102,남측 입면도')
        self.assertEqual(plan, [SheetSpec('A101', '1층 평면도'), SheetSpec('A102', '남측 입면도')])

    def test_export_preserves_codepoints(self):
        self.assertEqual(csv_text([SheetSpec('A101', '1층 평면도')]), 'Number,Name\r\nA101,1층 평면도\r\n')

    def test_quoted_korean_round_trip(self):
        sheets = [SheetSpec('A101', '남측, "입면도"')]
        self.assertEqual(read_csv_text(csv_text(sheets)), sheets)

    def test_utf8_bom_round_trip(self):
        directory = tempfile.mkdtemp()
        try:
            path = os.path.join(directory, '한글 시트.csv')
            sheets = [SheetSpec('A101', '1층 평면도')]
            write_csv_file(path, sheets)
            with open(path, 'rb') as source:
                self.assertEqual(source.read(), b'\xef\xbb\xbf' + csv_text(sheets).encode('utf-8'))
            self.assertEqual(read_csv_file(path), sheets)
        finally:
            shutil.rmtree(directory)

    def test_default_3d_name_becomes_valid_sheet_name(self):
        self.assertEqual(for_views(['{3D}'])[0].name, '3D')

    def test_prohibited_characters_removed_from_new_sheet(self):
        self.assertEqual(for_views(['[1층]: 평면도?'])[0].name, '1층 평면도')

    def test_regular_korean_view_name_is_unchanged(self):
        self.assertEqual(for_views(['1층 평면도'])[0].name, '1층 평면도')

    def test_empty_cleaned_name_has_fallback(self):
        self.assertEqual(for_views(['{}[]'])[0].name, 'View')

    def test_dotnet_char_and_string(self):
        try:
            import System
        except ImportError:
            self.skipTest('CLR string/char test runs under IronPython')
        self.assertEqual(_text(System.Char.Parse('층')), '층')
        value = System.String.Concat('1층', ' 평면도')
        self.assertEqual(for_views([value])[0].name, '1층 평면도')


if __name__ == '__main__':
    unittest.main()
