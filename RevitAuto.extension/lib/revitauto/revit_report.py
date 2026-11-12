# -*- coding: utf-8 -*-
"""Read-only Revit snapshot adapter. Does not start transactions or change a model."""
from __future__ import unicode_literals

import math
from pyrevit import DB
from revitauto.reports import ExportCancelled, new_snapshot
from revitauto.sheets import _text


def element_id(value):
    if value is None:
        return None
    return int(value.Value if hasattr(value, 'Value') else value)


def point(value):
    return {'x': float(value.X), 'y': float(value.Y), 'z': float(value.Z)}


def transform(value):
    return dict((name, point(getattr(value, name))) for name in ('Origin', 'BasisX', 'BasisY', 'BasisZ'))


def box(value):
    if value is None:
        return None
    return {'min': point(value.Min), 'max': point(value.Max), 'transform': transform(value.Transform)}


class SnapshotCollector(object):
    def __init__(self, doc, progress=None):
        self.doc = doc
        self.data = new_snapshot(doc.Title)
        self.data['application'] = {'version': _text(doc.Application.VersionNumber), 'build': _text(doc.Application.VersionBuild)}
        self.progress = progress
        self.documents = {}
        self.seen_elements, self.seen_types, self.seen_materials = set(), set(), set()
        self.seen_views, self.seen_memberships = set(), set()
        self.done, self.total, self.steps = 0, 1, 0

    def issue(self, scope, entity, field, error):
        self.data['issues'].append({'scope': scope, 'entity': _text(entity), 'field': field, 'message': _text(error)})

    def read(self, scope, entity, field, operation, default=None):
        try:
            return operation()
        except Exception as error:
            self.issue(scope, entity, field, error)
            return default

    def checkpoint(self, force=False):
        self.steps += 1
        if self.progress and (force or self.steps % 100 == 0):
            if self.progress(self.done, self.total) is False:
                raise ExportCancelled()

    def name(self, element):
        try:
            return _text(element.Name)
        except Exception:
            return self.read('element', element_id(element.Id), 'name', lambda: _text(DB.Element.Name.GetValue(element)), '')

    def key(self, context, value):
        identifier = element_id(value)
        return '{}:{}'.format(context, identifier) if identifier is not None and identifier >= 0 else None

    def reference(self, doc, identifier):
        if identifier is None or element_id(identifier) < 0:
            return None
        item = doc.GetElement(identifier)
        return {'id': element_id(identifier), 'name': self.name(item)} if item else {'id': element_id(identifier)}

    def collect(self, doc, context, view_id=None, element_class=None):
        entity = element_id(view_id) if view_id is not None else context
        collector = None
        try:
            collector = DB.FilteredElementCollector(doc, view_id) if view_id is not None else DB.FilteredElementCollector(doc)
            if element_class is not None:
                collector = collector.OfClass(element_class)
            return list(collector.WhereElementIsNotElementType())
        except Exception as error:
            self.issue('collector', entity, 'elements', error)
            return []
        finally:
            if collector is not None:
                collector.Dispose()

    def register_document(self, doc, context, link=None):
        if context in self.documents:
            return
        record = {'key': context, 'title': _text(doc.Title), 'path': _text(doc.PathName), 'is_linked': link is not None,
                  'link_instance_id': element_id(link.Id) if link else None,
                  'transform': self.read('document', context, 'transform', lambda: transform(link.GetTotalTransform())) if link else None,
                  'units': {}}
        self.documents[context] = record
        self.data['documents'].append(record)
        units = self.read('document', context, 'units', lambda: doc.GetUnits())
        if units:
            for label in ('Length', 'Area', 'Volume', 'Angle'):
                def unit_info(label=label):
                    options = units.GetFormatOptions(getattr(DB.SpecTypeId, label))
                    return {'unit_id': _text(options.GetUnitTypeId().TypeId), 'accuracy': float(options.Accuracy)}
                record['units'][label] = self.read('document', context, label, unit_info)
        information = self.read('document', context, 'project_information', lambda: doc.ProjectInformation)
        if information:
            record['project_information_key'] = self.add_element(doc, information, context)

    def parameters(self, doc, element, context, key):
        values = self.read('parameters', key, 'enumeration', lambda: list(element.Parameters), [])
        for parameter in values:
            self.checkpoint()
            record = {'object_key': key, 'id': self.read('parameter', key, 'id', lambda: element_id(parameter.Id)),
                      'name': '', 'raw': None, 'display': None, 'referenced_element_key': None}
            parameter_key = '{}:{}'.format(key, record['id'])
            record['name'] = self.read('parameter', parameter_key, 'name', lambda: _text(parameter.Definition.Name), '')
            storage = self.read('parameter', parameter_key, 'storage_type', lambda: _text(parameter.StorageType), 'None')
            record['storage_type'] = storage
            record['read_only'] = self.read('parameter', parameter_key, 'read_only', lambda: bool(parameter.IsReadOnly))
            record['shared'] = self.read('parameter', parameter_key, 'shared', lambda: bool(parameter.IsShared))
            record['spec_id'] = self.read('parameter', parameter_key, 'spec_id', lambda: _text(parameter.Definition.GetDataType().TypeId))
            if record['shared']:
                record['guid'] = self.read('parameter', parameter_key, 'guid', lambda: _text(parameter.GUID))
            has_value = self.read('parameter', parameter_key, 'has_value', lambda: bool(parameter.HasValue), False)
            if has_value:
                def raw_value():
                    if storage == 'String':
                        value = parameter.AsString()
                        return _text(value) if value is not None else None
                    if storage == 'Integer':
                        return int(parameter.AsInteger())
                    if storage == 'Double':
                        value = float(parameter.AsDouble())
                        if math.isnan(value) or math.isinf(value):
                            raise ValueError('Non-finite numeric parameter')
                        return value
                    if storage == 'ElementId':
                        return element_id(parameter.AsElementId())
                    return None
                record['raw'] = self.read('parameter', parameter_key, 'raw', raw_value)
                record['display'] = self.read('parameter', parameter_key, 'display', lambda: parameter.AsValueString())
                if record['display'] is not None:
                    record['display'] = _text(record['display'])
                elif storage == 'String':
                    record['display'] = record['raw']
                if storage == 'Double':
                    # Unitless doubles can legitimately have no unit type.
                    try:
                        record['unit_id'] = _text(parameter.GetUnitTypeId().TypeId)
                    except Exception:
                        record['unit_id'] = None
                if storage == 'ElementId' and record['raw'] is not None and record['raw'] >= 0:
                    record['referenced_element_key'] = '{}:{}'.format(context, record['raw'])
            self.data['parameters'].append(record)

    def add_type(self, doc, identifier, context):
        key = self.key(context, identifier)
        if key is None or key in self.seen_types:
            return key
        element = doc.GetElement(identifier)
        if not element:
            return None
        self.seen_types.add(key)
        record = {'key': key, 'document_key': context, 'id': element_id(identifier), 'name': self.name(element),
                  'class': _text(element.GetType().Name),
                  'category': self.name(element.Category) if element.Category else None,
                  'family': self.read('type', key, 'family', lambda: _text(element.FamilyName)) if isinstance(element, DB.ElementType) else None}
        self.data['types'].append(record)
        self.parameters(doc, element, context, key)
        return key

    def add_material(self, doc, identifier, context):
        key = self.key(context, identifier)
        if key is None or key in self.seen_materials:
            return key
        material = doc.GetElement(identifier)
        if not material:
            return None
        self.seen_materials.add(key)
        record = {'key': key, 'document_key': context, 'id': element_id(identifier), 'name': self.name(material)}
        record['color'] = self.read('material', key, 'color', lambda: {
            'r': int(material.Color.Red), 'g': int(material.Color.Green), 'b': int(material.Color.Blue)})
        for field, attribute in [('transparency', 'Transparency'), ('shininess', 'Shininess'), ('smoothness', 'Smoothness')]:
            record[field] = self.read('material', key, field, lambda attribute=attribute: int(getattr(material, attribute)))
        self.data['materials'].append(record)
        self.parameters(doc, material, context, key)
        return key

    def add_element(self, doc, element, context):
        key = self.key(context, element.Id)
        if key in self.seen_elements:
            return key
        self.seen_elements.add(key)
        self.checkpoint()
        identifier = element_id(element.Id)
        type_id = self.read('element', key, 'type_id', lambda: element.GetTypeId())
        type_key = self.add_type(doc, type_id, context)
        type_element = doc.GetElement(type_id) if type_key else None
        record = {'key': key, 'document_key': context, 'id': identifier, 'unique_id': _text(element.UniqueId),
                  'name': self.name(element), 'class': _text(element.GetType().Name),
                  'category': self.name(element.Category) if element.Category else None,
                  'type_key': type_key, 'type_name': self.name(type_element) if type_element else None,
                  'family': self.read('element', key, 'family', lambda: _text(type_element.FamilyName)) if type_element else None,
                  'owner_view_id': self.read('element', key, 'owner_view', lambda: element_id(element.OwnerViewId)),
                  'level': self.read('element', key, 'level', lambda: self.reference(doc, element.LevelId)),
                  'bounding_box': self.read('element', key, 'bounding_box', lambda: box(element.get_BoundingBox(None))),
                  'is_annotation': bool(element.Category and element.Category.CategoryType == DB.CategoryType.Annotation)}
        location = self.read('element', key, 'location', lambda: element.Location)
        if isinstance(location, DB.LocationPoint):
            record['location'] = self.read('element', key, 'location_point', lambda: {'point': point(location.Point), 'rotation': float(location.Rotation)})
        elif isinstance(location, DB.LocationCurve):
            record['location'] = self.read('element', key, 'location_curve', lambda: {
                'start': point(location.Curve.GetEndPoint(0)), 'end': point(location.Curve.GetEndPoint(1)), 'length': float(location.Curve.Length)})
        if isinstance(element, DB.TextNote):
            record['text'] = self.read('annotation', key, 'text', lambda: _text(element.Text))
        elif isinstance(element, DB.IndependentTag):
            record['text'] = self.read('annotation', key, 'tag_text', lambda: _text(element.TagText))
        elif isinstance(element, DB.Dimension):
            def dimension_data():
                segments = list(element.Segments) if element.NumberOfSegments else [element]
                return [{'value': float(x.Value) if x.Value is not None else None, 'text': x.ValueString,
                         'override': x.ValueOverride, 'prefix': x.Prefix, 'suffix': x.Suffix} for x in segments]
            record['dimension'] = self.read('annotation', key, 'dimension', dimension_data)
        record['material_keys'] = []
        for paint in (False, True):
            identifiers = self.read('element', key, 'paint_materials' if paint else 'materials', lambda paint=paint: list(element.GetMaterialIds(paint)), [])
            for material_id in identifiers:
                material_key = self.add_material(doc, material_id, context)
                if material_key and material_key not in record['material_keys']:
                    record['material_keys'].append(material_key)
        self.data['elements'].append(record)
        self.parameters(doc, element, context, key)
        return key

    def members(self, doc, view, context, source, elements=None):
        elements = self.collect(doc, context, view.Id) if elements is None else elements
        for element in elements:
            key = self.add_element(doc, element, context)
            membership = (self.key('host', view.Id), key)
            if membership not in self.seen_memberships:
                self.seen_memberships.add(membership)
                self.data['view_elements'].append({'view_key': membership[0], 'element_key': key, 'source': source})
        return elements

    def add_view(self, view):
        key = self.key('host', view.Id)
        if key in self.seen_views:
            return key
        self.seen_views.add(key)
        record = {'key': key, 'id': element_id(view.Id), 'name': self.name(view), 'view_type': _text(view.ViewType),
                  'scale': self.read('view', key, 'scale', lambda: int(view.Scale)),
                  'level': self.read('view', key, 'level', lambda: self.reference(self.doc, view.GenLevel.Id) if view.GenLevel else None),
                  'template': self.read('view', key, 'template', lambda: self.reference(self.doc, view.ViewTemplateId)),
                  'crop_active': self.read('view', key, 'crop_active', lambda: bool(view.CropBoxActive)),
                  'crop_visible': self.read('view', key, 'crop_visible', lambda: bool(view.CropBoxVisible)),
                  'crop_box': self.read('view', key, 'crop_box', lambda: box(view.CropBox))}
        self.data['views'].append(record)
        self.add_element(self.doc, view, 'host')
        template = self.doc.GetElement(view.ViewTemplateId)
        if template:
            self.add_element(self.doc, template, 'host')
        level = self.read('view', key, 'associated_level', lambda: view.GenLevel)
        if level:
            self.add_element(self.doc, level, 'host')
        if isinstance(view, DB.ViewSchedule):
            self.schedule_cells(view, key)
        elements = self.members(self.doc, view, 'host', 'host_view_candidates')
        for link in (x for x in elements if isinstance(x, DB.RevitLinkInstance)):
            linked_doc = self.read('link', element_id(link.Id), 'document', lambda: link.GetLinkDocument())
            if linked_doc is None:
                self.issue('link', element_id(link.Id), 'document', 'Link is unloaded or unavailable')
                continue
            context = 'link:{}'.format(element_id(link.Id))
            self.register_document(linked_doc, context, link)
            collector = None
            try:
                collector = DB.FilteredElementCollector(self.doc, view.Id, link.Id).WhereElementIsNotElementType()
                linked_elements = list(collector)
                self.members(linked_doc, view, context, 'direct_link_view_candidates', linked_elements)
            except ExportCancelled:
                raise
            except Exception as error:
                self.issue('link', element_id(link.Id), 'view_elements', error)
            finally:
                if collector is not None:
                    collector.Dispose()
        return key

    def schedule_cells(self, view, key):
        table = self.read('schedule', key, 'table', lambda: view.GetTableData())
        if table is None:
            return
        for section_name in ('Header', 'Body'):
            section = getattr(DB.SectionType, section_name)
            data = self.read('schedule', key, section_name, lambda: table.GetSectionData(section))
            if data is None:
                continue
            for row in range(data.FirstRowNumber, data.LastRowNumber + 1):
                self.checkpoint()
                for column in range(data.FirstColumnNumber, data.LastColumnNumber + 1):
                    text = self.read('schedule', key, 'cell:{}:{}'.format(row, column), lambda: _text(view.GetCellText(section, row, column)))
                    self.data['schedule_cells'].append({'view_key': key, 'section': section_name, 'row': row, 'column': column, 'text': text})

    def snapshot(self, sheets):
        self.total = max(1, len(sheets))
        self.register_document(self.doc, 'host')
        schedules = self.collect(self.doc, 'host', element_class=DB.ScheduleSheetInstance)
        schedules_by_sheet = {}
        for instance in schedules:
            schedules_by_sheet.setdefault(element_id(instance.OwnerViewId), []).append(instance)
        for index, sheet in enumerate(sheets):
            self.done = index
            self.checkpoint(True)
            sheet_key = self.add_element(self.doc, sheet, 'host')
            placeholder = bool(sheet.IsPlaceholder)
            record = {'key': sheet_key, 'id': element_id(sheet.Id), 'number': _text(sheet.SheetNumber),
                      'name': self.name(sheet), 'placeholder': placeholder, 'titleblocks': [], 'revision_numbers': []}
            self.data['sheets'].append(record)
            view_ids = self.read('sheet', sheet_key, 'placed_views', lambda: list(sheet.GetAllPlacedViews()), [])
            if not placeholder:
                candidates = self.members(self.doc, sheet, 'host', 'sheet_candidates')
                for element in candidates:
                    if element.Category and element_id(element.Category.Id) == int(DB.BuiltInCategory.OST_TitleBlocks):
                        record['titleblocks'].append({'key': self.key('host', element.Id), 'name': self.name(element)})
                viewport_ids = self.read('sheet', sheet_key, 'viewports', lambda: list(sheet.GetAllViewports()), [])
                for identifier in viewport_ids:
                    viewport = self.doc.GetElement(identifier)
                    view_ids.append(viewport.ViewId)
                    self.data['placements'].append({
                        'sheet_key': sheet_key, 'view_key': self.key('host', viewport.ViewId), 'kind': 'viewport', 'id': element_id(identifier),
                        'detail_number': self.read('placement', element_id(identifier), 'detail_number', lambda: viewport.get_Parameter(DB.BuiltInParameter.VIEWPORT_DETAIL_NUMBER).AsString()),
                        'center': self.read('placement', element_id(identifier), 'center', lambda: point(viewport.GetBoxCenter())),
                        'outline': self.read('placement', element_id(identifier), 'outline', lambda: {'min': point(viewport.GetBoxOutline().MinimumPoint), 'max': point(viewport.GetBoxOutline().MaximumPoint)}),
                        'rotation': _text(viewport.Rotation)})
                for instance in schedules_by_sheet.get(element_id(sheet.Id), []):
                    view_ids.append(instance.ScheduleId)
                    self.data['placements'].append({'sheet_key': sheet_key, 'view_key': self.key('host', instance.ScheduleId),
                        'kind': 'schedule', 'id': element_id(instance.Id),
                        'center': self.read('placement', element_id(instance.Id), 'point', lambda: point(instance.Point))})
            unique_ids = dict((element_id(identifier), identifier) for identifier in view_ids)
            record['view_count'] = len(unique_ids)
            for identifier in unique_ids.values():
                view = self.doc.GetElement(identifier)
                if view is not None:
                    self.add_view(view)
            revision_ids = self.read('sheet', sheet_key, 'revisions', lambda: list(sheet.GetAllRevisionIds()), [])
            for identifier in revision_ids:
                revision = self.doc.GetElement(identifier)
                number = self.read('revision', element_id(identifier), 'number', lambda: _text(sheet.GetRevisionNumberOnSheet(identifier)))
                record['revision_numbers'].append(number)
                item = {'sheet_key': sheet_key, 'id': element_id(identifier), 'number': number}
                for field, attribute in [('sequence', 'SequenceNumber'), ('description', 'Description'), ('date', 'RevisionDate'),
                                         ('issued', 'Issued'), ('issued_to', 'IssuedTo'), ('issued_by', 'IssuedBy')]:
                    item[field] = self.read('revision', element_id(identifier), field, lambda attribute=attribute: getattr(revision, attribute))
                self.data['revisions'].append(item)
                self.add_element(self.doc, revision, 'host')
            self.done = index + 1
            self.checkpoint(True)
        return self.data


def export_pdf(doc, sheets, folder):
    """Native PDF export, only when explicitly selected by the user."""
    import os
    from System.Collections.Generic import List
    identifiers = List[DB.ElementId]()
    for sheet in sheets:
        if not sheet.IsPlaceholder:
            identifiers.Add(sheet.Id)
    if identifiers.Count == 0:
        raise ValueError('PDF로 출력할 일반 시트가 없습니다.')
    options = DB.PDFExportOptions()
    try:
        options.Combine = True
        options.FileName = 'sheets'
        if not doc.Export(folder, identifiers, options):
            raise RuntimeError('Revit PDF export returned false')
    finally:
        options.Dispose()
    path = os.path.join(folder, 'sheets.pdf')
    if not os.path.isfile(path):
        raise RuntimeError('Revit did not create sheets.pdf')
    return path
