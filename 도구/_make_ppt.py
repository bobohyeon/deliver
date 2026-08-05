# -*- coding: utf-8 -*-
"""발표자료(.pptx)를 만든다.

색은 웹 화면의 디자인 토큰과 같은 값을 쓴다 (주색 #1E40AF).
글자 크기는 제목 28pt / 소제목 15pt / 본문 14pt / 설명 11pt 로 층을 나눈다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pptx import (  # noqa: E402
    BLUE, H, INK, LINE, MUTED, NAVY, PAPER, W, WHITE,
    _para, _shape, _table, build, slide_xml,
)

IN = 914400
M = int(0.72 * IN)                 # 좌우 여백
CW = W - 2 * M                     # 본문 폭
TITLE_Y = int(0.52 * IN)
BODY_Y = int(1.42 * IN)

SZ_T = 2800     # 슬라이드 제목
SZ_ST = 1500    # 소제목
SZ_B = 1400     # 본문
SZ_S = 1100     # 설명
SZ_XS = 950     # 각주


def head(title, eyebrow=None, note=None):
    """슬라이드 제목 + 밑줄. 필요하면 눈썹 라벨과 우측 보조 문구."""
    out = []
    if eyebrow:
        out.append(_shape(90, "눈썹", M, int(0.30 * IN), CW, int(0.24 * IN),
                          [_para([(eyebrow, SZ_XS, BLUE, True)])]))
    out.append(_shape(91, "제목", M, TITLE_Y, CW, int(0.62 * IN),
                      [_para([(title, SZ_T, INK, True)])]))
    out.append(_shape(92, "밑줄", M, int(1.18 * IN), int(0.62 * IN), 22860,
                      [], fill=NAVY))
    if note:
        out.append(_shape(93, "보조", M, int(1.24 * IN), CW, int(0.26 * IN),
                          [_para([(note, SZ_S, MUTED, False)])]))
    return out


def bullets(items, x, y, w, gap=460000, size=SZ_B):
    """• 없이 앞에 남색 사각 표식을 두는 목록."""
    out = []
    for i, item in enumerate(items):
        cy = y + i * gap
        out.append(_shape(200 + i * 2, "표식", x, cy + 55000, 68580, 68580, [], fill=NAVY))
        if isinstance(item, tuple):
            runs = [(item[0], size, INK, True), ("  " + item[1], size, MUTED, False)]
        else:
            runs = [(item, size, INK, False)]
        out.append(_shape(201 + i * 2, "항목", x + 160000, cy, w - 160000,
                          gap, [_para(runs, line=105000)]))
    return out


def card(sid, x, y, w, h, title, lines, accent=NAVY, title_size=SZ_ST):
    """옅은 배경의 상자. 좌측에 강조색 띠."""
    out = [_shape(sid, "카드", x, y, w, h, [], fill=PAPER, line_clr=LINE, line_w=6350),
           _shape(sid + 1, "띠", x, y, 45720, h, [], fill=accent)]
    paras = [_para([(title, title_size, NAVY, True)], space_after=500)]
    for ln in lines:
        if isinstance(ln, tuple):
            paras.append(_para([(ln[0], SZ_S, INK, True), ("  " + ln[1], SZ_S, MUTED, False)],
                               space_after=260, line=105000))
        else:
            paras.append(_para([(ln, SZ_S, INK, False)], space_after=260, line=105000))
    out.append(_shape(sid + 2, "카드글", x + 130000, y + 130000,
                      w - 280000, h - 260000, paras))
    return out


def flow(items, y, h=int(0.78 * IN)):
    """가로 흐름 상자 + 화살표."""
    out = []
    n = len(items)
    arrow = 200000
    bw = (CW - arrow * (n - 1)) // n
    for i, (num, text) in enumerate(items):
        x = M + i * (bw + arrow)
        out.append(_shape(300 + i * 3, "흐름", x, y, bw, h, [], fill=WHITE,
                          line_clr=NAVY, line_w=9525))
        out.append(_shape(301 + i * 3, "흐름번호", x, y + 90000, bw, int(0.2 * IN),
                          [_para([(num, SZ_XS, BLUE, True)], align="ctr")]))
        out.append(_shape(302 + i * 3, "흐름글", x, y + int(0.30 * IN), bw,
                          int(0.42 * IN),
                          [_para([(text, SZ_S, INK, True)], align="ctr", line=100000)]))
        if i < n - 1:
            out.append(_shape(360 + i, "화살표", x + bw, y + h // 2 - 90000,
                              arrow, 200000,
                              [_para([("→", SZ_ST, NAVY, True)], align="ctr")]))
    return out


def foot(text):
    return _shape(99, "각주", M, H - int(0.62 * IN), CW, int(0.3 * IN),
                  [_para([(text, SZ_XS, MUTED, False)])])


S = []

# ── 1. 표지 ───────────────────────────────────────────────────────────
S.append(slide_xml([
    _shape(1, "상단띠", 0, 0, W, int(0.1 * IN), [], fill=NAVY),
    _shape(2, "라벨", M, int(1.9 * IN), CW, int(0.3 * IN),
           [_para([("교육과정 미니프로젝트  ·  2026. 08. 07", 1200, BLUE, True)])]),
    _shape(3, "제목", M, int(2.28 * IN), CW, int(1.0 * IN),
           [_para([("PDF Brief AI", 5400, INK, True)])]),
    _shape(4, "부제", M, int(3.34 * IN), CW, int(0.5 * IN),
           [_para([("문서를 읽고 ", 2000, MUTED, False),
                   ("요약·분류", 2000, NAVY, True),
                   ("하는 웹 서비스", 2000, MUTED, False)])]),
    _shape(5, "선", M, int(4.16 * IN), int(1.4 * IN), 22860, [], fill=NAVY),
    _shape(6, "팀", M, int(4.5 * IN), CW, int(0.9 * IN),
           [_para([("김보현", SZ_B, INK, True), ("  조회·검색·출력 · 공통 컴포넌트 · 산출물", SZ_B, MUTED, False)], space_after=400),
            _para([("최재정", SZ_B, INK, True), ("  문서 추출 파이프라인 · 업로드/분석 화면", SZ_B, MUTED, False)], space_after=400),
            _para([("박세현", SZ_B, INK, True), ("  AI 요약·분류 · OCR 엔진 비교 · UI 개편", SZ_B, MUTED, False)])]),
]))

# ── 2. 목차 ───────────────────────────────────────────────────────────
toc = [("01", "프로젝트 개요"), ("02", "프로젝트 팀 구성 및 역할"),
       ("03", "프로젝트 수행 절차 및 방법"), ("04", "프로젝트 수행 경과"),
       ("05", "자체 평가 의견")]
sh = head("목차", eyebrow="CONTENTS")
for i, (num, name) in enumerate(toc):
    y = BODY_Y + i * int(0.86 * IN)
    sh.append(_shape(10 + i * 3, "번호", M, y, int(1.0 * IN), int(0.6 * IN),
                     [_para([(num, 3200, NAVY, True)])]))
    sh.append(_shape(11 + i * 3, "이름", M + int(1.1 * IN), y + int(0.12 * IN),
                     CW - int(1.1 * IN), int(0.4 * IN),
                     [_para([(name, 1900, INK, True)])]))
    sh.append(_shape(12 + i * 3, "구분선", M, y + int(0.66 * IN), CW, 12700,
                     [], fill=LINE))
sh.append(foot("발표 시간 15분 · 3인 릴레이 · 라이브 시연 포함"))
S.append(slide_xml(sh))


def divider(num, title, desc):
    return slide_xml([
        _shape(1, "배경", 0, 0, W, H, [], fill=NAVY),
        _shape(2, "번호", M, int(2.5 * IN), int(2.2 * IN), int(1.4 * IN),
               [_para([(num, 9600, WHITE, True)])]),
        _shape(3, "제목", M, int(3.9 * IN), CW, int(0.6 * IN),
               [_para([(title, 3200, WHITE, True)])]),
        _shape(4, "설명", M, int(4.6 * IN), CW, int(0.4 * IN),
               [_para([(desc, SZ_B, "BFDBFE", False)])]),
    ])


# ── 01 프로젝트 개요 ──────────────────────────────────────────────────
S.append(divider("01", "프로젝트 개요", "무엇을 왜 만들었는가"))

sh = head("문제 정의와 해결 방안", eyebrow="01-1 OVERVIEW")
sh += card(10, M, BODY_Y, (CW - 300000) // 2, int(2.0 * IN), "지금의 불편",
           [("형식이 제각각", "PDF · DOCX · HWPX · 스캔 이미지가 섞여 있다"),
            ("열어봐야 안다", "제목만으로는 내용을 알 수 없어 하나씩 열어 읽는다"),
            ("검색이 안 된다", "스캔·촬영 문서는 글자 정보가 없어 찾을 수 없다")],
           accent=MUTED)
sh += card(20, M + (CW - 300000) // 2 + 300000, BODY_Y, (CW - 300000) // 2,
           int(2.0 * IN), "해결 방안",
           [("한 번의 업로드", "형식을 자동 판별해 글자를 뽑고 필요하면 OCR"),
            ("읽지 않아도 안다", "요약과 카테고리를 자동으로 붙인다"),
            ("본문까지 검색", "추출한 원문을 저장해 내용으로 찾는다")])
sh.append(_shape(30, "정의띠", M, BODY_Y + int(2.3 * IN), CW, int(0.82 * IN),
                 [], fill=NAVY))
sh.append(_shape(31, "정의", M + 200000, BODY_Y + int(2.42 * IN),
                 CW - 400000, int(0.6 * IN),
                 [_para([("업로드한 문서를 ", 1800, "BFDBFE", False),
                         ("읽을 수 있는 형태로 바꾸고, 요약·분류해 검색 가능한 상태로 보관", 1800, WHITE, True),
                         ("하는 서비스", 1800, "BFDBFE", False)])]))
S.append(slide_xml(sh))

sh = head("범위와 의도적 제외", eyebrow="01-2 SCOPE",
          note="선택 기능을 빼고 필수 산출물에 시간을 배분했다")
sh.append(_table(10, M, BODY_Y + 120000, CW,
                 [int(1.9 * IN), CW - int(1.9 * IN)],
                 [["구분", "내용"],
                  ["구현 범위", "업로드 · 텍스트 추출 · OCR · AI 요약 · 카테고리 분류 · 목록 · 검색 · 다운로드 · 삭제"],
                  ["지원 형식", "PDF · DOCX · HWPX · PNG · JPG  (이미지는 OCR 경로)"],
                  ["처리 제약", "파일 10MB · PDF 30페이지 · 추출 45,000자"],
                  ["의도적 제외", "인증(지시서상 선택 항목) · PDF 형식 다운로드 · 기준별 분석기"],
                  ["제외 근거", "선택 기능에 6~10시간을 쓰면 테스트·문서·발표가 미완이 된다. 삽입 지점만 확보"]],
                 font=1150))
sh.append(foot("에러 코드 11종을 정의해 제약 위반 시 화면에 사유를 안내한다"))
S.append(slide_xml(sh))

# ── 02 팀 구성 및 역할 ────────────────────────────────────────────────
S.append(divider("02", "프로젝트 팀 구성 및 역할", "누가 무엇을 맡았는가"))

sh = head("역할 분담", eyebrow="02-1 TEAM",
          note="화면 · API · 로직을 한 세트로 묶어 각자 전체 흐름을 경험하도록 나눴다")
sh.append(_table(10, M, BODY_Y + 120000, CW,
                 [int(1.15 * IN), int(5.6 * IN), CW - int(6.75 * IN)],
                 [["팀원", "담당 범위", "주요 산출물"],
                  ["최재정", "문서 추출 파이프라인 (PDF · 이미지 · 전처리 · 표 검출 · 읽기 순서) · 업로드/분석 화면", "ERD"],
                  ["박세현", "AI 요약·분류 · OCR 엔진 3종 비교와 정확도 측정 · 프론트엔드 UI 개편", "프롬프트 설계"],
                  ["김보현", "목록 · 상세 · 검색 · 다운로드 · 삭제 · 공통 컴포넌트 · 전처리 프리셋", "화면정의서 · WBS"],
                  ["공통", "API 계약 · DB 모델 · Docker 구성 · 에러 코드 체계", "API 계약서"]],
                 font=1150))
sh.append(foot("세로 분할(화면+API+로직) — 가로 분할(프론트/백엔드)을 택하지 않은 이유는 전원이 전체 흐름을 익히기 위함"))
S.append(slide_xml(sh))

sh = head("협업 방식과 규칙", eyebrow="02-2 PROCESS")
sh += card(10, M, BODY_Y, (CW - 300000) // 2, int(2.5 * IN), "충돌을 줄인 규칙",
           [("담당자별 파일 분리", "Docker 설정을 3명이 각자 만들어 2시간을 버린 뒤 정한 규칙"),
            ("feature/기능명 브랜치", "기능 단위로 분리해 작업 중 영향 차단"),
            ("API 계약 먼저 확정", "엔드포인트·응답 형식을 정한 뒤 각자 구현"),
            ("Fake 구현체", "AI 키가 없어도 화면·조회를 병렬로 개발")])
sh += card(20, M + (CW - 300000) // 2 + 300000, BODY_Y, (CW - 300000) // 2,
           int(2.5 * IN), "기록으로 남긴 것",
           [("이슈 46건", "현상 · 원인 · 조치를 발생 즉시 기록"),
            ("결정사항 29건", "채택안과 함께 미채택 대안과 그 이유까지"),
            ("중복 구현 통합 원칙", "먼저 올라온 코드를 기준으로 두고 보완만 덧붙인다"),
            ("산출물 형식 통일", "CSV는 UTF-8 · 목록 시트는 담당자별로 나누지 않는다")],
           accent=BLUE)
sh.append(foot("규칙은 미리 정한 것이 아니라 대부분 문제를 겪은 뒤에 정했다 — 그 과정을 이슈로 남겼다"))
S.append(slide_xml(sh))

# ── 03 수행 절차 및 방법 ──────────────────────────────────────────────
S.append(divider("03", "프로젝트 수행 절차 및 방법", "어떻게 만들었는가"))

sh = head("전체 처리 흐름", eyebrow="03-1 PIPELINE",
          note="업로드 한 번으로 추출부터 분류까지 이어진다")
sh += flow([("01", "업로드"), ("02", "형식 판별"), ("03", "텍스트 추출\n/ OCR"),
            ("04", "읽기 순서\n복원"), ("05", "AI 요약\n· 분류"), ("06", "저장 · 조회")],
           BODY_Y + 100000)
sh += card(50, M, BODY_Y + int(1.25 * IN), CW, int(1.95 * IN), "경로가 갈리는 지점",
           [("글자 정보가 있으면", "텍스트 레이어를 그대로 읽는다 (정확도 100% · 0.1초)"),
            ("글자 정보가 없으면", "이미지로 판단해 OCR 을 태운다 (이미지 1장당 약 13초)"),
            ("둘이 섞여 있으면", "혼합(HYBRID) 경로로 두 결과를 하나의 좌표계에서 합친다"),
            ("공통 처리", "Recursive XY-Cut 으로 단·블록 순서를 복원해 읽는 순서를 맞춘다")])
sh.append(foot("OCR 을 항상 태우지 않는 이유 — 텍스트 PDF 에 OCR 을 쓰면 정확도는 떨어지고 시간만 130배 늘어난다"))
S.append(slide_xml(sh))

sh = head("시스템 아키텍처", eyebrow="03-2 ARCHITECTURE")
layers = [("화면", "React · React Router · Axios", "목록 · 상세 · 업로드 · OCR 비교 · 404"),
          ("Router", "FastAPI 엔드포인트 6종", "요청 검증과 응답 변환만 담당"),
          ("Service", "비즈니스 로직", "추출 · 분석 · 조회 · 삭제 규칙"),
          ("Repository", "SQLAlchemy", "DB 접근을 이 계층으로만 제한"),
          ("DB", "PostgreSQL 16", "documents · extracted_texts · analyses")]
for i, (name, tech, desc) in enumerate(layers):
    y = BODY_Y + i * int(0.62 * IN)
    sh.append(_shape(10 + i * 4, "층", M, y, int(1.5 * IN), int(0.5 * IN), [],
                     fill=NAVY if i in (1, 2, 3) else PAPER,
                     line_clr=LINE if i not in (1, 2, 3) else None))
    sh.append(_shape(11 + i * 4, "층이름", M, y + 100000, int(1.5 * IN), int(0.3 * IN),
                     [_para([(name, SZ_ST, WHITE if i in (1, 2, 3) else INK, True)],
                            align="ctr")]))
    sh.append(_shape(12 + i * 4, "기술", M + int(1.7 * IN), y + 60000,
                     int(3.2 * IN), int(0.3 * IN),
                     [_para([(tech, SZ_B, INK, True)])]))
    sh.append(_shape(13 + i * 4, "설명", M + int(5.0 * IN), y + 70000,
                     CW - int(5.0 * IN), int(0.34 * IN),
                     [_para([(desc, SZ_S, MUTED, False)])]))
sh.append(_shape(80, "컨테이너", M, BODY_Y + int(3.2 * IN), CW, int(0.5 * IN),
                 [_para([("컨테이너 3개  ", SZ_S, NAVY, True),
                         ("db · api · frontend  —  docker compose 한 번으로 전원이 같은 환경에서 실행", SZ_S, MUTED, False)])]))
S.append(slide_xml(sh))

sh = head("설계 포인트 ① 교체 가능한 구조", eyebrow="03-3 DESIGN",
          note="새 기능을 넣을 때 기존 코드를 고치지 않도록 확장 지점을 미리 뚫어 두었다")
w3 = (CW - 2 * 260000) // 3
sh += card(10, M, BODY_Y, w3, int(2.15 * IN), "TextExtractor",
           [("무엇", "파일 형식별 추출기"),
            ("구현", "PDF · DOCX · HWPX · 이미지 · Tesseract · EasyOCR"),
            ("확장", "새 형식은 registry 에 등록만 하면 된다")])
sh += card(20, M + w3 + 260000, BODY_Y, w3, int(2.15 * IN), "Analyzer",
           [("무엇", "분석기"),
            ("구현", "요약 · 카테고리 분류"),
            ("확장", "기준별 분석기 등 새 분석기를 같은 방식으로 추가")], accent=BLUE)
sh += card(30, M + 2 * (w3 + 260000), BODY_Y, w3, int(2.15 * IN), "AiClient",
           [("무엇", "AI 제공자"),
            ("구현", "OpenAI · Fake"),
            ("확장", "제공자를 바꿔도 호출 측 코드는 그대로")], accent=BLUE)
sh += card(40, M, BODY_Y + int(2.4 * IN), CW, int(0.86 * IN), "효과",
           [("Fake 구현체 덕분에", "AI 키를 확보하기 전에도 업로드 · 조회 · 화면을 병렬로 개발할 수 있었다. 실제 연동은 8/5에 한 번에 전환했다")],
           accent=MUTED)
S.append(slide_xml(sh))

sh = head("설계 포인트 ② 전처리와 좌표 책임", eyebrow="03-4 DESIGN",
          note="전처리는 공짜가 아니다 — 정보를 깎는 대가로 인식률을 사는 선택이다")
sh += card(10, M, BODY_Y, (CW - 300000) // 2, int(2.3 * IN), "프리셋으로 분리",
           [("none", "전처리 없음 — 비교의 기준선"),
            ("light", "문서 기본 — 흑백 변환 + 해상도 보정"),
            ("scan", "스캔·촬영본 — 조명 보정과 노이즈 제거까지"),
            ("full", "기울기 보정 포함 — 좌표를 쓰지 않는 경로만")])
sh += card(20, M + (CW - 300000) // 2 + 300000, BODY_Y, (CW - 300000) // 2,
           int(2.3 * IN), "좌표 책임을 한 곳에 가둠",
           [("문제", "확대·회전이 OCR 이 돌려주는 좌표를 바꿔 호출 측과 어긋난다"),
            ("해결", "추출기 안에서 원본 좌표계로 되돌려 반환한다"),
            ("안전장치", "되돌릴 수 없는 회전이 섞이면 예외로 막는다")], accent=BLUE)
sh.append(_shape(50, "성과", M, BODY_Y + int(2.55 * IN), CW, int(0.62 * IN),
                 [_para([("결과  ", SZ_B, NAVY, True),
                         ("다른 담당자가 같은 파일에 283줄을 추가했지만 좌표 경계는 그대로 유지됐다. "
                          "주석으로 부탁하는 대신 함수 시그니처로 계약을 만든 것이 이유다", SZ_B, INK, False)])]))
S.append(slide_xml(sh))

sh = head("OCR 엔진 비교 — 측정으로 선택", eyebrow="03-5 MEASUREMENT",
          note="같은 문서를 세 엔진에 동시에 넣어 정확도와 소요 시간을 비교했다")
sh.append(_table(10, M, BODY_Y + 100000, CW,
                 [int(2.4 * IN), int(1.8 * IN), int(1.9 * IN), CW - int(6.1 * IN)],
                 [["엔진", "정확도", "소요 시간", "추출 글자 수"],
                  ["PaddleOCR  (채택)", "98.1 %", "15,541 ms", "239자"],
                  ["Tesseract", "64.4 %", "931 ms", "283자"],
                  ["EasyOCR", "81.8 %", "15,496 ms", "253자"]],
                 font=1250))
sh += card(30, M, BODY_Y + int(1.7 * IN), CW, int(1.55 * IN),
           "숫자에서 읽어낸 것",
           [("가장 많이 뽑은 엔진이 가장 부정확했다", "Tesseract 는 글자 수가 제일 많지만 한 글자씩 세로로 쪼개져 정확도가 최저였다"),
            ("그래서 글자 수는 품질 지표가 아니다", "정답 텍스트와 대조하는 편집거리 방식으로 정확도를 재기로 결정했다"),
            ("Tesseract 는 17배 빠르지만 쓸 수 없었다", "속도와 정확도는 맞바꾸는 관계이며, 문서 인식에서는 정확도가 먼저다")],
           accent=BLUE)
S.append(slide_xml(sh))

sh = head("시연", eyebrow="03-6 DEMO   ★ 추천 추가 슬라이드",
          note="실제 화면으로 업로드부터 검색·다운로드까지 이어서 보여준다")
sh += flow([("01", "문서 업로드"), ("02", "추출 결과\n확인"), ("03", "요약 · 분류\n실행"),
            ("04", "목록 · 검색"), ("05", "요약 다운로드")], BODY_Y + 100000)
sh += card(50, M, BODY_Y + int(1.25 * IN), CW, int(1.95 * IN), "시연 진행 원칙",
           [("짧은 문서로 시연한다", "공고문(HWPX) 처럼 글자 정보가 있는 문서는 수 초 안에 끝난다"),
            ("OCR 이미지는 사전 업로드분으로 보여준다", "이미지 문서는 1장당 약 13초가 걸려 실시간 시연에 맞지 않는다"),
            ("OCR 엔진 비교는 사전 측정 결과를 쓴다", "세 엔진 동시 실행은 CPU 를 한계까지 사용한다"),
            ("네트워크가 끊기면", "미리 녹화한 화면으로 대체한다 (AI 호출이 필요한 구간)")])
sh.append(foot("검색은 '제안자' 와 '제 안 자' 를 나란히 입력해 같은 결과가 나오는 것을 보여준다"))
S.append(slide_xml(sh))

# ── 04 수행 경과 ──────────────────────────────────────────────────────
S.append(divider("04", "프로젝트 수행 경과", "무엇을 만들고 무엇에 막혔는가"))

sh = head("일정 및 진행 현황", eyebrow="04-1 PROGRESS")
sh.append(_table(10, M, BODY_Y, CW,
                 [int(2.0 * IN), int(1.3 * IN), CW - int(3.3 * IN)],
                 [["산출물", "상태", "비고"],
                  ["소스코드", "완료", "08-05 코드 프리즈. 이후 산출물 작업만 진행"],
                  ["화면정의서", "완료", "6화면 · 요소 52개에 번호 대응"],
                  ["단위테스트결과서", "완료", "66항목 전 항목 판정"],
                  ["통합테스트시나리오", "진행중", "44항목 중 34건 판정 · 잔여 10건"],
                  ["WBS · 이슈 · 결정사항", "완료", "작업 118행 · 이슈 46건 · 결정사항 29건"],
                  ["ERD · 운영 메뉴얼 · 완료 보고서", "진행중", "발표 전 마감 예정"]],
                 font=1150))
sh += card(40, M, BODY_Y + int(2.55 * IN), CW, int(0.72 * IN), "일정",
           [("07-31 착수  →  08-05 코드 프리즈  →  08-06 산출물 마감  →  08-07 발표",
             "주말 작업을 포함한 5.5일 일정")], accent=BLUE)
S.append(slide_xml(sh))

sh = head("트러블슈팅 — 담당별 릴레이", eyebrow="04-2 TROUBLESHOOTING",
          note="이슈 46건 중 각자 대표 사례를 이어서 설명한다")
w3 = (CW - 2 * 240000) // 3
sh += card(10, M, BODY_Y, w3, int(3.05 * IN), "최재정 · 추출",
           [("자간이 넓은 공문서", "'제 안 자' 가 세로로 쪼개져 검색 실패 → 줄 단위 좌표로 병합"),
            ("표 인식 실패", "간격으로 표를 나누려다 오판 → OpenCV 선 검출로 전환"),
            ("2단 문서 순서", "중앙 여백 판정 실패 → Recursive XY-Cut 적용")])
sh += card(20, M + w3 + 240000, BODY_Y, w3, int(3.05 * IN), "박세현 · 분석",
           [("응답 지연 2배", "요약·분류 순차 실행 → asyncio.gather 병렬화"),
            ("정확도 지표의 한계", "엔진 자체 confidence 는 오탈자를 반영하지 못함 → 편집거리 방식으로 변경"),
            ("메모리 영구 상주", "캐시 해제로는 회수되지 않음을 실측 → 별도 프로세스로 격리")], accent=BLUE)
sh += card(30, M + 2 * (w3 + 240000), BODY_Y, w3, int(3.05 * IN), "김보현 · 조회·협업",
           [("다운로드 줄바꿈 소실", "응답 코드만 확인해 놓친 버그 → 검증 기준을 '결과 파일 열어 확인' 으로 변경"),
            ("표 좌표계 불일치", "두 브랜치가 서로 다른 좌표계를 전제 → 원본 기준으로 통일"),
            ("main 직접 푸시", "커밋 이력이 섞여 작업 주체 추적 불가 → 브랜치 규칙 복구")], accent=MUTED)
S.append(slide_xml(sh))

sh = head("측정으로 방향을 바꾼 사례", eyebrow="04-3 KEY LEARNING   ★ 핵심",
          note="네 건 모두 '해봤더니 아니어서' 접근을 바꿨다 — 측정하지 않았으면 그대로 갔을 것이다")
rows = [["사례", "처음 접근", "측정 결과", "바꾼 방향"],
        ["표 영역 분리", "글자 사이 간격으로 표와 본문을 구분", "자간이 넓은 공문서에서 본문을 표로 오판", "OpenCV 로 실제 선을 검출"],
        ["2단 문서 순서", "페이지 중앙의 세로 여백을 찾아 판정", "여백이 일정하지 않은 문서에서 계속 실패", "Recursive XY-Cut 알고리즘"],
        ["EasyOCR 메모리", "인프로세스 캐시를 해제하면 회수될 것", "PyTorch 가 메모리를 OS 에 반환하지 않음", "추론을 별도 프로세스로 격리"],
        ["자동 전처리", "품질을 분석해 필요한 전처리만 적용", "글자 수 +2.3% 인데 처리 시간 3배", "문서 종류별 임계값 분리로 이관"]]
sh.append(_table(10, M, BODY_Y, CW,
                 [int(1.9 * IN), int(3.2 * IN), int(3.7 * IN), CW - int(8.8 * IN)],
                 rows, font=1050))
sh += card(40, M, BODY_Y + int(2.5 * IN), CW, int(0.78 * IN), "",
           [("배운 것", "빠른 방법이 옳은 방법은 아니다. 간격·여백 같은 간접 신호로 판단하려 한 두 시도는 모두 실패했고, "
                      "실제로 그려진 선과 재귀 분할처럼 근거가 분명한 방식으로 바꾼 뒤에 해결됐다")],
           accent=BLUE, title_size=SZ_S)
S.append(slide_xml(sh))

sh = head("테스트 결과", eyebrow="04-4 TEST")
sh += card(10, M, BODY_Y, (CW - 300000) // 2, int(1.5 * IN), "단위 테스트 — 화면 흐름",
           [("66항목 · 전 항목 판정 완료", ""),
            ("업로드 11 · 추출 9 · 분석 9 · 목록 11 · 상세 8 · 다운로드 5 · 삭제 5 · 비교 4 · 환경 4", "")])
sh += card(20, M + (CW - 300000) // 2 + 300000, BODY_Y, (CW - 300000) // 2,
           int(1.5 * IN), "통합 테스트 — 기능 연동",
           [("44항목 · 34건 판정 · 잔여 10건", ""),
            ("업로드·추출 / AI 분석 / 조회·검색 / 다운로드 / 삭제 / 엔진 비교 / 오류 일관성 / 실행 환경", "")],
           accent=BLUE)
sh += card(30, M, BODY_Y + int(1.75 * IN), CW, int(1.5 * IN),
           "테스트가 잡아낸 결함",
           [("현상", "오류 응답의 request_id 로 서버 로그를 찾을 수 없었다"),
            ("원인", "비즈니스 오류 처리기에 로그 호출이 없어 404 · 409 · 413 이 로그에 남지 않는다"),
            ("판단", "코드 프리즈 이후에 발견해 고치지 않고 결함으로 기록했다. request_id 전달 자체는 정상이므로 로깅만 보완하면 해결된다")],
           accent=MUTED)
sh.append(foot("에러 코드 11종 중 7종을 실제로 발생시켜 확인했다 · 잔여 4종은 발표 전 확인 예정"))
S.append(slide_xml(sh))

# ── 05 자체 평가 ──────────────────────────────────────────────────────
S.append(divider("05", "자체 평가 의견", "무엇을 얻고 무엇이 남았는가"))

sh = head("성과와 한계", eyebrow="05-1 SELF ASSESSMENT")
sh += card(10, M, BODY_Y, (CW - 300000) // 2, int(3.05 * IN), "잘된 점",
           [("확장 지점을 미리 뚫었다", "추출기 · 분석기 · AI 제공자를 등록만으로 교체 가능"),
            ("Fake 구현체로 병렬 개발", "AI 키 없이도 화면과 조회를 동시에 진행"),
            ("판단 근거를 남겼다", "이슈 46건 · 결정사항 29건에 미채택 대안까지 기록"),
            ("측정으로 결론을 뒤집었다", "네 건의 접근을 실측 결과에 따라 바꿨다"),
            ("인터페이스로 경계를 지켰다", "다른 담당자의 대규모 수정에도 좌표 계약이 유지됨")])
sh += card(20, M + (CW - 300000) // 2 + 300000, BODY_Y, (CW - 300000) // 2,
           int(3.05 * IN), "아쉬운 점",
           [("이미지 문서 처리 시간", "이미지 1장당 약 13초 — 12페이지 문서는 55초"),
            ("정답 데이터 기반 측정 미완", "기능은 만들었으나 정답 파일을 확보하지 못해 실제 정확도 미산출"),
            ("규칙을 겪은 뒤에 만들었다", "Docker 3중 작업 · main 직접 푸시 등은 사전 합의로 막을 수 있었다"),
            ("조회 쿼리 최적화 미착수", "문서 20건 조회에 41개 쿼리가 발생함을 알고도 개선하지 못했다"),
            ("구형 HWP 미지원", "바이너리 형식은 안내 처리로만 대응")], accent=MUTED)
S.append(slide_xml(sh))

sh = head("향후 과제와 본프로젝트 연결", eyebrow="05-2 NEXT   ★ 추천 추가 슬라이드",
          note="미니프로젝트에서 확인한 한계를 그대로 본프로젝트 과제로 옮긴다")
sh.append(_table(10, M, BODY_Y, CW,
                 [int(2.5 * IN), int(4.3 * IN), CW - int(6.8 * IN)],
                 [["과제", "지금 상태", "본프로젝트에서 할 일"],
                  ["OCR 처리 시간", "이미지 1장당 약 13초 · 개선 시도 2건 모두 기각", "비동기 처리와 진행률 표시 · 이미지 단위 병렬화"],
                  ["전처리 임계값", "자동 선택이 스크린샷에 과하게 적용돼 시간 3배", "문서 종류별 임계값 분리"],
                  ["정확도 측정", "정답 데이터 기반 기능은 구현 · 실측 미완", "정답 데이터 축적 후 엔진 재평가"],
                  ["조회 성능", "문서 20건에 41개 쿼리", "벌크 조회로 전환하고 개선 전후 수치 제시"],
                  ["인증", "삽입 지점만 확보", "로그인 · 권한 · 문서 소유자 구분"],
                  ["오류 추적", "비즈니스 오류가 서버 로그에 남지 않음", "로깅 보완 후 request_id 기반 추적 완성"]],
                 font=1050))
S.append(slide_xml(sh))

# ── 마무리 ────────────────────────────────────────────────────────────
S.append(slide_xml([
    _shape(1, "배경", 0, 0, W, H, [], fill=NAVY),
    _shape(2, "제목", M, int(2.7 * IN), CW, int(0.9 * IN),
           [_para([("감사합니다", 4400, WHITE, True)], align="ctr")]),
    _shape(3, "선", (W - int(1.2 * IN)) // 2, int(3.75 * IN), int(1.2 * IN), 22860,
           [], fill="BFDBFE"),
    _shape(4, "부제", M, int(4.05 * IN), CW, int(0.4 * IN),
           [_para([("PDF Brief AI  ·  김보현 · 최재정 · 박세현", SZ_B, "BFDBFE", False)],
                  align="ctr")]),
    _shape(5, "링크", M, int(4.55 * IN), CW, int(0.34 * IN),
           [_para([("github.com/ParkSehyeon1009/OCR_MiniProject", SZ_S, "93C5FD", False)],
                  align="ctr")]),
]))

out = Path(__file__).resolve().parent.parent / "산출물" / "발표자료.pptx"
build(str(out), S, title="PDF Brief AI 발표자료")
print(f"생성: {out.name}  ({len(S)}장, {out.stat().st_size:,} bytes)")
