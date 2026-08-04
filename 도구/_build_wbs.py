# -*- coding: utf-8 -*-
"""
PDF_WBS(작업분할구조도).xlsx 생성 스크립트
openpyxl 없이 xlsx(zip+xml)를 직접 작성.
2026-07-31 킥오프 확정사항 반영판.
"""
import zipfile
from xml.sax.saxutils import escape

# ------------------------------------------------------------------ 유틸

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


def sheet_xml(rows, widths=None, freeze=None):
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
        cell, xsplit, ysplit = freeze
        pane = (f'<pane xSplit="{xsplit}" ySplit="{ysplit}" topLeftCell="{cell}" '
                f'activePane="bottomRight" state="frozen"/>')

    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetViews><sheetView workbookViewId="0" showGridLines="1">{pane}</sheetView></sheetViews>'
            '<sheetFormatPr defaultRowHeight="16.5"/>'
            f'{cols}<sheetData>{"".join(body)}</sheetData>'
            '<pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.3" footer="0.3"/>'
            '</worksheet>')


# ------------------------------------------------------------------ 스타일
STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<fonts count="8">
<font><sz val="10"/><name val="맑은 고딕"/></font>
<font><b/><sz val="16"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><name val="맑은 고딕"/></font>
<font><b/><sz val="10"/><color rgb="FFC00000"/><name val="맑은 고딕"/></font>
<font><sz val="9"/><color rgb="FF808080"/><name val="맑은 고딕"/></font>
<font><sz val="10"/><color rgb="FF00806B"/><name val="맑은 고딕"/></font>
</fonts>
<fills count="9">
<fill><patternFill patternType="none"/></fill>
<fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF2F5597"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFDEEAF6"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF9DC3E6"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFF9999"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF2F2F2"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFC6EFCE"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="2">
<border><left/><right/><top/><bottom/><diagonal/></border>
<border>
<left style="thin"><color rgb="FFBFBFBF"/></left>
<right style="thin"><color rgb="FFBFBFBF"/></right>
<top style="thin"><color rgb="FFBFBFBF"/></top>
<bottom style="thin"><color rgb="FFBFBFBF"/></bottom>
<diagonal/></border>
</borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="13">
<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="3" fillId="3" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="5" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="5" fillId="6" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="5" fillId="0" borderId="1" xfId="0" applyFont="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="6" fillId="7" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
<xf numFmtId="0" fontId="7" fillId="8" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment horizontal="center" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="8" borderId="1" xfId="0" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>
</cellXfs>
<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>
</styleSheet>'''

S_TITLE, S_HDR, S_MAJOR, S_MID, S_TXT, S_CEN, S_BAR, S_MILE, S_WARN, S_NOTE, S_DONE, S_DONETXT = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12

# ------------------------------------------------------------------ 데이터

DAYS = ["7/31\n(금)", "8/1\n(토)", "8/2\n(일)", "8/3\n(월)",
        "8/4\n(화)", "8/5\n(수)", "8/6\n(목)", "8/7\n(금)"]
DAY_KEY = ["0731", "0801", "0802", "0803", "0804", "0805", "0806", "0807"]

A, B, C, ALL, PM = "최재정", "박세현", "김보현", "전원", "김보현"

# (ID, 대분류, 중분류, 작업명, 담당, 시작, 종료, 진행률, 산출물, 비고, 간트, 마일스톤)
TASKS = [
    ("1", "프로젝트 기획 및 개발환경 구축", "", "", "", "", "", "", "", "", [], False),
    ("1.1", "", "요구사항 분석 / 기술 결정", "", "", "", "", "", "", "", [], False),
    ("1.1.1", "", "", "과제 지시서 분석 및 요구사항 도출", ALL, "07-31", "07-31", "100%", "요구사항 체크리스트", "", ["0731"], False),
    ("1.1.2", "", "", "문서 도메인 / 카테고리 값 정의", ALL, "07-31", "08-01", "50%", "회의 결정사항", "카테고리 확정은 D2", ["0731", "0801"], False),
    ("1.1.3", "", "", "텍스트 추출 전략 수립 (레이어 우선 + OCR)", PM, "07-31", "07-31", "100%", "기술 검토서", "", ["0731"], False),
    ("1.1.4", "", "", "OCR 엔진 선정 — PaddleOCR v5 확정", A, "07-31", "07-31", "100%", "Docker 동작 검증", "컨테이너 실행 테스트 완료", ["0731"], False),
    ("1.1.5", "", "", "DB 선정 — PostgreSQL (본프로젝트까지 단일 사용)", ALL, "07-31", "07-31", "100%", "결정사항", "DB 교체 없이 연속 사용", ["0731"], False),
    ("1.2", "", "프로젝트 계획", "", "", "", "", "", "", "", [], False),
    ("1.2.1", "", "", "역할 분담 확정 (A 최재정 / B 박세현 / C 김보현)", PM, "07-31", "07-31", "100%", "역할표", "", ["0731"], False),
    ("1.2.2", "", "", "WBS 작성 / 갱신", PM, "07-31", "08-06", "30%", "WBS", "매일 진행률 갱신", ["0731", "0801", "0802", "0803", "0804", "0805", "0806"], False),
    ("1.2.3", "", "", "Git 브랜치 전략 / 공유파일 규칙 합의", ALL, "07-31", "07-31", "100%", "협업 규칙", "feature/기능명 (기능 단위)", ["0731"], False),
    ("1.2.4", "", "", "주말 작업 가능 여부 확인 — 가능 확정", PM, "07-31", "07-31", "100%", "일정 확정", "시나리오 A 적용", ["0731"], False),
    ("1.3", "", "설계", "", "", "", "", "", "", "", [], False),
    ("1.3.1", "", "", "API 엔드포인트 6종 합의 완료", ALL, "07-31", "07-31", "100%", "API 계약서", "경로/필드명(snake_case)/status 확정", ["0731"], False),
    ("1.3.2", "", "", "DB 모델 설계 및 ERD 작성", A, "07-31", "08-01", "60%", "ERD.png", "모델 코드 완료, ERD 도면 D2", ["0731", "0801"], False),
    ("1.3.3", "", "", "화면 정의서 작성", C, "07-31", "08-01", "10%", "화면_정의서.pdf", "", ["0731", "0801"], False),
    ("1.4", "", "개발환경 구축", "", "", "", "", "", "", "", [], False),
    ("1.4.1", "", "", "Git / Docker 설치 (전원)", ALL, "07-31", "07-31", "100%", "설치 확인", "", ["0731"], False),
    ("1.4.2", "", "", "docker-compose 구성 (db + api + frontend)", PM, "07-31", "07-31", "100%", "docker-compose.yml", "healthcheck, env_file 포함", ["0731"], False),
    ("1.4.3", "", "", "공통 인프라 core/ 구현", PM, "07-31", "07-31", "100%", "config/예외/로깅/미들웨어/트랜잭션", "", ["0731"], False),
    ("1.4.4", "", "", "DB 계층 (db/ models/ repositories/)", PM, "07-31", "07-31", "100%", "SQLAlchemy 3개 테이블", "", ["0731"], False),
    ("1.4.5", "", "", "Protocol 3종 + Fake 구현체 + DI 조립", PM, "07-31", "07-31", "100%", "protocol.py x3, dependencies.py", "", ["0731"], False),
    ("1.4.6", "", "", "담당자별 구현 가이드 작성 / 전원 숙지", PM, "07-31", "07-31", "100%", "IMPLEMENTATION_GUIDE.md", "전원 읽음 확인", ["0731"], False),
    ("1.4.7", "", "", "main 병합 (겹친 파일 4개 정리)", PM, "07-31", "07-31", "100%", "머지 커밋", "이슈 ISS-001~004 참고", ["0731"], False),
    ("1.4.8", "", "", "DB 테이블 3개 생성 확인", ALL, "07-31", "07-31", "100%", "psql \\dt 확인", "documents / extracted_texts / analyses", ["0731"], False),
    ("1.4.9", "", "", "★ 마일스톤: 전원 compose up + /health 200", ALL, "07-31", "07-31", "", "동작 확인", "미달 시 D2 블로킹", ["0731"], True),

    ("2", "업로드 / 텍스트 추출  [A · 재정]", "", "", "", "", "", "", "", "", [], False),
    ("2.1", "", "백엔드", "", "", "", "", "", "", "", [], False),
    ("2.1.1", "", "", "upload_router.py — POST /api/documents", A, "08-01", "08-01", "0%", "업로드 API", "동기 라우터", ["0801"], False),
    ("2.1.2", "", "", "extraction_service.py — 업로드/추출 로직", A, "08-01", "08-02", "0%", "서비스", "Repository 경유", ["0801", "0802"], False),
    ("2.1.3", "", "", "pdf_extractor.py (PyMuPDF)", A, "08-01", "08-01", "0%", "PdfExtractor", "주 경로", ["0801"], False),
    ("2.1.4", "", "", "파일 검증 (10MB / 30p / 확장자)", A, "08-01", "08-03", "0%", "검증 로직", "registry.get()이 확장자 검증", ["0801", "0803"], False),
    ("2.1.5", "", "", "docx / hwpx extractor", A, "08-03", "08-03", "0%", "구현체 2종", "구형 HWP 제외", ["0803"], False),
    ("2.1.6", "", "", "requirements OCR 주석 해제 + 전원 재빌드 공지", A, "08-03", "08-03", "0%", "requirements.txt", "★ 사전 공지 필수", ["0803"], False),
    ("2.1.7", "", "", "ocr_extractor.py (PaddleOCR) + 이미지 크기 측정", A, "08-03", "08-04", "0%", "OcrExtractor, 이미지 크기", "배포 용량 확인용", ["0803", "0804"], False),
    ("2.1.8", "", "", "extractor registry 등록 (dependencies.py)", A, "08-01", "08-03", "0%", "레지스트리 등록", "공유파일 — 즉시 푸시", ["0801", "0803"], False),
    ("2.2", "", "프론트엔드", "", "", "", "", "", "", "", [], False),
    ("2.2.1", "", "", "업로드 화면 + 드래그앤드롭", A, "08-01", "08-02", "0%", "UploadPage", "", ["0801", "0802"], False),
    ("2.2.2", "", "", "로딩 상태 UI (status 단계 표시)", A, "08-02", "08-02", "0%", "Spinner/StatusBar", "지시서 필수항목", ["0802"], False),

    ("3", "AI 분석 — 요약 / 카테고리  [B · 세현]", "", "", "", "", "", "", "", "", [], False),
    ("3.1", "", "백엔드", "", "", "", "", "", "", "", [], False),
    ("3.1.1", "", "", "prompts.py — 프롬프트 + PROMPT_VERSION", B, "08-01", "08-02", "0%", "프롬프트 설계", "", ["0801", "0802"], False),
    ("3.1.2", "", "", "summary_analyzer.py (async)", B, "08-01", "08-02", "0%", "SummaryAnalyzer", "generate_with_meta 사용", ["0801", "0802"], False),
    ("3.1.3", "", "", "category_analyzer.py (Literal로 값 고정)", B, "08-02", "08-02", "0%", "CategoryAnalyzer", "값 고정 안 하면 C 필터 깨짐", ["0802"], False),
    ("3.1.4", "", "", "analysis_service.py + analysis_router.py (async)", B, "08-02", "08-03", "0%", "분석 API", "재분석 시 행 추가", ["0802", "0803"], False),
    ("3.1.5", "", "", "analyzer registry 등록 (dependencies.py)", B, "08-02", "08-02", "0%", "레지스트리 등록", "공유파일 — 즉시 푸시", ["0802"], False),
    ("3.1.6", "", "", "토큰/지연/모델명 기록 검증", B, "08-03", "08-03", "0%", "analyses 컬럼 확인", "★ 본프로젝트 필수 데이터", ["0803"], False),
    ("3.1.7", "", "", "OpenAI 실연동 전환 (계정 확보 후)", B, "08-03", "08-04", "0%", "openai_client.py", "그전까지 FakeClient", ["0803", "0804"], False),
    ("3.2", "", "프론트엔드", "", "", "", "", "", "", "", [], False),
    ("3.2.1", "", "", "분석 요청 / 진행 표시", B, "08-02", "08-02", "0%", "analyze 연동", "", ["0802"], False),
    ("3.2.2", "", "", "요약 / 카테고리 결과 컴포넌트", B, "08-02", "08-03", "0%", "ResultView", "", ["0802", "0803"], False),

    ("4", "조회 / 검색 / 출력  [C · 팀장]", "", "", "", "", "", "", "", "", [], False),
    ("4.1", "", "백엔드", "", "", "", "", "", "", "", [], False),
    ("4.1.1", "", "", "document_service.py", C, "08-01", "08-02", "0%", "서비스", "", ["0801", "0802"], False),
    ("4.1.2", "", "", "document_router.py — 목록/상세 (동기)", C, "08-01", "08-01", "0%", "조회 API", "PageResponse 사용", ["0801"], False),
    ("4.1.3", "", "", "검색 (q / document_type / category)", C, "08-03", "08-03", "0%", "검색 API", "지시서 필수항목", ["0803"], False),
    ("4.1.4", "", "", "다운로드 (.txt, 한글 파일명 대응)", C, "08-03", "08-03", "0%", "다운로드 API", "filename*=UTF-8''", ["0803"], False),
    ("4.1.5", "", "", "삭제 (cascade + 업로드 파일 제거)", C, "08-03", "08-03", "0%", "DELETE API", "", ["0803"], False),
    ("4.2", "", "프론트엔드", "", "", "", "", "", "", "", [], False),
    ("4.2.1", "", "", "목록 화면", C, "08-01", "08-02", "0%", "ListPage", "", ["0801", "0802"], False),
    ("4.2.2", "", "", "상세 화면 (요약 + 카테고리)", C, "08-02", "08-02", "0%", "DetailPage", "", ["0802"], False),
    ("4.2.3", "", "", "검색 UI + 다운로드 버튼", C, "08-03", "08-03", "0%", "SearchBar", "", ["0803"], False),

    ("5", "통합 / 테스트 / 배포", "", "", "", "", "", "", "", "", [], False),
    ("5.1", "", "통합", "", "", "", "", "", "", "", [], False),
    ("5.1.1", "", "", "★ 마일스톤: E2E 전 구간 관통", ALL, "08-02", "08-02", "0%", "동작 확인", "실패 시 범위 축소", ["0802"], True),
    ("5.1.2", "", "", "API 계약 불일치 수정", ALL, "08-02", "08-03", "0%", "수정 이력", "", ["0802", "0803"], False),
    ("5.2", "", "테스트", "", "", "", "", "", "", "", [], False),
    ("5.2.1", "", "", "단위 테스트 작성 / 실행", ALL, "08-04", "08-04", "0%", "단위테스트결과서.xlsx", "각자 담당 파트", ["0804"], False),
    ("5.2.2", "", "", "통합 테스트 시나리오 작성 / 실행", PM, "08-04", "08-04", "0%", "통합테스트시나리오.xlsx", "", ["0804"], False),
    ("5.2.3", "", "", "에러 / 이슈 리포트 정리", ALL, "08-04", "08-05", "20%", "이슈리포트", "이슈관리 시트 (6건 기록됨)", ["0804", "0805"], False),
    ("5.3", "", "배포", "", "", "", "", "", "", "", [], False),
    ("5.3.1", "", "", "프론트엔드 컨테이너 검증", C, "08-04", "08-05", "0%", "frontend Dockerfile", "", ["0804", "0805"], False),
    ("5.3.2", "", "", "docker compose 전체 3컨테이너 기동 검증", ALL, "08-05", "08-05", "0%", "배포 확인", "PaddleOCR 포함 이미지", ["0805"], False),
    ("5.3.3", "", "", "운영 메뉴얼 / 배포 문서", PM, "08-05", "08-05", "0%", "운영 메뉴얼", "지시서 필수항목", ["0805"], False),

    ("6", "산출물 / 발표 준비", "", "", "", "", "", "", "", "", [], False),
    ("6.1", "", "문서 산출물", "", "", "", "", "", "", "", [], False),
    ("6.1.1", "", "", "프로젝트 완료 보고서", PM, "08-05", "08-06", "0%", "완료 보고서", "지시서 필수항목", ["0805", "0806"], False),
    ("6.1.2", "", "", "산출물 11종 최종 점검", PM, "08-06", "08-06", "0%", "제출 목록", "", ["0806"], False),
    ("6.2", "", "발표", "", "", "", "", "", "", "", [], False),
    ("6.2.1", "", "", "★ 코드 프리즈", ALL, "08-05", "08-05", "0%", "-", "이후 기능 추가 금지", ["0805"], True),
    ("6.2.2", "", "", "발표자료(PPT) 작성 — 목차 5장", ALL, "08-05", "08-06", "0%", "발표자료.pptx", "전원 분담", ["0805", "0806"], False),
    ("6.2.3", "", "", "발표영상 녹화 / 편집", ALL, "08-05", "08-06", "0%", "발표영상.zip", "시나리오 사전 작성", ["0805", "0806"], False),
    ("6.2.4", "", "", "발표 리허설 2회 (시간 측정)", ALL, "08-06", "08-06", "0%", "리허설 기록", "전원 발표 필수", ["0806"], False),
    ("6.2.5", "", "", "★ 최종 발표", ALL, "08-07", "08-07", "0%", "-", "팀원 전원 참여", ["0807"], True),
]

# ------------------------------------------------------------------ Sheet1: WBS

HDR = ["WBS ID", "대분류", "중분류", "작업명", "담당", "시작일", "종료일",
       "일수", "진행률", "산출물", "비고"]
NC = len(HDR)

rows = []
rows.append((26, [(1, "PDF Brief AI 시스템 - WBS (작업분할구조도)", S_TITLE)]))
rows.append((16, [(1, "기간: 2026-07-31(금) ~ 08-06(목)  |  발표: 08-07(금)  |  A 최재정 / B 박세현 / C 김보현(팀장)", S_NOTE),
                  (9, "★ = 마일스톤", S_NOTE)]))
rows.append((16, [(1, "확정: OCR=PaddleOCR v5 / DB=PostgreSQL(본프로젝트까지 단일) / 주말작업 가능 / 폴더 소문자 / 브랜치 feature별", S_NOTE)]))
rows.append((6, []))

hdr_cells = [(i + 1, h, S_HDR) for i, h in enumerate(HDR)]
hdr_cells += [(NC + 1 + i, d, S_HDR) for i, d in enumerate(DAYS)]
rows.append((32, hdr_cells))

for (wid, major, mid, name, owner, start, end, prog, out, note, bars, mile) in TASKS:
    if major:
        cells = [(1, wid, S_MAJOR), (2, major, S_MAJOR)]
        cells += [(c, "", S_MAJOR) for c in range(3, NC + len(DAYS) + 1)]
        rows.append((20, cells))
        continue
    if mid:
        cells = [(1, wid, S_MID), (2, "", S_MID), (3, mid, S_MID)]
        cells += [(c, "", S_MID) for c in range(4, NC + len(DAYS) + 1)]
        rows.append((18, cells))
        continue

    done = (prog == "100%")
    st_name = S_WARN if mile else (S_DONETXT if done else S_TXT)
    st_cell = S_DONE if done else S_CEN
    cells = [
        (1, wid, S_CEN), (2, "", S_TXT), (3, "", S_TXT),
        (4, name, st_name), (5, owner, st_cell),
        (6, start, S_CEN), (7, end, S_CEN),
        (8, len(bars) if bars else "", S_CEN),
        (9, prog, st_cell),
        (10, out, S_TXT), (11, note, S_TXT),
    ]
    for i, key in enumerate(DAY_KEY):
        if key in bars:
            cells.append((NC + 1 + i, "", S_MILE if mile else S_BAR))
        else:
            cells.append((NC + 1 + i, "", S_CEN))
    rows.append((18, cells))

widths = [(1, 8), (2, 30), (3, 16), (4, 44), (5, 7), (6, 10), (7, 10),
          (8, 6), (9, 8), (10, 26), (11, 26)]
widths += [(NC + 1 + i, 6) for i in range(len(DAYS))]

sheet1 = sheet_xml(rows, widths, freeze=("E6", 4, 5))

# ------------------------------------------------------------------ Sheet2: 산출물

DELIVERABLES = [
    ("1", "WBS (작업분할구조도)", "xlsx", PM, "07-31 초안 / 08-06 최종", "진행중", "본 파일"),
    ("2", "ERD", "png", A, "08-01", "진행중", "모델 코드 + 테이블 3개 생성 확인 완료, 도면 작성 필요"),
    ("3", "화면 정의서", "pdf", C, "08-01", "진행중", ""),
    ("4", "단위테스트결과서", "xlsx", ALL, "08-04", "대기", "각자 담당 파트"),
    ("5", "통합테스트시나리오(결과)", "xlsx", PM, "08-04", "대기", "E2E 시나리오"),
    ("6", "에러 / 이슈 리포트", "xlsx", ALL, "08-05", "진행중", "이슈관리 시트 6건 기록"),
    ("7", "운영 메뉴얼", "docx/pdf", PM, "08-05", "대기", "설치/실행/배포 절차"),
    ("8", "프로젝트 완료 보고서", "docx/pdf", PM, "08-06", "대기", "지시서 필수항목"),
    ("9", "발표자료", "pptx/pdf", ALL, "08-06", "대기", "목차 5장 고정"),
    ("10", "발표영상", "zip", ALL, "08-06", "대기", "데모 녹화 + 나레이션"),
    ("11", "소스코드", "GitHub", ALL, "08-06", "진행중", "README 포함"),
    ("-", "담당자별 구현 가이드", "md", PM, "07-31", "완료", "IMPLEMENTATION_GUIDE.md (내부용)"),
]

d_rows = []
d_rows.append((26, [(1, "산출물 목록 및 담당", S_TITLE)]))
d_rows.append((16, [(1, "양식 파일이 배포되면 형식을 맞춰 갱신", S_NOTE)]))
d_rows.append((6, []))
dh = ["No", "산출물명", "형식", "담당", "마감일", "상태", "비고"]
d_rows.append((28, [(i + 1, h, S_HDR) for i, h in enumerate(dh)]))
for r in DELIVERABLES:
    done = r[5] == "완료"
    d_rows.append((18, [(1, r[0], S_CEN), (2, r[1], S_DONETXT if done else S_TXT), (3, r[2], S_CEN),
                        (4, r[3], S_CEN), (5, r[4], S_CEN),
                        (6, r[5], S_DONE if done else S_CEN), (7, r[6], S_TXT)]))
sheet2 = sheet_xml(d_rows, [(1, 6), (2, 30), (3, 12), (4, 8), (5, 20), (6, 10), (7, 34)],
                   freeze=("A5", 0, 4))

# ------------------------------------------------------------------ Sheet3: 이슈관리

i_rows = []
i_rows.append((26, [(1, "에러 / 이슈 리포트", S_TITLE)]))
i_rows.append((16, [(1, "발생 즉시 기록. 발표자료 '04 수행경과' 트러블슈팅 슬라이드의 원천 자료", S_NOTE)]))
i_rows.append((6, []))
ih = ["ID", "발생일", "구분", "제목", "현상 / 내용", "원인", "조치 내용", "담당", "상태", "해결일"]
i_rows.append((28, [(i + 1, h, S_HDR) for i, h in enumerate(ih)]))

ISSUES = [
    ("ISS-001", "07-31", "환경", "폴더명 대소문자 충돌 (BackEnd vs backend)",
     "머지 시 GitHub에 backend/와 BackEnd/ 두 폴더가 생길 위험. Windows에서는 동일하게 보임",
     "Windows는 대소문자 비구분이지만 Git은 구분. 추적 중 파일은 소문자로 처리되나 신규(untracked) 파일은 디스크 실제 이름으로 커밋됨",
     "2단계 rename(BackEnd→temp→backend) + git add에 소문자 경로 명시. 소문자 backend/frontend로 팀 통일",
     PM, "해결", "07-31"),
    ("ISS-002", "07-31", "협업", "Docker 설정 3중 중복 작업",
     "팀원 2명과 팀장이 각각 docker-compose.yml / Dockerfile을 작성. 합계 2시간 이상 소요",
     "담당 영역이 파일 단위로 정해지지 않은 상태에서 동시 작업",
     "담당자별 파일 분리 규칙 수립(라우터·서비스). 공유 파일은 수정 즉시 커밋·푸시 + 채널 알림. 세 버전을 병합해 하나로 통일",
     ALL, "해결", "07-31"),
    ("ISS-003", "07-31", "버그", "config.py import 실패",
     "from pydantic_settings import BaseSetting → ImportError",
     "pydantic-settings v2의 클래스명은 BaseSettings(복수형). v1 표기와 혼동",
     "BaseSettings로 수정. 설정 항목이 더 많은 버전을 기준으로 병합하고 APP_NAME/DEBUG 반영",
     PM, "해결", "07-31"),
    ("ISS-004", "07-31", "환경", "requirements.txt가 git에서 binary로 인식",
     "warning: Cannot merge binary files. 충돌 마커 없이 한쪽 버전만 남음",
     "파일 앞에 BOM(Byte Order Mark)이 포함되어 텍스트로 인식되지 않음",
     "BOM 없이 ASCII로 재저장. 전이 의존성 제거하고 직접 의존성만 명시",
     PM, "해결", "07-31"),
    ("ISS-005", "07-31", "버그", "Settings 인스턴스화 실패 (extra_forbidden)",
     ".env에 DATABASE_URL 등을 추가하자 앱 기동 시 검증 에러",
     "pydantic-settings v2는 Settings 클래스에 선언되지 않은 .env 키를 기본적으로 거부",
     ".env의 모든 키를 Settings에 대문자 스네이크 필드로 선언",
     PM, "해결", "07-31"),
    ("ISS-006", "07-31", "환경", "PowerShell에서 한글 주석이 깨져 보임",
     "Get-Content로 .py 파일을 읽으면 한글 주석이 알 수 없는 문자로 표시",
     "파일은 UTF-8인데 Windows PowerShell 5.1의 Get-Content가 기본 ANSI(CP949)로 읽음. 파일 자체는 정상",
     "Get-Content -Encoding UTF8 사용, 또는 docker compose exec api python -c로 컨테이너 안에서 확인",
     PM, "해결", "07-31"),
    ("ISS-007", "07-31", "성능", "PaddleOCR 도입 후 Docker 이미지 2.75GB로 증가",
     "OCR 패키지 활성화 후 이미지가 2.75GB. 최초 빌드 10분 이상, 팀원 전원 재빌드 필요",
     "paddlepaddle(추론 엔진) 701MB로 전체 패키지의 47%. apt 빌드도구(gcc 등) 391MB. paddleocr 자체는 708KB로 무게는 전부 엔진에 있음",
     "배포를 로컬 docker compose 시연으로 확정하여 크기 제약 없음. 절감안(gcc 제거 약 200MB, 멀티스테이지 300~400MB)은 본프로젝트 개선 항목으로 기록",
     A, "조치완료", "07-31"),
    ("ISS-008", "07-31", "성능", "opencv 중복 설치 (contrib + headless)",
     "opencv-contrib-python 4.10.0.84 와 opencv-python-headless 4.12.0.88 이 동시 설치되어 cv2 모듈을 서로 덮어씀",
     "paddleocr 3.x의 의존성인 paddlex가 opencv-contrib-python을 요구. headless가 아닌 버전이 활성화되어 libgl1 시스템 라이브러리가 추가로 필요해짐",
     "Dockerfile에 libgl1 포함하여 동작 확보. paddlex 의존성이라 강제 제거는 리스크가 커서 본프로젝트 개선 항목으로 이관",
     A, "보류", ""),
    ("ISS-009", "", "", "", "", "", "", "", "", ""),
    ("ISS-010", "", "", "", "", "", "", "", "", ""),
]
for r in ISSUES:
    h = 60 if r[1] else 20
    i_rows.append((h, [(i + 1, v, S_TXT if i in (3, 4, 5, 6) else S_CEN)
                       for i, v in enumerate(r)]))
for n in range(9, 22):
    i_rows.append((20, [(i + 1, "", S_TXT if i in (3, 4, 5, 6) else S_CEN)
                        for i in range(len(ih))]))
sheet3 = sheet_xml(i_rows, [(1, 10), (2, 10), (3, 9), (4, 32), (5, 40), (6, 40),
                            (7, 44), (8, 8), (9, 9), (10, 10)], freeze=("A5", 0, 4))

# ------------------------------------------------------------------ Sheet4: 결정사항

k_rows = []
k_rows.append((26, [(1, "주요 결정사항 로그", S_TITLE)]))
k_rows.append((16, [(1, "기술 선택의 '근거'를 남긴다. 발표 '03 수행절차 및 방법'에 그대로 사용", S_NOTE)]))
k_rows.append((6, []))
kh = ["No", "일자", "안건", "결정 내용", "결정 근거", "대안 (미채택)", "결정자"]
k_rows.append((28, [(i + 1, h, S_HDR) for i, h in enumerate(kh)]))
DECISIONS = [
    ("1", "07-31", "OCR 엔진", "PaddleOCR v5",
     "담당자가 Docker 컨테이너에서 동작 테스트 완료. 한국어 문서 인식 성능",
     "EasyOCR / Tesseract (경량이지만 한국어 정확도 낮음)", A),
    ("2", "07-31", "텍스트 추출 전략", "텍스트 레이어 우선 추출 + OCR 폴백",
     "텍스트 PDF는 OCR 불필요(정확도 100%, 0.1초). 지시서 플로우 ③도 두 경로로 명시",
     "OCR 단일 경로 (정확도·속도 손실)", ALL),
    ("3", "07-31", "AI Provider", "OpenAI + Protocol로 교체 가능 구조. 개발 중 FakeClient",
     "지시서에 ChatGPT/Ollama 명시. USE_FAKE_AI=true 기본값으로 API 비용 0",
     "Upstage Solar (지시서 미명시)", ALL),
    ("4", "07-31", "DB", "PostgreSQL 16-alpine — 본프로젝트까지 단일 DB로 사용",
     "미니→본 프로젝트에서 DB를 교체하지 않는다. 교체 시 모델 검증·쿼리 수정·데이터 이관 비용이 발생하고, 미니에서 쌓은 분석 결과(본프로젝트 학습 데이터)를 그대로 이어 쓸 수 있음. 검색 요구사항에도 유리",
     "SQLite (전문검색 약함, 동시성 제약) / 미니는 SQLite 후 본에서 교체", ALL),
    ("5", "07-31", "마이그레이션", "Base.metadata.create_all()",
     "6일 일정에 Alembic 도입은 과함. 스키마 변경 시 볼륨 재생성으로 대응",
     "Alembic (본프로젝트에서 도입 예정)", PM),
    ("6", "07-31", "인증 기능", "구현하지 않음",
     "지시서상 '회원가입 및 로그인(선택) — 없어도 됨'",
     "간단 로그인 (6일 일정 우선순위 밖)", ALL),
    ("7", "07-31", "HWP 지원 범위", "HWPX만 지원, 구형 바이너리 HWP는 안내 처리",
     "바이너리 파싱 리스크 대비 효용 낮음. 반나절 이상 투입하지 않기로",
     "pyhwp 전면 도입", ALL),
    ("8", "07-31", "폴더 / 서비스 이름", "backend·frontend 소문자, 서비스 db·api·frontend, 컨테이너 ocr-*",
     "Git 대소문자 구분 문제(ISS-001) 재발 방지. DATABASE_URL 호스트명=서비스명 db",
     "BackEnd·FrontEnd 대문자 표기", ALL),
    ("9", "07-31", "라우터 / 서비스 파일 구성", "담당자별 파일 분리 (upload/analysis/document)",
     "3인이 같은 파일을 동시 수정해 머지 충돌 반복(ISS-002). 파일을 나누면 충돌 0",
     "단일 document_router.py에 6개 엔드포인트", ALL),
    ("9-1", "07-31", "Git 브랜치 전략", "feature/기능명 (기능 단위 브랜치)",
     "기능 단위로 브랜치를 끊어 PR 리뷰 범위를 작게 유지. main은 항상 동작 상태",
     "feature/이름/기능 (사람 단위) / main 직접 push", ALL),
    ("9-2", "07-31", "API 엔드포인트", "6종 확정 (업로드/분석/목록/상세/다운로드/삭제)",
     "필드명 snake_case 통일(Python·DB·JSON 변환 계층 제거), status Enum 6종, error_code 9종, result는 dict로 자유 구조",
     "camelCase (Pydantic alias 설정 필요, 스키마마다 누락 위험)", ALL),
    ("10", "07-31", "Analysis 테이블 메타 컬럼", "provider / model_name / prompt_version / tokens_in / tokens_out / latency_ms 기록",
     "본프로젝트에서 파인튜닝 모델과 상용 API의 비용·성능 비교에 필수. 사후 복원 불가",
     "요약 결과만 저장 (비교 실험 불가)", PM),
    ("11", "07-31", "주말 작업", "8/1~8/2 작업 가능 — 시나리오 A 적용",
     "실작업 6.5일 확보. 8/2 E2E 관통 후 8/6 리허설 2회 가능",
     "주말 미작업 시 기능 축소 필요 (.pdf 다운로드, 검색 고급기능, HWPX)", ALL),
    ("12", "", "", "", "", "", ""),
]
for r in DECISIONS:
    k_rows.append((44, [(i + 1, v, S_CEN if i in (0, 1, 6) else S_TXT)
                        for i, v in enumerate(r)]))
sheet4 = sheet_xml(k_rows, [(1, 6), (2, 10), (3, 26), (4, 44), (5, 46), (6, 36), (7, 8)],
                   freeze=("A5", 0, 4))

# ------------------------------------------------------------------ 패키징

SHEETS = [("WBS", sheet1), ("산출물목록", sheet2), ("이슈관리", sheet3), ("결정사항", sheet4)]

content_types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                 '<Default Extension="xml" ContentType="application/xml"/>'
                 '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                 + "".join(
                     f'<Override PartName="/xl/worksheets/sheet{i+1}.xml" '
                     f'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     for i in range(len(SHEETS)))
                 + '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                 '</Types>')

root_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
             '</Relationships>')

workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets>' + "".join(
                f'<sheet name="{escape(n)}" sheetId="{i+1}" r:id="rId{i+1}"/>'
                for i, (n, _) in enumerate(SHEETS)) + '</sheets></workbook>')

wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           + "".join(
               f'<Relationship Id="rId{i+1}" '
               f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
               f'Target="worksheets/sheet{i+1}.xml"/>' for i in range(len(SHEETS)))
           + f'<Relationship Id="rId{len(SHEETS)+1}" '
             'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
             'Target="styles.xml"/></Relationships>')

OUT = "PDF_WBS(작업분할구조도).xlsx"
with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("[Content_Types].xml", content_types)
    z.writestr("_rels/.rels", root_rels)
    z.writestr("xl/workbook.xml", workbook)
    z.writestr("xl/_rels/workbook.xml.rels", wb_rels)
    z.writestr("xl/styles.xml", STYLES)
    for i, (_, xml) in enumerate(SHEETS):
        z.writestr(f"xl/worksheets/sheet{i+1}.xml", xml)

print("생성 완료:", OUT)
