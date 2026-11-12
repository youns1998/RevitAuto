# -*- coding: utf-8 -*-
"""Revit API operations. Imported only inside a pyRevit command context."""
from __future__ import unicode_literals

from pyrevit import DB, forms, revit, script
from revitauto.sheets import SheetSpec, for_views, read_csv_file, validate, write_csv_file


def run(command):
    doc = revit.doc
    if doc is None or doc.IsFamilyDocument:
        forms.alert('Revit 프로젝트를 먼저 여세요.', title='RevitAuto')
        return
    try:
        command(doc)
    except Exception as error:
        script.get_logger().exception('RevitAuto command failed')
        forms.alert('작업을 완료하지 못했습니다.\n{}'.format(error), title='RevitAuto')


def _sheets(doc):
    return list(DB.FilteredElementCollector(doc).OfClass(DB.ViewSheet))


def _validate_revit_names(plan):
    for item in plan:
        if not DB.NamingUtils.IsValidName(item.name):
            raise ValueError("시트 '{}'의 이름에 Revit에서 허용하지 않는 문자가 있습니다: {}".format(item.number, item.name))


def _titleblock(doc):
    options = {'도곽 없이 생성': DB.ElementId.InvalidElementId}
    for symbol in DB.FilteredElementCollector(doc).OfClass(DB.FamilySymbol).OfCategory(DB.BuiltInCategory.OST_TitleBlocks):
        name = symbol.get_Parameter(DB.BuiltInParameter.SYMBOL_NAME_PARAM).AsString()
        options['{} : {}'.format(symbol.FamilyName, name)] = symbol.Id
    choice = forms.SelectFromList.show(sorted(options), title='도곽 선택', button_name='다음')
    return options[choice] if choice is not None else None


def _confirm(plan):
    preview = '\n'.join('{}  |  {}'.format(x.number, x.name) for x in plan[:25])
    if len(plan) > 25:
        preview += '\n외 {}개'.format(len(plan) - 25)
    return forms.alert('{}개 시트를 생성합니다.\n\n{}\n\n진행할까요?'.format(len(plan), preview),
                       title='RevitAuto · 생성 미리보기', ok=False, yes=True, no=True)


def _change(doc, name, action):
    """One explicit transaction: no partial sheets after operation errors."""
    transaction = DB.Transaction(doc, name)
    try:
        if transaction.Start() != DB.TransactionStatus.Started:
            raise RuntimeError('Revit 변경 작업을 시작할 수 없습니다.')
        options = transaction.GetFailureHandlingOptions()
        options.SetClearAfterRollback(True)
        transaction.SetFailureHandlingOptions(options)
        action()
        if transaction.Commit() != DB.TransactionStatus.Committed:
            raise RuntimeError('Revit이 변경을 확정하지 못했습니다. Revit 오류 창을 확인하세요.')
    except Exception:
        if transaction.GetStatus() == DB.TransactionStatus.Started:
            transaction.RollBack()
        raise
    finally:
        transaction.Dispose()


def import_sheets(doc):
    path = forms.pick_file(file_ext='csv', title='Number,Name CSV 선택')
    if not path:
        return
    plan = validate(read_csv_file(path), [x.SheetNumber for x in _sheets(doc)])
    _validate_revit_names(plan)
    titleblock = _titleblock(doc)
    if titleblock is None or not _confirm(plan):
        return

    def create():
        for item in plan:
            sheet = DB.ViewSheet.Create(doc, titleblock)
            sheet.SheetNumber, sheet.Name = item.number, item.name

    _change(doc, 'RevitAuto: CSV 시트 일괄 생성', create)
    forms.alert('시트 {}개를 생성했습니다. 실행 취소 1회로 되돌릴 수 있습니다.'.format(len(plan)), title='RevitAuto')


def place_views(doc):
    placed = set(x.ViewId.Value for x in DB.FilteredElementCollector(doc).OfClass(DB.Viewport))
    allowed = (DB.ViewType.FloorPlan, DB.ViewType.CeilingPlan, DB.ViewType.EngineeringPlan,
               DB.ViewType.Elevation, DB.ViewType.Section, DB.ViewType.ThreeD,
               DB.ViewType.DraftingView, DB.ViewType.Detail)
    candidates = [x for x in DB.FilteredElementCollector(doc).OfClass(DB.View)
                  if not x.IsTemplate and x.ViewType in allowed and x.Id.Value not in placed]
    if not candidates:
        forms.alert('시트에 배치하지 않은 평면·입면·단면·3D·상세 뷰가 없습니다.', title='RevitAuto')
        return
    chosen = forms.SelectFromList.show(sorted(candidates, key=lambda x: x.Name), name_attr='Name',
                                       title='시트에 배치할 뷰 선택', multiselect=True, button_name='다음')
    if not chosen:
        return
    plan = for_views([x.Name for x in chosen], [x.SheetNumber for x in _sheets(doc)])
    _validate_revit_names(plan)
    titleblock = _titleblock(doc)
    if titleblock is None or not _confirm(plan):
        return

    def create():
        for view, item in zip(chosen, plan):
            sheet = DB.ViewSheet.Create(doc, titleblock)
            sheet.SheetNumber, sheet.Name = item.number, item.name
            doc.Regenerate()
            if not DB.Viewport.CanAddViewToSheet(doc, sheet.Id, view.Id):
                raise ValueError("'{}' 뷰를 배치할 수 없어 전체 작업을 취소했습니다.".format(view.Name))
            outline = sheet.Outline
            center = DB.XYZ((outline.Min.U + outline.Max.U) / 2.0,
                            (outline.Min.V + outline.Max.V) / 2.0, 0)
            viewport = DB.Viewport.Create(doc, sheet.Id, view.Id, center)
            doc.Regenerate()
            viewport.SetBoxCenter(center)

    _change(doc, 'RevitAuto: 뷰별 시트 생성 및 배치', create)
    forms.alert('뷰 {}개를 새 시트에 배치했습니다. 출력 전 축척과 도곽 여백을 확인하세요.'.format(len(chosen)), title='RevitAuto')


def export_sheets(doc):
    path = forms.save_file(file_ext='csv', default_name='sheet-register.csv', title='시트 목록 저장')
    if not path:
        return
    sheets = [SheetSpec(x.SheetNumber, x.Name) for x in sorted(_sheets(doc), key=lambda x: x.SheetNumber.lower())]
    write_csv_file(path, sheets)
    forms.alert('시트 {}개의 번호와 이름을 저장했습니다.\n{}'.format(len(sheets), path), title='RevitAuto')
