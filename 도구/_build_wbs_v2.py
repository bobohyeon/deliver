# -*- coding: utf-8 -*-
"""관리/WBS(작업분할구조도)_v2.xlsx 를 만든다.

이 파일의 책임: 본프로젝트 작업분할구조와 간트 차트, 산출물 목록, 이슈·결정사항
  틀을 다섯 시트짜리 xlsx 로 만든다. 작업 데이터를 이 파일이 직접 들고 있으므로
  일정·인일 집계는 이 스크립트 출력을 정본으로 한다.
다른 파일과의 관계: 관리/기능명세서.md 의 기능 ID 와 관리/API_계약서_v2.md 의
  엔드포인트 번호를 인용한다. 일정 구간은 관리/작업인수인계.md 를 따른다.
Spring 비교: 없음 — 순수 문서 생성 스크립트다.

openpyxl 이 없고 네트워크도 막힌 환경이라 xlsx(zip + OOXML) 를 직접 쓴다.
미니 프로젝트 도구/_build_wbs.py 방식과 같고 스타일만 흑백 무채색으로 바꿨다.

사용:
    python3 도구/_build_wbs_v2.py
"""

import pathlib
import zipfile
from datetime import date, timedelta
from xml.sax.saxutils import escape

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "관리" / "WBS(작업분할구조도)_v2.xlsx"


# ─────────────────────────────────────────────── 달력

WEEKDAY = ["월", "화", "수", "목", "금", "토", "일"]

# 설계 5 + 구현 15(영업일) + 테스트 5 + 리허설 2(주말) = 27열
DAYS = []
for d in range(0, 35):
    day = date(2026, 8, 10) + timedelta(days=d)
    if day > date(2026, 9, 13):
        break
    if day.weekday() < 5:                      # 영업일
        DAYS.append(day)
    elif day >= date(2026, 9, 12):             # 리허설 주말만 포함
        DAYS.append(day)

DAY_KEY = [d.isoformat() for d in DAYS]
DAY_LABEL = [f"{d.month}/{d.day}\n{WEEKDAY[d.weekday()]}" for d in DAYS]
IS_WEEKEND = [d.weekday() >= 5 for d in DAYS]

PHASES = [
    ("설계·합의", "2026-08-10", "2026-08-14"),
    ("구현 1주", "2026-08-17", "2026-08-21"),
    ("구현 2주", "2026-08-24", "2026-08-28"),
    ("구현 3주", "2026-08-31", "2026-09-04"),
    ("테스트·산출물", "2026-09-07", "2026-09-11"),
    ("리허설·예비", "2026-09-12", "2026-09-13"),
]


def span(start, end):
    """시작~종료 사이의 DAY_KEY 인덱스 목록. 주말은 자동으로 빠진다."""
    return [i for i, k in enumerate(DAY_KEY) if start <= k <= end]


def workdays(start, end):
    return len(span(start, end))


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


def sheet_xml(rows, widths=None, freeze=None, autofilter=None, merges=None):
    cols = ""
    if widths:
        cols = "<cols>" + "".join(
            f'<col min="{c}" max="{c2}" width="{w}" customWidth="1"/>'
            for c, c2, w in widths) + "</cols>"

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
    mg = ""
    if merges:
        mg = (f'<mergeCells count="{len(merges)}">'
              + "".join(f'<mergeCell ref="{r}"/>' for r in merges)
              + "</mergeCells>")

    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetViews><sheetView workbookViewId="0" showGridLines="0">'
            f'{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16.5"/>'
            f'{cols}<sheetData>{"".join(body)}</sheetData>{af}{mg}'
            '<pageMargins left="0.2" right="0.2" top="0.4" bottom="0.4" '
            'header="0.3" footer="0.3"/></worksheet>')


# ─────────────────────────────────────────────── 스타일 (흑백)
STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="8">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="15"/><name val="맑은 고딕"/></font>
<font><b/><sz val="9"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF767676"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
<font><b/><sz val="8"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="7">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF000000"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFE0E0E0"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF6F6F6"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF555555"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEDEDED"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFC8C8C8"/></left>
<right style="thin"><color rgb="FFC8C8C8"/></right>
<top style="thin"><color rgb="FFC8C8C8"/></top>
<bottom style="thin"><color rgb="FFC8C8C8"/></bottom>
<diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="15">
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
<xf numFmtId="0" fontId="0" fillId="2" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1"/>
<xf numFmtId="0" fontId="0" fillId="6" borderId="1" xfId="0" applyFill="1" applyBorder="1"/>
<xf numFmtId="0" fontId="6" fillId="5" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="7" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

S_TITLE, S_HDR, S_GROUP, S_TXT, S_CEN, S_CENB = 1, 2, 3, 4, 5, 6
S_NOTE, S_SUB, S_TXTB = 7, 8, 9
S_BAR, S_EMPTY, S_WEEKEND, S_PHASE, S_MILE = 10, 11, 12, 13, 14


# ─────────────────────────────────────────────── 작업 데이터
# (ID, 대분류, 중분류, 작업명, 기능ID, 담당, 시작, 종료, 산출물, 마일스톤)
A, J, B, ALL = "세현", "재정", "보현", "전원"

TASKS = [
    # ── 1. 설계·합의
    ("1", "설계·합의", "", "", "", "", "", "", "", False),
    ("1.1", "", "범위·컨셉 확정", "", "", "", "", "", "", False),
    ("1.1.1", "", "", "기능명세서 116건 검토·합의", "전 영역", ALL, "2026-08-10", "2026-08-11", "기능명세서 확정", False),
    ("1.1.2", "", "", "폐기 설계 6건 공유·승인 (폐기 ID)", "ANL-04·ANL-13·AMT-04·AMT-05·AMT-10·VIS-08", B, "2026-08-10", "2026-08-10", "폐기 기록", False),
    ("1.1.3", "", "", "P1 45건 내부 우선순위 재정렬", "", ALL, "2026-08-11", "2026-08-11", "우선순위 확정", False),
    ("1.2", "", "설계 확정", "", "", "", "", "", "", False),
    ("1.2.1", "", "", "DB 모델링 확정 (DBML → PostgreSQL DDL)", "SYS-01", "세현·보현", "2026-08-11", "2026-08-11", "DDL 스크립트", False),
    ("1.2.2", "", "", "action_items 테이블 추가 여부 결정", "TSK-03", ALL, "2026-08-11", "2026-08-11", "결정사항", False),
    ("1.2.3", "", "", "API 계약서 v2 합의 (엔드포인트 50개)", "전 영역", ALL, "2026-08-12", "2026-08-12", "API 계약서 확정", True),
    ("1.2.4", "", "", "Pydantic 스키마 작성", "", B, "2026-08-12", "2026-08-13", "schemas/*.py", False),
    ("1.2.5", "", "", "페이크 응답 준비 (분석기 4종)", "SYS-05", B, "2026-08-13", "2026-08-13", "fake_client 확장", False),
    ("1.3", "", "계획 수립", "", "", "", "", "", "", False),
    ("1.3.1", "", "", "WBS v2 확정", "", B, "2026-08-13", "2026-08-13", "WBS v2", False),
    ("1.3.2", "", "", "통합테스트 시나리오 틀 작성", "", B, "2026-08-13", "2026-08-14", "통합테스트 시나리오", False),
    ("1.3.3", "", "", "역할 분담 확정 · 킥오프", "", ALL, "2026-08-14", "2026-08-14", "킥오프 회의록", True),

    # ── 2. 기반 정비
    ("2", "기반 정비", "", "", "", "", "", "", "", False),
    ("2.0", "", "미니 프로젝트 자산 (수정 없음)", "", "", "", "", "", "", False),
    ("2.0.1", "", "", "재사용 확인만 — 작업 없음", "DOC-02·DOC-03·DOC-04·ANL-01·ANL-07·ANL-08·SYS-04·SYS-05", ALL, "2026-08-17", "2026-08-17", "재사용 점검표", False),
    ("2.1", "", "선행 결함 수정", "", "", "", "", "", "", False),
    ("2.1.1", "", "", "에러 로그 누락 수정 (미니 ISS-046)", "SYS-09", A, "2026-08-17", "2026-08-17", "코드", False),
    ("2.2", "", "마이그레이션·큐", "", "", "", "", "", "", False),
    ("2.2.1", "", "", "Alembic 도입 · 초기 마이그레이션", "SYS-01", A, "2026-08-17", "2026-08-18", "migrations/", False),
    ("2.2.2", "", "", "documents.project_id 3단계 전환", "SYS-01", A, "2026-08-18", "2026-08-18", "마이그레이션", False),
    ("2.2.3", "", "", "Celery + Redis 구성", "SYS-02", A, "2026-08-18", "2026-08-20", "docker-compose", False),
    ("2.3", "", "공통 규약", "", "", "", "", "", "", False),
    ("2.3.1", "", "", "에러코드 23종 확장 · 응답 형식 통일", "SYS-03", A, "2026-08-19", "2026-08-19", "error_codes.py", False),
    ("2.3.2", "", "", "N+1 방지 · FK 인덱스 컨벤션 공유", "SYS-07·SYS-08", A, "2026-08-20", "2026-08-20", "코드 컨벤션 문서", False),
    ("2.4", "", "인증", "", "", "", "", "", "", False),
    ("2.4.1", "", "", "회원가입·로그인·토큰 갱신 (API 1~4)", "AUTH-01~04", A, "2026-08-19", "2026-08-21", "코드", False),
    ("2.4.2", "", "", "get_current_user 의존성 · 전 API 적용 확인", "AUTH-05", A, "2026-08-21", "2026-08-21", "적용 목록", True),

    # ── 3. 협업 기반
    ("3", "협업 기반", "", "", "", "", "", "", "", False),
    ("3.1", "", "프로젝트·권한", "", "", "", "", "", "", False),
    ("3.1.1", "", "", "프로젝트 CRUD · 보관 (API 6~10)", "PRJ-01~05", A, "2026-08-24", "2026-08-25", "코드", False),
    ("3.1.2", "", "", "멤버 초대·역할 관리 (API 11~14)", "PRJ-06·PRJ-07", A, "2026-08-25", "2026-08-26", "코드", False),
    ("3.1.3", "", "", "리포지토리 계층 스코프 강제", "PRJ-08", A, "2026-08-26", "2026-08-27", "코드 + 침투 테스트", True),
    ("3.2", "", "비동기·저장소", "", "", "", "", "", "", False),
    ("3.2.1", "", "", "업로드 202 전환 · 워커 파이프라인 (API 15)", "DOC-06", A, "2026-08-24", "2026-08-26", "코드", False),
    ("3.2.2", "", "", "파일 저장소 S3·MinIO 이전", "DOC-14", A, "2026-08-27", "2026-08-28", "코드", False),
    ("3.3", "", "태스크", "", "", "", "", "", "", False),
    ("3.3.1", "", "", "tasks 스키마 확장 (completed_at·출처 FK·CHECK)", "TSK-01", A, "2026-08-24", "2026-08-24", "마이그레이션", False),
    ("3.3.2", "", "", "태스크 CRUD · 칸반 보드 · 담당자·기한 (API 38~41)", "TSK-01·TSK-02·TSK-06", A, "2026-08-27", "2026-09-01", "코드", False),
    ("3.3.3", "", "", "AI 생성 배지 · 필터 · 출처 표시", "TSK-04·TSK-05", A, "2026-09-01", "2026-09-02", "코드", False),

    # ── 4. 문서·검수
    ("4", "문서 처리·검수", "", "", "", "", "", "", "", False),
    ("4.1", "", "업로드·처리", "", "", "", "", "", "", False),
    ("4.1.1", "", "", "다중 업로드 · 처리 모드 · 유형 지정", "DOC-01·DOC-05·DOC-16", J, "2026-08-17", "2026-08-19", "코드", False),
    ("4.1.2", "", "", "진행 상태 폴링 steps 응답 (API 18)", "DOC-07", J, "2026-08-19", "2026-08-20", "코드", False),
    ("4.1.3", "", "", "문서 목록·상세·삭제·원본 다운로드", "DOC-08~11", B, "2026-08-17", "2026-08-19", "코드", False),
    ("4.2", "", "OCR 검수 1단계", "", "", "", "", "", "", False),
    ("4.2.1", "", "", "페이지 이미지 생성 · document_pages 저장", "REV-01", J, "2026-08-20", "2026-08-21", "코드", False),
    ("4.2.2", "", "", "ocr_elements 비율 좌표 저장", "REV-02", J, "2026-08-21", "2026-08-24", "코드", False),
    ("4.2.3", "", "", "Bounding Box 표시 · 신뢰도별 구분", "REV-03·REV-04", J, "2026-08-24", "2026-08-26", "검수 화면", False),
    ("4.2.4", "", "", "박스 선택·텍스트 수정 · 낙관적 락", "REV-05·REV-16", J, "2026-08-26", "2026-08-28", "코드", False),
    ("4.2.5", "", "", "낮은 신뢰도 모아보기", "REV-06", J, "2026-08-28", "2026-08-28", "코드", False),
    ("4.2.6", "", "", "텍스트 재조립 · revision 전파", "REV-17·REV-18", J, "2026-08-31", "2026-09-01", "코드", True),
    ("4.2.7", "", "", "검수 완료 처리 → 분석 1회 실행", "REV-07", J, "2026-09-01", "2026-09-02", "코드", False),
    ("4.3", "", "일괄 처리", "", "", "", "", "", "", False),
    ("4.3.1", "", "", "다중 파일 순차 업로드 · 처리 대기열", "BAT-01·BAT-02", J, "2026-09-02", "2026-09-04", "코드", False),
    ("4.4", "", "검수 2단계 (P2 · 여유 시)", "", "", "", "", "", "", False),
    ("4.4.1", "", "", "박스 이동·생성·삭제·재OCR·단락 편집", "REV-08~REV-15", J, "2026-09-01", "2026-09-04", "코드", False),

    # ── 5. 분석·제안
    ("5", "분석·제안", "", "", "", "", "", "", "", False),
    ("5.1", "", "분석기", "", "", "", "", "", "", False),
    ("5.1.1", "", "", "분류 분석기 7종 확장 + reason", "ANL-02", B, "2026-08-17", "2026-08-18", "코드", False),
    ("5.1.2", "", "", "extract 분석기 (액션·결정·일정)", "ANL-03·ANL-14·ANL-15", B, "2026-08-18", "2026-08-21", "코드 + 프롬프트", False),
    ("5.1.3", "", "", "amount 분석기 (금액 항목)", "AMT-01", B, "2026-08-21", "2026-08-25", "코드 + 프롬프트", False),
    ("5.1.4", "", "", "gather 4개 병렬 실행 · 진행률 일반화", "ANL-05", B, "2026-08-25", "2026-08-26", "코드", False),
    ("5.1.5", "", "", "확정 텍스트 기준 분석 · revision 기록 · 재분석", "ANL-06·DOC-12", B, "2026-08-26", "2026-08-27", "코드", False),
    ("5.2", "", "제안 승인", "", "", "", "", "", "", False),
    ("5.2.1", "", "", "제안 4종 조회 API · 판단 근거 표시 (API 35)", "ANL-03·AMT-01·AMT-09", B, "2026-08-27", "2026-08-28", "코드", False),
    ("5.2.2", "", "", "승인·수정·거부 + 태스크 생성 (API 36·37)", "TSK-03·TSK-07·TSK-08", "보현·세현", "2026-08-28", "2026-09-01", "코드", True),
    ("5.2.3", "", "", "제안 카드 UI (공통 컴포넌트)", "AMT-02", A, "2026-09-01", "2026-09-02", "프론트", False),
    ("5.3", "", "금액 집계", "", "", "", "", "", "", False),
    ("5.3.1", "", "", "합계 대조 (항목 합계 vs 문서 기재)", "AMT-03", B, "2026-08-31", "2026-09-01", "코드 + 단위테스트", False),
    ("5.3.2", "", "", "프로젝트 금액 집계 · 불일치 태스크 제안", "AMT-06·AMT-07", B, "2026-09-01", "2026-09-02", "코드", False),

    # ── 6. 산출물
    ("6", "산출물", "", "", "", "", "", "", "", False),
    ("6.1", "", "산출물 기반", "", "", "", "", "", "", False),
    ("6.1.1", "", "", "산출물 페이지 · 기간 선택 · 형식 선택", "DLV-01·DLV-02·DLV-08", "보현·세현", "2026-08-31", "2026-09-01", "프론트", False),
    ("6.1.2", "", "", "생성 대상 미리보기 (API 42)", "DLV-03", B, "2026-09-01", "2026-09-02", "코드", False),
    ("6.2", "", "산출물 생성", "", "", "", "", "", "", False),
    ("6.2.1", "", "", "주간 보고서 생성 (LLM 1회 + 집계)", "DLV-04", B, "2026-09-02", "2026-09-03", "코드 + 템플릿", True),
    ("6.2.2", "", "", "결정사항 대장 · 다음 회의 안건", "DLV-05·DLV-06", B, "2026-09-03", "2026-09-04", "코드 + 템플릿", False),
    ("6.2.3", "", "", "생성 이력 · 다운로드 · 갱신 판정", "DLV-09·DLV-10", B, "2026-09-03", "2026-09-04", "코드", False),

    # ── 7. 가시성 (P2)
    ("7", "가시성 (P2)", "", "", "", "", "", "", "", False),
    ("7.1", "", "대시보드·검색", "", "", "", "", "", "", False),
    ("7.1.1", "", "", "지표 카드 · 유형 분포 · 최근 문서", "VIS-01·VIS-02·VIS-04", ALL, "2026-09-02", "2026-09-03", "프론트", False),
    ("7.1.2", "", "", "승인 대기 배너 · 이번 주 활동", "VIS-03·VIS-05", ALL, "2026-09-03", "2026-09-03", "프론트", False),
    ("7.1.3", "", "", "통합 검색 (PostgreSQL FTS)", "VIS-06", ALL, "2026-09-03", "2026-09-04", "코드", False),

    # ── 8. 통합·측정
    ("8", "통합·측정", "", "", "", "", "", "", "", False),
    ("8.1", "", "통합", "", "", "", "", "", "", False),
    ("8.1.1", "", "", "전 기능 통합 · 시연 시나리오 점검", "", ALL, "2026-09-03", "2026-09-04", "시연 대본", False),
    ("8.2", "", "측정", "", "", "", "", "", "", False),
    ("8.2.1", "", "", "처리 시간 · 토큰 · 쿼리 수 측정", "", B, "2026-09-03", "2026-09-04", "측정 결과표", False),
    ("8.2.2", "", "", "분석기 4개 vs 통합 1개 비교 측정", "ANL-03", B, "2026-09-04", "2026-09-04", "비교표", False),
    ("8.3", "", "프리즈", "", "", "", "", "", "", False),
    ("8.3.1", "", "", "코드 프리즈", "", ALL, "2026-09-04", "2026-09-04", "", True),

    # ── 9. 테스트·산출물
    ("9", "테스트·산출물", "", "", "", "", "", "", "", False),
    ("9.1", "", "테스트 실행", "", "", "", "", "", "", False),
    ("9.1.1", "", "", "단위테스트 실행·판정", "", ALL, "2026-09-07", "2026-09-08", "단위테스트결과서", False),
    ("9.1.2", "", "", "통합테스트 실행·판정 (완료 판정 기준 기반)", "", ALL, "2026-09-08", "2026-09-09", "통합테스트결과서", False),
    ("9.1.3", "", "", "결함 조치 · 이슈 대장 마감", "", ALL, "2026-09-09", "2026-09-10", "이슈관리 시트", False),
    ("9.2", "", "문서 산출물", "", "", "", "", "", "", False),
    ("9.2.1", "", "", "화면정의서 갱신", "", B, "2026-09-07", "2026-09-08", "화면정의서", False),
    ("9.2.2", "", "", "WBS 갱신 · 결정사항 정리", "", B, "2026-09-08", "2026-09-09", "WBS v3", False),
    ("9.2.3", "", "", "완료보고서 작성", "", ALL, "2026-09-09", "2026-09-10", "완료보고서", False),
    ("9.2.4", "", "", "발표자료 작성", "", ALL, "2026-09-10", "2026-09-11", "발표자료", True),

    # ── 10. 리허설
    ("10", "리허설·예비", "", "", "", "", "", "", "", False),
    ("10.1", "", "리허설", "", "", "", "", "", "", False),
    ("10.1.1", "", "", "리허설 1회 · 시연 환경 점검", "", ALL, "2026-09-12", "2026-09-12", "리허설 기록", False),
    ("10.1.2", "", "", "리허설 2회 · 예비일", "", ALL, "2026-09-13", "2026-09-13", "", True),
]


# ─────────────────────────────────────────────── 시트 1 · WBS

GANTT_START = 11          # K열부터 간트


def build_wbs_sheet():
    rows = []
    rows.append((24, [(1, "DocFlow WBS v2 — 본프로젝트 작업분할구조도", S_TITLE)]))

    # 구간 머리글
    phase_cells = [(c, "", S_PHASE) for c in range(1, GANTT_START)]
    for name, s, e in PHASES:
        idxs = span(s, e)
        for n, i in enumerate(idxs):
            phase_cells.append((GANTT_START + i,
                                name if n == 0 else "", S_PHASE))
    rows.append((26, phase_cells))

    hdr = ["ID", "대분류", "중분류", "작업명", "기능 ID", "담당",
           "시작", "종료", "일수", "산출물"]
    hdr_cells = [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]
    for i, label in enumerate(DAY_LABEL):
        hdr_cells.append((GANTT_START + i, label, S_HDR))
    rows.append((34, hdr_cells))

    for tid, big, mid, name, fid, owner, s, e, out, mile in TASKS:
        depth = tid.count(".")
        if depth == 0:                      # 대분류
            cells = [(1, tid, S_GROUP), (2, big, S_GROUP)]
            cells += [(c, "", S_GROUP) for c in range(3, GANTT_START)]
            cells += [(GANTT_START + i, "", S_GROUP) for i in range(len(DAYS))]
            rows.append((20, cells))
            continue
        if depth == 1:                      # 중분류
            cells = [(1, tid, S_CENB), (2, "", S_TXT), (3, mid, S_TXTB)]
            cells += [(c, "", S_TXT) for c in range(4, GANTT_START)]
            cells += [(GANTT_START + i,
                       "", S_WEEKEND if IS_WEEKEND[i] else S_EMPTY)
                      for i in range(len(DAYS))]
            rows.append((None, cells))
            continue

        d = workdays(s, e)
        cells = [
            (1, tid, S_CEN), (2, "", S_TXT), (3, "", S_TXT),
            (4, name, S_TXTB if mile else S_TXT),
            (5, fid, S_SUB), (6, owner, S_CEN),
            (7, s[5:], S_CEN), (8, e[5:], S_CEN), (9, d, S_CEN),
            (10, out, S_SUB),
        ]
        filled = set(span(s, e))
        for i in range(len(DAYS)):
            if i in filled:
                st = S_MILE if (mile and i == max(filled)) else S_BAR
                cells.append((GANTT_START + i, "M" if st == S_MILE else "", st))
            else:
                cells.append((GANTT_START + i, "",
                              S_WEEKEND if IS_WEEKEND[i] else S_EMPTY))
        rows.append((None, cells))

    last = len(rows)
    widths = [(1, 1, 7), (2, 2, 15), (3, 3, 19), (4, 4, 44), (5, 5, 24),
              (6, 6, 9), (7, 7, 7), (8, 8, 7), (9, 9, 5), (10, 10, 22),
              (GANTT_START, GANTT_START + len(DAYS) - 1, 3.4)]
    return sheet_xml(rows, widths, freeze=("K4", 10, 3),
                     autofilter=f"A3:J{last}")


# ─────────────────────────────────────────────── 시트 2 · 산출물목록

DELIVERABLES = [
    ("D-01", "기능명세서", "설계", B, "2026-08-11", "완료", "관리/기능명세서.md · 산출물/기능명세서.xlsx"),
    ("D-02", "DB 스키마 (DBML)", "설계", B, "2026-08-11", "완료", "관리/DocFlow_DB.dbml"),
    ("D-03", "API 계약서 v2", "설계", B, "2026-08-12", "작성 완료 · 합의 대기", "관리/API_계약서_v2.md"),
    ("D-04", "Pydantic 스키마", "설계", B, "2026-08-13", "예정", "backend/app/schemas/"),
    ("D-05", "WBS v2", "관리", B, "2026-08-13", "완료", "관리/WBS(작업분할구조도)_v2.xlsx"),
    ("D-06", "통합테스트 시나리오", "테스트", B, "2026-08-14", "예정", "완료 판정 기준을 기대결과로 옮긴다"),
    ("D-07", "단위테스트 체크리스트", "테스트", ALL, "2026-08-28", "예정", "구현과 병행해서 쌓는다"),
    ("D-08", "화면정의서", "산출물", B, "2026-09-08", "예정", "화면이 끝날 때마다 갱신"),
    ("D-09", "단위테스트결과서", "산출물", ALL, "2026-09-08", "예정", ""),
    ("D-10", "통합테스트결과서", "산출물", ALL, "2026-09-09", "예정", ""),
    ("D-11", "이슈 대장", "관리", ALL, "2026-09-10", "진행", "발생 즉시 기록"),
    ("D-12", "결정사항 대장", "관리", ALL, "2026-09-10", "진행", "미채택 대안과 이유 포함"),
    ("D-13", "완료보고서", "산출물", ALL, "2026-09-10", "예정", ""),
    ("D-14", "발표자료", "산출물", ALL, "2026-09-11", "예정", "흑백 · 한 장에 한 주장"),
    ("D-15", "시연 대본", "산출물", ALL, "2026-09-11", "예정", "스캔 계약변경합의서 한 흐름"),
]


def build_deliverable_sheet():
    rows = [(24, [(1, "산출물 목록", S_TITLE)]),
            (34, [(1, "구현과 병행해서 쌓는다. 테스트·산출물 5일에는 새로 쓰지 않고 "
                      "실행과 판정에만 쓴다 — 미니 프로젝트에서 프리즈 뒤로 몰린 것을 "
                      "되풀이하지 않기 위한 것이다.", S_NOTE)]),
            (None, [])]
    hdr = ["ID", "산출물", "구분", "담당", "완료 예정", "상태", "위치 · 비고"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for r in DELIVERABLES:
        rows.append((None, [(1, r[0], S_CENB), (2, r[1], S_TXTB), (3, r[2], S_CEN),
                            (4, r[3], S_CEN), (5, r[4][5:], S_CEN),
                            (6, r[5], S_CEN), (7, r[6], S_TXT)]))
    return sheet_xml(rows, [(1, 1, 7), (2, 2, 26), (3, 3, 10), (4, 4, 9),
                            (5, 5, 11), (6, 6, 18), (7, 7, 52)],
                     freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 시트 3 · 이슈관리

ISSUES = [
    ("ISS-001", "2026-08-10", "설계", "미니 프로젝트 ISS-046 이관 — business_error_handler 에 "
     "로그 호출이 없어 404·409·413 이 서버 로그에 안 남는다", A, "조치 예정",
     "SYS-09. 구현 첫날 수정", "2026-08-17"),
]


def build_issue_sheet():
    rows = [(24, [(1, "이슈 관리", S_TITLE)]),
            (34, [(1, "담당자별로 표를 나누지 않는다. 미니 프로젝트에서 두 표로 나뉘어 "
                      "ID 가 중복된 사례가 있었다 (ISS-037). 발생 즉시 기록한다.", S_NOTE)]),
            (None, [])]
    hdr = ["ID", "발생일", "구분", "현상", "담당", "상태", "원인 · 조치", "조치일"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for r in ISSUES:
        rows.append((None, [(1, r[0], S_CENB), (2, r[1][5:], S_CEN), (3, r[2], S_CEN),
                            (4, r[3], S_TXT), (5, r[4], S_CEN), (6, r[5], S_CEN),
                            (7, r[6], S_TXT), (8, r[7][5:], S_CEN)]))
    for n in range(2, 26):          # 빈 행
        rows.append((None, [(1, f"ISS-{n:03d}", S_SUB)]
                    + [(c, "", S_SUB) for c in range(2, 9)]))
    return sheet_xml(rows, [(1, 1, 9), (2, 2, 8), (3, 3, 10), (4, 4, 56),
                            (5, 5, 9), (6, 6, 11), (7, 7, 50), (8, 8, 8)],
                     freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 시트 4 · 결정사항

DECISIONS = [
    ("DEC-001", "2026-08-10", "제품 정의를 '문서를 올리면 프로젝트 문서가 나오는 도구' 로 잡는다",
     "태스크 보드만으로는 '그 모음집으로 뭘 하나' 에 답이 없었다. 산출물 생성을 제품의 출력으로 둔다",
     "태스크 보드까지만 두고 끝낸다 — 출력물이 없어 가치가 안 보인다", ALL),
    ("DEC-002", "2026-08-10", "분석기를 4개로 두고 문서 유형 구분 없이 항상 다 돌린다",
     "회의록·보고서에도 금액이 나온다. 유형으로 껐다 켜면 놓친다. gather 한 번으로 병렬이 유지된다",
     "① 유형별 선택 규칙(analyzer_rules) — 분류를 먼저 돌려야 해서 gather 가 두 단계로 쪼개진다 "
     "② 통합 1개 — 토큰 75% 싸지만 기존 코드 회귀 위험과 금액 정확도 저하", ALL),
    ("DEC-003", "2026-08-10", "근거를 페이지·좌표 대신 reason(판단 근거 서술)으로 표시한다",
     "분석기 규격이 텍스트만 받아 페이지를 모른다. 규격을 바꾸면 세 사람이 인터페이스를 기다린다",
     "① Protocol 확장(ANL-13) ② 인용문 문자열 매칭 — LLM 이 원문을 그대로 안 내면 실패", ALL),
    ("DEC-004", "2026-08-10", "금액은 추계가 아니라 집계로 한다",
     "단가 마스터가 없어도 성립하고 '그 숫자 근거가 뭐냐' 에 전부 문서에서 나왔다고 답할 수 있다",
     "① 단가 x 수량 추계 — 단가 근거를 댈 수 없다 ② 비용추계서 서식 — 타깃 사용자와 안 맞는다", ALL),
    ("DEC-005", "2026-08-10", "문서 유형을 7종으로 늘린다 (계약변경 추가)",
     "원계약은 계약금액, 변경합의서는 증감액을 뽑아 프롬프트 힌트가 달라야 한다",
     "프롬프트가 스스로 판단 — 그게 또 하나의 분류 문제가 되고 틀렸을 때 고칠 방법이 없다", ALL),
    ("DEC-006", "2026-08-10", "구현을 20일로 못박고 테스트·산출물 5일을 남긴다",
     "미니 프로젝트에서 산출물이 코드 프리즈 뒤로 몰려 발표 준비가 빡빡했다",
     "기획안 로드맵 8주 — 8/10 부터 8주면 10/4 로 마감(9/13)을 3주 넘긴다", ALL),
    ("DEC-007", "", "action_items 테이블을 추가할지", "", "", ALL),
    ("DEC-008", "", "tasks.completed_at 추가", "", "", A),
    ("DEC-009", "", "VIEWER 에게 금액을 노출할지", "", "", ALL),
    ("DEC-010", "", "검수 2단계를 P2 로 둘지", "", "", J),
]


def build_decision_sheet():
    rows = [(24, [(1, "결정 사항", S_TITLE)]),
            (34, [(1, "결정 내용과 함께 미채택 대안과 그 이유를 남긴다. 발표 "
                      "'수행절차 및 방법' 에 그대로 쓴다 — 미니 프로젝트 결정사항 "
                      "29건과 같은 형식이다.", S_NOTE)]),
            (None, [])]
    hdr = ["ID", "결정일", "결정 내용", "근거", "미채택 대안과 이유", "결정 주체"]
    rows.append((26, [(i + 1, h, S_HDR) for i, h in enumerate(hdr)]))
    for r in DECISIONS:
        decided = bool(r[1])
        st = S_TXT if decided else S_SUB
        rows.append((None, [(1, r[0], S_CENB if decided else S_CEN),
                            (2, r[1][5:] if decided else "미결", S_CEN),
                            (3, r[2], S_TXTB if decided else st),
                            (4, r[3], st), (5, r[4], st), (6, r[5], S_CEN)]))
    for n in range(11, 31):
        rows.append((None, [(1, f"DEC-{n:03d}", S_SUB)]
                    + [(c, "", S_SUB) for c in range(2, 7)]))
    return sheet_xml(rows, [(1, 1, 9), (2, 2, 8), (3, 3, 46), (4, 4, 48),
                            (5, 5, 56), (6, 6, 10)], freeze=("A5", 0, 4))


# ─────────────────────────────────────────────── 시트 5 · 인일 배분

def workload():
    per = {}
    for tid, _b, _m, _n, _f, owner, s, e, _o, _mi in TASKS:
        if tid.count(".") != 2 or not owner:
            continue
        d = workdays(s, e)
        for who in owner.replace("·", " ").split():
            who = {"전원": None}.get(who, who)
            if who is None:
                for x in (A, J, B):
                    per[x] = per.get(x, 0) + d
            else:
                per[who] = per.get(who, 0) + d
    return per


def solo_workload():
    """전원 작업을 뺀 개별 배정. 균형 판단은 이 값으로 한다."""
    per = {A: 0, J: 0, B: 0}
    for tid, _b, _m, _n, _f, owner, s, e, _o, _mi in TASKS:
        if tid.count(".") != 2 or not owner or owner == ALL:
            continue
        d = workdays(s, e)
        for who in owner.replace("·", " ").split():
            if who in per:
                per[who] += d
    return per


def build_load_sheet():
    per = workload()
    rows = [(24, [(1, "인일 배분 · 일정 요약", S_TITLE)]), (None, [])]

    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["구간", "시작", "종료", "영업일", "할 일"])]))
    phase_note = {
        "설계·합의": "범위 확정 · DB 모델링 · API 계약 · WBS · 역할 분담",
        "구현 1주": "기반 정비(Alembic·Celery·인증) + 각 파트 착수",
        "구현 2주": "협업 기반 · 검수 화면 · 분석기 4개",
        "구현 3주": "제안 승인 · 금액 집계 · 산출물 생성. 9/4 코드 프리즈",
        "테스트·산출물": "테스트 실행·판정 + 문서 마감",
        "리허설·예비": "리허설 2회 · 시연 환경 점검",
    }
    tot = 0
    for name, s, e in PHASES:
        d = workdays(s, e)
        tot += d
        rows.append((None, [(1, name, S_TXTB), (2, s[5:], S_CEN), (3, e[5:], S_CEN),
                            (4, d, S_CEN), (5, phase_note[name], S_TXT)]))
    rows.append((20, [(1, "합계", S_GROUP), (2, "", S_GROUP), (3, "", S_GROUP),
                      (4, tot, S_GROUP), (5, "", S_GROUP)]))

    rows.append((None, []))
    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["담당", "배정 인일", "주 영역", "", ""])]))
    area = {A: "기반·인증·프로젝트·태스크·비동기·저장소",
            J: "업로드·처리 모드·OCR 검수·일괄 처리",
            B: "분석기 4개·제안 승인·금액 집계·산출물 생성·문서 조회"}
    for who in (A, J, B):
        rows.append((None, [(1, who, S_TXTB), (2, per.get(who, 0), S_CEN),
                            (3, area[who], S_TXT), (4, "", S_TXT), (5, "", S_TXT)]))
    rows.append((20, [(1, "합계", S_GROUP), (2, sum(per.values()), S_GROUP),
                      (3, "", S_GROUP), (4, "", S_GROUP), (5, "", S_GROUP)]))

    rows.append((None, []))
    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["담당", "개별 작업", "공동(전원)", "합계", "비고"])]))
    solo = solo_workload()
    common = per[A] - solo[A]
    for who in (A, J, B):
        rows.append((None, [(1, who, S_TXTB), (2, solo[who], S_CEN),
                            (3, common, S_CEN), (4, per.get(who, 0), S_CEN),
                            (5, "", S_TXT)]))
    rows.append((76, [(1, "개별 작업이 한쪽으로 쏠려 있다. 보현이 재정보다 두 배 "
                         "가깝다. 원인은 두 가지다 — 분석기 4개·제안 승인·금액 집계·"
                         "산출물 생성이 한 파트에 모여 있고, 검수 2단계(REV-08~15, "
                         "P2 8건)를 짧게 잡아 재정 쪽이 과소평가됐다. "
                         "킥오프(1.3.3)에서 조정해야 한다. 조정 후보는 "
                         "① 산출물 UI 를 세현과 더 나눈다 "
                         "② DLV-07 프로젝트 현황(P2)을 뒤로 미룬다 "
                         "③ 검수 2단계를 재정이 앞당겨 P1 급으로 올린다.", S_NOTE)]))

    rows.append((None, []))
    rows.append((60, [(1, "가용 인일은 구현 15 영업일 x 3인 = 45 인일이다. 위 배정 "
                         "합계가 45 를 넘는 것은 작업 기간이 겹쳐 있기 때문이며 "
                         "(한 사람이 같은 날 두 작업을 진행), 실제 처리량은 그보다 "
                         "작다. 회의·문서 병행을 빼면 실 가용은 30 인일 안팎으로 본다. "
                         "P0+P1 이 80건이라 다 못 하므로 덜어내기보다 '묶기' 로 "
                         "접근한다 — 같은 골격을 쓰는 기능을 함께 만들면 두 번째부터 "
                         "싸다.", S_NOTE)]))

    rows.append((None, []))
    rows.append((26, [(i + 1, h, S_HDR) for i, h in
                      enumerate(["마일스톤", "날짜", "무엇", "", ""])]))
    for tid, _b, _m, name, _f, _o, _s, e, _out, mile in TASKS:
        if mile:
            rows.append((None, [(1, tid, S_CENB), (2, e[5:], S_CEN),
                                (3, name, S_TXTB), (4, "", S_TXT), (5, "", S_TXT)]))
    return sheet_xml(rows, [(1, 1, 16), (2, 2, 10), (3, 3, 58), (4, 4, 10), (5, 5, 58)])


# ─────────────────────────────────────────────── 패키징

SHEETS = [
    ("WBS", build_wbs_sheet()),
    ("산출물목록", build_deliverable_sheet()),
    ("이슈관리", build_issue_sheet()),
    ("결정사항", build_decision_sheet()),
    ("인일배분", build_load_sheet()),
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
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("xl/workbook.xml", workbook)
        z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
        z.writestr("xl/styles.xml", STYLES)
        for i, (_, xml) in enumerate(SHEETS):
            z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml)

    leaves = [t for t in TASKS if t[0].count(".") == 2]
    per = workload()
    print(f"생성 완료: {OUT.relative_to(ROOT)}")
    print(f"  시트 {len(SHEETS)}개 — " + " · ".join(n for n, _ in SHEETS))
    print(f"  간트 열 {len(DAYS)}개 ({DAY_KEY[0]} ~ {DAY_KEY[-1]})")
    print(f"  작업 {len(leaves)}개 (대분류 {sum(1 for t in TASKS if t[0].count('.')==0)} · "
          f"중분류 {sum(1 for t in TASKS if t[0].count('.')==1)})")
    print(f"  마일스톤 {sum(1 for t in TASKS if t[9])}개")
    print()
    for name, s, e in PHASES:
        print(f"  {name:14} {s[5:]} ~ {e[5:]}  영업일 {workdays(s, e)}")
    print()
    solo = solo_workload()
    for who in (A, J, B):
        print(f"  {who}  개별 {solo[who]:>3} + 공동 {per[who]-solo[who]:>3} "
              f"= {per.get(who, 0):>3} 인일")
    print(f"  파일 크기: {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
