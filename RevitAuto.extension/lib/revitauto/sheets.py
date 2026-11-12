# -*- coding: utf-8 -*-
"""Revit-independent CSV validation and sheet numbering (Python 2.7 / 3)."""
from __future__ import unicode_literals

import csv
import io
import sys
import unicodedata
from collections import namedtuple

PY2 = sys.version_info[0] == 2
if PY2:
    from StringIO import StringIO
else:
    from io import StringIO

SheetSpec = namedtuple('SheetSpec', 'number name')


def _text(value):
    return value.decode('utf-8') if isinstance(value, bytes) else value


def validate(sheets, existing_numbers=()):
    """Normalize and validate the whole plan before any Revit transaction."""
    if not sheets:
        raise ValueError('생성할 시트가 없습니다.')
    existing = set(_text(x).strip().lower() for x in existing_numbers)
    seen, result = set(), []
    for item in sheets:
        number, name = (_text(x).strip() for x in item)
        if not number or not name:
            raise ValueError('시트 번호와 이름은 비워 둘 수 없습니다.')
        if any(unicodedata.category(x) == 'Cc' for x in number + name):
            raise ValueError('시트 번호와 이름에 줄바꿈이나 제어 문자를 사용할 수 없습니다.')
        key = number.lower()
        if key in seen:
            raise ValueError('중복 시트 번호: {}'.format(number))
        if key in existing:
            raise ValueError('이미 존재하는 시트 번호: {}'.format(number))
        seen.add(key)
        result.append(SheetSpec(number, name))
    return result


def read_csv_text(text):
    text = _text(text).lstrip('\ufeff')
    stream = StringIO(text.encode('utf-8') if PY2 else text)
    try:
        rows = csv.reader(stream, strict=True)
        header = next(rows, None)
        if header is None or [_text(x).strip().lower() for x in header] != ['number', 'name']:
            raise ValueError('CSV 첫 줄은 Number,Name이어야 합니다.')
        sheets = []
        for row in rows:
            if not row:
                continue
            if len(row) != 2:
                raise ValueError('CSV {}행: 번호와 이름 두 열이 필요합니다.'.format(rows.line_num))
            sheets.append(SheetSpec(*[_text(x) for x in row]))
        return validate(sheets)
    except csv.Error as error:
        raise ValueError('CSV 따옴표와 구분자를 확인하세요: {}'.format(error))
    finally:
        stream.close()


def read_csv_file(path):
    with io.open(path, 'r', encoding='utf-8-sig', newline='') as source:
        return read_csv_text(source.read())


def for_views(names, existing_numbers=()):
    used = set(_text(x).strip().lower() for x in existing_numbers)
    sheets, index = [], 1
    for name in names:
        while 'ra-{:03d}'.format(index) in used:
            index += 1
        number = 'RA-{:03d}'.format(index)
        used.add(number.lower())
        sheets.append(SheetSpec(number, name))
        index += 1
    return validate(sheets)


def _safe_cell(value):
    value = _text(value)
    if value.lstrip().startswith(('=', '+', '-', '@')):
        value = "'" + value
    return value.encode('utf-8') if PY2 else value


def csv_text(sheets):
    stream = StringIO()
    try:
        writer = csv.writer(stream, lineterminator='\r\n')
        writer.writerow([_safe_cell('Number'), _safe_cell('Name')])
        for sheet in sheets:
            writer.writerow([_safe_cell(sheet.number), _safe_cell(sheet.name)])
        return _text(stream.getvalue())
    finally:
        stream.close()


def write_csv_file(path, sheets):
    with io.open(path, 'w', encoding='utf-8-sig', newline='') as target:
        target.write(csv_text(sheets))
