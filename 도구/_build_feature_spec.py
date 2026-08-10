# -*- coding: utf-8 -*-
"""관리/기능명세서.md 를 엑셀(xlsx) 로 뽑는다.

이 파일의 책임: 기능명세서의 108개 기능과 부속 표(요약·라우팅·비기능·미결)를
  다섯 시트짜리 xlsx 로 만든다. 데이터를 이 파일에 직접 들고 있으므로,
  기능명세서.md 를 고치면 여기도 같이 고쳐야 한다 (단일 원천은 .md 쪽이다).
다른 파일과의 관계: 관리/기능명세서.md 의 기능 ID·우선순위·완료 판정 기준을
  그대로 옮긴다. WBS(작업분할구조도) xlsx 의 산출물목록 시트에 붙여넣어
  쓸 수 있게 열 구성을 맞췄다.
Spring 비교: 없음 — 순수 문서 생성 스크립트다.

openpyxl 이 없고 네트워크도 막힌 환경이라 xlsx(zip + OOXML) 를 직접 쓴다.
미니 프로젝트의 도구/_build_wbs.py 에서 쓴 방식과 같고, 스타일만 흑백
무채색으로 바꿨다 (산출물은 색을 쓰지 않는다).

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
    """rows = [(height|None, [(col, value, style), ...]), ...]"""
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

    # 스키마 순서: sheetData → autoFilter → pageMargins
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
# 색을 쓰지 않는다. 강조는 검정 채움 하나로만 한다.
STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="6">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="15"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
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
<cellXfs count="11">
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
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

S_TITLE = 1      # 큰 제목
S_HDR = 2        # 표 머리글 — 검정 채움
S_GROUP = 3      # 영역 구분 행 — 회색 채움
S_TXT = 4        # 본문 (줄바꿈)
S_CEN = 5        # 가운데
S_CENB = 6       # 가운데 굵게
S_NOTE = 7       # 설명 (테두리 없음)
S_SUB = 8        # 옅은 채움 본문 (P2·P3)
S_TXTB = 9       # 본문 굵게
S_CENS = 10      # 가운데 · 옅은 채움


# ─────────────────────────────────────────────── 기능 데이터
# (기능ID, 기능명, 상태, 우선, 담당, 선행, 완료 판정 기준, 비고)
S = "세현"
J = "재정"
B = "보현"
ALL = "공통"

AREAS = [
    ("A. 계정·권한", "AUTH", S, [
        ("AUTH-01", "회원가입", "신규", "P0", S, "", "이메일 중복 시 409. 비밀번호는 해시로만 저장되고 응답에 포함되지 않는다", ""),
        ("AUTH-02", "로그인", "신규", "P0", S, "AUTH-01", "올바른 자격으로 access·refresh 토큰 발급. 틀리면 401", ""),
        ("AUTH-03", "내 정보 조회", "신규", "P0", S, "AUTH-02", "유효 토큰으로 본인 정보 반환. 만료 토큰은 401", ""),
        ("AUTH-04", "토큰 갱신 · 로그아웃", "신규", "P0", S, "AUTH-02", "refresh 로 access 재발급. 로그아웃 후 해당 refresh 는 재사용 불가", ""),
        ("AUTH-05", "인증 의존성 get_current_user", "신규", "P0", S, "AUTH-02", "토큰 없이 보호된 엔드포인트 호출 시 401. 모든 프로젝트 스코프 API 에 적용됨을 목록으로 확인", "라우터마다 검사하면 누락된다"),
        ("AUTH-06", "SSO", "신규", "P3", S, "", "", ""),
    ]),
    ("B. 프로젝트", "PRJ", S, [
        ("PRJ-01", "프로젝트 생성", "신규", "P0", S, "AUTH-05", "생성자가 자동으로 OWNER 멤버로 등록된다", ""),
        ("PRJ-02", "내 프로젝트 목록", "신규", "P0", S, "PRJ-01", "내가 멤버인 프로젝트만 나온다. 카드에 문서 수·열린 태스크·승인 대기 표시", "미확정 금액 지표 추가 — AMT-08"),
        ("PRJ-03", "프로젝트 상세 · 수정", "신규", "P0", S, "PRJ-01", "EDITOR 이상만 수정 가능. VIEWER 는 403", ""),
        ("PRJ-04", "상태 변경 (진행 중 · 보관됨)", "신규", "P0", S, "PRJ-01", "보관 시 목록에서 구분 표시되고 문서는 유지된다", ""),
        ("PRJ-05", "프로젝트 삭제", "신규", "P0", S, "PRJ-01", "OWNER 만 가능. 문서·태스크가 함께 정리된다", ""),
        ("PRJ-06", "멤버 초대", "신규", "P0", S, "PRJ-01", "역할 지정 후 초대. 이미 멤버면 409", ""),
        ("PRJ-07", "권한 3종 OWNER/EDITOR/VIEWER", "신규", "P0", S, "PRJ-06", "역할별 허용 동작 표가 문서로 존재하고 각 항목이 테스트로 확인된다", "금액 열람은 미결 — AMT-11"),
        ("PRJ-08", "프로젝트 스코프 강제", "신규", "P0", S, "PRJ-01", "다른 프로젝트의 document_id 를 직접 넣어도 404 가 나온다", "리포지토리 계층에서 막는다"),
        ("PRJ-09", "조직(Organization) 계층", "신규", "P3", S, "", "", ""),
    ]),
    ("C. 문서 입력·처리", "DOC", J, [
        ("DOC-01", "파일 업로드 (드래그앤드롭 · 다중)", "확장", "P0", J, "PRJ-01", "PDF·DOCX·HWPX·JPG·PNG, 최대 20MB. 여러 파일 동시 선택 가능", ""),
        ("DOC-02", "파일 검증", "기존", "P0", J, "", "미지원 형식 415, 크기 초과 413. 에러코드가 서버 로그에 남는다", "SYS-09 와 함께"),
        ("DOC-03", "형식별 추출기 자동 선택", "기존", "P0", J, "", "확장자별로 지정된 추출기가 선택된다", "ExtractorRegistry"),
        ("DOC-04", "OCR 실행", "기존", "P0", J, "", "스캔 PDF·이미지에서 텍스트가 나온다", ""),
        ("DOC-05", "처리 모드 선택 (일반·검수·일괄)", "신규", "P1", J, "DOC-01", "업로드 시 모드가 저장되고 기본값은 일반. 검수 모드는 review_status=PENDING 으로 시작", "목업에 없음 — UI 변경 8"),
        ("DOC-06", "비동기 큐 처리", "신규", "P0", S, "SYS-02", "업로드가 즉시 202 + document_id 를 반환한다. 24페이지 스캔 PDF 에서 요청이 블로킹되지 않는다", "본프로젝트 최우선"),
        ("DOC-07", "처리 진행 상태 표시", "확장", "P0", J, "DOC-06", "단계별 진행이 화면에 보이고 실패 단계에 오류 표시가 남는다", "ANL-05 와 함께"),
        ("DOC-08", "문서 목록", "확장", "P0", B, "PRJ-08", "프로젝트 스코프. 페이징. 쿼리 수가 문서 수에 비례하지 않는다", "SYS-07"),
        ("DOC-09", "문서 상세", "확장", "P0", B, "", "요약·추출 원문·메타(추출방식·OCR엔진·페이지·글자수·평균신뢰도·처리시간) 표시", ""),
        ("DOC-10", "원본 다운로드", "신규", "P0", B, "DOC-14", "업로드한 원본 파일이 그대로 내려온다", ""),
        ("DOC-11", "문서 삭제", "기존", "P0", B, "", "하위 데이터(추출텍스트·분석·OCR요소)가 함께 정리된다", "cascade"),
        ("DOC-12", "재분석", "신규", "P1", B, "ANL-07", "기존 분석을 지우지 않고 새 행으로 쌓인다. 이전 결과와 비교 가능", "analyses 1:N 의 효과"),
        ("DOC-13", "중복 파일 검사 (SHA-256)", "신규", "P2", J, "", "", ""),
        ("DOC-14", "파일 저장소 이전 (S3·MinIO)", "신규", "P1", S, "", "컨테이너 재기동 후에도 파일이 유지된다", ""),
        ("DOC-15", "문서 버전 관리 · 변경점 비교", "신규", "P3", J, "", "", ""),
    ]),
    ("D. OCR 검수", "REV", J, [
        ("REV-01", "페이지 이미지 생성 · 저장", "신규", "P1", J, "", "페이지별 이미지와 좌표 기준 크기(width·height)가 저장된다", "document_pages"),
        ("REV-02", "OCR 박스 저장", "신규", "P1", J, "REV-01", "박스별 텍스트·좌표·신뢰도가 0~1 비율 좌표로 저장된다", "ocr_elements"),
        ("REV-03", "이미지 위 Bounding Box 표시", "신규", "P1", J, "REV-02", "화면 확대·축소와 무관하게 박스가 글자 위에 정확히 얹힌다", "좌표 기준 이미지 고정 필요"),
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
        ("REV-17", "텍스트 재조립", "신규", "P1", J, "REV-05", "박스 수정 후 extracted_texts.content 가 같은 트랜잭션에서 갱신된다", "조각 offset 도 함께 남긴다 — ANL-13"),
        ("REV-18", "분석 결과 오래됨 표시", "신규", "P1", J, "REV-17", "OCR 을 고친 뒤 화면에 '분석을 다시 실행해 주세요' 가 뜬다", "revision 전파 사슬"),
    ]),
    ("E. 일괄 처리", "BAT", J, [
        ("BAT-01", "다중 파일 순차 업로드", "신규", "P1", J, "DOC-01", "여러 파일을 한 번에 등록하고 파일별로 성공·실패가 표시된다", "브라우저 순차 호출로 충분"),
        ("BAT-02", "처리 대기열 화면", "신규", "P1", J, "BAT-01", "대기·처리중·검수필요·완료·실패가 파일별로 보이고 실패 사유가 표시된다", ""),
        ("BAT-03", "서버 일괄 작업 모델", "신규", "P2", J, "DOC-06", "브라우저를 닫아도 작업이 계속된다", "batch_jobs / batch_items"),
        ("BAT-04", "실패 재시도", "신규", "P2", J, "BAT-03", "", ""),
        ("BAT-05", "OCR Worker 수 제한 병렬", "신규", "P2", J, "BAT-03", "", "메모리 한도 안에서"),
        ("BAT-06", "실시간 진행률 (SSE)", "신규", "P2", J, "BAT-03", "", ""),
        ("BAT-07", "로컬 폴더 자동 감시 프로그램", "신규", "P3", J, "", "", "별도 설치형. 범위 밖"),
    ]),
    ("F. 분석", "ANL", B, [
        ("ANL-01", "요약 분석기", "기존", "P0", B, "", "요약문과 토큰·지연시간이 기록된다", ""),
        ("ANL-02", "분류 분석기", "기존", "P0", B, "", "6종 카테고리 중 하나로 분류된다", "라우팅의 선행 고정 단계"),
        ("ANL-03", "액션아이템 분석기", "신규", "P1", B, "ANL-13", "내용·담당자·기한·확신도를 배열로 반환. 담당자·기한을 못 찾으면 미지정 표시", "제안 골격의 첫 사례"),
        ("ANL-04", "분석기 라우팅", "신규", "P1", B, "ANL-02", "문서 유형에 따라 실행할 분석기가 결정된다. 새 분석기 추가 시 라우팅 표에 행 하나 추가로 끝난다", "analyzer_routes 테이블"),
        ("ANL-05", "분석 진행률 일반화", "신규", "P1", B, "ANL-04", "진행 단계가 분석기 수에 따라 자동으로 '분석 2/3' 처럼 표시된다. 분석기 추가 시 화면 코드를 고치지 않는다", "목업 4단계 하드코딩 해소"),
        ("ANL-06", "확정 텍스트 기준 분석", "신규", "P1", B, "REV-07", "검수 완료된 문서는 수정된 텍스트로 분석된다. 어느 ocr_revision 을 썼는지 기록된다", ""),
        ("ANL-07", "분석 이력 보존", "기존", "P0", B, "", "재분석이 이전 결과를 덮지 않는다", "analyses 1:N"),
        ("ANL-08", "프롬프트 버전 관리", "기존", "P0", B, "", "prompt_version 이 결과와 함께 저장된다", ""),
        ("ANL-09", "LLM 재시도 · 폴백", "신규", "P2", B, "", "일시 실패 시 재시도, 지속 실패 시 대체 모델", "현재 타임아웃만 있다"),
        ("ANL-10", "분석기별 채택률 지표", "신규", "P2", B, "TSK-07", "채택률이 분석기별로 나뉘어 표시된다", "목업은 단일 숫자"),
        ("ANL-11", "교정 분석기", "신규", "P3", B, "ANL-04", "", ""),
        ("ANL-12", "번역 분석기", "신규", "P3", B, "ANL-04", "", ""),
        ("ANL-13", "Analyzer Protocol 확장 — 위치 컨텍스트", "신규", "P1", B, "REV-17", "분석기가 근거 페이지와 좌표를 결과에 담을 수 있다. 기존 두 분석기는 고치지 않는다", "없으면 TSK-04·AMT-09 역추적 불가. 규격을 첫 주에 확정"),
    ]),
    ("G. 금액·비용추계", "AMT", B, [
        ("AMT-01", "금액 항목 추출", "신규", "P1", B, "ANL-13", "항목명·수량·단위·단가·금액·근거 페이지와 원문 인용을 구조화 스키마로 반환. 스키마에 없는 필드는 나올 수 없다", "문서에 없는 값은 비운다"),
        ("AMT-02", "금액 항목 승인 · 수정 UI", "신규", "P1", B, "AMT-01", "액션아이템과 같은 제안 카드 형식. 승인 전에는 어디에도 반영되지 않는다", "UI 패턴 재사용"),
        ("AMT-03", "검증 모드 — 문서 합계와 대조", "신규", "P1", B, "AMT-01", "항목 합계와 문서에 적힌 합계가 다르면 불일치 금액과 함께 표시된다", "금액만 가능한 검증"),
        ("AMT-04", "단가 마스터 관리", "신규", "P1", B, "", "단가마다 출처와 기준일이 있고 화면에 표시된다. 사람이 수정 가능", "최대 위험 — 범위 합의 필요"),
        ("AMT-05", "전제 입력 · 승인", "신규", "P1", B, "AMT-04", "계산에 필요한 전제가 비어 있으면 계산을 실행하지 않고 무엇이 빈지 알려준다", ""),
        ("AMT-06", "추계 계산", "신규", "P1", B, "AMT-05", "Python 이 계산한다. 같은 입력이면 항상 같은 결과가 나온다 (단위테스트로 확인)", "LLM 은 계산하지 않는다"),
        ("AMT-07", "불일치 · 미확정 태스크 제안", "신규", "P1", B, "TSK-03", "불일치 또는 전제 미확정 시 태스크 제안 카드가 생긴다. 자동 등록은 하지 않는다", "보드를 채우는 소재"),
        ("AMT-08", "프로젝트 금액 현황", "신규", "P2", B, "AMT-06", "계약금액·변경 증감·미확정 금액이 프로젝트 단위로 집계된다", ""),
        ("AMT-09", "금액 근거 역추적", "신규", "P1", B, "ANL-13", "금액 숫자를 누르면 문서 원문의 해당 위치가 하이라이트된다", "ocr_element_id 사용"),
        ("AMT-10", "비용추계서 서식 출력", "신규", "P3", B, "AMT-06", "확정된 항목을 서식에 배치한다. 생성이 아니라 배치", ""),
        ("AMT-11", "금액 열람 권한 분리", "신규", "P2", B, "PRJ-07", "", "미결 — VIEWER 노출 여부"),
    ]),
    ("H. 태스크·협업", "TSK", S, [
        ("TSK-01", "태스크 CRUD", "신규", "P1", S, "PRJ-01", "제목·설명·담당자·기한·상태를 사람이 직접 만들 수 있다", ""),
        ("TSK-02", "칸반 보드", "신규", "P1", S, "TSK-01", "할 일·진행 중·완료 3열, 열별 개수 표시, 드래그로 상태 변경", ""),
        ("TSK-03", "AI 제안 → 태스크 확정", "신규", "P1", S, "ANL-03", "승인해야 등록된다. 승인 전에는 보드에 나타나지 않는다", "자동 등록 금지 원칙"),
        ("TSK-04", "근거 역추적", "신규", "P1", S, "ANL-13", "태스크에서 출처를 누르면 문서 원문의 해당 문단이 하이라이트된다. 페이지 번호가 함께 표시된다", "ANL-13 없이는 불가"),
        ("TSK-05", "AI 생성 배지 · 필터", "신규", "P1", S, "TSK-03", "AI 생성 태스크가 구분 표시되고 AI생성만·기한임박·출처문서별 필터가 동작한다", "분석기별 구분 필요"),
        ("TSK-06", "담당자 · 기한 지정", "신규", "P1", S, "TSK-01", "AI 가 못 찾은 경우 미지정 상태로 남고 사람이 채운다", ""),
        ("TSK-07", "제안 거부", "신규", "P1", S, "TSK-03", "거부한 제안은 다시 뜨지 않는다. 거부 사실이 기록된다", "채택률 지표의 원천"),
        ("TSK-08", "일괄 승인", "신규", "P1", S, "TSK-03", "문서 단위로 여러 제안을 한 번에 승인할 수 있다", ""),
        ("TSK-09", "활동 로그", "신규", "P2", S, "PRJ-01", "", "activity_logs"),
        ("TSK-10", "알림 (이메일 · Slack)", "신규", "P3", S, "TSK-09", "", ""),
    ]),
    ("I. 가시성", "VIS", ALL, [
        ("VIS-01", "대시보드 지표 카드", "신규", "P2", ALL, "PRJ-01", "", "전체 문서·처리 중·열린 태스크·승인 대기"),
        ("VIS-02", "문서 유형 분포", "신규", "P2", ALL, "ANL-02", "", "유형별 분석기 목록 함께 표시"),
        ("VIS-03", "승인 대기 배너", "신규", "P1", ALL, "TSK-03", "승인 대기 건수와 출처 문서명이 보이고 검토 화면으로 이동한다", "분석기별로 나눠 표시"),
        ("VIS-04", "최근 문서", "신규", "P2", ALL, "DOC-08", "", ""),
        ("VIS-05", "이번 주 활동", "신규", "P2", ALL, "ANL-10", "", "분석기별 채택률 포함"),
        ("VIS-06", "통합 검색 (PostgreSQL FTS)", "신규", "P2", ALL, "PRJ-08", "", "프로젝트 스코프 안에서"),
        ("VIS-07", "시맨틱 검색 (pgvector)", "신규", "P3", ALL, "VIS-06", "", ""),
        ("VIS-08", "주간 자동 리포트", "신규", "P3", ALL, "VIS-05", "", ""),
        ("VIS-09", "활동 타임라인", "신규", "P2", ALL, "TSK-09", "", ""),
    ]),
    ("J. 공통·기반", "SYS", S, [
        ("SYS-01", "Alembic 마이그레이션", "신규", "P0", S, "", "create_all() 의존을 제거한다. 컬럼 추가가 데이터 유실 없이 반영된다", "P0 착수 전 완료"),
        ("SYS-02", "Celery + Redis", "신규", "P0", S, "", "워커가 죽어도 작업이 큐에 남고 재시작 시 이어진다", ""),
        ("SYS-03", "에러코드 체계", "확장", "P0", S, "", "기존 11종에 인증·권한·프로젝트 코드를 추가. 응답 형식이 일관된다", ""),
        ("SYS-04", "request_id 로깅", "기존", "P0", S, "", "요청 단위로 로그 추적 가능", ""),
        ("SYS-05", "Fake AI Client", "기존", "P0", S, "", "API 키 없이 전체 흐름이 동작한다", "병렬 작업의 전제"),
        ("SYS-06", "API 호출 쿼터", "신규", "P2", S, "", "", "프로젝트별 월 한도"),
        ("SYS-07", "N+1 방지", "신규", "P0", S, "", "목록 조회 쿼리 수가 문서 수와 무관하게 일정하다. selectinload 사용", "미니 2+2N 해소"),
        ("SYS-08", "FK 인덱스", "신규", "P0", S, "SYS-01", "모든 FK 에 명시적 인덱스. PostgreSQL 은 자동 생성하지 않는다", ""),
        ("SYS-09", "에러 로그 누락 수정", "확장", "P0", S, "", "404·409·413 이 서버 로그에 남는다", "미니 ISS-046. 첫날 수정"),
        ("SYS-10", "로컬 sLLM 옵션", "신규", "P3", S, "", "", ""),
    ]),
]


# ─────────────────────────────────────────────── 시트 1 · 기능명세

HEADERS = ["기능 ID", "영역", "기능명", "상태", "우선", "담당", "선행",
           "완료 판정 기준", "비고"]
WIDTHS = [(1, 11), (2, 17), (3, 36), (4, 7), (5, 7), (6, 8), (7, 11),
          (8, 62), (9, 30)]


def build_spec_sheet():
    rows = []
    total = sum(len(items) for _, _, _, items in AREAS)
    rows.append((22, [(1, f"DocFlow 기능명세서 — 전체 {total}건", S_TITLE)]))
    rows.append((30, [(i + 1, h, S_HDR) for i, h in enumerate(HEADERS)]))

    for area_name, _prefix, _owner, items in AREAS:
        n = len(items)
        p0 = sum(1 for it in items if it[3] == "P0")
        p1 = sum(1 for it in items if it[3] == "P1")
        label = f"{area_name}   ({n}건 · P0 {p0} · P1 {p1})"
        rows.append((20, [(1, label, S_GROUP)]
                     + [(c, "", S_GROUP) for c in range(2, 10)]))

        for fid, name, state, pri, owner, dep, done, note in items:
            # P2·P3 는 옅은 채움으로 시각적으로 뒤로 물린다
            minor = pri in ("P2", "P3")
            st_txt = S_SUB if minor else S_TXT
            st_cen = S_CENS if minor else S_CEN
            rows.append((None, [
                (1, fid, S_CENB if not minor else S_CENS),
                (2, area_name, st_txt),
                (3, name, S_TXTB if not minor else st_txt),
                (4, state, st_cen),
                (5, pri, st_cen),
                (6, owner, st_cen),
                (7, dep, st_txt),
                (8, done, st_txt),
                (9, note, st_txt),
            ]))

    last = len(rows)
    return sheet_xml(rows, WIDTHS, freeze=("A3", 0, 2),
                     autofilter=f"A2:I{last}")


# ─────────────────────────────────────────────── 시트 2 · 요약

def build_summary_sheet():
    rows = []
    rows.append((22, [(1, "요약", S_TITLE)]))
    rows.append((18, [(1, "구현 20일 (8/17~9/5 · 영업일 15일 · 3인 45 인일). "
                          "P0+P1 을 다 못 하므로 '묶기' 로 접근한다.", S_NOTE)]))

    rows.append((None, []))
    hdr = ["영역", "기능 수", "P0", "P1", "P2", "P3", "주 담당"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))

    tot = [0, 0, 0, 0, 0]
    for area_name, _p, owner, items in AREAS:
        c = {k: sum(1 for it in items if it[3] == k)
             for k in ("P0", "P1", "P2", "P3")}
        rows.append((None, [
            (1, area_name, S_TXT),
            (2, len(items), S_CEN),
            (3, c["P0"], S_CEN), (4, c["P1"], S_CEN),
            (5, c["P2"], S_CEN), (6, c["P3"], S_CEN),
            (7, owner, S_CEN),
        ]))
        tot[0] += len(items)
        for i, k in enumerate(("P0", "P1", "P2", "P3")):
            tot[i + 1] += c[k]

    rows.append((20, [(1, "합계", S_GROUP), (2, tot[0], S_GROUP),
                      (3, tot[1], S_GROUP), (4, tot[2], S_GROUP),
                      (5, tot[3], S_GROUP), (6, tot[4], S_GROUP),
                      (7, "", S_GROUP)]))

    rows.append((None, []))
    rows.append((20, [(1, "우선순위 정의", S_GROUP)]
                 + [(c, "", S_GROUP) for c in range(2, 4)]))
    for k, v in [
        ("P0", "MVP 필수. 없으면 '팀 도구' 가 성립하지 않는다"),
        ("P1", "차별화 핵심. 발표 데모의 중심"),
        ("P2", "확장. 없어도 데모가 성립한다"),
        ("P3", "향후. 발표에서 '향후 개선사항' 으로 배치한다"),
    ]:
        rows.append((None, [(1, k, S_CENB), (2, v, S_TXT), (3, "", S_TXT)]))

    rows.append((None, []))
    rows.append((20, [(1, "묶음 — 같은 골격을 쓰므로 함께 만들면 두 번째부터 싸다",
                       S_GROUP)] + [(c, "", S_GROUP) for c in range(2, 4)]))
    for k, v in [
        ("제안 골격", "ANL-03 AMT-01 TSK-03 TSK-04 TSK-05 TSK-07 TSK-08 — "
                    "제안 카드·승인·역추적 UI 를 공유한다. 분석기만 갈아 끼운다"),
        ("검수 골격", "REV-01~REV-07 REV-16~REV-18 — 박스 표시와 텍스트 수정이 하나로 묶인다"),
        ("스코프", "AUTH-* PRJ-* — 인증 없이 스코프가 성립하지 않는다"),
    ]:
        rows.append((None, [(1, k, S_CENB), (2, v, S_TXT), (3, "", S_TXT)]))

    return sheet_xml(rows, [(1, 24), (2, 78), (3, 20), (4, 8), (5, 8),
                            (6, 8), (7, 10)])


# ─────────────────────────────────────────────── 시트 3 · 분석기 라우팅

ROUTES = [
    ("회의록", "O", "O", "O", "비용 발생 요인만", "meeting_v1"),
    ("계약서", "O", "O", "조항 검토", "O", "contract_v1"),
    ("보고서", "O", "O", "O", "진행률 대비", "report_v1"),
    ("공지사항", "O", "O", "—", "—", "—"),
    ("메뉴얼", "O", "O", "—", "—", "—"),
    ("기타", "O", "O", "—", "—", "—"),
]


def build_route_sheet():
    rows = []
    rows.append((22, [(1, "분석기 라우팅 (ANL-04)", S_TITLE)]))
    rows.append((34, [(1, "문서 유형에 따라 실행할 분석기를 정한다. "
                          "분류(CATEGORY)는 라우팅 대상이 아니라 모든 문서에 "
                          "무조건 먼저 실행되는 고정 선행 단계다 — 분류 결과가 "
                          "라우팅 기준이 되므로 순환을 피해야 한다.", S_NOTE)]))
    rows.append((None, []))
    hdr = ["문서 유형 (document_type)", "요약", "분류", "액션아이템", "금액",
           "prompt_variant"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for r in ROUTES:
        rows.append((None, [
            (1, r[0], S_TXTB),
            (2, r[1], S_CEN), (3, r[2], S_CEN),
            (4, r[3], S_CEN), (5, r[4], S_CEN), (6, r[5], S_CEN),
        ]))
    rows.append((None, []))
    rows.append((44, [(1, "prompt_variant 가 필요한 이유 — 같은 액션아이템 "
                          "분석기라도 회의록(담당자·기한 중심)과 계약서(조항 검토 "
                          "중심)는 프롬프트가 달라야 한다. 목업 보드의 '하도급 계약 "
                          "조항 검토' 카드가 그 사례다.", S_NOTE)]))
    return sheet_xml(rows, [(1, 30), (2, 10), (3, 10), (4, 18), (5, 20),
                            (6, 18)])


# ─────────────────────────────────────────────── 시트 4 · 비기능

NFR = [
    ("성능", "10페이지 스캔 PDF 처리 완료 ≤ 60초", "동일 파일 3회 평균", ""),
    ("성능", "목록 조회 쿼리 수가 문서 수와 무관", "쿼리 로그 개수", "SYS-07"),
    ("동시성", "4~5인 동시 사용 시 정상 동작", "동시 업로드 5건", ""),
    ("정확도", "액션아이템 승인율 ≥ 70%", "TSK-07 거부 기록 기반", "TSK-07"),
    ("정확도", "카테고리 분류 정확도 ≥ 85%", "Golden Dataset", ""),
    ("정확도", "금액 항목 추출 정확도", "Golden Dataset · 원문 대조",
     "원문이 정답이라 측정 가능"),
    ("정확도", "금액 계산 정확도 = 100%", "단위테스트",
     "Python 이 계산하므로 AI 지표가 아니다"),
    ("보안", "타 프로젝트 데이터 접근 차단", "PRJ-08 침투 테스트", "PRJ-08"),
    ("보안", "API 키는 서버에만", "프론트 번들 검사", ""),
    ("안정성", "컨테이너 재기동 후 파일 유지", "재기동 후 다운로드", "DOC-14"),
]

NOGO = [
    ("실시간 공동 편집", "Notion·Google Docs 대체가 아니다"),
    ("간트 차트 등 본격 PMS", "범위 밖"),
    ("사람이 원가를 입력하는 비용 관리 모듈",
     "컨셉과 반대다. 우리는 문서에서 뽑는다"),
    ("모바일 네이티브 앱", "반응형 웹으로 대응"),
    ("법안 등 법률문서 자동 생성", "환각 위험·법적 책임·검증 부담"),
    ("파인튜닝", "20일에 자리가 없다. 프롬프트 + 구조화 출력으로 목표 달성 가능"),
]


def build_nfr_sheet():
    rows = []
    rows.append((22, [(1, "비기능 요구사항 · 하지 않을 것", S_TITLE)]))
    rows.append((None, []))
    hdr = ["구분", "요구", "측정 방법", "관련"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for a, b, c, d in NFR:
        rows.append((None, [(1, a, S_CEN), (2, b, S_TXT),
                            (3, c, S_TXT), (4, d, S_TXT)]))
    rows.append((None, []))
    rows.append((20, [(1, "하지 않을 것", S_GROUP)]
                 + [(c, "", S_GROUP) for c in range(2, 5)]))
    for a, b in NOGO:
        rows.append((None, [(1, "", S_TXT), (2, a, S_TXTB),
                            (3, b, S_TXT), (4, "", S_TXT)]))
    rows.append((None, []))
    rows.append((44, [(1, "'사람이 원가를 입력하는 모듈' 과 '문서에서 뽑은 금액 "
                          "집계·검증' 의 경계를 분명히 한다. 차이는 입력을 사람이 "
                          "하는가 문서가 하는가다.", S_NOTE)]))
    return sheet_xml(rows, [(1, 12), (2, 46), (3, 34), (4, 32)])


# ─────────────────────────────────────────────── 시트 5 · 미결

OPEN = [
    ("우선순위", 1, "P0+P1 78개, 구현 20일. 덜어내기보다 묶기로 접근",
     "요약 시트 묶음 3개 참고", "전원"),
    ("우선순위", 2, "액션아이템(ANL-03)과 금액(AMT-01) 중 무엇을 먼저",
     "액션아이템으로 골격 → 금액을 두 번째 분석기로", "전원"),
    ("우선순위", 3, "검수 2단계(REV-08~REV-15)를 P2 로 두는 데 동의하는지",
     "1단계만으로 금액 파트는 성립한다", "재정"),
    ("우선순위", 4, "ANL-13 Protocol 확장을 언제 하는지",
     "구현 첫 주에 규격만 확정. 페이크 값으로 병렬 진행", "전원"),
    ("설계", 5, "분석기 규격에 위치 정보 추가 (ANL-13)",
     "analyze(text, context=None). 기존 두 분석기는 안 고친다", "보현"),
    ("설계", 6, "파이프라인 단계 일반화 (ANL-05)",
     "목업·프론트·enum·백엔드 4곳이 걸린다", "세현"),
    ("설계", 7, "분류 결과를 라우팅 기준으로 격상 (document_type)",
     "분류를 고정 선행 단계로. documents 컬럼 의미가 바뀐다", "세현"),
    ("설계", 8, "분류가 틀렸을 때 사람이 document_type 을 고칠 수 있게 할지",
     "틀리면 라우팅도 틀린다", "세현"),
    ("설계", 9, "tasks 출처를 nullable FK 3개로 둘지",
     "FK 무결성을 DB 가 보장한다. source_type+source_id 는 못 건다", "세현"),
    ("설계", 10, "제안 거부를 result_json.decision 에 둘지 별도 테이블로 둘지",
     "채택률 지표의 원천", "보현"),
    ("설계", 11, "analyzer_routes 를 테이블로 둘지 코드 상수로 둘지",
     "테이블이면 설정 화면에 표로 보여줄 수 있다", "보현"),
    ("설계", 12, "단가 마스터 범위",
     "AMT 최대 위험. 소규모 자체 데이터로 고정하고 '데모 범위' 명시 권장", "보현"),
    ("설계", 13, "VIEWER 에게 금액 노출 여부 (AMT-11)",
     "노출 안 하면 조회 쿼리에 조건이 붙는다", "전원"),
    ("OCR DB", 14, "page_number 를 0 부터 셀지 1 부터 셀지",
     "1 부터. 화면 표시와 일치해 변환이 없다", "재정"),
    ("OCR DB", 15, "좌표 기준 이미지를 원본·렌더링본·전처리본 중 무엇으로",
     "렌더링본. 전처리본은 프리셋에 따라 달라진다", "재정"),
    ("OCR DB", 16, "polygon_json 저장 여부", "MVP 제외, 컬럼만 준비", "재정"),
    ("OCR DB", 17, "검수 완료 후 재수정 허용",
     "허용하고 IN_PROGRESS 로 되돌린다", "재정"),
    ("OCR DB", 18, "수정 이력을 MVP 부터 저장할지",
     "P2. 단 ocr_engine·engine_version·preprocess_info 는 MVP 부터", "재정"),
    ("OCR DB", 19, "박스 1개 수정이 ocr_revision 을 항상 올리는지",
     "올린다. 안 올리면 전파 사슬이 깨진다", "재정"),
    ("OCR DB", 20, "텍스트 재조립을 동기로 할지 비동기로 할지",
     "동기 · 같은 트랜잭션", "재정"),
    ("OCR DB", 21, "group_id 만 먼저 둘지 ocr_groups 를 처음부터 만들지",
     "group_id 먼저. ocr_groups 는 P2", "재정"),
    ("OCR DB", 22, "재OCR 결과가 기존 박스를 자동 교체할지",
     "사용자 확인 후 반영", "재정"),
    ("OCR DB", 23, "오래된 분석을 자동 재실행할지",
     "사용자 재실행 요구. 자동은 API 비용이 튄다", "보현"),
    ("운영", 24, "배포 환경 — 클라우드 · 온프레미스",
     "OCR GPU 필요 여부와 직결", "전원"),
    ("운영", 25, "AI 제공자 — OpenAI 유지 · 로컬 sLLM 병행",
     "1조 사례로 보아 상용 API 유지 권장", "전원"),
]


def build_open_sheet():
    rows = []
    rows.append((22, [(1, "미결 사항 — 착수 전 합의 필요", S_TITLE)]))
    rows.append((None, []))
    hdr = ["구분", "#", "안건", "제안 / 의견", "결정 주체", "결정", "결정일"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for cat, n, item, opinion, who in OPEN:
        rows.append((None, [
            (1, cat, S_CEN), (2, n, S_CEN),
            (3, item, S_TXTB), (4, opinion, S_TXT),
            (5, who, S_CEN), (6, "", S_TXT), (7, "", S_CEN),
        ]))
    rows.append((None, []))
    rows.append((32, [(1, "결정 열은 회의에서 채운다. 미채택 대안과 이유도 함께 "
                          "남긴다 — 미니 프로젝트 결정사항 29건과 같은 형식이다.",
                       S_NOTE)]))
    return sheet_xml(rows, [(1, 11), (2, 5), (3, 48), (4, 58), (5, 11),
                            (6, 26), (7, 12)],
                     freeze=("A4", 0, 3))


# ─────────────────────────────────────────────── 패키징

SHEETS = [
    ("기능명세", build_spec_sheet()),
    ("요약", build_summary_sheet()),
    ("분석기라우팅", build_route_sheet()),
    ("비기능·제외", build_nfr_sheet()),
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

    total = sum(len(items) for _, _, _, items in AREAS)
    print(f"생성 완료: {OUT.relative_to(ROOT)}")
    print(f"  시트 {len(SHEETS)}개 — " + " · ".join(n for n, _ in SHEETS))
    print(f"  기능 {total}건")
    for k in ("P0", "P1", "P2", "P3"):
        c = sum(1 for _, _, _, items in AREAS for it in items if it[3] == k)
        print(f"    {k}: {c}")
    print(f"  파일 크기: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
