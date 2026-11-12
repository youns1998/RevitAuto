# -*- coding: utf-8 -*-
"""Exercise the snapshot graph with stand-in Revit objects; never open a model."""
import importlib
import sys
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from revitauto.reports import ExportCancelled

with patch.dict(sys.modules, {'pyrevit': NS(DB=None)}):
    adapter = importlib.import_module('revitauto.revit_report')


def eid(value):
    return NS(Value=value)


def xyz(x=0, y=0, z=0):
    return NS(X=x, Y=y, Z=z)


class Parameter:
    def __init__(self, name='面積 한글', storage='Double', raw=12.5, broken=False):
        self.Id, self.StorageType, self.raw = eid(-10), storage, raw
        self.Definition = NS(Name=name, GetDataType=lambda: NS(TypeId='spec:area'))
        self.IsReadOnly, self.IsShared, self.HasValue, self.broken = True, False, True, broken

    def AsDouble(self):
        if self.broken:
            raise ValueError('unreadable parameter')
        return self.raw

    def AsValueString(self):
        return '1.16 m²'

    def GetUnitTypeId(self):
        return NS(TypeId='unit:square-meters')


class Element:
    def __init__(self, identifier, name, category='Walls', category_id=1, type_id=-1):
        self.Id, self.UniqueId, self.Name = eid(identifier), 'uid-' + str(identifier), name
        self.Category = NS(Id=eid(category_id), Name=category, CategoryType='Model')
        self.OwnerViewId, self.LevelId, self.type_id = eid(-1), eid(-1), eid(type_id)
        self.Parameters, self.Location = [], None

    def GetType(self):
        return NS(Name=type(self).__name__)

    def GetTypeId(self):
        return self.type_id

    def get_BoundingBox(self, unused):
        return None

    def GetMaterialIds(self, paint):
        return []


class ElementType(Element):
    FamilyName = '기본 벽'


class View(Element):
    ViewType, Scale, GenLevel, ViewTemplateId = 'FloorPlan', 50, None, eid(-1)
    CropBoxActive, CropBoxVisible, CropBox = True, False, None


class ViewSchedule(View):
    ViewType = 'Schedule'

    def GetTableData(self):
        return NS(GetSectionData=lambda section: NS(FirstRowNumber=0, LastRowNumber=0, FirstColumnNumber=0, LastColumnNumber=0))

    def GetCellText(self, section, row, column):
        return '부재표' if section == 'Body' else '제목'


class TextNote(Element):
    Text = '한글 주석'


class RevitLinkInstance(Element):
    def GetLinkDocument(self):
        return self.linked_doc

    def GetTotalTransform(self):
        return NS(Origin=xyz(10), BasisX=xyz(1), BasisY=xyz(0, 1), BasisZ=xyz(0, 0, 1))


class ScheduleSheetInstance(Element):
    ScheduleId, OwnerViewId, Point = eid(201), eid(100), xyz(1, 2)


class Collector:
    def __init__(self, doc, view_id=None, link_id=None):
        self.doc, self.view_id, self.link_id, self.element_class = doc, view_id, link_id, None
        if view_id is not None and view_id.Value == 201:
            raise ValueError('schedule cannot be iterated')

    def OfClass(self, cls):
        self.element_class = cls
        return self

    def WhereElementIsNotElementType(self):
        return self

    def __iter__(self):
        if self.link_id is not None:
            return iter(self.doc.objects[self.link_id.Value].linked_doc.candidates[200])
        if self.element_class is ScheduleSheetInstance:
            return iter(self.doc.schedules)
        return iter(self.doc.candidates.get(self.view_id.Value if self.view_id else None, []))

    def Dispose(self):
        pass


class Document:
    Title, PathName, ProjectInformation = '실습 모델', 'C:/models/test.rvt', None
    Application = NS(VersionNumber='2026', VersionBuild='test')

    def __init__(self):
        self.objects, self.candidates, self.schedules = {}, {}, []

    def GetElement(self, identifier):
        return self.objects.get(identifier.Value)

    def GetUnits(self):
        return NS(GetFormatOptions=lambda spec: NS(GetUnitTypeId=lambda: NS(TypeId='unit:metric'), Accuracy=0.01))


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.db = NS(FilteredElementCollector=Collector, ElementType=ElementType,
                     LocationPoint=type('LocationPoint', (), {}), LocationCurve=type('LocationCurve', (), {}),
                     TextNote=TextNote, IndependentTag=type('IndependentTag', (), {}), Dimension=type('Dimension', (), {}),
                     ViewSchedule=ViewSchedule, RevitLinkInstance=RevitLinkInstance, ScheduleSheetInstance=ScheduleSheetInstance,
                     CategoryType=NS(Annotation='Annotation'), BuiltInCategory=NS(OST_TitleBlocks=-2000280),
                     BuiltInParameter=NS(VIEWPORT_DETAIL_NUMBER='detail'), SectionType=NS(Header='Header', Body='Body'),
                     SpecTypeId=NS(Length='length', Area='area', Volume='volume', Angle='angle'), Transaction=Mock())
        active = patch.object(adapter, 'DB', self.db)
        active.start()
        self.addCleanup(active.stop)
        self.doc = Document()
        sheet = Element(100, '1층 시트')
        sheet.SheetNumber, sheet.IsPlaceholder = 'A101', False
        sheet.GetAllPlacedViews = lambda: [eid(200)]
        sheet.GetAllViewports = lambda: [eid(300)]
        sheet.GetAllRevisionIds = lambda: [eid(400)]
        self.sheet = sheet
        view = View(200, '1층 평면도')
        wall = Element(10, '외벽', type_id=500)
        wall.Parameters = [Parameter()]
        self.wall = wall
        wall_type = ElementType(500, '벽 유형')
        wall_type.Parameters = [Parameter('유형 면적')]
        note = TextNote(11, '문자', 'Text Notes')
        note.Category.CategoryType = 'Annotation'
        titleblock = Element(12, 'A3 도곽', 'Title Blocks', -2000280)
        viewport = Element(300, '뷰포트')
        viewport.ViewId, viewport.Rotation = eid(200), 'None'
        viewport.GetBoxCenter = lambda: xyz(1, 2)
        viewport.GetBoxOutline = lambda: NS(MinimumPoint=xyz(), MaximumPoint=xyz(2, 3))
        viewport.get_Parameter = lambda identifier: NS(AsString=lambda: '1')
        revision = Element(400, '개정 1')
        revision.SequenceNumber, revision.Description, revision.RevisionDate = 1, '설계 변경', '2026-11-12'
        revision.Issued, revision.IssuedTo, revision.IssuedBy = False, '담당자', '작성자'
        sheet.GetRevisionNumberOnSheet = lambda identifier: 'R1'
        link = RevitLinkInstance(700, '연결 모델')
        link.linked_doc = Document()
        linked_wall = Element(10, '연결 외벽')
        link.linked_doc.objects = {10: linked_wall}
        link.linked_doc.candidates = {200: [linked_wall]}
        schedule = ViewSchedule(201, '부재 일람표')
        schedule_instance = ScheduleSheetInstance(301, '일람표 배치')
        schedule_instance.OwnerViewId = eid(100)
        self.doc.objects = {x.Id.Value: x for x in (sheet, view, wall, wall_type, note, titleblock, viewport, revision, link, schedule)}
        self.doc.candidates = {100: [titleblock, viewport], 200: [wall, note, link]}
        self.doc.schedules = [schedule_instance]

    def test_sheet_view_element_type_and_link_graph(self):
        snapshot = adapter.SnapshotCollector(self.doc).snapshot([self.sheet])
        self.assertEqual(snapshot['sheets'][0]['titleblocks'][0]['name'], 'A3 도곽')
        self.assertEqual(snapshot['sheets'][0]['view_count'], 2)
        self.assertEqual(len(snapshot['views']), 2)
        self.assertEqual(set(x['kind'] for x in snapshot['placements']), {'viewport', 'schedule'})
        self.assertEqual(snapshot['revisions'][0]['number'], 'R1')
        self.assertEqual(len(snapshot['schedule_cells']), 2)
        self.assertTrue(any(x['key'] == 'host:10' and x['type_key'] == 'host:500' for x in snapshot['elements']))
        self.assertTrue(any(x['key'] == 'link:700:10' for x in snapshot['elements']))
        self.assertTrue(any(x['element_key'] == 'link:700:10' and x['view_key'] == 'host:200' for x in snapshot['view_elements']))
        self.assertTrue(any(x['text'] == '한글 주석' for x in snapshot['elements'] if 'text' in x))
        self.assertTrue(any(x['object_key'] == 'host:10' and x['raw'] == 12.5 and x['unit_id'] == 'unit:square-meters' for x in snapshot['parameters']))
        self.assertEqual(snapshot['documents'][1]['transform']['Origin']['x'], 10)
        self.db.Transaction.assert_not_called()

    def test_unreadable_parameters_are_reported(self):
        self.wall.Parameters.append(Parameter('불량 값', broken=True))
        snapshot = adapter.SnapshotCollector(self.doc).snapshot([self.sheet])
        self.assertTrue(any(x['field'] == 'raw' and 'unreadable' in x['message'] for x in snapshot['issues']))
        self.assertTrue(any(x['scope'] == 'collector' and x['entity'] == '201' for x in snapshot['issues']))
        self.assertEqual(len(snapshot['sheets']), 1)

    def test_cancel_stops_collection_without_transaction(self):
        with self.assertRaises(ExportCancelled):
            adapter.SnapshotCollector(self.doc, progress=lambda current, total: False).snapshot([self.sheet])
        self.db.Transaction.assert_not_called()

    def test_placeholder_has_no_sheet_graphics(self):
        self.sheet.IsPlaceholder = True
        self.sheet.GetAllPlacedViews = lambda: []
        self.sheet.GetAllRevisionIds = lambda: []
        snapshot = adapter.SnapshotCollector(self.doc).snapshot([self.sheet])
        self.assertTrue(snapshot['sheets'][0]['placeholder'])
        self.assertEqual(snapshot['placements'], [])


if __name__ == '__main__':
    unittest.main()
