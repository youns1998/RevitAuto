# -*- coding: utf-8 -*-
"""Portable package regressions, also executed under IronPython."""
from __future__ import unicode_literals

import csv
import io
import json
import os
import shutil
import tempfile
import unittest
import zipfile

from revitauto.reports import TABLES, new_snapshot, table_bytes, write_bundle


def read_member(archive, name):
    # Python 2 ZipFile.read relies on refcounting to close ZipExtFile; IronPython does not.
    with archive.open(name) as source:
        return source.read()


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.path = os.path.join(self.directory, '한글 상세정보.zip')

    def tearDown(self):
        shutil.rmtree(self.directory)

    def sample(self):
        result = new_snapshot('한글 프로젝트')
        result['sheets'].append({'key': 'host:1', 'number': 'A101', 'name': '1층 평면도', 'view_count': 1})
        result['views'].append({'key': 'host:2', 'name': '평면, "1층"', 'scale': 50})
        result['placements'].append({'sheet_key': 'host:1', 'view_key': 'host:2', 'kind': 'viewport'})
        result['elements'].append({'key': 'host:3', 'name': '외벽', 'type_key': 'host:4'})
        result['view_elements'].append({'view_key': 'host:2', 'element_key': 'host:3', 'source': 'host_view_candidates'})
        result['parameters'].append({'object_key': 'host:3', 'name': '면적', 'raw': 123.5, 'display': '11.47 m²'})
        return result

    def test_csv_quotes_bom_and_formula_protection(self):
        encoded = table_bytes([{'name': '=1+1', 'text': '입면, "남측"', 'value': {'이름': '한글'}}], ['name', 'text', 'value'])
        self.assertTrue(encoded.startswith(b'\xef\xbb\xbf'))
        rows = list(csv.reader(io.StringIO(encoded.decode('utf-8-sig'))))
        self.assertEqual(rows[1][0], "'=1+1")
        self.assertEqual(rows[1][1], '입면, "남측"')
        self.assertEqual(json.loads(rows[1][2]), {'이름': '한글'})

    def test_package_schema_and_relationships(self):
        manifest = write_bundle(self.path, self.sample())
        self.assertEqual(manifest['counts']['sheets'], 1)
        with zipfile.ZipFile(self.path) as archive:
            self.assertEqual(set(archive.namelist()), set([name + '.csv' for name, unused in TABLES] + ['snapshot.json', 'manifest.json']))
            snapshot = json.loads(read_member(archive, 'snapshot.json').decode('utf-8'))
            self.assertEqual(snapshot['parameters'][0]['display'], '11.47 m²')
            self.assertEqual(snapshot['placements'][0]['view_key'], snapshot['views'][0]['key'])
            self.assertEqual(snapshot['view_elements'][0]['element_key'], snapshot['elements'][0]['key'])
            self.assertTrue(read_member(archive, 'sheets.csv').startswith(b'\xef\xbb\xbf'))

    def test_optional_pdf_and_issues_are_kept(self):
        pdf = os.path.join(self.directory, 'sheets.pdf')
        with open(pdf, 'wb') as target:
            target.write(b'%PDF-1.7\nfixture')
        snapshot = self.sample()
        snapshot['issues'].append({'scope': 'link', 'entity': 'link:1', 'field': 'document', 'message': '연결 모델 없음'})
        manifest = write_bundle(self.path, snapshot, pdf, 'included')
        self.assertEqual(manifest['counts']['issues'], 1)
        with zipfile.ZipFile(self.path) as archive:
            self.assertTrue(read_member(archive, 'sheets.pdf').startswith(b'%PDF-'))
            self.assertEqual(json.loads(read_member(archive, 'manifest.json').decode('utf-8'))['pdf'], 'included')

    def test_failed_package_preserves_existing_file(self):
        with open(self.path, 'wb') as target:
            target.write(b'previous output')
        broken = self.sample()
        broken['elements'][0]['bad_number'] = float('nan')
        with self.assertRaises(ValueError):
            write_bundle(self.path, broken)
        with open(self.path, 'rb') as source:
            self.assertEqual(source.read(), b'previous output')
        self.assertEqual(os.listdir(self.directory), [os.path.basename(self.path)])

    def test_successful_overwrite(self):
        write_bundle(self.path, self.sample())
        updated = self.sample()
        updated['sheets'][0]['name'] = '변경된 이름'
        write_bundle(self.path, updated)
        with zipfile.ZipFile(self.path) as archive:
            self.assertEqual(json.loads(read_member(archive, 'snapshot.json').decode('utf-8'))['sheets'][0]['name'], '변경된 이름')


if __name__ == '__main__':
    unittest.main()
