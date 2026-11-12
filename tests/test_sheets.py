# -*- coding: utf-8 -*-
import os
import tempfile
import unittest

from revitauto.sheets import SheetSpec, csv_text, for_views, read_csv_file, read_csv_text, validate, write_csv_file


class SheetTests(unittest.TestCase):
    def test_korean_and_bom(self):
        self.assertEqual(read_csv_text('\ufeffNumber,Name\r\nA101,1층 평면도'), [SheetSpec('A101', '1층 평면도')])

    def test_quoted_comma_and_quote(self):
        self.assertEqual(read_csv_text('Number,Name\nA101,"평면, ""1층"""')[0].name, '평면, "1층"')

    def test_whitespace(self):
        self.assertEqual(read_csv_text('Number,Name\n A101 , 평면 '), [SheetSpec('A101', '평면')])

    def test_header_case(self):
        self.assertEqual(read_csv_text('number,NAME\nA101,평면')[0].number, 'A101')

    def test_blank_rows(self):
        self.assertEqual(len(read_csv_text('Number,Name\n\nA101,평면\n\n')), 1)

    def test_invalid_csv(self):
        for source in ('', '번호,이름\nA101,평면', 'Number,Name\n', 'Number,Name\nA101',
                       'Number,Name\nA101,평면,extra', 'Number,Name\n,평면', 'Number,Name\nA101, ',
                       'Number,Name\nA101,"평면', 'Number,Name\nA101,"평면"extra',
                       'Number,Name\nA101,"평면\n입면"'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                read_csv_text(source)

    def test_duplicate_case(self):
        with self.assertRaises(ValueError):
            read_csv_text('Number,Name\nA101,평면\na101,입면')

    def test_existing_collision(self):
        with self.assertRaises(ValueError):
            validate([SheetSpec('A101', '평면')], [' a101 '])

    def test_control_characters(self):
        with self.assertRaises(ValueError):
            validate([SheetSpec('A101', '평면\t입면')])

    def test_no_views(self):
        with self.assertRaises(ValueError):
            for_views([])

    def test_skip_used_numbers(self):
        self.assertEqual([x.number for x in for_views(['평면', '입면'], ['RA-001', 'ra-003'])], ['RA-002', 'RA-004'])

    def test_many_views(self):
        plan = for_views(['평면'] * 1001)
        self.assertEqual(plan[-1].number, 'RA-1001')
        self.assertEqual(len(set(x.number for x in plan)), 1001)

    def test_csv_round_trip(self):
        sheets = [SheetSpec('A101', '1층 평면'), SheetSpec('A102', '입면, "남측"')]
        self.assertEqual(read_csv_text(csv_text(sheets)), sheets)

    def test_formula_protection(self):
        for value in ('=1+1', '+1', '-1', '@SUM(1)', ' =1'):
            result = read_csv_text(csv_text([SheetSpec(value, value)]))[0]
            self.assertTrue(result.number.startswith("'"))
            self.assertTrue(result.name.startswith("'"))

    def test_utf8_file_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, '시트.csv')
            sheets = [SheetSpec('A101', '한글 평면')]
            write_csv_file(path, sheets)
            with open(path, 'rb') as source:
                self.assertEqual(source.read(3), b'\xef\xbb\xbf')
            self.assertEqual(read_csv_file(path), sheets)

    def test_sample(self):
        root = os.path.dirname(os.path.dirname(__file__))
        self.assertEqual(len(read_csv_file(os.path.join(root, 'samples', 'house-sheets.csv'))), 5)


if __name__ == '__main__':
    unittest.main()
