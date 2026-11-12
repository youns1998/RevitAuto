# -*- coding: utf-8 -*-
"""Revit-independent sheet tools for IronPython 2.7 and CPython 3."""
from __future__ import unicode_literals

import csv
import io
import unicodedata
from collections import namedtuple

try:
    text_type = unicode
except NameError:
    text_type = str

SheetSpec = namedtuple('SheetSpec', 'number name')


def _text(value):
    if isinstance(value, bytes):
        return value.decode('utf-8')
    # Normalize CLR System.String/Char at the boundary as well as Python strings.
    return text_type(value)


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
        if any(unicodedata.category(_text(x)) == 'Cc' for x in number + name):
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
    # IronPython's csv module accepts Unicode. Encoding it here produces
    # mojibake (and C1 control characters) when its reader yields strings.
    stream = io.StringIO(text)
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


def sheet_name_for_view(name):
    """Keep the source view intact; remove prohibited characters from the new sheet name."""
    prohibited = '\\:{}[]|;<>?`~'
    cleaned = ''.join(' ' if x in prohibited else x for x in _text(name))
    return ' '.join(cleaned.split()) or 'View'


def for_views(names, existing_numbers=()):
    used = set(_text(x).strip().lower() for x in existing_numbers)
    sheets, index = [], 1
    for name in names:
        while 'ra-{:03d}'.format(index) in used:
            index += 1
        number = 'RA-{:03d}'.format(index)
        used.add(number.lower())
        sheets.append(SheetSpec(number, sheet_name_for_view(name)))
        index += 1
    return validate(sheets)


def _safe_cell(value):
    value = _text(value)
    if value.lstrip().startswith(('=', '+', '-', '@')):
        value = "'" + value
    return value


def csv_text(sheets):
    stream = io.StringIO()
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
