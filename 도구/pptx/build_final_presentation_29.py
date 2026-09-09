#!/usr/bin/env python3
"""
① 이 파일의 책임: Tasqra 최종 발표 29장 전체본을 SVG와 PPTX로 생성한다.
② 다른 파일과의 관계: 확정된 5장 파일럿의 디자인 헬퍼를 재사용하고, 산출물/최종발표/전체본에 결과를 만든다.
③ Spring 비교: 슬라이드 정의가 View 템플릿, 이 스크립트가 전체 덱을 조립하는 ViewResolver 역할을 한다.
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import sys
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_final_presentation_pilot as v2

W, H = v2.W, v2.H
EMU_W, EMU_H = v2.EMU_W, v2.EMU_H
C = v2.C
rect, circle, line = v2.rect, v2.circle, v2.line
text, multiline, pill, icon = v2.text, v2.multiline, v2.pill, v2.icon
finish = v2.finish

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "산출물" / "최종발표" / "전체본"
PNG_DIR = Path(os.environ.get("TASQRA_FINAL_PNG_DIR", str(OUT / "png")))
PPTX_PATH = OUT / "Tasqra_최종발표_29장_v1.pptx"


def svg_base(no: int, section: str, presenter: str, owner: str, *, dark: bool = False):
    bg = C["rail"] if dark else C["canvas"]
    fg = "#FFFFFF" if dark else C["text"]
    p = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs>',
        '<style>@font-face{font-family:NotoKR;src:url("../../포트폴리오/NotoSansKR.ttf") format("truetype");} text{font-family:NotoKR,Arial,sans-serif;}</style>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="12" stdDeviation="16" flood-color="#0E162F" flood-opacity="0.11"/></filter>',
        '<filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="7" stdDeviation="10" flood-color="#0E162F" flood-opacity="0.08"/></filter>',
        '</defs>',
        rect(0, 0, W, H, bg),
        text(80, 60, f"{no:02d}  /  {section}", 17, 800, C["cyan"] if dark else C["blue"], spacing=2),
        text(1840, 60, "TASQRA", 16, 800, fg, anchor="end", spacing=2.6, opacity=0.62),
        line(80, 1015, 1840, 1015, "#29385F" if dark else C["border"], 1),
        text(80, 1050, f"PRESENTER  {presenter}", 14, 700, "#8EA0CA" if dark else C["muted"], spacing=1),
        text(1840, 1050, f"OWNER  {owner}", 14, 700, "#8EA0CA" if dark else C["muted"], anchor="end", spacing=1),
    ]
    return p


def slide_title(p, kicker: str, title_value: str, subtitle: str | None = None, *, dark=False, size=52):
    p.append(text(80, 125, kicker, 18, 800, C["cyan"] if dark else C["blue"], spacing=1.6))
    p.append(text(80, 195, title_value, size, 800, "#FFFFFF" if dark else C["text"], spacing=-0.8))
    if subtitle:
        p.append(text(82, 245, subtitle, 22, 500, "#B9C6E5" if dark else C["body"]))


def panel(x, y, w, h, *, fill="#FFFFFF", stroke=None, rx=24, shadow=True, sw=2):
    return rect(x, y, w, h, fill, rx=rx, stroke=stroke or C["border"], sw=sw, extra='filter="url(#softShadow)"' if shadow else "")


def number_badge(x, y, value, color=None, dark=False):
    color = color or C["blue"]
    return pill(x, y, 62, 34, value, color if dark else C["soft_blue"], "#FFFFFF" if dark else color, size=15)


def arrow(x1, y1, x2, y2, color="#AEBDE0", sw=4):
    if abs(x2 - x1) >= abs(y2 - y1):
        if x2 >= x1:
            head = f'M {x2-15} {y2-11} L {x2} {y2} L {x2-15} {y2+11}'
        else:
            head = f'M {x2+15} {y2-11} L {x2} {y2} L {x2+15} {y2+11}'
    else:
        if y2 >= y1:
            head = f'M {x2-11} {y2-15} L {x2} {y2} L {x2+11} {y2-15}'
        else:
            head = f'M {x2-11} {y2+15} L {x2} {y2} L {x2+11} {y2+15}'
    return line(x1, y1, x2, y2, color, sw) + f'<path d="{head}" fill="none" stroke="{color}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round"/>'


def small_note(p, x, y, w, title_value, body, *, color=None, dark=False):
    color = color or C["blue"]
    fill = "#192953" if dark else C["panel"]
    body_color = "#C7D3EC" if dark else C["body"]
    p.append(panel(x, y, w, 112, fill=fill, stroke="#30436F" if dark else C["border"], rx=20, shadow=not dark))
    p.append(rect(x, y, 8, 112, color, rx=4))
    p.append(text(x + 28, y + 40, title_value, 20, 800, "#FFFFFF" if dark else C["text"]))
    p.append(text(x + 28, y + 79, body, 17, 500, body_color))


def card_title(p, x, y, no, heading, accent, *, width=470, height=250, body_lines=(), icon_kind=None, dark=False):
    fill = "#17264F" if dark else C["panel"]
    stroke = accent if dark else C["border"]
    p.append(panel(x, y, width, height, fill=fill, stroke=stroke, rx=26, shadow=True, sw=2))
    p.append(rect(x, y, width, 10, accent, rx=5))
    p.append(number_badge(x + 28, y + 32, no, accent, dark=dark))
    if icon_kind:
        p.append(circle(x + width - 62, y + 63, 35, "#24345F" if dark else C["soft"], stroke=accent, sw=2))
        p.append(icon(icon_kind, x + width - 62, y + 63, 32, accent, 3))
    p.append(text(x + 30, y + 116, heading, 30, 800, "#FFFFFF" if dark else C["text"]))
    if body_lines:
        p.append(multiline(x + 30, y + 166, body_lines, 20, 500, "#C8D4EC" if dark else C["body"], line_height=1.5))


def metric(p, x, y, value, label, *, color=None, suffix="", dark=False, width=300):
    color = color or C["blue"]
    fill = "#17264F" if dark else C["panel"]
    p.append(panel(x, y, width, 150, fill=fill, stroke=color, rx=24, shadow=True))
    p.append(text(x + 24, y + 72, value + suffix, 48, 800, color))
    p.append(text(x + 25, y + 116, label, 18, 600, "#C6D2EA" if dark else C["body"]))


def label_tag(p, x, y, value, *, fill=None, color=None, width=None):
    width = width or max(120, len(value) * 19 + 34)
    p.append(pill(x, y, width, 38, value, fill or C["soft_blue"], color or C["navy"], size=16))


def polyline(points, stroke, sw=5, opacity=1):
    pts = " ".join(f"{x},{y}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round" opacity="{opacity}"/>'



def slide6():
    p = svg_base(6, "ARCHITECTURE", "김보현", "최재정 · 공통")
    slide_title(p, "SYSTEM MAP", "전체 시스템 아키텍처", "동기 API와 비동기 Worker가 PostgreSQL·공유 파일을 중심으로 연결됩니다.")
    # 동기 요청 경로
    card_title(p, 80, 315, "01", "React / Vite", C["blue"], width=320, height=205, body_lines=("사용자 화면", "Axios REST 요청"), icon_kind="users")
    card_title(p, 470, 315, "02", "FastAPI", C["cyan"], width=320, height=205, body_lines=("Router · Service", "Repository"), icon_kind="structure")
    card_title(p, 860, 315, "03", "PostgreSQL", C["lime"], width=320, height=205, body_lines=("업무 데이터", "pgvector 1024D"), icon_kind="document")
    p.append(arrow(405, 415, 455, 415)); p.append(arrow(795, 415, 845, 415))
    # 비동기 경로
    p.append(panel(1245, 292, 595, 505, fill=C["navy"], stroke="#31477A", rx=32, shadow=True))
    p.append(text(1290, 345, "ASYNC PATH", 17, 800, C["cyan"], spacing=1.8))
    p.append(text(1290, 395, "Redis Queue", 30, 800, "#FFFFFF"))
    p.append(arrow(1400, 438, 1660, 438, "#536DAA", 4))
    p.append(circle(1355, 438, 42, "#203568", stroke=C["cyan"], sw=2)); p.append(text(1355, 446, "Q", 22, 800, C["cyan"], anchor="middle"))
    p.append(circle(1710, 438, 42, "#203568", stroke=C["lime"], sw=2)); p.append(text(1710, 446, "W", 22, 800, C["lime"], anchor="middle"))
    p.append(text(1290, 510, "Celery Worker", 26, 800, "#FFFFFF"))
    p.append(multiline(1290, 554, ("OCR · 청킹 · 임베딩", "LLM 분석 작업 분리"), 19, 500, "#C8D4EC", line_height=1.5))
    p.append(line(1290, 648, 1790, 648, "#354B7E", 2))
    p.append(text(1290, 690, "공유 저장소", 18, 800, C["cyan"]))
    p.append(text(1450, 690, "./backend/uploads", 18, 600, "#FFFFFF"))
    p.append(text(1290, 735, "로컬 AI", 18, 800, C["lime"]))
    p.append(text(1450, 735, "Ollama / OpenAI 호환", 18, 600, "#FFFFFF"))
    small_note(p, 80, 575, 1100, "실제 실행 구조", "API와 Worker가 같은 PostgreSQL·uploads·모델 캐시를 공유합니다.", color=C["blue"])
    small_note(p, 80, 710, 1100, "운영 경계", "현재 compose는 개발 구성입니다. S3·Kubernetes·오토스케일링은 포함하지 않습니다.", color=C["lime"])
    return finish(p)


def slide7():
    p = svg_base(7, "DATA MODEL", "김보현", "최재정")
    slide_title(p, "RELATIONAL CORE", "핵심 데이터 구조", "Project와 Document를 중심으로 검색·분석·업무 데이터가 외래키로 연결됩니다.")
    # central nodes
    p.append(circle(960, 575, 112, C["navy"], stroke=C["blue"], sw=5, extra='filter="url(#shadow)"'))
    p.append(text(960, 565, "PROJECT", 22, 800, C["cyan"], anchor="middle", spacing=1.5))
    p.append(text(960, 612, "업무 범위", 30, 800, "#FFFFFF", anchor="middle"))
    nodes = [
        (360, 370, "USER · MEMBER", ("소유자와 구성원", "OWNER · EDITOR · VIEWER"), C["cyan"]),
        (1560, 370, "DOCUMENT", ("원문 경로와 메타데이터", "추출본문 · OCR · 분석 이력"), C["blue"]),
        (360, 780, "TASK · REVIEW", ("태스크와 검토 제안", "결정 · 일정 · 액션 · 금액"), C["lime"]),
        (1560, 780, "CHUNK · ANALYSIS", ("본문 구간과 1024D 벡터", "모델 · 버전 · 원문 좌표"), C["cyan"]),
    ]
    for x, y, heading, body, accent in nodes:
        p.append(line(960, 575, x, y, "#A9B9D8", 4))
        p.append(panel(x-235, y-105, 470, 210, fill=C["panel"], stroke=accent, rx=26, shadow=True))
        p.append(text(x, y-35, heading, 22, 800, accent, anchor="middle", spacing=1.0))
        p.append(multiline(x, y+18, body, 20, 500, C["body"], line_height=1.5, anchor="middle"))
    label_tag(p, 700, 900, "Document 1:1 ExtractedText", width=270)
    label_tag(p, 995, 900, "Document 1:N Chunk / Analysis", width=330)
    p.append(text(960, 975, "파일 자체는 DB BLOB이 아니라 공유 로컬 경로로 보관합니다.", 18, 600, C["muted"], anchor="middle"))
    return finish(p)


def slide8():
    p = svg_base(8, "STATE DESIGN", "김보현", "최재정 · 박세현")
    slide_title(p, "SEPARATE LIFECYCLES", "상태를 분리한 운영 설계", "문서 추출·OCR 검수·LLM 분석을 하나의 상태로 섞지 않았습니다.")
    rails = [
        (315, "문서 추출", ["PENDING", "EXTRACTING", "EXTRACTED"], C["blue"], "오류 시 FAILED · 재시도는 PENDING부터"),
        (550, "OCR 검수", ["PENDING", "IN_PROGRESS", "COMPLETED"], C["cyan"], "OCR 대상이 없으면 NOT_REQUIRED"),
        (785, "LLM 분석 Job", ["PENDING", "RUNNING", "COMPLETED / PARTIAL / FAILED"], C["lime"], "문서 상태와 별도 · 원문 revision 검증"),
    ]
    for y, heading, states, accent, note in rails:
        p.append(text(80, y+12, heading, 24, 800, C["text"]))
        start_x = 390
        widths = [300, 300, 450]
        for idx, state in enumerate(states):
            w = widths[idx]
            x = start_x + idx * 390
            p.append(panel(x, y-55, w, 100, fill=C["panel"], stroke=accent, rx=22, shadow=False))
            p.append(text(x+w/2, y+6, state, 21, 800, accent, anchor="middle"))
            if idx < 2:
                p.append(arrow(x+w+15, y-5, start_x+(idx+1)*390-15, y-5, "#9DADCB", 3))
        p.append(text(390, y+85, note, 17, 600, C["body"]))
    p.append(panel(80, 910, 1760, 78, fill=C["navy"], stroke=C["navy"], rx=20, shadow=False))
    p.append(text(120, 958, "핵심", 18, 800, C["cyan"]))
    p.append(text(225, 958, "Document의 ANALYZING·COMPLETED enum은 선언돼 있지만 자동 대입 경로가 없어 발표 흐름에서 제외했습니다.", 18, 600, "#FFFFFF"))
    return finish(p)


def slide9():
    p = svg_base(9, "RAG", "김보현", "김보현")
    slide_title(p, "INDEX → RETRIEVE", "RAG 색인과 검색", "문서 구조와 원문 위치를 보존한 청크에서 근거를 찾습니다.")
    steps = [
        ("01", "확정 본문", ("OCR 검수 결과", "text_version"), C["blue"], "document"),
        ("02", "구조 청킹", ("최대 480토큰", "앞 문맥 48토큰"), C["cyan"], "structure"),
        ("03", "임베딩", ("BGE-m3-ko", "1024차원"), C["lime"], "search"),
        ("04", "pgvector", ("HNSW 코사인", "ef_search 100"), C["blue2"], "search"),
        ("05", "근거 결과", ("페이지·문서명", "원문 좌표"), C["cyan"], "check"),
    ]
    xs = [85, 440, 795, 1150, 1505]
    for idx, (no, heading, body, accent, kind) in enumerate(steps):
        x=xs[idx]
        card_title(p, x, 360, no, heading, accent, width=285, height=285, body_lines=body, icon_kind=kind)
        if idx < len(steps)-1:
            p.append(arrow(x+292, 500, xs[idx+1]-10, 500, "#AABADB", 3))
    p.append(panel(85, 705, 1705, 210, fill=C["navy"], stroke="#31477A", rx=28, shadow=True))
    p.append(text(130, 765, "검색 요청", 20, 800, C["cyan"], spacing=1))
    p.append(text(130, 822, "질의를 별도 임베딩 → 권한 있는 프로젝트 범위 → 같은 embedding_model의 가까운 청크 조회", 27, 700, "#FFFFFF"))
    p.append(text(130, 870, "HNSW는 근사검색이며, 모델 변경 시 기존 청크는 재임베딩이 필요합니다.", 18, 500, "#B9C8E5"))
    label_tag(p, 1530, 755, "실모델 설정 조건", fill="#243A70", color=C["lime"], width=210)
    return finish(p)


def slide10():
    p = svg_base(10, "HYBRID SEARCH", "김보현", "김보현")
    slide_title(p, "ONE SEARCH BOX", "하이브리드 검색", "서로 다른 점수를 더하지 않고, 두 검색의 순위를 RRF로 결합합니다.")
    # two branches
    card_title(p, 100, 330, "A", "키워드 검색", C["cyan"], width=570, height=390,
               body_lines=("ILIKE로 연속 문자열 포함 보장", "word_similarity로 내부 순위", "숫자·코드·정확 표현에 강점"), icon_kind="document", dark=True)
    card_title(p, 1250, 330, "B", "의미 검색", C["blue2"], width=570, height=390,
               body_lines=("질의·청크 임베딩", "pgvector 코사인 거리", "표현이 달라도 문맥 탐색"), icon_kind="search", dark=True)
    p.append(circle(960, 515, 130, C["lime"], stroke="#A9C932", sw=4, extra='filter="url(#shadow)"'))
    p.append(text(960, 493, "RRF", 52, 800, C["rail"], anchor="middle"))
    p.append(text(960, 545, "Σ 1 / (60 + 순위)", 18, 800, C["rail"], anchor="middle"))
    p.append(arrow(690, 515, 810, 515, C["cyan"], 5)); p.append(arrow(1230, 515, 1110, 515, C["blue2"], 5))
    small_note(p, 100, 780, 520, "후보 폭", "두 검색에서 각각 기본 30개", color=C["blue"])
    small_note(p, 700, 780, 520, "단일 UX", "사용자는 검색 방식을 고르지 않음", color=C["cyan"])
    small_note(p, 1300, 780, 520, "주의", "전문 검색엔진·점수 정규화·가중합 아님", color=C["lime"])
    return finish(p)



def slide11():
    p = svg_base(11, "SEARCH SCALE", "김보현", "김보현 · 박세현")
    slide_title(p, "MEASURED LIMIT", "검색 범위가 커질수록 첫 정답 순위가 무너졌습니다", "동일 모델·동일 평가셋에서 후보 청크 수만 바꾼 결과입니다.", size=46)
    chart_x, chart_y, chart_w, chart_h = 120, 360, 1160, 480
    p.append(panel(80, 300, 1280, 620, fill=C["panel"], stroke=C["border"], rx=28, shadow=True))
    for value in [40, 60, 80, 100]:
        y = chart_y + chart_h - (value-30)/70*chart_h
        p.append(line(chart_x, y, chart_x+chart_w, y, C["border"], 2, dash="8 10"))
        p.append(text(chart_x-20, y+7, f"{value}%", 16, 600, C["muted"], anchor="end"))
    candidates=[30,50,100,200,400,700,1339]
    r1=[90.2,86.4,80.8,71.3,58.7,49.5,36.9]
    r5=[98.9,98.3,95.9,92.5,89.3,85.0,74.3]
    xs=[chart_x+i*chart_w/(len(candidates)-1) for i in range(len(candidates))]
    def cy(v): return chart_y+chart_h-(v-30)/70*chart_h
    pts1=list(zip(xs,[cy(v) for v in r1])); pts5=list(zip(xs,[cy(v) for v in r5]))
    p.append(polyline(pts1,C["blue"],6)); p.append(polyline(pts5,C["cyan"],5))
    for x,v,y in [(x,v,cy(v)) for x,v in zip(xs,r1)]:
        p.append(circle(x,y,8,C["blue"])); p.append(text(x,y-18,f"{v:.1f}",14,800,C["blue"],anchor="middle"))
    for x,v,y in [(x,v,cy(v)) for x,v in zip(xs,r5)]:
        p.append(circle(x,y,7,C["cyan"])); p.append(text(x,y-18,f"{v:.1f}",14,800,"#189BC5",anchor="middle"))
    for x,c in zip(xs,candidates): p.append(text(x,chart_y+chart_h+35,f"{c:,}",15,600,C["body"],anchor="middle"))
    p.append(text(chart_x+chart_w/2, chart_y+chart_h+72, "후보 청크 수", 17,700,C["muted"],anchor="middle"))
    label_tag(p, 955, 325, "R@1", fill=C["soft_blue"], color=C["blue"], width=100)
    label_tag(p, 1070, 325, "R@5", fill="#E6FAFF", color="#189BC5", width=100)
    metric(p, 1420, 330, "90.2", "후보 30 · R@1", color=C["blue"], suffix="%", width=360)
    metric(p, 1420, 515, "36.9", "전체 1,339 · R@1", color=C["cyan"], suffix="%", width=360)
    p.append(panel(1420, 700, 360, 220, fill=C["navy"], stroke=C["navy"], rx=24, shadow=True))
    p.append(text(1450, 755, "평가 조건", 18,800,C["lime"]))
    p.append(multiline(1450,800,("BGE-m3-ko · 질의 214", "문서 30 · 정답 1청크/질의", "R@k = 상위 k 안에 정답 포함"),18,500,"#FFFFFF",line_height=1.55))
    p.append(text(80, 970, "※ 후보 30의 90.2%는 제품 문서 수 제한 정책이 아니라 검색 후보 범위 실험값입니다.", 16,600,C["muted"]))
    return finish(p)


def slide12():
    p = svg_base(12, "RERANKER", "김보현", "박세현")
    slide_title(p, "CANDIDATE REORDERING", "학습 리랭커는 후보 안에서 첫 정답을 끌어올렸습니다", "동일 조건의 R@1 비교이며, 후보에 없는 정답은 복구할 수 없습니다.", size=45)
    labels=["임베딩 단독","BGE 학습 전","BGE 학습 후"]
    vals=[33.18,34.11,49.07]
    colors=["#AAB7D4",C["cyan"],C["blue"]]
    base_y=835; x0=170; bw=230; gap=140; max_h=440
    p.append(panel(80,300,1100,620,fill=C["panel"],stroke=C["border"],rx=28,shadow=True))
    for i,(lab,val,col) in enumerate(zip(labels,vals,colors)):
        x=x0+i*(bw+gap); h=val/55*max_h; y=base_y-h
        p.append(rect(x,y,bw,h,col,rx=20))
        p.append(text(x+bw/2,y-24,f"{val:.2f}%",30,800,col,anchor="middle"))
        p.append(text(x+bw/2,875,lab,18,700,C["body"],anchor="middle"))
    p.append(text(125,350,"R@1",18,800,C["blue"],spacing=1.5))
    metric(p,1260,320,"+14.96","학습 전 → 후 R@1",color=C["lime"],suffix="%p",width=520)
    p.append(panel(1260,505,520,250,fill=C["navy"],stroke="#31477A",rx=26,shadow=True))
    p.append(text(1300,560,"적용 경로",18,800,C["cyan"],spacing=1.2))
    p.append(multiline(1300,610,("벡터·키워드 후보", "→ RRF 융합", "→ 상위 후보 전문 재정렬"),23,700,"#FFFFFF",line_height=1.55))
    small_note(p,1260,785,520,"실행 조건","기본 비활성 · GPU 권장 · 실패 시 원래 순서",color=C["blue"])
    p.append(text(100,965,"R@5  72.43% → 71.50% → 80.84%   ·   학습 후 MRR@10 0.6235   ·   측정 지연 0.192초",17,600,C["muted"]))
    return finish(p)


def slide13():
    p = svg_base(13, "GROUNDED QA", "김보현", "김보현")
    slide_title(p, "EVIDENCE CONTRACT", "답변보다 먼저 근거의 경계를 설계했습니다", "검색 결과를 토큰 예산 안에 조립하고, 모델이 반환한 근거 ID를 서버가 검증합니다.", size=48)
    steps=[
        ("01","하이브리드 검색",("최대 24개 후보", "프로젝트 권한 범위"),C["blue"],"search"),
        ("02","전문 재조회",("짧은 snippet이 아닌", "청크 원문 사용"),C["cyan"],"document"),
        ("03","컨텍스트 조립",("최대 8개 · 4,000토큰", "중복 문장 제거"),C["lime"],"structure"),
        ("04","LLM JSON",("answer · answerable", "evidence_ids"),C["blue2"],"tasks"),
        ("05","서버 검증",("ID 존재·범위·중복", "원문 메타데이터 매핑"),C["cyan"],"check"),
    ]
    xs=[70,425,780,1135,1490]
    for i,s in enumerate(steps):
        no,head,body,accent,kind=s
        card_title(p,xs[i],330,no,head,accent,width=300,height=310,body_lines=body,icon_kind=kind)
        if i<4:p.append(arrow(xs[i]+305,485,xs[i+1]-5,485,"#A9BAD9",3))
    p.append(panel(90,700,1740,210,fill=C["navy"],stroke="#31477A",rx=28,shadow=True))
    p.append(text(135,760,"반환",18,800,C["cyan"],spacing=1.2))
    p.append(text(135,817,"답변 + 문서명 + 페이지 + 조각 번호 + 원문 좌표",30,800,"#FFFFFF"))
    p.append(text(135,865,"근거가 없으면 LLM을 호출하지 않고 고정 응답을 반환합니다.",18,500,"#BFCBE5"))
    label_tag(p,1380,755,"의미적 사실 검증 아님",fill="#243864",color=C["lime"],width=360)
    p.append(text(1380,825,"서버 검증 범위는 근거 ID 계약과 권한입니다.",18,600,"#FFFFFF"))
    return finish(p)


def slide14():
    p = svg_base(14, "HUMAN REVIEW", "김보현", "김보현 · 최재정")
    slide_title(p, "APPROVAL BOUNDARY", "AI 제안과 실제 업무 사이에 사람 검토를 둡니다", "자동 반영이 아니라 PENDING 제안을 승인 가능한 상태로 저장합니다.", size=47)
    # gates
    p.append(panel(90,330,430,430,fill="#E8EEFF",stroke=C["blue"],rx=30,shadow=True))
    p.append(text(130,390,"AI 제안",20,800,C["blue"],spacing=1.2))
    p.append(text(130,455,"PENDING",50,800,C["navy"]))
    p.append(multiline(130,520,("결정 · 일정 · 금액", "액션 태스크 후보"),24,600,C["body"],line_height=1.6))
    p.append(arrow(540,545,685,545,C["blue"],5))
    p.append(panel(700,300,520,500,fill=C["navy"],stroke=C["blue"],rx=34,shadow=True))
    p.append(text(960,370,"사람의 검토",34,800,"#FFFFFF",anchor="middle"))
    actions=[("승인","APPROVED",C["cyan"]),("수정 승인","EDITED",C["lime"]),("거절","REJECTED","#F0A0A0"),("취소","PENDING","#9EAFD1")]
    for i,(a,state,col) in enumerate(actions):
        y=435+i*82
        p.append(circle(770,y,18,col)); p.append(text(810,y+8,a,22,700,"#FFFFFF")); p.append(pill(1010,y-20,160,40,state,"#243766",col,size=14))
    p.append(arrow(1235,545,1380,545,C["lime"],5))
    p.append(panel(1400,330,430,430,fill=C["panel"],stroke=C["lime"],rx=30,shadow=True))
    p.append(text(1440,390,"후속 소비",20,800,"#86A800",spacing=1.2))
    p.append(multiline(1440,455,("태스크", "대시보드", "산출물", "근거 QA"),28,800,C["text"],line_height=1.6))
    p.append(panel(90,850,1740,100,fill=C["panel"],stroke=C["border"],rx=22,shadow=False))
    p.append(text(130,910,"일관된 필터",18,800,C["blue"]))
    p.append(text(310,910,"승인·수정 승인된 항목만 집계와 산출물에 반영합니다.",21,700,C["text"]))
    return finish(p)


def slide15():
    p = svg_base(15, "ACTION TO TASK", "김보현", "최재정")
    slide_title(p, "CONTROLLED AUTOMATION", "액션아이템은 승인 전까지 태스크가 아닙니다", "계약·변경계약 문서의 후보를 단건 검토한 뒤 실제 Task를 생성합니다.", size=47)
    steps=[
        ("01","규칙 후보",("의무·기한 표현", "근거 구간"),C["blue"],"document"),
        ("02","모델 선택",("후보 ID 중 선택", "일반 규정 제외"),C["cyan"],"search"),
        ("03","PENDING 저장",("task_suggestions", "담당자·기한"),C["lime"],"structure"),
        ("04","단건 승인·거절",("승인 시 실제 Task", "origin=AI_APPROVED"),C["blue2"],"check"),
    ]
    xs=[100,540,980,1420]
    for i,s in enumerate(steps):
        no,head,body,accent,kind=s
        card_title(p,xs[i],350,no,head,accent,width=360,height=330,body_lines=body,icon_kind=kind,dark=(i==3))
        if i<3:p.append(arrow(xs[i]+370,515,xs[i+1]-10,515,"#A9BADA",4))
    p.append(panel(100,760,1680,150,fill=C["navy"],stroke="#31477A",rx=28,shadow=True))
    p.append(text(145,815,"UI 범위",18,800,C["cyan"],spacing=1.2))
    p.append(text(145,865,"현재 화면은 승인·거절을 지원합니다. 수정 승인·승인 취소·오래된 원문 방어는 다음 개선 범위입니다.",21,600,"#FFFFFF"))
    return finish(p)


def slide16():
    p = svg_base(16, "AMOUNT SNAPSHOT", "김보현", "김보현")
    slide_title(p, "SAFE RE-ANALYSIS", "금액을 다시 분석해도 집계는 흔들리지 않습니다", "새 분석의 검토가 끝날 때까지 직전 완료 스냅샷을 계속 사용합니다.", size=46)
    # old snapshot lane
    p.append(text(100,340,"기존 유효 스냅샷",22,800,C["blue"]))
    p.append(panel(100,380,650,230,fill=C["panel"],stroke=C["blue"],rx=28,shadow=True))
    p.append(text(145,445,"APPROVED · EDITED",24,800,C["blue"]))
    p.append(text(145,500,"대시보드 · QA · 산출물",28,800,C["text"]))
    p.append(text(145,555,"새 검토가 끝날 때까지 계속 사용",18,600,C["body"]))
    # new lane
    p.append(text(100,700,"신규 재분석",22,800,C["cyan"]))
    stages=[("새 Analysis","PENDING"),("단건 검토","승인·수정·거절"),("검토 완료","유효 후보")]
    for i,(h,b) in enumerate(stages):
        x=100+i*330
        p.append(panel(x,740,280,150,fill=C["panel"],stroke=C["cyan"] if i<2 else C["lime"],rx=24,shadow=False))
        p.append(text(x+24,790,h,20,800,C["text"]));p.append(text(x+24,840,b,17,600,C["body"]))
        if i<2:p.append(arrow(x+287,815,x+323,815,"#9EB0D0",3))
    # switch
    p.append(circle(1090,615,90,C["lime"],stroke="#9DBD25",sw=4,extra='filter="url(#shadow)"'))
    p.append(text(1090,605,"원자",24,800,C["rail"],anchor="middle"));p.append(text(1090,642,"전환",24,800,C["rail"],anchor="middle"))
    p.append(arrow(990,815,1080,690,C["lime"],4));p.append(arrow(1180,615,1270,615,C["lime"],4))
    p.append(panel(1290,420,500,390,fill=C["navy"],stroke="#31477A",rx=30,shadow=True))
    p.append(text(1335,480,"새 유효 스냅샷",22,800,C["lime"]))
    p.append(multiline(1335,545,("미결 행 0", "원래 추출 행 수와 일치", "전부 거절·0건도 완료"),24,700,"#FFFFFF",line_height=1.6))
    return finish(p)


def slide17():
    p = svg_base(17, "DASHBOARD · OUTPUTS", "김보현", "김보현 · 최재정")
    slide_title(p, "FROM APPROVED DATA", "승인된 정보가 대시보드와 산출물로 이어집니다", "사람 검토를 통과한 동일 데이터를 화면과 문서가 함께 소비합니다.", size=45)
    # dashboard side
    p.append(panel(80,310,770,590,fill=C["navy"],stroke="#31477A",rx=30,shadow=True))
    p.append(text(125,365,"PROJECT DASHBOARD",17,800,C["cyan"],spacing=1.6))
    metrics=[("문서 상태","PENDING · EXTRACTED"),("열린 태스크","담당자 · 기한"),("승인 일정","달력"),("금액 검토","대기 건수")]
    for i,(h,b) in enumerate(metrics):
        x=125+(i%2)*345;y=425+(i//2)*185
        p.append(panel(x,y,300,145,fill="#1D2E5B",stroke="#3A4F82",rx=22,shadow=False))
        p.append(text(x+24,y+50,h,20,800,"#FFFFFF"));p.append(text(x+24,y+98,b,16,500,"#BFCBE5"))
    p.append(text(125,845,"※ 대시보드의 승인 대기 집계는 현재 금액 중심입니다.",16,500,"#9FAFCE"))
    # outputs
    p.append(text(930,330,"DELIVERABLES",17,800,C["blue"],spacing=1.6))
    outputs=[("01","주간 보고서","기간 내 문서·완료 태스크"),("02","프로젝트 현황","전체 재료와 향후 계획"),("03","결정사항 대장","승인된 결정 전체"),("04","회의 안건","승인됐지만 미결인 결정")]
    for i,(no,h,b) in enumerate(outputs):
        x=930+(i%2)*440;y=385+(i//2)*230
        card_title(p,x,y,no,h,[C["blue"],C["cyan"],C["lime"],C["blue2"]][i],width=395,height=195,body_lines=(b,))
    p.append(panel(930,860,835,68,fill=C["soft_blue"],stroke=C["border"],rx=18,shadow=False))
    p.append(text(975,904,"출력 형식",17,800,C["blue"]));p.append(text(1130,904,"XLSX · HTML · MD · PDF",20,800,C["navy"]))
    return finish(p)



def slide18():
    p = svg_base(18, "OCR EVOLUTION", "박세현", "박세현")
    slide_title(p, "PARK SEHYEON SECTION", "텍스트층을 버리지 않는 OCR 파이프라인", "페이지 특성에 따라 TEXT_LAYER·OCR·HYBRID를 선택하고 읽기 순서를 복원합니다.", size=46)
    modes=[
        ("TEXT_LAYER","기존 텍스트 보존",("텍스트 블록 추출", "불필요한 OCR 생략"),C["blue"],"document"),
        ("OCR","스캔 페이지 보완",("큰 이미지 + 부족한 텍스트층", "전체 페이지 OCR"),C["cyan"],"search"),
        ("HYBRID","두 결과를 좌표순 결합",("텍스트와 이미지 OCR", "같은 좌표계로 정렬"),C["lime"],"structure"),
    ]
    xs=[100,675,1250]
    for i,(mode,head,body,accent,kind) in enumerate(modes):
        card_title(p,xs[i],340,mode,head,accent,width=500,height=370,body_lines=body,icon_kind=kind,dark=(i==2))
    p.append(arrow(610,525,655,525,"#A9BADA",3));p.append(arrow(1185,525,1230,525,"#A9BADA",3))
    p.append(panel(100,775,1650,140,fill=C["panel"],stroke=C["border"],rx=26,shadow=True))
    p.append(text(145,830,"결과",18,800,C["blue"],spacing=1.2))
    p.append(text(145,875,"페이지 본문 + OCR 검수 박스 + content_start/end 원문 오프셋",24,800,C["text"]))
    p.append(text(1430,875,"TEXT_LAYER / OCR / HYBRID",17,700,C["muted"],anchor="middle"))
    return finish(p)


def slide19():
    p = svg_base(19, "OCR REVIEW", "박세현", "박세현")
    slide_title(p, "TEXT INTEGRITY", "OCR 박스를 고치면 본문과 오프셋도 함께 바뀝니다", "화면의 수정과 검색 원문이 어긋나지 않도록 범위·버전·revision을 한 트랜잭션에서 갱신합니다.", size=43)
    stages=[
        ("01","박스 수정",C["blue"]),("02","범위 검증",C["cyan"]),("03","본문 구간 교체",C["lime"]),
        ("04","뒤 오프셋 이동",C["blue2"]),("05","revision 증가",C["cyan"]),("06","검수 재확정",C["lime"]),
    ]
    xs=[105,395,685,975,1265,1555]
    for i,(no,head,accent) in enumerate(stages):
        p.append(circle(xs[i],500,74,C["panel"],stroke=accent,sw=4,extra='filter="url(#softShadow)"'))
        p.append(text(xs[i],484,no,16,800,accent,anchor="middle"))
        p.append(text(xs[i],526,head,19,800,C["text"],anchor="middle"))
        if i<5:p.append(arrow(xs[i]+82,500,xs[i+1]-82,500,"#A7B8D7",3))
    p.append(panel(100,665,800,220,fill=C["navy"],stroke="#31477A",rx=28,shadow=True))
    p.append(text(145,720,"동시 수정 방어",18,800,C["cyan"],spacing=1.2))
    p.append(multiline(145,770,("stale version이면 전체 롤백", "여러 범위는 뒤에서부터 교체", "문서 버전은 배치당 한 번 증가"),21,600,"#FFFFFF",line_height=1.55))
    p.append(panel(960,665,800,220,fill=C["panel"],stroke=C["lime"],rx=28,shadow=True))
    p.append(text(1005,720,"검수 완료 후",18,800,"#87A800",spacing=1.2))
    p.append(multiline(1005,770,("제외·복원 요소를 본문에 반영", "is_confirmed 확정", "청킹·임베딩 재작업 enqueue"),21,600,C["text"],line_height=1.55))
    return finish(p)


def slide20():
    p = svg_base(20, "ASYNC SAFETY", "박세현", "박세현 · 최재정")
    slide_title(p, "FAILURE ISOLATION", "비동기 작업의 실패 경계를 분리했습니다", "OCR·청킹은 재시도하고, LLM 분석은 원문 변경과 부분 실패를 job 상태로 통제합니다.", size=46)
    # left OCR lane
    p.append(panel(80,310,820,600,fill=C["panel"],stroke=C["blue"],rx=30,shadow=True))
    p.append(text(125,365,"OCR · CHUNK",18,800,C["blue"],spacing=1.5))
    ocr=[("late ack","작업 유실 시 requeue"),("exponential backoff","최대 60초 · 추가 2회"),("후속 enqueue 격리","OCR 성공을 다시 돌리지 않음")]
    for i,(h,b) in enumerate(ocr):
        y=430+i*135
        p.append(number_badge(125,y-25,f"0{i+1}",C["blue"]));p.append(text(215,y,h,22,800,C["text"]));p.append(text(215,y+38,b,17,500,C["body"]))
    p.append(text(125,850,"OCR 완료 후 LLM 분석은 자동 연쇄되지 않습니다.",17,700,C["muted"]))
    # right analysis lane
    p.append(panel(960,310,880,600,fill=C["navy"],stroke="#31477A",rx=30,shadow=True))
    p.append(text(1005,365,"LLM ANALYSIS JOB",18,800,C["cyan"],spacing=1.5))
    items=[("활성 job 1개","PENDING/RUNNING 중복 방지"),("원문 snapshot","text_version + SHA-256 재검증"),("순차 analyzer","GPU 요청 폭주 방지"),("PARTIAL 저장","일부 성공 결과는 보존"),("timeout","앱 timeout + Celery hard limit")]
    for i,(h,b) in enumerate(items):
        y=425+i*82
        p.append(circle(1025,y,8,C["lime"] if i==3 else C["cyan"]));p.append(text(1055,y+7,h,20,800,"#FFFFFF"));p.append(text(1280,y+7,b,16,500,"#BFCBE5"))
    p.append(pill(1005,840,700,42,"PENDING  →  RUNNING  →  COMPLETED / PARTIAL / FAILED","#243866","#FFFFFF",size=17))
    return finish(p)


def slide21():
    p = svg_base(21, "BASE MODEL", "박세현", "박세현")
    slide_title(p, "MODEL SELECTION", "작은 로컬 모델 중 Qwen2.5-3B를 학습 베이스로 선택했습니다", "분류 21건·요약 12건·입력 6,000자 조건의 비교입니다.", size=42)
    headers=["MODEL","정확도","MACRO-F1","JSON 형식"]
    xcols=[100,730,1030,1330]; widths=[600,270,270,400]
    p.append(panel(80,300,1760,570,fill=C["panel"],stroke=C["border"],rx=28,shadow=True))
    p.append(rect(100,335,1720,70,C["navy"],rx=18))
    for x,h in zip(xcols,headers):p.append(text(x+20,380,h,17,800,"#FFFFFF",spacing=1))
    rows=[
        ("Qwen2.5-3B",71.4,0.190,"분류·요약 100%",C["blue"]),
        ("Gemma2-2B",61.9,0.143,"비교 대상","#8CA0C8"),
        ("Gemma3-4B",52.4,0.145,"비교 대상","#A1B0CD"),
        ("Gemma3-1B",23.8,0.053,"비교 대상","#BBC6D9"),
    ]
    for i,(model,acc,f1,json_text,accent) in enumerate(rows):
        y=420+i*100
        if i==0:p.append(rect(100,y,1720,88,"#EAF0FF",rx=14))
        p.append(circle(130,y+44,7,accent));p.append(text(160,y+52,model,23,800 if i==0 else 600,C["text"]))
        p.append(text(775,y+52,f"{acc:.1f}%",23,800,accent))
        p.append(text(1080,y+52,f"{f1:.3f}",23,700,C["text"]))
        p.append(text(1380,y+52,json_text,20,700 if i==0 else 500,C["body"]))
    p.append(panel(100,890,1720,74,fill=C["navy"],stroke=C["navy"],rx=20,shadow=False))
    p.append(text(145,937,"선택 이유",18,800,C["cyan"]));p.append(text(290,937,"정확도와 구조화 JSON 안정성의 균형 · Apache 2.0 · 3B 로컬 실행",20,700,"#FFFFFF"))
    return finish(p)


def slide22():
    p = svg_base(22, "TASK-SPECIFIC FINE-TUNING", "박세현", "박세현")
    slide_title(p, "TWO DEPLOYED MODELS", "하나로 합치지 않고 태스크별 모델 2개를 배포했습니다", "같은 Qwen2.5-3B 베이스에 요약·분류 LoRA를 따로 학습해 각각 병합했습니다.", size=43)
    # shared base
    p.append(panel(690,300,540,105,fill=C["navy"],stroke=C["blue"],rx=24,shadow=True))
    p.append(text(960,345,"COMMON BASE",16,800,C["cyan"],anchor="middle",spacing=1.5))
    p.append(text(960,383,"Qwen2.5-3B-Instruct",25,800,"#FFFFFF",anchor="middle"))
    p.append(line(960,405,510,490,"#A8B9D8",4));p.append(line(960,405,1410,490,"#A8B9D8",4))
    # two models
    p.append(panel(120,480,760,390,fill=C["panel"],stroke=C["blue"],rx=30,shadow=True))
    p.append(text(165,540,"분류 모델",20,800,C["blue"],spacing=1.2))
    p.append(text(165,630,"93.2%",72,800,C["blue"]))
    p.append(text(165,680,"실제 문서 103건 · 5-fold 교차검증",21,700,C["text"]))
    p.append(text(165,725,"±2.5%p · 7종 분류 · q8_0",18,500,C["body"]))
    label_tag(p,165,785,"Tasqra-classification",width=310)
    p.append(panel(1040,480,760,390,fill=C["navy"],stroke=C["cyan"],rx=30,shadow=True))
    p.append(text(1085,540,"요약 모델",20,800,C["cyan"],spacing=1.2))
    p.append(text(1085,630,"65.4%",72,800,C["cyan"]))
    p.append(text(1085,680,"평가 26건 · 오차 약 ±8%p",21,700,"#FFFFFF"))
    p.append(text(1085,725,"2~3문장 200자 · q4_k_m · 재학습 예정",18,500,"#BFCBE5"))
    label_tag(p,1085,785,"Tasqra-summation",fill="#243866",color=C["lime"],width=300)
    p.append(text(960,935,"어댑터 둘을 하나로 합치지 못해 배포 모델도 2개입니다.",18,700,C["muted"],anchor="middle"))
    return finish(p)


def slide23():
    p = svg_base(23, "STRUCTURED EXTRACTION", "박세현", "김보현 · 최재정 · 박세현")
    slide_title(p, "THREE SAFETY STRATEGIES", "결정·일정·액션아이템은 같은 방식으로 뽑지 않습니다", "정보 유형에 맞는 후보 생성과 검증을 거친 뒤 모두 PENDING으로 저장합니다.", size=43)
    cards=[
        ("01","결정사항",("구간별 모델 추출", "원문 유사도·중복 제거", "DECIDED / PENDING / REVERSED"),C["blue"],"document"),
        ("02","일정",("Python 날짜 탐지", "모델은 후보 역할만 라벨링", "기간·마감·회의·마일스톤"),C["cyan"],"structure"),
        ("03","액션아이템",("규칙 기반 의무 후보", "모델은 후보 ID 중 선택", "계약·변경계약 범위"),C["lime"],"tasks"),
    ]
    xs=[100,680,1260]
    for i,(no,h,b,accent,kind) in enumerate(cards):
        card_title(p,xs[i],330,no,h,accent,width=500,height=420,body_lines=b,icon_kind=kind,dark=(i==2))
    p.append(arrow(600,540,660,540,"#A8B8D7",3));p.append(arrow(1180,540,1240,540,"#A8B8D7",3))
    p.append(panel(100,815,1660,105,fill=C["navy"],stroke="#31477A",rx=24,shadow=True))
    p.append(text(145,878,"공통 저장 경계",18,800,C["cyan"]));p.append(text(350,878,"Analysis 이력 + 검토 테이블 PENDING → 사람 승인 후 후속 기능에 반영",22,800,"#FFFFFF"))
    return finish(p)


def slide24():
    p = svg_base(24, "LONG DOCUMENT FIX", "박세현", "박세현")
    slide_title(p, "INVISIBLE CHARACTER", "보이지 않는 제어문자 516개가 근거 대조를 깨뜨렸습니다", "사람 눈에는 같은 문장이지만 모델 인용과 원문 문자열 비교는 실패했습니다.", size=42)
    # before after
    p.append(panel(90,315,790,315,fill="#FFF3F3",stroke="#E9A2A2",rx=28,shadow=True))
    p.append(text(135,370,"BEFORE",18,800,"#B34C4C",spacing=1.3))
    p.append(text(135,435,"…계약에 관한 법률」  \\x01  제5조의2…",26,700,C["text"]))
    p.append(text(135,500,"모델 인용에는 \\x01이 없음",20,600,C["body"]))
    p.append(text(135,550,"→ quote not in source",22,800,"#B34C4C"))
    p.append(panel(1040,315,790,315,fill="#F0FAF4",stroke="#86C99B",rx=28,shadow=True))
    p.append(text(1085,370,"AFTER",18,800,"#298451",spacing=1.3))
    p.append(text(1085,435,"…계약에 관한 법률」      제5조의2…",26,700,C["text"]))
    p.append(text(1085,500,"같은 길이의 공백으로 치환",20,600,C["body"]))
    p.append(text(1085,550,"→ 원문 span 복원",22,800,"#298451"))
    p.append(arrow(900,472,1020,472,C["blue"],5))
    fixes=[("01","추출 경계 정리","C0·DEL → 한 글자 공백","오프셋·char_count 유지",C["blue"]),("02","근거 대조 개선","공백·제어문자 차이 허용","틀린 인용만 제거",C["cyan"])]
    for i,(no,h,b1,b2,accent) in enumerate(fixes):
        x=160+i*880
        p.append(panel(x,710,720,190,fill=C["panel"],stroke=accent,rx=26,shadow=True))
        p.append(number_badge(x+30,740,no,accent));p.append(text(x+120,770,h,25,800,C["text"]));p.append(text(x+30,825,b1,19,600,C["body"]));p.append(text(x+30,865,b2,19,600,C["body"]))
    p.append(text(960,962,"PR #89 · d47502e  |  탭·줄바꿈·캐리지리턴은 문단 구조를 위해 보존",17,700,C["muted"],anchor="middle"))
    return finish(p)


def slide25():
    p = svg_base(25, "VALIDATION STATUS", "박세현", "팀")
    slide_title(p, "EVIDENCE, NOT CLAIMS", "확인된 근거와 아직 증명되지 않은 결과를 구분했습니다", "테스트 파일 수·계획 절차 수를 최신 전체 PASS로 바꾸어 말하지 않습니다.", size=43)
    p.append(panel(90,310,820,580,fill="#F0FAF4",stroke="#82C999",rx=30,shadow=True))
    p.append(text(135,370,"확인됨",28,800,"#288351"))
    confirmed=[("97건","기능명세 xlsx ↔ md 일치"),("48개","backend pytest 파일"),("회귀시험","OCR·재조립·제어문자·근거 계약"),("395 passed","2026-08-26의 과거 저장 기준")]
    for i,(v,d) in enumerate(confirmed):
        y=440+i*105
        p.append(text(140,y,v,31,800,"#288351"));p.append(text(350,y,d,20,600,C["text"]))
    p.append(panel(1010,310,820,580,fill="#FFF6ED",stroke="#E6B476",rx=30,shadow=True))
    p.append(text(1055,370,"아직 증명되지 않음",28,800,"#B66B1E"))
    pending=[("최신 전체 PASS","origin/main 전체 실행 기록 없음"),("CI","GitHub Actions 실행 0건"),("79 + 70 절차","단위·통합 수치는 계획 절차"),("실문서 성공","수정 후 저장된 실문서 결과 없음")]
    for i,(v,d) in enumerate(pending):
        y=440+i*105
        p.append(text(1060,y,v,25,800,"#B66B1E"));p.append(text(1320,y,d,18,600,C["text"]))
    p.append(panel(90,925,1740,58,fill=C["navy"],stroke=C["navy"],rx=17,shadow=False))
    p.append(text(960,963,"발표 원칙  ·  실행 기록이 없으면 ‘테스트 존재’까지만 말한다",20,800,"#FFFFFF",anchor="middle"))
    return finish(p)



def slide26():
    p = svg_base(26, "DEMO", "박세현", "팀", dark=True)
    slide_title(p, "RECORDED PRODUCT DEMO", "실제 제품 흐름을 영상으로 확인합니다", "발표 직전 녹화본을 삽입할 16:9 영역입니다.", dark=True, size=48)
    p.append(panel(95,300,1280,640,fill="#070D20",stroke="#334A7D",rx=28,shadow=True))
    p.append(circle(735,610,78,C["blue"],stroke="#6D8BFF",sw=4,extra='filter="url(#shadow)"'))
    p.append('<path d="M 715 568 L 715 652 L 780 610 Z" fill="#FFFFFF"/>')
    p.append(text(735,735,"여기에 녹화 영상 삽입",24,700,"#9EADD0",anchor="middle"))
    chapters=[("01","문서 업로드"),("02","OCR 검수"),("03","근거 QA"),("04","태스크 승인"),("05","대시보드·산출물")]
    for i,(no,h) in enumerate(chapters):
        y=330+i*120
        p.append(number_badge(1450,y,no,C["cyan"],dark=True));p.append(text(1530,y+24,h,20,700,"#FFFFFF"))
        if i<4:p.append(line(1481,y+45,1481,y+92,"#405787",3))
    p.append(text(1450,950,"영상 재생 예상  3~4분",17,600,"#94A5C9"))
    return finish(p)


def slide27():
    p = svg_base(27, "LIMITS · NEXT", "박세현", "팀")
    slide_title(p, "WHAT WE LEARNED", "현재 한계를 다음 우선순위로 바꿨습니다", "기능 개수보다 검색 확장성·모델 품질·검토 무결성·운영 증명을 먼저 개선합니다.", size=45)
    items=[
        ("01","검색 확장성","전체 1,339청크 R@1 36.9%","후보 생성·인덱스·리랭킹 재설계",C["blue"]),
        ("02","요약 품질","26건 기준 65.4% · 오차 큼","평가셋 확대와 재학습",C["cyan"]),
        ("03","검토 UX","액션 후보 수정·취소·stale 방어 제한","결정·일정 수준으로 상태 전이 강화",C["lime"]),
        ("04","운영 검증","최신 전체 PASS·CI·모니터링 부재","재현 가능한 CI와 관측 지표 구축",C["blue2"]),
    ]
    for i,(no,h,current,next_step,accent) in enumerate(items):
        x=90+(i%2)*875;y=315+(i//2)*310
        p.append(panel(x,y,820,265,fill=C["panel"],stroke=accent,rx=28,shadow=True))
        p.append(number_badge(x+30,y+30,no,accent));p.append(text(x+120,y+61,h,26,800,C["text"]))
        p.append(text(x+30,y+125,"현재",16,800,C["muted"],spacing=1.1));p.append(text(x+110,y+125,current,19,600,C["body"]))
        p.append(line(x+30,y+158,x+790,y+158,C["border"],2))
        p.append(text(x+30,y+207,"다음",16,800,accent,spacing=1.1));p.append(text(x+110,y+207,next_step,19,700,C["text"]))
    p.append(text(960,960,"우선순위  ·  검색 R@1 90%를 문서 수 제한 없이 증명하는 것",20,800,C["blue"],anchor="middle"))
    return finish(p)


def slide28():
    p = svg_base(28, "CONCLUSION", "박세현", "팀", dark=True)
    slide_title(p, "FROM DOCUMENTS TO DECISIONS", "문서를 저장하는 도구에서, 판단과 실행을 잇는 플랫폼으로", None, dark=True, size=47)
    cards=[
        ("01","근거를 찾는다",("하이브리드 검색", "원문 위치가 있는 QA"),C["cyan"],"search"),
        ("02","사람이 확정한다",("PENDING 검토", "승인된 정보만 소비"),C["lime"],"check"),
        ("03","업무로 연결한다",("태스크 · 대시보드", "4종 산출물"),C["blue2"],"tasks"),
    ]
    xs=[110,700,1290]
    for i,(no,h,b,accent,kind) in enumerate(cards):
        card_title(p,xs[i],360,no,h,accent,width=520,height=350,body_lines=b,icon_kind=kind,dark=True)
    p.append(panel(110,790,1700,125,fill="#1D2D59",stroke="#344A7E",rx=26,shadow=True))
    p.append(text(960,850,"AI가 제안하고, 사람이 확정하고, 승인된 정보가 실행으로 이어집니다.",29,800,"#FFFFFF",anchor="middle"))
    p.append(text(960,892,"Tasqra",18,800,C["cyan"],anchor="middle",spacing=2.2))
    return finish(p)


def slide29():
    p = svg_base(29, "Q&A", "팀", "팀", dark=True)
    # subtle grid
    for x in range(110,1880,110):p.append(line(x,120,x,970,"#1A294F",1,opacity=.45))
    for y in range(150,980,110):p.append(line(80,y,1840,y,"#1A294F",1,opacity=.45))
    p.append(text(960,365,"Q&A",128,800,"#FFFFFF",anchor="middle",spacing=3))
    p.append(text(960,455,"질문을 받겠습니다",34,600,"#C2CEE7",anchor="middle"))
    tags=[("문서·OCR",C["cyan"]),("RAG·검색",C["blue2"]),("LLM·검토",C["lime"]),("태스크·산출물",C["cyan"])]
    widths=[220,220,220,250];total=sum(widths)+30*3;start=(W-total)/2
    for i,((lab,col),w) in enumerate(zip(tags,widths)):
        p.append(pill(start+sum(widths[:i])+30*i,570,w,54,lab,"#1C2D58",col,stroke="#344A79",size=19))
    p.append(text(960,755,"김보현  ·  박세현  ·  최재정",24,700,"#FFFFFF",anchor="middle"))
    p.append(text(960,805,"FINAL PROJECT PRESENTATION",16,700,"#7186B6",anchor="middle",spacing=2.2))
    return finish(p)


def all_slides():
    slides=[v2.slide1(),v2.slide2(),v2.slide3(),v2.slide4(),v2.slide5()]
    # 최신 근거에 맞춰 단일 멀티태스크 표현을 태스크별 LoRA로 교정한다.
    slides[3]=slides[3].replace("로컬 LLM 비교·멀티태스크 학습","로컬 LLM 비교·태스크별 LoRA 학습")
    slides.extend([
        slide6(),slide7(),slide8(),slide9(),slide10(),slide11(),slide12(),slide13(),slide14(),slide15(),slide16(),slide17(),
        slide18(),slide19(),slide20(),slide21(),slide22(),slide23(),slide24(),slide25(),slide26(),slide27(),slide28(),slide29(),
    ])
    assert len(slides)==29
    return slides


def write_svgs():
    OUT.mkdir(parents=True,exist_ok=True)
    for idx,content in enumerate(all_slides(),start=1):
        path=OUT/f"slide-{idx:02d}.svg"
        path.write_text(content,encoding="utf-8")
        ET.parse(path)
    parts=['<!doctype html><html><head><meta charset="utf-8"><style>',
           'body{margin:0;background:#dce4f1;font-family:Arial,sans-serif}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;padding:18px}.item{background:white;padding:6px;box-shadow:0 5px 18px #0e162f22}.item img{width:100%;display:block}.item b{display:block;padding:6px;color:#16234a}',
           '</style></head><body><div class="grid">']
    for idx in range(1,30):parts.append(f'<div class="item"><b>{idx:02d}</b><img src="slide-{idx:02d}.svg"></div>')
    parts.append('</div></body></html>')
    (OUT/'preview.html').write_text(''.join(parts),encoding='utf-8')
    print(f"SVG slides written: {OUT} (29)")


def package_pptx():
    count=29
    pngs=[PNG_DIR/f"slide-{i:02d}.png" for i in range(1,count+1)]
    missing=[str(p) for p in pngs if not p.exists()]
    if missing: raise SystemExit("PNG files missing: "+", ".join(missing[:5]))
    for p in pngs:
        d=p.read_bytes(); assert d[:8]==b'\x89PNG\r\n\x1a\n'; assert struct.unpack('>II',d[16:24])==(1920,1080),(p,struct.unpack('>II',d[16:24]))
    stage=OUT/'.pptx-stage'
    if stage.exists():shutil.rmtree(stage)
    for d in ['_rels','docProps','ppt/_rels','ppt/slides/_rels','ppt/slides','ppt/slideMasters/_rels','ppt/slideMasters','ppt/slideLayouts/_rels','ppt/slideLayouts','ppt/theme','ppt/media']:(stage/d).mkdir(parents=True,exist_ok=True)
    overrides=[
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>']
    overrides += [f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>' for i in range(1,count+1)]
    types='<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>'+''.join(overrides)+'</Types>'
    (stage/'[Content_Types].xml').write_text(types,encoding='utf-8')
    (stage/'_rels/.rels').write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/><Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/></Relationships>''',encoding='utf-8')
    (stage/'docProps/core.xml').write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Tasqra 최종 발표 29장</dc:title><dc:creator>김보현 · 박세현 · 최재정</dc:creator><cp:lastModifiedBy>Kiro</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-09-08T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-08T00:00:00Z</dcterms:modified></cp:coreProperties>''',encoding='utf-8')
    (stage/'docProps/app.xml').write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office PowerPoint</Application><PresentationFormat>Widescreen</PresentationFormat><Slides>{count}</Slides><Company>Tasqra</Company></Properties>''',encoding='utf-8')
    sld_ids=''.join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1,count+1))
    presentation=f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{sld_ids}</p:sldIdLst><p:sldSz cx="{EMU_W}" cy="{EMU_H}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'''
    (stage/'ppt/presentation.xml').write_text(presentation,encoding='utf-8')
    rels=['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">','<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    rels += [f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>' for i in range(1,count+1)]
    rels.append('</Relationships>');(stage/'ppt/_rels/presentation.xml.rels').write_text(''.join(rels),encoding='utf-8')
    master='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Blank Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'''
    (stage/'ppt/slideMasters/slideMaster1.xml').write_text(master,encoding='utf-8')
    (stage/'ppt/slideMasters/_rels/slideMaster1.xml.rels').write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>''',encoding='utf-8')
    layout='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld></p:sldLayout>'''
    (stage/'ppt/slideLayouts/slideLayout1.xml').write_text(layout,encoding='utf-8')
    (stage/'ppt/slideLayouts/_rels/slideLayout1.xml.rels').write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>''',encoding='utf-8')
    theme='''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Tasqra"><a:themeElements><a:clrScheme name="Tasqra"><a:dk1><a:srgbClr val="0E162F"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="16234A"/></a:dk2><a:lt2><a:srgbClr val="F4F7FC"/></a:lt2><a:accent1><a:srgbClr val="315BD8"/></a:accent1><a:accent2><a:srgbClr val="3BC7F4"/></a:accent2><a:accent3><a:srgbClr val="C9E85B"/></a:accent3><a:accent4><a:srgbClr val="5576E8"/></a:accent4><a:accent5><a:srgbClr val="475569"/></a:accent5><a:accent6><a:srgbClr val="DCE5F1"/></a:accent6><a:hlink><a:srgbClr val="315BD8"/></a:hlink><a:folHlink><a:srgbClr val="16234A"/></a:folHlink></a:clrScheme><a:fontScheme name="Tasqra"><a:majorFont><a:latin typeface="Noto Sans KR"/><a:ea typeface="Noto Sans KR"/><a:cs typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Noto Sans KR"/><a:ea typeface="Noto Sans KR"/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Tasqra"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'''
    (stage/'ppt/theme/theme1.xml').write_text(theme,encoding='utf-8')
    for i,png in enumerate(pngs,start=1):
        shutil.copyfile(png,stage/f'ppt/media/image{i}.png')
        slide=f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr><p:pic><p:nvPicPr><p:cNvPr id="2" name="Tasqra Slide {i}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{EMU_W}" cy="{EMU_H}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'''
        srels=f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{i}.png"/></Relationships>'''
        (stage/f'ppt/slides/slide{i}.xml').write_text(slide,encoding='utf-8');(stage/f'ppt/slides/_rels/slide{i}.xml.rels').write_text(srels,encoding='utf-8')
    if PPTX_PATH.exists():PPTX_PATH.unlink()
    with zipfile.ZipFile(PPTX_PATH,'w',zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(stage.rglob('*')):
            if f.is_file():zf.write(f,f.relative_to(stage).as_posix())
    shutil.rmtree(stage)
    print(f"PPTX written: {PPTX_PATH}")


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['svg','pptx','all'],nargs='?',default='svg');args=parser.parse_args()
    if args.mode in {'svg','all'}:write_svgs()
    if args.mode in {'pptx','all'}:package_pptx()


if __name__=='__main__':main()
