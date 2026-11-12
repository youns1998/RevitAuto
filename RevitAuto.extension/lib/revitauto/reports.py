# -*- coding: utf-8 -*-
"""Portable UTF-8 CSV/JSON ZIP packaging. No Revit API calls."""
from __future__ import unicode_literals

import csv
import datetime
import io
import json
import os
import tempfile
import zipfile

from revitauto.sheets import _safe_cell, _text


class ExportCancelled(Exception):
    pass


TABLES = [
    ('documents', ['key', 'title', 'path', 'is_linked', 'link_instance_id', 'transform', 'units', 'project_information_key']),
    ('sheets', ['key', 'id', 'number', 'name', 'placeholder', 'view_count', 'titleblocks', 'revision_numbers']),
    ('views', ['key', 'id', 'name', 'view_type', 'scale', 'level', 'template', 'crop_active', 'crop_visible', 'crop_box']),
    ('placements', ['sheet_key', 'view_key', 'kind', 'id', 'detail_number', 'center', 'outline', 'rotation']),
    ('elements', ['key', 'document_key', 'id', 'unique_id', 'name', 'class', 'category', 'family', 'type_name', 'type_key',
                  'level', 'owner_view_id', 'is_annotation', 'bounding_box', 'location', 'text', 'dimension', 'material_keys']),
    ('types', ['key', 'document_key', 'id', 'name', 'class', 'category', 'family']),
    ('materials', ['key', 'document_key', 'id', 'name', 'color', 'transparency', 'shininess', 'smoothness']),
    ('view_elements', ['view_key', 'element_key', 'source']),
    ('parameters', ['object_key', 'id', 'name', 'storage_type', 'raw', 'display', 'spec_id', 'unit_id',
                    'read_only', 'shared', 'guid', 'referenced_element_key']),
    ('revisions', ['sheet_key', 'id', 'number', 'sequence', 'description', 'date', 'issued', 'issued_to', 'issued_by']),
    ('schedule_cells', ['view_key', 'section', 'row', 'column', 'text']),
    ('issues', ['scope', 'entity', 'field', 'message']),
]


def new_snapshot(project_title):
    snapshot = dict((name, []) for name, unused in TABLES)
    snapshot['project_title'] = _text(project_title)
    return snapshot


def _cell(value):
    if value is None:
        return ''
    if isinstance(value, (dict, list, tuple)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    return _safe_cell(_text(value))


def table_bytes(rows, columns):
    output = io.StringIO()
    try:
        writer = csv.writer(output, lineterminator='\r\n')
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(row.get(column)) for column in columns])
        return b'\xef\xbb\xbf' + output.getvalue().encode('utf-8')
    finally:
        output.close()


def write_bundle(path, snapshot, pdf_path=None, pdf_status='not_requested'):
    """Publish only a complete ZIP; preserve an existing output on packing errors."""
    path = os.path.abspath(path)
    handle, temporary = tempfile.mkstemp(prefix='.revitauto-', suffix='.zip', dir=os.path.dirname(path))
    os.close(handle)
    try:
        manifest = {
            'schema_version': 1,
            'created_utc': datetime.datetime.utcnow().isoformat() + 'Z',
            'application': snapshot.get('application'),
            'project_title': snapshot['project_title'],
            'counts': dict((name, len(snapshot[name])) for name, unused in TABLES),
            'pdf': pdf_status,
            'units': 'Revit internal units for raw numeric API values; parameter display/unit_id preserve document units',
            'scope': 'Selected sheets, their placed views, sheet/view collector candidates, readable instance/type parameters and direct loaded links',
            'visibility': 'View collectors return candidates; occluded or outside-crop elements may be included',
            'limitations': 'Not an RVT backup. No full solid/mesh geometry, external file bytes, nested-link traversal or rendered material assets. Read issues.csv for unreadable fields.',
        }
        with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'))
            archive.writestr('snapshot.json', json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8'))
            for name, columns in TABLES:
                archive.writestr(name + '.csv', table_bytes(snapshot[name], columns))
            if pdf_path is not None:
                archive.write(pdf_path, 'sheets.pdf')
        if hasattr(os, 'replace'):
            os.replace(temporary, path)
        elif os.path.exists(path):
            from System.IO import File
            File.Replace(temporary, path, None)
        else:
            os.rename(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.remove(temporary)
    return manifest
