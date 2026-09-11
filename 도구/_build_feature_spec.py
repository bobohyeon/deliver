# -*- coding: utf-8 -*-
"""관리/기능명세서.md 를 엑셀(xlsx) 로 뽑는다.

이 파일의 책임: 기능명세서의 전체 기능과 부속 표(요약·분석기구성·비기능·폐기·미결)를
  여섯 시트짜리 xlsx 로 만든다. 기능 데이터를 이 파일이 직접 들고 있으므로
  개수·우선순위 집계는 이 스크립트 출력을 정본으로 한다.
다른 파일과의 관계: 관리/기능명세서.md 의 기능 ID·우선순위·완료 판정 기준을
  그대로 옮긴다. 스키마는 관리/DocFlow_DB.dbml, 설계 의도는
  관리/데이터구조_설계.md 를 본다.
Spring 비교: 없음 — 순수 문서 생성 스크립트다.

openpyxl 이 없고 네트워크도 막힌 환경이라 xlsx(zip + OOXML) 를 직접 쓴다.
미니 프로젝트의 도구/_build_wbs.py 방식과 같고, 스타일만 흑백 무채색으로 바꿨다.

사용:
    python3 도구/_build_feature_spec.py
"""

import pathlib
import zipfile
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "산출물" / "기능명세서.xlsx"


# ─────────────────────────────────────────────── xlsx 유틸

def col_letter(idx):
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_xml(row, col, value, style=0):
    ref = f"{col_letter(col)}{row}"
    if value is None or value == "":
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, (int, float)):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    return (f'<c r="{ref}" s="{style}" t="inlineStr">'
            f'<is><t xml:space="preserve">{escape(str(value))}</t></is></c>')


def sheet_xml(rows, widths=None, freeze=None, autofilter=None):
    cols = ""
    if widths:
        cols = "<cols>" + "".join(
            f'<col min="{c}" max="{c}" width="{w}" customWidth="1"/>'
            for c, w in widths) + "</cols>"

    body = []
    for rnum, (height, cells) in enumerate(rows, start=1):
        h = f' ht="{height}" customHeight="1"' if height else ""
        cs = "".join(cell_xml(rnum, c, v, s) for c, v, s in cells)
        body.append(f'<row r="{rnum}"{h}>{cs}</row>')

    pane = ""
    if freeze:
        top_left, xsplit, ysplit = freeze
        pane = (f'<pane xSplit="{xsplit}" ySplit="{ysplit}" topLeftCell="{top_left}" '
                f'activePane="bottomRight" state="frozen"/>')

    af = f'<autoFilter ref="{autofilter}"/>' if autofilter else ""

    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
            f'{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16.5"/>'
            f'{cols}<sheetData>{"".join(body)}</sheetData>{af}'
            '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" '
            'header="0.3" footer="0.3"/>'
            '</worksheet>')


# ─────────────────────────────────────────────── 스타일 (흑백)
STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="7">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="15"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
<font><strike/><sz val="9"/><color rgb="FF8C8C8C"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="5">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF000000"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE4E4E4"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF6F6F6"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFC0C0C0"/></left>
<right style="thin"><color rgb="FFC0C0C0"/></right>
<top style="thin"><color rgb="FFC0C0C0"/></top>
<bottom style="thin"><color rgb="FFC0C0C0"/></bottom>
<diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="13">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" applyFont="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="5" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="4" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="6" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf>
<xf numFmtId="0" fontId="6" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

S_TITLE, S_HDR, S_GROUP, S_TXT, S_CEN, S_CENB = 1, 2, 3, 4, 5, 6
S_NOTE, S_SUB, S_TXTB, S_CENS, S_DEAD, S_DEADC = 7, 8, 9, 10, 11, 12


# ─────────────────────────────────────────────── 기능 데이터
# (기능ID, 기능명, 상태, 우선, 담당, 선행, 완료 판정 기준, 비고)
S, J, B, ALL = "세현", "재정", "보현", "공통"

AREAS = [
    ("A. 계정·권한", "AUTH", J, [
        ("AUTH-01", "회원가입", "신규", "P0", J, "", "이메일 중복 시 409. 비밀번호는 해시로만 저장되고 응답에 포함되지 않는다", ""),
        ("AUTH-02", "로그인", "신규", "P0", J, "AUTH-01", "올바른 자격으로 access·refresh 토큰 발급. 틀리면 401", ""),
        ("AUTH-03", "내 정보 조회", "신규", "P0", J, "AUTH-02", "유효 토큰으로 본인 정보 반환. 만료 토큰은 401", ""),
        ("AUTH-04", "토큰 갱신 · 로그아웃", "신규", "P0", J, "AUTH-02", "refresh 로 access 재발급. 로그아웃 후 해당 refresh 는 재사용 불가", ""),
        ("AUTH-05", "인증 의존성 get_current_user", "신규", "P0", J, "AUTH-02", "토큰 없이 보호된 엔드포인트 호출 시 401. 모든 프로젝트 스코프 API 에 적용됨을 목록으로 확인", "라우터마다 검사하면 누락된다"),
        ("AUTH-06", "SSO", "신규", "P3", J, "", "", ""),
    ]),
    ("B. 프로젝트", "PRJ", J, [
        ("PRJ-01", "프로젝트 생성", "신규", "P0", J, "AUTH-05", "생성자가 자동으로 OWNER 멤버로 등록된다", ""),
        ("PRJ-02", "내 프로젝트 목록", "신규", "P0", J, "PRJ-01", "내가 멤버인 프로젝트만 나온다. 카드에 문서 수·열린 태스크·승인 대기 표시", ""),
        ("PRJ-03", "프로젝트 상세 · 수정", "신규", "P0", J, "PRJ-01", "EDITOR 이상만 수정 가능. VIEWER 는 403", ""),
        ("PRJ-04", "상태 변경 (진행 중 · 보관됨)", "신규", "P0", J, "PRJ-01", "보관 시 목록에서 구분 표시되고 문서는 유지된다", ""),
        ("PRJ-05", "프로젝트 삭제", "신규", "P0", J, "PRJ-01", "OWNER 만 가능. 문서·태스크가 함께 정리된다", ""),
        ("PRJ-06", "멤버 초대", "신규", "P0", J, "PRJ-01", "역할 지정 후 초대. 이미 멤버면 409", ""),
        ("PRJ-07", "권한 3종 OWNER/EDITOR/VIEWER", "신규", "P0", J, "PRJ-06", "역할별 허용 동작 표가 문서로 존재하고 각 항목이 테스트로 확인된다", "금액 열람은 미결 — AMT-11"),
        ("PRJ-08", "프로젝트 스코프 강제", "신규", "P0", J, "PRJ-01", "다른 프로젝트의 document_id 를 직접 넣어도 404 가 나온다", "리포지토리 계층에서 막는다"),
        ("PRJ-09", "조직(Organization) 계층", "신규", "P3", J, "", "", ""),
    ]),
    ("C. 문서 입력·처리", "DOC", J, [
        ("DOC-01", "파일 업로드 (드래그앤드롭 · 다중)", "확장", "P0", J, "PRJ-01", "PDF·DOCX·HWPX·JPG·PNG, 최대 20MB. 여러 파일 동시 선택 가능", ""),
        ("DOC-02", "파일 검증", "기존", "P0", J, "", "미지원 형식 415, 크기 초과 413. 에러코드가 서버 로그에 남는다", "SYS-09 와 함께"),
        ("DOC-03", "형식별 추출기 자동 선택", "기존", "P0", J, "", "확장자별로 지정된 추출기가 선택된다", "ExtractorRegistry"),
        ("DOC-04", "OCR 실행", "기존", "P0", J, "", "스캔 PDF·이미지에서 텍스트가 나온다", ""),
        ("DOC-05", "처리 모드 선택 (일반·검수·일괄)", "신규", "P1", J, "DOC-01", "업로드 시 모드가 저장되고 기본값은 일반. 검수 모드는 review_status=PENDING 으로 시작", ""),
        ("DOC-06", "비동기 큐 처리", "신규", "P0", J, "SYS-02", "업로드가 즉시 202 + document_id 를 반환한다. 24페이지 스캔 PDF 에서 요청이 블로킹되지 않는다", "본프로젝트 최우선"),
        ("DOC-07", "처리 진행 상태 표시", "확장", "P0", J, "DOC-06", "단계별 진행이 화면에 보이고 실패 단계에 오류 표시가 남는다", "ANL-05 와 함께"),
        ("DOC-08", "문서 목록", "확장", "P0", J, "PRJ-08", "프로젝트 스코프. 페이징. 쿼리 수가 문서 수에 비례하지 않는다", "SYS-07"),
        ("DOC-09", "문서 상세", "확장", "P0", J, "", "요약·추출 원문·메타(추출방식·OCR엔진·페이지·글자수·평균신뢰도·처리시간) 표시", ""),
        ("DOC-10", "원본 다운로드", "신규", "P0", J, "DOC-14", "업로드한 원본 파일이 그대로 내려온다", ""),
        ("DOC-11", "문서 삭제", "기존", "P0", J, "", "하위 데이터(추출텍스트·분석·OCR요소·금액·결정·일정)가 함께 정리된다", "cascade"),
        ("DOC-12", "재분석", "신규", "P1", J, "ANL-07", "기존 분석을 지우지 않고 새 행으로 쌓인다. 이전 결과와 비교 가능", "analyses 1:N 의 효과"),
        ("DOC-13", "중복 파일 검사 (SHA-256)", "신규", "P2", J, "", "", ""),
        ("DOC-14", "파일 저장소 이전 (S3·MinIO)", "신규", "P1", J, "", "컨테이너 재기동 후에도 파일이 유지된다", "산출물 파일도 같은 곳에 둔다"),
        ("DOC-15", "문서 버전 관리 · 변경점 비교", "신규", "P3", J, "", "", ""),
        ("DOC-16", "업로드 시 문서 유형 지정", "신규", "P1", J, "DOC-01", "7종 중 고르거나 자동 판별(기본값). 일괄은 배치 단위로 한 번 지정한다", "분석기를 껐다 켜지는 않는다. 목록 필터·프롬프트 힌트·산출물 분류에 쓴다"),
    ]),
    ("D. OCR 검수", "REV", J, [
        ("REV-01", "페이지 이미지 생성 · 저장", "신규", "P1", J, "", "페이지별 이미지와 좌표 기준 크기(width·height)가 저장된다", "document_pages"),
        ("REV-02", "OCR 박스 저장", "신규", "P1", J, "REV-01", "박스별 텍스트·좌표·신뢰도가 0~1 비율 좌표로 저장된다", "ocr_elements"),
        ("REV-03", "이미지 위 Bounding Box 표시", "신규", "P1", J, "REV-02", "화면 확대·축소와 무관하게 박스가 글자 위에 정확히 얹힌다", "좌표 기준 이미지를 렌더링본으로 고정"),
        ("REV-04", "신뢰도별 박스 구분", "신규", "P1", J, "REV-03", "높음·검토권장·낮음·선택 네 가지가 시각적으로 구분된다", ""),
        ("REV-05", "박스 선택 + 텍스트 수정", "신규", "P1", J, "REV-03", "수정 후 original_text 는 그대로 남고 text 만 바뀐다", ""),
        ("REV-06", "낮은 신뢰도만 모아보기", "신규", "P1", J, "REV-04", "임계치 미만 박스만 목록으로 순회할 수 있다", ""),
        ("REV-07", "검수 완료 처리", "신규", "P1", J, "REV-05", "완료 시 is_confirmed=true, 확정자·시각이 남고 분석이 1회 실행된다", ""),
        ("REV-08", "박스 이동 · 크기 조정", "신규", "P2", J, "REV-05", "", "크기만 바꾸면 텍스트 유지"),
        ("REV-09", "박스 생성 · 삭제", "신규", "P2", J, "REV-05", "", "삭제는 논리 삭제"),
        ("REV-10", "박스 병합 · 분리", "신규", "P2", J, "REV-08", "", ""),
        ("REV-11", "선택 영역 다시 OCR", "신규", "P2", J, "REV-08", "", "사용자 확인 후 반영. source=RE_OCR"),
        ("REV-12", "단락 지정 · 병합 · 분리", "신규", "P2", J, "REV-02", "", "OCR 재실행 불필요"),
        ("REV-13", "읽기 순서 변경", "신규", "P2", J, "REV-12", "사용자 지정이 자동 결과를 덮지 않는다", "지정 순서 > 지정 단락 > XY-Cut"),
        ("REV-14", "표 행 · 열 수동 보정", "신규", "P3", J, "REV-12", "", ""),
        ("REV-15", "수정 이력 · 되돌리기", "신규", "P2", J, "REV-05", "", "ocr_element_revisions"),
        ("REV-16", "동시 수정 충돌 방지", "신규", "P1", J, "REV-02", "같은 박스를 두 사용자가 수정하면 나중 요청이 409 를 받는다", "ocr_elements.version"),
        ("REV-17", "텍스트 재조립", "신규", "P1", J, "REV-05", "박스 수정 후 extracted_texts.content 가 같은 트랜잭션에서 갱신된다", "offset 기록은 불필요 (ANL-13 폐기)"),
        ("REV-18", "분석 결과 오래됨 표시", "신규", "P1", J, "REV-17", "OCR 을 고친 뒤 화면에 '분석을 다시 실행해 주세요' 가 뜬다", "revision 전파 사슬"),
    ]),
    ("E. 일괄 처리", "BAT", J, [
        ("BAT-01", "다중 파일 순차 업로드", "신규", "P1", J, "DOC-01", "여러 파일을 한 번에 등록하고 파일별로 성공·실패가 표시된다", "브라우저 순차 호출로 데모 충분"),
        ("BAT-02", "처리 대기열 화면", "신규", "P1", J, "BAT-01", "대기·처리중·검수필요·완료·실패가 파일별로 보이고 실패 사유가 표시된다", ""),
        ("BAT-03", "서버 일괄 작업 모델", "신규", "P2", J, "DOC-06", "브라우저를 닫아도 작업이 계속된다", "batch_jobs / batch_items"),
        ("BAT-04", "실패 재시도", "신규", "P2", J, "BAT-03", "", ""),
        ("BAT-05", "OCR Worker 수 제한 병렬", "신규", "P2", J, "BAT-03", "", "메모리 한도 안에서"),
        ("BAT-06", "실시간 진행률 (SSE)", "신규", "P2", J, "BAT-03", "", ""),
        ("BAT-07", "로컬 폴더 자동 감시 프로그램", "신규", "P3", J, "", "", "별도 설치형. 범위 밖"),
    ]),
    ("F. 분석", "ANL", S, [
        ("ANL-01", "요약 분석기", "기존", "P0", S, "", "요약문과 토큰·지연시간이 기록된다", "코드를 고치지 않는다"),
        ("ANL-02", "분류 분석기", "확장", "P0", S, "DOC-16", "7종 중 하나로 분류하고 reason 을 함께 반환한다. 자동 판별인 문서에만 실행한다", ""),
        ("ANL-03", "항목 추출 분석기", "신규", "P1", S, "", "액션아이템·결정·일정을 한 번의 호출로 배열로 반환. 각 항목에 reason 과 확신도가 붙는다", "제안 골격의 첫 사례"),
        ("ANL-05", "분석 진행률 일반화", "신규", "P1", S, "", "진행 단계가 분석기 수에 따라 자동으로 '분석 3/4' 처럼 표시된다. 분석기 추가 시 화면 코드를 고치지 않는다", "목업 4단계 하드코딩 해소"),
        ("ANL-06", "확정 텍스트 기준 분석", "신규", "P1", S, "REV-07", "검수 완료된 문서는 수정된 텍스트로 분석된다. 어느 ocr_revision 을 썼는지 기록된다", ""),
        ("ANL-07", "분석 이력 보존", "기존", "P0", S, "", "재분석이 이전 결과를 덮지 않는다", "analyses 1:N"),
        ("ANL-08", "프롬프트 버전 관리", "기존", "P0", S, "", "prompt_version 이 결과와 함께 저장된다", "분석기별로 따로 올린다"),
        ("ANL-09", "LLM 재시도 · 폴백", "신규", "P2", S, "", "일시 실패 시 재시도, 지속 실패 시 대체 모델", "현재 타임아웃만 있다"),
        ("ANL-10", "제안 종류별 채택률", "신규", "P2", S, "TSK-07", "채택률이 액션아이템·결정·일정·금액별로 나뉘어 표시된다", "목업은 단일 숫자"),
        ("ANL-11", "교정 분석기", "신규", "P3", S, "", "", ""),
        ("ANL-12", "번역 분석기", "신규", "P3", S, "", "", ""),
        ("ANL-14", "결정사항 추출", "신규", "P1", S, "ANL-03", "회의록에서 결정된 것을 뽑아 decisions 에 쌓는다. 결론이 안 난 것은 PENDING 으로 남아 회의 안건이 된다", "DLV-05·DLV-06 의 재료"),
        ("ANL-15", "일정 · 기한 추출", "신규", "P1", S, "ANL-03", "문서의 날짜를 뽑아 schedule_items 에 쌓는다. 날짜는 형식이 있어 원문 대조로 정확도를 잴 수 있다", "DLV-04·DLV-07 의 재료"),
        ("ANL-16", "구조화 출력 검증 · 재시도", "신규", "P1", B, "ANL-03", "모델이 형식을 어기면 검출해 재시도하고 실패가 로그에 남는다", "결과를 String 으로 먼저 받기로 해서 파싱 실패가 흔하다"),
        ("ANL-17", "평가셋 기반 정확도 측정 자동화", "신규", "P1", B, "ANL-03", "정답 데이터와 대조해 정확도가 수치로 나온다. 모델·프롬프트를 바꿔도 같은 자로 잰다", "세현님 모델 비교에 직접 쓰인다"),
    ]),
    ("G. 금액", "AMT", B, [
        ("AMT-01", "금액 항목 추출", "신규", "P1", S, "", "항목명·수량·단위·금액·reason 을 구조화 스키마로 반환. 문서에 없는 값은 비운다", "LLM 은 추출만. 계산은 코드"),
        ("AMT-02", "금액 항목 승인 · 수정 UI", "신규", "P1", S, "AMT-01", "액션아이템과 같은 제안 카드 형식. 승인 전에는 어디에도 반영되지 않는다", "UI 패턴 재사용"),
        ("AMT-03", "합계 대조", "신규", "P1", B, "AMT-01", "항목 합계와 문서에 적힌 합계가 다르면 불일치 금액과 함께 표시된다", "검증 가능한 유일한 기능"),
        ("AMT-06", "프로젝트 금액 집계", "신규", "P1", B, "AMT-02", "여러 문서의 금액을 프로젝트 단위로 모은다. 같은 입력이면 항상 같은 결과가 나온다", "단위테스트로 확인. 추계가 아니라 집계"),
        ("AMT-07", "불일치 태스크 제안", "신규", "P1", B, "TSK-03", "불일치 시 태스크 제안 카드가 생긴다. 자동 등록은 하지 않는다", ""),
        ("AMT-08", "프로젝트 금액 현황", "신규", "P2", B, "AMT-06", "계약금액·변경 증감·집행률·잔액이 프로젝트 단위로 보인다", ""),
        ("AMT-09", "금액 판단 근거 표시", "신규", "P1", S, "AMT-01", "금액 항목마다 reason 이 보이고 출처 문서로 이동할 수 있다", "위치 하이라이트는 범위 밖"),
        ("AMT-11", "금액 열람 권한 분리", "신규", "P2", B, "PRJ-07", "", "미결 — VIEWER 노출 여부"),
        ("AMT-12", "추출 결과 스키마 검증 · 정규화", "신규", "P1", B, "AMT-01", "모델 응답이 계약 스키마에 맞는지 검사하고 어긋나면 AI_INVALID_RESPONSE 로 재시도한다", "쉼표·단위 제거, 원 단위 정수화"),
        ("AMT-13", "단가 · 원가구분 컬럼 추가", "신규", "P1", B, "AMT-01", "unit_price 와 category 가 저장되고 부가세가 구분된다", "리비전 0008. 부가세를 구분 못 하면 합계가 틀린다"),
        ("AMT-14", "비용 산출 엔진", "신규", "P1", B, "AMT-13", "수량 × 단가 계산과 항목 합계를 코드가 수행한다. LLM 은 계산에 관여하지 않는다", "결정론적. 같은 입력 같은 결과"),
        ("AMT-15", "근거 변경 탐지 및 재계산", "신규", "P2", B, "AMT-14", "문서가 수정되면 변경된 필드만 다시 추출해 재계산한다. 모델 재학습은 없다", ""),
        ("AMT-16", "계산 버전 · 변경 내역 저장", "신규", "P2", B, "AMT-15", "변경 전후 값과 차액이 남아 어떤 근거로 금액이 바뀌었는지 추적된다", ""),
        ("AMT-17", "계산식 · 산출 근거 표시", "신규", "P1", B, "AMT-14", "금액마다 계산식과 출처 문서 · 원문 인용이 함께 보인다", "AMT-09 와 짝"),
    ]),
    ("H. 태스크·협업", "TSK", ALL, [
        ("TSK-01", "태스크 CRUD", "신규", "P1", J, "PRJ-01", "제목·설명·담당자·기한·상태를 사람이 직접 만들 수 있다", ""),
        ("TSK-02", "칸반 보드", "신규", "P1", J, "TSK-01", "할 일·진행 중·완료 3열, 열별 개수 표시, 드래그로 상태 변경", ""),
        ("TSK-03", "AI 제안 → 태스크 확정", "신규", "P1", B, "ANL-03", "승인해야 등록된다. 승인 전에는 보드에 나타나지 않는다", "자동 등록 금지 원칙"),
        ("TSK-04", "출처 · 판단 근거 표시", "신규", "P1", B, "TSK-03", "태스크에 출처 문서 링크와 AI 판단 근거(reason)가 함께 보인다", "원문 위치 하이라이트는 범위 밖"),
        ("TSK-05", "AI 생성 배지 · 필터", "신규", "P1", J, "TSK-03", "AI 생성 태스크가 구분 표시되고 AI생성만·기한임박·출처문서별 필터가 동작한다", ""),
        ("TSK-06", "담당자 · 기한 지정", "신규", "P1", J, "TSK-01", "AI 가 못 찾은 경우 미지정 상태로 남고 사람이 채운다", ""),
        ("TSK-07", "제안 거부", "신규", "P1", B, "TSK-03", "거부한 제안은 다시 뜨지 않는다. 거부 사실이 기록된다", "채택률 지표의 원천"),
        ("TSK-08", "일괄 승인", "신규", "P1", B, "TSK-03", "문서 단위로 여러 제안을 한 번에 승인할 수 있다", ""),
        ("TSK-09", "활동 로그", "신규", "P2", B, "PRJ-01", "", "activity_logs. 주간 보고서 재료"),
        ("TSK-10", "알림 (이메일 · Slack)", "신규", "P3", J, "TSK-09", "", ""),
    ]),
    ("I. 가시성", "VIS", B, [
        ("VIS-01", "대시보드 지표 카드", "신규", "P2", B, "PRJ-01", "", "전체 문서·처리 중·열린 태스크·승인 대기"),
        ("VIS-02", "문서 유형 분포", "신규", "P2", B, "ANL-02", "", ""),
        ("VIS-03", "승인 대기 배너", "신규", "P1", B, "TSK-03", "승인 대기 건수와 출처 문서명이 보이고 검토 화면으로 이동한다", "제안 종류별로 나눠 표시"),
        ("VIS-04", "최근 문서", "신규", "P2", B, "DOC-08", "", ""),
        ("VIS-05", "이번 주 활동", "신규", "P2", B, "ANL-10", "", "제안 종류별 채택률 포함"),
        ("VIS-06", "통합 검색 (PostgreSQL FTS)", "신규", "P2", B, "PRJ-08", "", "프로젝트 스코프 안에서"),
        ("VIS-07", "시맨틱 검색 (pgvector)", "신규", "P3", B, "VIS-06", "", ""),
        ("VIS-09", "활동 타임라인", "신규", "P2", B, "TSK-09", "", ""),
    ]),
    ("J. 공통·기반", "SYS", ALL, [
        ("SYS-01", "Alembic 마이그레이션", "신규", "P0", B, "", "create_all() 의존을 제거한다. 컬럼 추가가 데이터 유실 없이 반영된다", "P0 착수 전 완료"),
        ("SYS-02", "Celery + Redis", "신규", "P0", J, "", "워커가 죽어도 작업이 큐에 남고 재시작 시 이어진다", ""),
        ("SYS-03", "에러코드 체계", "확장", "P0", B, "", "기존 11종에 인증·권한·프로젝트 코드를 추가. 응답 형식이 일관된다", ""),
        ("SYS-04", "request_id 로깅", "기존", "P0", J, "", "요청 단위로 로그 추적 가능", ""),
        ("SYS-05", "Fake AI Client", "기존", "P0", S, "", "API 키 없이 전체 흐름이 동작한다", "병렬 작업의 전제"),
        ("SYS-06", "API 호출 쿼터", "신규", "P2", S, "", "", "프로젝트별 월 한도"),
        ("SYS-07", "N+1 방지", "신규", "P0", B, "", "목록 조회 쿼리 수가 문서 수와 무관하게 일정하다. selectinload 사용", "미니 2+2N 해소"),
        ("SYS-08", "FK 인덱스", "신규", "P0", B, "SYS-01", "모든 FK 에 명시적 인덱스. PostgreSQL 은 자동 생성하지 않는다", ""),
        ("SYS-09", "에러 로그 누락 수정", "확장", "P0", J, "", "404·409·413 이 서버 로그에 남는다", "미니 ISS-046. 첫날 수정"),
        ("SYS-10", "로컬 sLLM 옵션", "신규", "P3", S, "", "", ""),
    ]),
    ("K. 산출물", "DLV", B, [
        ("DLV-01", "산출물 페이지 (사이드바 메뉴)", "신규", "P1", B, "PRJ-01", "사이드바에 '산출물' 메뉴가 있고 개수 배지가 붙는다", "대시보드와 분리한다 — 이력 성격"),
        ("DLV-02", "기간 선택", "신규", "P1", B, "DLV-01", "이번 주·지난 주·이번 달·직접 지정. 기간이 필요 없는 종류는 선택이 흐려진다", ""),
        ("DLV-03", "생성 대상 미리보기", "신규", "P1", B, "DLV-02", "선택한 기간에 잡히는 문서·완료 태스크·결정·기한·금액 건수가 LLM 호출 전에 보인다. 승인 대기 건수도 함께", "빈 보고서 방지 + 비용 절약 + 승인 유도"),
        ("DLV-04", "주간 보고서 생성", "신규", "P1", B, "DLV-03", "개요·문서 목록·태스크·결정·기한·금액 변동이 한 파일로 나온다. LLM 호출은 개요 한 단락에만 1회", "tasks.completed_at 필수. 저장된 요약을 재요약한다"),
        ("DLV-05", "결정사항 대장 생성", "신규", "P1", B, "ANL-14", "결정 내용·결정일·출처 문서·상태(확정/미결/뒤집힘)가 표로 나온다", "미니 프로젝트 결정사항 29건을 대신한다"),
        ("DLV-06", "다음 회의 안건 생성", "신규", "P1", B, "ANL-14", "decisions.status=PENDING 인 항목만 모아 안건으로 만든다", "DLV-05 의 부산물. 거의 공짜"),
        ("DLV-07", "프로젝트 현황 한 장", "신규", "P2", B, "ANL-15", "일정·태스크·결정·금액 현재 상태를 한 페이지로", ""),
        ("DLV-08", "형식 선택", "신규", "P1", B, "DLV-01", "XLSX·HTML·MD. 기본값이 없다. 고르지 않으면 생성 버튼이 비활성", "_md2html.py·_build_wbs.py 재사용"),
        ("DLV-09", "생성 이력 · 다운로드", "신규", "P1", B, "DLV-04", "만든 산출물이 목록으로 남고 다시 내려받을 수 있다", "deliverables 테이블"),
        ("DLV-10", "갱신 필요 판정", "신규", "P1", B, "DLV-09", "생성 후 문서가 추가되면 '문서 N건이 나중에 추가됨' 과 다시 만들기가 표시된다", "source_counts_json 스냅샷 비교"),
        ("DLV-11", "인수인계 문서 생성", "신규", "P3", B, "DLV-07", "", "프로젝트 종료 시 전체 누적"),
    ]),
    ("L. 검색·근거", "RAG", B, [
        ("RAG-01", "텍스트 정규화 · 청킹", "신규", "P1", B, "REV-17", "ocr_elements 의 element_type 으로 단락을 묶고 토큰 수 기준으로 자른다. 표는 행 단위로 유지된다", "재정님 단락 분리를 입력으로 쓴다"),
        ("RAG-02", "임베딩 생성 · 저장", "신규", "P1", B, "RAG-01", "청크마다 벡터가 저장되고 어느 모델·차원으로 만든 것인지 기록된다", "document_chunks. 모델 교체 시 재생성 판단 근거"),
        ("RAG-03", "벡터 인덱스 구축 (pgvector)", "신규", "P1", B, "RAG-02", "확장 설치와 인덱스 생성이 마이그레이션으로 반영된다", "리비전 0009. 차원은 임베딩 모델 확정 후"),
        ("RAG-04", "의미 검색", "신규", "P1", B, "RAG-03", "글자가 하나도 겹치지 않는 질의로 관련 문서가 나온다. 다른 프로젝트 문서는 나오지 않는다", "PRJ-08 스코프 강제"),
        ("RAG-05", "하이브리드 검색 (키워드 + 벡터)", "신규", "P2", B, "RAG-04", "고유명사·코드번호 검색에서 벡터 단독보다 정확하다", "VIS-06 FTS 와 결합"),
        ("RAG-06", "검색 결과 재순위", "신규", "P3", B, "RAG-05", "", ""),
        ("RAG-07", "프롬프트 컨텍스트 조립", "신규", "P1", B, "RAG-04", "토큰 예산 안에서 청크를 골라 넣는다. 45000자 문서에서도 컨텍스트 초과가 나지 않는다", "긴 문서 요약에도 쓰인다"),
        ("RAG-08", "근거 스니펫 연결", "신규", "P1", B, "RAG-04", "검색·응답 결과마다 출처 문서와 원문 인용이 함께 나온다", "AMT-17 · TSK-04 와 같은 패턴"),
        ("RAG-09", "검수 확정 시 재임베딩", "신규", "P1", B, "REV-07", "OCR 을 고치면 해당 문서의 청크가 다시 임베딩된다. 낡은 벡터로 검색되지 않는다", "놓치기 쉽다. 검수 전파 사슬의 끝"),
        ("RAG-10", "검색 품질 측정", "신규", "P2", B, "RAG-04", "질의 목록에 대한 적중 여부가 수치로 나온다", "청킹 기준 변경의 판단 근거"),
        ("RAG-11", "질의응답 챗봇", "신규", "P3", B, "RAG-07", "업로드 문서에 대해 질문하면 근거와 함께 답한다", "후순위 합의. 검색이 먼저"),
        ("RAG-12", "유사 사업 단가 선례 검색", "신규", "P2", B, "RAG-04", "과거 사업 문서에서 같은 항목의 단가를 찾아 출처와 함께 보여준다", "비용추계의 근거. 도메인을 좁힌 이유"),
    ]),
]

# (기능ID, 기능명, 영역, 왜 폐기했나)
DEPRECATED = [
    ("ANL-04", "분석기 선택 규칙 (analyzer_rules)", "F. 분석",
     "회의록·보고서에도 금액이 나온다. 유형으로 껐다 켜면 오히려 놓친다. "
     "그리고 분류를 먼저 돌려야 해서 asyncio.gather 가 두 단계로 쪼개져 병렬성이 깨졌다"),
    ("ANL-13", "Analyzer Protocol 위치 컨텍스트 확장", "F. 분석",
     "근거를 페이지·좌표 대신 reason(판단 근거 서술)으로 표시하기로 해서 규격을 "
     "고칠 필요가 없어졌다. 세 사람의 인터페이스 대기가 하나 줄었다"),
    ("AMT-04", "단가 마스터 관리", "G. 금액",
     "추계를 버리고 집계로 좁혀서 단가가 필요 없어졌다. 최대 위험이 통째로 사라졌다"),
    ("AMT-05", "전제 입력 · 승인", "G. 금액", "AMT-04 와 같은 이유"),
    ("AMT-10", "비용추계서 서식 출력", "G. 금액",
     "국회 의안 서식은 타깃 사용자(SI·스타트업·공공사업 수행팀)와 맞지 않는다. "
     "향후 개선사항으로 배치"),
    ("VIS-08", "주간 자동 리포트", "I. 가시성",
     "폐기가 아니라 이동. DLV-04 로 옮기고 P3 -> P1 로 승격했다"),
]

# 폐기와 함께 없앤 테이블
DEAD_TABLES = ["analyzer_rules", "unit_prices", "cost_estimates", "cost_estimate_lines"]


# ─────────────────────────────────────────────── 시트 1 · 기능명세

HEADERS = ["기능 ID", "영역", "기능명", "상태", "우선", "담당", "선행",
           "완료 판정 기준", "비고"]
WIDTHS = [(1, 11), (2, 17), (3, 36), (4, 7), (5, 7), (6, 8), (7, 11),
          (8, 62), (9, 32)]


def counts():
    tot = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    per = []
    for area, prefix, owner, items in AREAS:
        c = {k: sum(1 for it in items if it[3] == k) for k in tot}
        for k in tot:
            tot[k] += c[k]
        per.append((area, prefix, owner, len(items), c))
    return per, tot


def build_spec_sheet():
    rows = []
    total = sum(len(items) for _, _, _, items in AREAS)
    rows.append((22, [(1, f"DocFlow 기능명세서 — 유효 {total}건 "
                          f"(폐기 {len(DEPRECATED)}건은 별도 시트)", S_TITLE)]))
    rows.append((30, [(i + 1, h, S_HDR) for i, h in enumerate(HEADERS)]))

    for area_name, _prefix, _owner, items in AREAS:
        n = len(items)
        p0 = sum(1 for it in items if it[3] == "P0")
        p1 = sum(1 for it in items if it[3] == "P1")
        rows.append((20, [(1, f"{area_name}   ({n}건 · P0 {p0} · P1 {p1})", S_GROUP)]
                     + [(c, "", S_GROUP) for c in range(2, 10)]))

        for fid, name, state, pri, owner, dep, done, note in items:
            minor = pri in ("P2", "P3")
            st_txt = S_SUB if minor else S_TXT
            st_cen = S_CENS if minor else S_CEN
            rows.append((None, [
                (1, fid, S_CENS if minor else S_CENB),
                (2, area_name, st_txt),
                (3, name, st_txt if minor else S_TXTB),
                (4, state, st_cen),
                (5, pri, st_cen),
                (6, owner, st_cen),
                (7, dep, st_txt),
                (8, done, st_txt),
                (9, note, st_txt),
            ]))

    return sheet_xml(rows, WIDTHS, freeze=("A3", 0, 2),
                     autofilter=f"A2:I{len(rows)}")


# ─────────────────────────────────────────────── 시트 2 · 요약

def build_summary_sheet():
    per, tot = counts()
    rows = []
    rows.append((22, [(1, "요약", S_TITLE)]))
    rows.append((46, [(1, "구현 20일 (8/17~9/5 · 영업일 15일 · 3인 45 인일). "
                          "P0+P1 을 다 못 하므로 '묶기' 로 접근한다. "
                          "설계가 크게 단순해졌다 — 분석기 선택 규칙·추계·단가 마스터·"
                          "위치 하이라이트를 폐기하면서 세 사람이 서로 기다리는 지점이 "
                          "사라졌다.", S_NOTE)]))
    rows.append((None, []))

    hdr = ["영역", "기능 수", "P0", "P1", "P2", "P3", "주 담당"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for area, prefix, owner, n, c in per:
        rows.append((None, [
            (1, f"{area} ({prefix})", S_TXT), (2, n, S_CEN),
            (3, c["P0"], S_CEN), (4, c["P1"], S_CEN),
            (5, c["P2"], S_CEN), (6, c["P3"], S_CEN), (7, owner, S_CEN),
        ]))
    rows.append((20, [(1, "합계", S_GROUP),
                      (2, sum(p[3] for p in per), S_GROUP),
                      (3, tot["P0"], S_GROUP), (4, tot["P1"], S_GROUP),
                      (5, tot["P2"], S_GROUP), (6, tot["P3"], S_GROUP),
                      (7, "", S_GROUP)]))

    rows.append((None, []))
    rows.append((20, [(1, "우선순위 정의", S_GROUP)] + [(c, "", S_GROUP) for c in (2, 3)]))
    for k, v in [
        ("P0", "MVP 필수. 없으면 '팀 도구' 가 성립하지 않는다"),
        ("P1", "차별화 핵심. 발표 데모의 중심"),
        ("P2", "확장. 없어도 데모가 성립한다"),
        ("P3", "향후. 발표에서 '향후 개선사항' 으로 배치한다"),
    ]:
        rows.append((None, [(1, k, S_CENB), (2, v, S_TXT), (3, "", S_TXT)]))

    rows.append((None, []))
    rows.append((20, [(1, "묶음 — 같은 골격을 쓰므로 함께 만들면 두 번째부터 싸다",
                       S_GROUP)] + [(c, "", S_GROUP) for c in (2, 3)]))
    for k, v in [
        ("제안 골격", "ANL-03 ANL-14 ANL-15 AMT-01 TSK-03~TSK-08 — "
                    "제안 카드·승인·태스크 등록 UI 를 공유한다. 분석기만 갈아 끼운다"),
        ("산출물 골격", "DLV-01~DLV-10 — 기간 필터·파일 생성·이력이 하나로 묶인다. 종류만 늘린다"),
        ("검수 골격", "REV-01~REV-07 REV-16~REV-18 — 박스 표시와 텍스트 수정이 하나로 묶인다"),
        ("스코프", "AUTH-* PRJ-* — 인증 없이 스코프가 성립하지 않는다"),
    ]:
        rows.append((None, [(1, k, S_CENB), (2, v, S_TXT), (3, "", S_TXT)]))

    return sheet_xml(rows, [(1, 26), (2, 80), (3, 20), (4, 8), (5, 8), (6, 8), (7, 10)])


# ─────────────────────────────────────────────── 시트 3 · 분석기 구성

ANALYZERS = [
    ("summary", "요약", "기존 — 코드 무수정", "요약문", "약 2,800", "약 125", "ANL-01"),
    ("category", "분류", "확장 — 7종 + reason", "유형 + 판단 근거", "약 2,850", "약 60", "ANL-02"),
    ("extract", "항목 추출", "신규", "액션아이템 · 결정 · 일정 배열", "약 2,900", "약 250",
     "ANL-03 · ANL-14 · ANL-15"),
    ("amount", "금액", "신규", "금액 항목 배열", "약 2,850", "약 150", "AMT-01"),
]


def build_analyzer_sheet():
    rows = []
    rows.append((22, [(1, "분석기 구성 — 4개, gather 한 번", S_TITLE)]))
    rows.append((60, [(1, "문서 유형으로 분석기를 고르지 않는다. 항상 넷 다 돌린다. "
                          "회의록·보고서에도 금액이 나오므로 유형으로 껐다 켜면 놓치고, "
                          "분류를 먼저 돌리면 asyncio.gather 가 두 단계로 쪼개져 병렬성이 "
                          "깨진다. 그래서 ANL-04 분석기 선택 규칙을 폐기했다. "
                          "FastAPI 라우터와는 무관한 층이었다.", S_NOTE)]))
    rows.append((None, []))
    hdr = ["registry 키", "이름", "상태", "무엇을 뽑나", "입력 토큰", "출력 토큰", "기능 ID"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for r in ANALYZERS:
        rows.append((None, [(1, r[0], S_CENB), (2, r[1], S_TXTB), (3, r[2], S_TXT),
                            (4, r[3], S_TXT), (5, r[4], S_CEN), (6, r[5], S_CEN),
                            (7, r[6], S_TXT)]))
    rows.append((20, [(1, "합계", S_GROUP), (2, "", S_GROUP), (3, "", S_GROUP),
                      (4, "", S_GROUP), (5, "약 11,400", S_GROUP),
                      (6, "약 585", S_GROUP), (7, "", S_GROUP)]))

    rows.append((None, []))
    rows.append((20, [(1, "통합 1개와 비교 — 4개를 고른 이유", S_GROUP)]
                 + [(c, "", S_GROUP) for c in range(2, 4)]))
    for k, v in [
        ("입력 토큰", "4개 약 11,400 / 통합 약 2,850. 통합이 75% 싸다 — 본문을 한 번만 보낸다"),
        ("기존 코드", "4개는 요약·분류를 0줄 고친다 / 통합은 흡수하며 회귀 위험"),
        ("실패 단위", "4개는 하나 실패해도 나머지가 살아남는다 / 통합은 전부 실패"),
        ("금액 정확도", "4개는 프롬프트를 집중할 수 있다 / 통합은 주의가 분산된다"),
        ("프롬프트 버전", "4개는 분석기별로 따로 올린다 / 통합은 하나로 뭉친다"),
        ("결론", "토큰 2배를 감수하고 4개로 간다. 개발은 USE_FAKE_AI 로 하고 실제 호출은 "
               "데모·측정 때만이다. 통합 방식은 측정해서 비교하고 발표 소재로 쓴다"),
    ]:
        rows.append((None, [(1, k, S_CENB), (2, v, S_TXT), (3, "", S_TXT)]))

    rows.append((None, []))
    rows.append((44, [(1, "분석기 하나를 추가하는 비용 — 새 클래스 + 프롬프트 + "
                          "dependencies.py 한 줄 + AnalyzerType 값. 라우터·서비스·스키마는 "
                          "안 고친다 (analysis_router 가 analyzer_types 를 그대로 넘기고 "
                          "analyses.analyzer_type 이 String(30) 이라 DB 변경도 없다).",
                       S_NOTE)]))
    return sheet_xml(rows, [(1, 14), (2, 12), (3, 22), (4, 34), (5, 12), (6, 12), (7, 28)])


# ─────────────────────────────────────────────── 시트 4 · 비기능·제외

NFR = [
    ("성능", "10페이지 스캔 PDF 처리 완료 ≤ 60초", "동일 파일 3회 평균", ""),
    ("성능", "목록 조회 쿼리 수가 문서 수와 무관", "쿼리 로그 개수", "SYS-07"),
    ("성능", "주간 보고서 생성 ≤ 15초", "LLM 1회 + DB 쿼리", "DLV-04"),
    ("동시성", "4~5인 동시 사용 시 정상 동작", "동시 업로드 5건", ""),
    ("정확도", "액션아이템 승인율 ≥ 70%", "TSK-07 거부 기록 기반", "TSK-07"),
    ("정확도", "카테고리 분류 정확도 ≥ 85%",
     "document_type_source=USER_CORRECTED 비율", "정답셋 대신 실사용 데이터"),
    ("정확도", "일정 추출 정확도", "Golden Dataset · 원문 대조", "날짜는 형식이 있다"),
    ("정확도", "금액 항목 추출 정확도", "Golden Dataset · 원문 대조", "원문이 정답이다"),
    ("정확도", "금액 집계 정확도 = 100%", "단위테스트", "코드가 계산하므로 AI 지표가 아니다"),
    ("보안", "타 프로젝트 데이터 접근 차단", "PRJ-08 침투 테스트", "PRJ-08"),
    ("보안", "API 키는 서버에만", "프론트 번들 검사", ""),
    ("안정성", "컨테이너 재기동 후 파일 유지", "재기동 후 다운로드", "DOC-14"),
]

NOGO = [
    ("실시간 공동 편집", "Notion·Google Docs 대체가 아니다"),
    ("간트 차트 등 본격 PMS", "범위 밖"),
    ("사람이 원가를 입력하는 비용 관리 모듈",
     "컨셉과 반대다. 우리는 문서에서 뽑는다. 경계는 '입력을 누가 하는가'"),
    ("금액 추계 · 예측", "없는 값을 만드는 일이다. 단가 근거를 댈 수 없다"),
    ("모바일 네이티브 앱", "반응형 웹으로 대응"),
    ("법안 등 법률문서 자동 생성", "환각 위험·법적 책임·검증 부담"),
    ("파인튜닝", "20일에 자리가 없다. 프롬프트 + 구조화 출력으로 목표 달성 가능"),
    ("원문 위치 하이라이트", "분석기 규격을 바꿔야 해서 세 사람이 서로 기다린다"),
]


def build_nfr_sheet():
    rows = []
    rows.append((22, [(1, "비기능 요구사항 · 하지 않을 것", S_TITLE)]))
    rows.append((None, []))
    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["구분", "요구", "측정 방법", "비고"])]))
    for a, b, c, d in NFR:
        rows.append((None, [(1, a, S_CEN), (2, b, S_TXT), (3, c, S_TXT), (4, d, S_TXT)]))
    rows.append((None, []))
    rows.append((20, [(1, "하지 않을 것", S_GROUP)] + [(c, "", S_GROUP) for c in (2, 3, 4)]))
    for a, b in NOGO:
        rows.append((None, [(1, "", S_TXT), (2, a, S_TXTB), (3, b, S_TXT), (4, "", S_TXT)]))
    return sheet_xml(rows, [(1, 12), (2, 44), (3, 40), (4, 30)])


# ─────────────────────────────────────────────── 시트 5 · 폐기

def build_dead_sheet():
    rows = []
    rows.append((22, [(1, "폐기한 기능 — 번호를 재사용하지 않는다", S_TITLE)]))
    rows.append((32, [(1, "왜 뺐는지가 결정 이력이다. 미니 프로젝트에서 결정사항에 "
                          "미채택 대안과 이유를 남긴 것과 같은 형식으로 관리한다.",
                       S_NOTE)]))
    rows.append((None, []))
    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["기능 ID", "기능명", "영역", "왜 폐기했나"])]))
    for fid, name, area, why in DEPRECATED:
        rows.append((None, [(1, fid, S_DEADC), (2, name, S_DEAD),
                            (3, area, S_DEAD), (4, why, S_DEAD)]))

    rows.append((None, []))
    rows.append((20, [(1, "함께 없앤 테이블", S_GROUP)] + [(c, "", S_GROUP) for c in (2, 3, 4)]))
    rows.append((None, [(1, "", S_TXT), (2, " · ".join(DEAD_TABLES), S_TXTB),
                        (3, "", S_TXT), (4, "", S_TXT)]))

    rows.append((None, []))
    rows.append((20, [(1, "폐기하지 않고 성격만 바꾼 것", S_GROUP)]
                 + [(c, "", S_GROUP) for c in (2, 3, 4)]))
    for fid, before, after in [
        ("DOC-16", "분석기 선택 기준을 만든다", "목록 필터 · 프롬프트 힌트 · 산출물 분류"),
        ("ANL-10", "분석기별 채택률", "제안 종류별 채택률"),
        ("TSK-04", "원문 위치 하이라이트", "출처 문서 링크 + reason"),
        ("AMT-06", "추계 계산", "프로젝트 금액 집계"),
        ("VIS-08", "주간 자동 리포트 (P3)", "DLV-04 로 이동해 P1 승격"),
    ]:
        rows.append((None, [(1, fid, S_CENB), (2, before, S_TXT),
                            (3, "→", S_CEN), (4, after, S_TXTB)]))
    return sheet_xml(rows, [(1, 11), (2, 40), (3, 16), (4, 66)])


# ─────────────────────────────────────────────── 시트 6 · 미결

OPEN = [
    ("우선순위", 1, "P0+P1 을 20일에 다 못 한다", "덜어내기보다 묶기로 접근 (요약 시트)", "전원"),
    ("우선순위", 2, "ANL-03 항목 추출과 AMT-01 금액 중 무엇을 먼저",
     "ANL-03 으로 제안 골격을 만들고 금액을 두 번째로 얹는다", "전원"),
    ("우선순위", 3, "검수 2단계(REV-08~REV-15)를 P2 로 두는 데 동의하는지",
     "1단계만으로도 금액·산출물 파트는 성립한다", "재정"),
    ("우선순위", 4, "DLV 산출물 영역을 P1 로 두는 데 동의하는지",
     "동의 필요. 이게 없으면 '태스크 모음으로 뭘 하나' 에 답이 없다", "전원"),
    ("DB", 5, "tasks.completed_at · updated_at 추가",
     "필수. 없으면 DLV-04 주간 보고서를 만들 수 없다. 목업이 이미 '3월 7일 완료' 를 표시한다", "세현"),
    ("DB", 6, "tasks.source_amount_item_id 추가", "필수. 출처 2갈래 + CHECK 제약", "세현"),
    ("DB", 7, "documents.document_type 7종 enum 실제 사용", "필수", "세현"),
    ("DB", 8, "documents.document_type_source 추가",
     "선택. USER_CORRECTED 비율이 곧 분류 오류율", "세현"),
    ("DB", 9, "projects.started_on · due_on 추가", "선택. 일정 산출물용", "세현"),
    ("DB", 10, "activity_logs.action_type 값 목록", "팀 합의 필요. 주간 보고서 재료", "전원"),
    ("설계", 11, "분석기 4개 vs 통합 1개", "4개로 시작. 측정 후 재검토", "보현"),
    ("설계", 12, "VIEWER 에게 금액 노출 여부 (AMT-11)", "미결", "전원"),
    ("설계", 13, "산출물 파일 저장 위치", "DOC-14 S3·MinIO 와 같은 곳", "보현"),
    ("OCR DB", 14, "page_number 0 부터 · 1 부터", "1 부터. 화면 표시와 일치해 변환이 없다", "재정"),
    ("OCR DB", 15, "좌표 기준 이미지", "렌더링본. 전처리본은 프리셋에 따라 달라진다", "재정"),
    ("OCR DB", 16, "polygon_json 저장 여부", "MVP 제외, 컬럼만 준비", "재정"),
    ("OCR DB", 17, "검수 완료 후 재수정 허용", "허용하고 IN_PROGRESS 로 되돌린다", "재정"),
    ("OCR DB", 18, "수정 이력을 MVP 부터 저장할지",
     "P2. 단 ocr_engine·engine_version·preprocess_info 는 MVP 부터", "재정"),
    ("OCR DB", 19, "박스 1개 수정이 ocr_revision 을 항상 올리는지",
     "올린다. 안 올리면 전파 사슬이 깨진다", "재정"),
    ("OCR DB", 20, "텍스트 재조립 동기 · 비동기", "동기 · 같은 트랜잭션", "재정"),
    ("OCR DB", 21, "group_id 만 먼저 둘지", "group_id 먼저. ocr_groups 는 P2", "재정"),
    ("OCR DB", 22, "재OCR 자동 교체 여부", "사용자 확인 후 반영", "재정"),
    ("OCR DB", 23, "오래된 분석 자동 재실행", "사용자 재실행 요구. 자동은 API 비용이 튄다", "보현"),
    ("운영", 24, "배포 환경 — 클라우드 · 온프레미스", "OCR GPU 필요 여부와 직결", "전원"),
    ("운영", 25, "AI 제공자 — OpenAI 유지 · 로컬 sLLM 병행",
     "상용 API 유지 권장. 1조가 Gemma 1B 에서 언어 쏠림을 겪었다", "전원"),
]


def build_open_sheet():
    rows = []
    rows.append((22, [(1, "미결 사항 — 착수 전 합의 필요", S_TITLE)]))
    rows.append((None, []))
    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["구분", "#", "안건", "제안 / 의견", "결정 주체",
                                 "결정", "결정일"])]))
    for cat, n, item, opinion, who in OPEN:
        rows.append((None, [
            (1, cat, S_CEN), (2, n, S_CEN), (3, item, S_TXTB),
            (4, opinion, S_TXT), (5, who, S_CEN), (6, "", S_TXT), (7, "", S_CEN),
        ]))
    rows.append((None, []))
    rows.append((32, [(1, "결정 열은 회의에서 채운다. 미채택 대안과 이유도 함께 남긴다 — "
                          "미니 프로젝트 결정사항 29건과 같은 형식이다.", S_NOTE)]))
    return sheet_xml(rows, [(1, 11), (2, 5), (3, 48), (4, 60), (5, 11), (6, 26), (7, 12)],
                     freeze=("A4", 0, 3))


# ─────────────────────────────────────────────── 패키징

SHEETS = [
    ("기능명세", build_spec_sheet()),
    ("요약", build_summary_sheet()),
    ("분석기구성", build_analyzer_sheet()),
    ("비기능·제외", build_nfr_sheet()),
    ("폐기", build_dead_sheet()),
    ("미결사항", build_open_sheet()),
]

content_types = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
    + "".join(
        f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for i in range(len(SHEETS)))
    + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    '</Types>')

root_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
    '</Relationships>')

workbook = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
    '<sheets>' + "".join(
        f'<sheet name="{escape(n)}" sheetId="{i+1}" r:id="rId{i+1}"/>'
        for i, (n, _) in enumerate(SHEETS)) + '</sheets></workbook>')

wb_rels = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    + "".join(
        f'<Relationship Id="rId{i+1}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{i+1}.xml"/>' for i in range(len(SHEETS)))
    + f'<Relationship Id="rId{len(SHEETS)+1}" '
      'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
      'Target="styles.xml"/></Relationships>')


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", STYLES)
        for i, (_, xml) in enumerate(SHEETS):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml)

    per, tot = counts()
    print(f"생성 완료: {OUT.relative_to(ROOT)}")
    print(f"  시트 {len(SHEETS)}개 — " + " · ".join(n for n, _ in SHEETS))
    print()
    print("  | 영역 | 기능 수 | P0 | P1 | P2 | P3 |")
    print("  |---|---:|---:|---:|---:|---:|")
    for area, prefix, _o, n, c in per:
        print(f"  | {area} `{prefix}` | {n} | {c['P0']} | {c['P1']} "
              f"| {c['P2']} | {c['P3']} |")
    total = sum(p[3] for p in per)
    print(f"  | **합계** | **{total}** | **{tot['P0']}** | **{tot['P1']}** "
          f"| **{tot['P2']}** | **{tot['P3']}** |")
    print()
    print(f"  유효 {total}건 · 폐기 {len(DEPRECATED)}건 · "
          f"P0+P1 {tot['P0'] + tot['P1']}건")
    print(f"  파일 크기: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
