# 상세정보 ZIP 형식

`manifest.json`의 `schema_version`은 `1`입니다. `snapshot.json`은 각 CSV와 같은 이름의 배열을 보유합니다. CSV는 UTF-8 BOM이며 쉼표·따옴표·줄바꿈은 CSV 인용으로 처리합니다. JSON은 UTF-8이고 숫자는 원시 수치로 유지합니다.

## 관계와 수집 범위

- 프로젝트 요소 키: `host:12345`
- 직접 연결된 모델 요소 키: `link:링크인스턴스ID:요소ID`
- `placements.sheet_key`와 `placements.view_key`: 어느 시트에 어떤 뷰가 놓였는지 연결합니다.
- `view_elements.view_key`와 `element_key`: 어느 뷰의 수집 결과에 요소가 포함됐는지 연결합니다.
- `elements.type_key`: `types.key`와 연결합니다.
- `parameters.object_key`: 시트·뷰·요소·유형·재료의 키와 연결합니다. `referenced_element_key`는 출력 범위 밖의 요소를 가리킬 수도 있습니다.
- 같은 뷰나 요소는 한 번만 기록하고, 시트·뷰와의 관계를 별도로 저장합니다. 같은 링크 파일의 여러 인스턴스는 각각의 위치 변환과 키를 유지합니다.

선택한 시트, 배치된 뷰와 일람표, 시트와 뷰에서 수집되는 비유형 요소, 관련 유형·재료, 읽을 수 있는 모든 `Element.Parameters`를 대상으로 합니다. 파라미터에는 이름·ID·저장 형식·원시 값·표시 값·Spec/Unit ID·읽기 전용·공유 GUID를 기록합니다. 시트 도곽의 사용자 파라미터도 요소 파라미터에 포함됩니다.

뷰 템플릿과 연관 레벨의 파라미터, 프로젝트 정보 파라미터도 수집합니다. 직접 배치된 로드된 Revit 링크는 호스트 뷰 기준 링크 수집기로 읽고, 링크 인스턴스의 변환을 `documents.transform`에 기록합니다. 링크 안의 중첩 링크는 순회하지 않습니다.

Revit 뷰 수집기는 최종 화면의 픽셀 가시성 판정이 아닙니다. 다른 요소에 가려지거나 자르기 영역 밖인 요소가 포함될 수 있습니다. 특히 비정형 자르기 영역의 정확한 가시성 필터를 구현한 것은 아닙니다. [Autodesk API 설명](https://help.autodesk.com/cloudhelp/2026/ENU/Revit-API-MainReference/files/html/6359776d-915e-f8a2-4147-b31024671ee1.htm)을 따릅니다.

## 단위와 형식

`parameters.raw`와 좌표·길이·치수는 Revit API의 내부 단위입니다. 길이는 피트이며 면적·체적은 이에 따른 단위입니다. `parameters.display`, `spec_id`, `unit_id`와 문서의 단위 설정을 함께 읽으세요. 문자열 값과 참조 ElementId도 원시 형식으로 저장합니다.

CSV에서 중첩 값(좌표·박스·목록)은 해당 셀 안의 JSON 문자열로 기록합니다. CSV 셀의 수식 실행을 막기 위해 `=`, `+`, `-`, `@`로 시작하는 값 앞에 작은따옴표를 붙입니다. 따라서 원시 수치를 다시 계산하거나 자동 처리할 때는 `snapshot.json`을 사용하세요.

## 오류·취소·PDF

읽을 수 없는 속성이나 파라미터는 빈 값과 `issues.csv`의 범위·요소·필드·원인으로 남깁니다. 자리표시자 시트는 메타데이터만 기록합니다. 순회할 수 없는 일람표는 표 셀을 읽고 요소 순회 실패를 별도로 기록할 수 있습니다. 로드되지 않은 링크도 누락 사유를 기록합니다.

PDF를 선택하면 Revit 기본 PDF Export로 일반 시트를 합쳐 `sheets.pdf`를 생성합니다. PDF 실패 시 CSV·JSON을 저장하고 `manifest.pdf`를 `failed_see_issues`로 표시합니다. PDF가 지원하지 않는 시트는 실패할 수 있습니다. PDF API 호출 중에는 취소 반영이 지연될 수 있습니다.

내보내기 중 취소하면 새 ZIP을 저장하지 않습니다. ZIP 생성 실패 시 기존 출력 파일은 보존합니다. 이 기능은 Revit Transaction을 시작하지 않으며 모델을 변경하지 않습니다.

전체 BRep/솔리드/메시, 모든 API 속성의 무차별 직렬화, 외부 CAD·이미지 파일의 원본 데이터, 중첩 링크 순회, 재료 렌더링 자산은 포함하지 않습니다. RVT·IFC 전체 내보내기를 대신하지 않습니다.
