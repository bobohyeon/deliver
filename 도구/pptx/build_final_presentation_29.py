#!/usr/bin/env python3
"""
① 이 파일의 책임: Tasqra 최종 발표 28장 전체본을 SVG와 PPTX로 생성한다.
② 다른 파일과의 관계: 확정된 5장 파일럿의 디자인 헬퍼를 재사용하고, 산출물/최종발표/전체본에 결과를 만든다.
③ Spring 비교: 슬라이드 정의가 View 템플릿, 이 스크립트가 전체 덱을 조립하는 ViewResolver 역할을 한다.
"""

from __future__ import annotations

import argparse
import os
import re
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
PPTX_PATH = OUT / "Tasqra_최종발표_28장_v1.pptx"


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
    accent = C["cyan"] if dark else C["blue"]
    p.append(text(80, 125, kicker, 18, 800, accent, spacing=1.6))
    p.append(text(80, 195, title_value, size, 800, "#FFFFFF" if dark else C["text"], spacing=-0.8))
    if subtitle:
        p.append(text(82, 245, subtitle, 22, 500, "#B9C6E5" if dark else C["body"]))
    # 제목 아래의 짧은 강조선으로 각 장의 발표 핵심 문장을 빠르게 찾게 한다.
    p.append(rect(80, 273, 118, 7, accent, rx=4))
    p.append(rect(206, 273, 24, 7, C["lime"] if dark else C["cyan"], rx=4))


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


def card_title(
    p, x, y, no, heading, accent, *, width=470, height=250, body_lines=(),
    icon_kind=None, dark=False, heading_size=30, body_size=20,
):
    fill = "#17264F" if dark else C["panel"]
    stroke = accent if dark else C["border"]
    p.append(panel(x, y, width, height, fill=fill, stroke=stroke, rx=26, shadow=True, sw=2))
    p.append(rect(x, y, width, 10, accent, rx=5))
    p.append(number_badge(x + 28, y + 32, no, accent, dark=dark))
    if icon_kind:
        p.append(circle(x + width - 62, y + 63, 35, "#24345F" if dark else C["soft"], stroke=accent, sw=2))
        p.append(icon(icon_kind, x + width - 62, y + 63, 32, accent, 3))
    p.append(text(x + 30, y + 116, heading, heading_size, 800, "#FFFFFF" if dark else C["text"]))
    if body_lines:
        p.append(multiline(x + 30, y + 166, body_lines, body_size, 500, "#C8D4EC" if dark else C["body"], line_height=1.5))


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


def slide3():
    p = v2.base(light=True, page="02", label="SERVICE GOAL")
    v2.title_block(p, "HUMAN IN THE LOOP", ["문서에서 찾은 정보를", "사람의 확인을 거쳐 업무로 연결합니다"], title_size=46)
    p.append(rect(110, 350, 118, 7, C["blue"], rx=4))
    p.append(rect(236, 350, 24, 7, C["cyan"], rx=4))
    cards = [
        (110, "01", "search", "근거를 찾는다", ("문서명·페이지와 함께", "필요한 내용을 찾습니다."), C["blue"]),
        (680, "02", "structure", "정보를 나눠 정리한다", ("결정·일정·금액과 계약 이행", "태스크 후보를 구분해 저장합니다."), C["cyan"]),
        (1250, "03", "check", "사람이 확정한다", ("확인한 정보만 실제 업무와", "산출물에 사용합니다."), C["lime"]),
    ]
    for x, no, kind, heading, body, accent in cards:
        p.append(rect(x, 405, 500, 300, C["panel"], rx=28, stroke=accent, sw=2, extra='filter="url(#softShadow)"'))
        p.append(circle(x + 250, 480, 48, C["soft"], stroke=accent, sw=3))
        p.append(icon(kind, x + 250, 480, 42, accent, 3))
        p.append(pill(x + 30, 430, 58, 34, no, C["soft_blue"], C["blue"], size=15))
        p.append(text(x + 250, 575, heading, 29, 800, C["text"], anchor="middle"))
        p.append(multiline(x + 250, 625, body, 20, 500, C["body"], line_height=1.45, anchor="middle"))
    p.append(rect(110, 770, 1640, 190, C["navy"], rx=28, extra='filter="url(#softShadow)"'))
    flow = [(330, "인공지능 제안", C["cyan"]), (960, "사람 확인", C["lime"]), (1590, "승인 정보만 반영", C["cyan"])]
    for i, (x, label, accent) in enumerate(flow):
        p.append(circle(x, 855, 42, "#243768", stroke=accent, sw=3))
        p.append(text(x, 863, str(i + 1), 20, 800, "#FFFFFF", anchor="middle"))
        p.append(text(x, 925, label, 24, 800, "#FFFFFF", anchor="middle"))
        if i < 2:
            p.append(arrow(x + 60, 855, flow[i + 1][0] - 60, 855, "#6076A8", 4))
    return finish(p)


def slide6():
    p = svg_base(6, "ARCHITECTURE", "김보현", "최재정 · 공통")
    slide_title(
        p,
        "REQUEST FLOW",
        "하나의 요청이 FastAPI에서 두 실행 경로로 나뉩니다",
        "바로 끝나는 요청은 데이터베이스로, 오래 걸리는 작업은 대기열과 Worker로 보냅니다.",
        size=43,
    )

    # 왼쪽 큰 영역은 위에서 아래로 읽는 요청 흐름에만 사용한다.
    p.append(panel(70, 300, 1320, 650, fill="#F7F9FD", stroke=C["border"], rx=28, shadow=False))
    p.append(panel(420, 325, 620, 76, fill=C["panel"], stroke=C["blue"], rx=18, shadow=True))
    p.append(text(450, 357, "사용자 화면", 15, 800, C["blue"], spacing=1.0))
    p.append(text(1005, 370, "React · Vite  /  Axios 요청", 21, 800, C["text"], anchor="end"))
    p.append(arrow(730, 410, 730, 445, "#8EA4CC", 5))
    p.append(panel(420, 455, 620, 76, fill=C["navy"], stroke=C["cyan"], rx=18, shadow=True))
    p.append(text(450, 487, "요청 진입점", 15, 800, C["cyan"], spacing=1.0))
    p.append(text(1005, 500, "FastAPI  ·  검증과 업무 처리", 21, 800, "#FFFFFF", anchor="end"))

    # FastAPI에서 동기·비동기 경로로 갈라지는 분기선을 크게 보여 준다.
    p.append(line(730, 531, 730, 575, "#6E87B8", 5))
    p.append(line(380, 575, 1080, 575, "#6E87B8", 5))
    p.append(arrow(380, 575, 380, 610, C["blue"], 5))
    p.append(arrow(1080, 575, 1080, 610, C["cyan"], 5))

    p.append(panel(110, 620, 540, 290, fill=C["panel"], stroke=C["blue"], rx=24, shadow=True))
    p.append(pill(140, 645, 185, 38, "바로 끝나는 요청", C["soft_blue"], C["blue"], size=15))
    p.append(panel(165, 705, 430, 66, fill="#F8FAFD", stroke=C["blue2"], rx=16, shadow=False))
    p.append(text(190, 746, "SQLAlchemy  ·  트랜잭션과 데이터 접근", 18, 800, C["text"]))
    p.append(arrow(380, 777, 380, 805, "#8EA4CC", 4))
    p.append(panel(165, 815, 430, 66, fill="#F8FAFD", stroke=C["lime"], rx=16, shadow=False))
    p.append(text(190, 856, "PostgreSQL  ·  업무 데이터와 pgvector", 18, 800, C["text"]))

    p.append(panel(810, 620, 540, 290, fill=C["navy"], stroke=C["cyan"], rx=24, shadow=True))
    p.append(pill(840, 645, 190, 38, "오래 걸리는 작업", "#243866", C["cyan"], size=15))
    async_nodes = [
        (700, "Redis 대기열", "작업 등록 · 중단되어도 유지"),
        (778, "Celery Worker", "OCR · 문서 나누기 · AI 분석"),
        (856, "공유 자원", "PostgreSQL · 문서 파일 · AI 모델"),
    ]
    for y, heading, body in async_nodes:
        p.append(panel(850, y, 460, 58, fill="#1D315F", stroke="#3A5289" if heading != "공유 자원" else C["lime"], rx=14, shadow=False))
        p.append(text(875, y + 25, heading, 17, 800, "#FFFFFF"))
        p.append(text(1285, y + 25, body, 14, 600, "#C8D4EC", anchor="end"))
        if y < 856:
            p.append(arrow(1080, y + 61, 1080, y + 73, "#6F89BF", 3))

    # 선택 이유는 오른쪽 보조 열로 축소해 흐름보다 먼저 보이지 않게 한다.
    p.append(panel(1430, 300, 410, 650, fill=C["panel"], stroke=C["border"], rx=28, shadow=True))
    p.append(text(1470, 355, "이렇게 나눈 이유", 23, 800, C["text"]))
    reasons = [
        (415, "01", "화면 응답 분리", "긴 작업이 요청을 막지 않음", C["blue"]),
        (535, "02", "작업 보존", "Worker 중단에도 Redis에 유지", C["cyan"]),
        (655, "03", "같은 기준 재조회", "같은 DB와 문서 파일 사용", C["blue2"]),
        (775, "04", "모델 교체 가능", "호환 요청과 로컬 모델 경로", C["lime"]),
    ]
    for y, no, heading, body, accent in reasons:
        p.append(circle(1475, y, 22, accent))
        p.append(text(1475, y + 6, no, 12, 800, "#FFFFFF" if accent != C["lime"] else C["rail"], anchor="middle"))
        p.append(text(1515, y - 4, heading, 18, 800, C["text"]))
        p.append(text(1515, y + 25, body, 14, 600, C["body"]))
    p.append(text(1635, 908, "요청  →  분기  →  실행  →  저장", 16, 800, C["blue"], anchor="middle"))
    return finish(p)


def slide7():
    p = svg_base(7, "DATA MODEL", "김보현", "최재정")
    slide_title(p, "RELATIONAL CORE", "데이터가 서로 연결되는 방식", "프로젝트를 기준으로 구성원·문서·태스크가 갈라지고, 문서에서 검색·분석 데이터가 이어집니다.")

    # 왼쪽의 프로젝트에서 오른쪽 자식 데이터로 흐르는 관계를 한 방향으로 정렬한다.
    project = (100, 475, 430, 220)
    children = [
        (760, 315, 430, 150, "USER · MEMBER", ("소유자와 구성원", "권한 역할"), C["cyan"]),
        (760, 510, 430, 170, "DOCUMENT", ("원문 경로와 메타데이터", "추출본문 · OCR · 분석 이력"), C["blue2"]),
        (760, 725, 430, 150, "TASK · REVIEW", ("태스크와 검토 제안", "결정 · 일정 · 액션 · 금액"), C["lime"]),
        (1390, 510, 430, 170, "CHUNK · ANALYSIS", ("본문 구간과 1024D 벡터", "모델 · 버전 · 원문 좌표"), C["cyan"]),
    ]

    # 카드보다 선을 먼저 그려 화살표가 카드 위를 가로지르지 않게 한다.
    p.append(line(530, 585, 650, 585, "#6E8AC5", 5))
    p.append(line(650, 390, 650, 800, "#9FB2D5", 4))
    for target_y, label in ((390, "구성원"), (595, "문서"), (800, "태스크·검토")):
        p.append(arrow(650, target_y, 742, target_y, "#6E8AC5", 5))
        label_tag(p, 555, target_y - 17, label, width=105)
    p.append(arrow(1198, 595, 1372, 595, C["cyan"], 5))
    label_tag(p, 1225, 548, "조각·분석", width=125)

    x, y, w, h = project
    p.append(panel(x, y, w, h, fill=C["navy"], stroke=C["blue"], rx=28, shadow=True))
    p.append(text(x + 35, y + 58, "PROJECT", 24, 800, C["cyan"], spacing=1.0))
    p.append(text(x + 35, y + 115, "프로젝트 업무 범위", 25, 800, "#FFFFFF"))
    p.append(multiline(x + 35, y + 158, ("권한 · 문서 · 태스크를", "하나의 기준으로 연결"), 17, 600, "#C8D4EC", line_height=1.35))
    p.append(text(x + w - 28, y + 40, "기준", 13, 800, "#8EA3CF", anchor="end", spacing=1.2))

    for x, y, w, h, heading, body, accent in children:
        p.append(panel(x, y, w, h, fill=C["panel"], stroke=accent, rx=24, shadow=True))
        p.append(text(x + 28, y + 45, heading, 19, 800, accent, spacing=.8))
        p.append(multiline(x + 28, y + 88, body, 17, 600, C["body"], line_height=1.35))
        p.append(text(x + w - 25, y + 32, "연결", 12, 800, C["muted"], anchor="end", spacing=1.0))

    p.append(panel(100, 910, 1720, 68, fill=C["panel"], stroke=C["border"], rx=18, shadow=False))
    p.append(text(135, 952, "원문 파일", 15, 800, C["blue"], spacing=1.0))
    p.append(text(255, 952, "공유 문서 경로에 저장", 18, 700, C["text"]))
    p.append(text(815, 952, "추출 본문", 15, 800, C["cyan"], spacing=1.0))
    p.append(text(940, 952, "문서와 1:1로 연결", 18, 700, C["text"]))
    p.append(text(1400, 952, "화살표 = 연결 방향", 15, 700, C["muted"]))
    return finish(p)


def slide8():
    p = svg_base(8, "STATE DESIGN", "김보현", "최재정 · 박세현")
    slide_title(p, "SEPARATE LIFECYCLES", "상태를 분리한 운영 설계", "문서 추출·OCR 검수·LLM 분석을 하나의 상태로 섞지 않았습니다.")
    lanes=[
        (300,"DOCUMENT EXTRACTION","문서 추출",("PENDING","EXTRACTING","EXTRACTED"),"FAILED → PENDING 재시도",C["blue"]),
        (505,"OCR REVIEW","OCR 검수",("PENDING","IN_PROGRESS","COMPLETED"),"대상 없음 → NOT_REQUIRED",C["cyan"]),
        (710,"ANALYSIS JOB","LLM 분석",("PENDING","RUNNING","COMPLETED / PARTIAL / FAILED"),"text_version + 원문 revision 검증",C["lime"]),
    ]
    for y,kicker,heading,states,note,accent in lanes:
        p.append(panel(80,y,1760,170,fill=C["panel"],stroke=C["border"],rx=24,shadow=True))
        p.append(rect(80,y,8,170,accent,rx=4))
        p.append(text(120,y+42,kicker,14,800,accent,spacing=1.4))
        p.append(text(120,y+88,heading,25,800,C["text"]))
        p.append(text(120,y+128,note,15,600,C["muted"]))
        widths=[245,245,360]
        xs=[500,825,1150]
        active_fill = {
            C["blue"]: "#E8EEFF",
            C["cyan"]: "#E6F8FC",
            C["lime"]: "#F0F6D8",
        }[accent]
        active_text = {
            C["blue"]: C["blue"],
            C["cyan"]: "#1689A8",
            C["lime"]: "#607816",
        }[accent]
        for i,(state,x,w) in enumerate(zip(states,xs,widths)):
            active=i==1
            p.append(panel(x,y+38,w,78,fill=active_fill if active else "#F8FAFD",stroke=accent,rx=18,shadow=False))
            p.append(text(x+w/2,y+86,state,18 if i<2 else 16,800,active_text if active else accent,anchor="middle"))
            if i<2:p.append(arrow(x+w+18,y+77,xs[i+1]-18,y+77,"#9DAFCE",3))
        p.append(panel(1550,y+34,245,86,fill="#F3F6FB",stroke=C["border"],rx=16,shadow=False))
        p.append(text(1575,y+66,"STATE OWNER",12,800,C["muted"],spacing=1.1))
        p.append(text(1575,y+98,"Document" if y<500 else ("OCR Review" if y<700 else "AnalysisJob"),17,700,C["text"]))
    p.append(panel(80,910,1760,75,fill=C["navy"],stroke=C["navy"],rx=20,shadow=False))
    p.append(text(120,956,"독립 저장",17,800,C["cyan"],spacing=1.0))
    p.append(text(260,956,"한 작업의 실패가 다른 수명주기의 성공 상태를 되돌리지 않습니다.",20,700,"#FFFFFF"))
    p.append(pill(1490,927,305,40,"NO SHARED STATUS FLAG","#243866",C["lime"],size=15))
    return finish(p)


def slide9():
    p = svg_base(9, "RAG", "김보현", "김보현")
    slide_title(p, "INDEX → RETRIEVE", "RAG 색인과 검색", "문서 구조와 원문 위치를 보존한 청크에서 근거를 찾습니다.", size=44)
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
        card_title(p, x, 360, no, heading, accent, width=285, height=285, body_lines=body, icon_kind=kind, heading_size=24, body_size=17)
        if idx < len(steps)-1:
            p.append(arrow(x+292, 500, xs[idx+1]-10, 500, "#AABADB", 3))
    p.append(panel(85, 705, 1705, 210, fill=C["navy"], stroke="#31477A", rx=28, shadow=True))
    p.append(text(130, 765, "검색 요청", 20, 800, C["cyan"], spacing=1))
    p.append(text(130, 822, "질문을 검색용 숫자로 바꾼 뒤, 권한이 있는 프로젝트 안에서 뜻이 가까운 문서 조각을 찾습니다.", 27, 700, "#FFFFFF"))
    p.append(text(130, 870, "검색 모델을 바꾸면 기존 문서도 새 모델에 맞게 다시 준비해야 합니다.", 18, 500, "#B9C8E5"))
    label_tag(p, 1530, 755, "실모델 설정 조건", fill="#243A70", color=C["lime"], width=210)
    return finish(p)


def slide10():
    p = svg_base(10, "HYBRID SEARCH", "김보현", "김보현")
    slide_title(
        p,
        "COMPLEMENTARY RETRIEVAL",
        "서로 다른 누락 위험을 한 검색창에서 보완했습니다",
        "키워드는 정확한 글자를, 의미 검색은 표현이 다른 문장을 찾고 두 결과의 순위를 합칩니다.",
        size=42,
    )

    # 두 검색은 강점보다 '각자 무엇을 놓치는가'를 먼저 보여 준다.
    search_cards = [
        (
            80,
            "A",
            "키워드 검색",
            "정확한 글자에 강함",
            ("계약번호 · 금액 · 날짜", "연속 문자열은 반드시 포함"),
            "놓침  ·  ‘휴가 규정’으로 ‘연차 사용 기준’ 찾기",
            C["cyan"],
            "document",
        ),
        (
            1160,
            "B",
            "의미 검색",
            "표현이 달라도 뜻을 찾음",
            ("질문·문서 조각 임베딩", "pgvector 코사인 순위"),
            "놓침  ·  번호·금액처럼 글자 자체가 정답인 표현",
            C["blue2"],
            "search",
        ),
    ]
    for x, no, heading, strength, body, miss, accent, kind in search_cards:
        p.append(panel(x, 320, 680, 350, fill=C["navy"], stroke=accent, rx=28, shadow=True))
        p.append(number_badge(x + 30, 350, no, accent, dark=True))
        p.append(circle(x + 605, 392, 38, "#24345F", stroke=accent, sw=2))
        p.append(icon(kind, x + 605, 392, 34, accent, 3))
        p.append(text(x + 30, 450, heading, 30, 800, "#FFFFFF"))
        p.append(text(x + 30, 495, strength, 17, 800, accent, spacing=.3))
        p.append(multiline(x + 30, 540, body, 18, 600, "#C8D4EC", line_height=1.5))
        p.append(panel(x + 30, 600, 620, 48, fill="#1D315F", stroke="#3A5289", rx=14, shadow=False))
        p.append(text(x + 50, 631, miss, 15, 700, "#FFFFFF"))

    # 점수의 단위가 다르므로 가운데에서는 순위만 사용한다.
    p.append(circle(960, 495, 130, C["lime"], stroke="#A9C932", sw=4, extra='filter="url(#shadow)"'))
    p.append(text(960, 477, "RRF", 38, 800, C["rail"], anchor="middle"))
    p.append(text(960, 520, "순위만 합산", 18, 800, C["rail"], anchor="middle"))
    p.append(text(960, 551, "각 상위 30개", 14, 700, C["rail"], anchor="middle"))
    p.append(arrow(770, 495, 815, 495, C["cyan"], 4))
    p.append(arrow(1150, 495, 1105, 495, C["blue2"], 4))

    reasons = [
        (80, "점수를 그대로 더하지 않음", ("글자 유사도와 벡터 거리는", "단위·분포가 달라 직접 비교 불가"), C["blue"]),
        (650, "각 검색 안에서 순위 계산", ("키워드·의미 검색에서", "각각 상위 30개 후보를 선택"), C["cyan"]),
        (1220, "하나의 결과 목록으로", ("RRF가 두 순위를 합쳐", "사용자에게 최종 순위로 제공"), C["lime"]),
    ]
    for x, heading, body, accent in reasons:
        p.append(panel(x, 735, 520, 205, fill=C["panel"], stroke=C["border"], rx=22, shadow=False))
        p.append(rect(x, 735, 7, 205, accent, rx=4))
        p.append(text(x + 28, 785, heading, 20, 800, C["text"]))
        p.append(multiline(x + 28, 835, body, 17, 600, C["body"], line_height=1.55))
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


def manual_slide21_reranker():
    """기존 12번 재정렬 모델 장을 새 발표 경계의 21번·박세현 발표용으로 만든다."""
    content = slide12()
    assert content.count("12  /  RERANKER") == 1
    assert content.count("PRESENTER  김보현") == 1
    return content.replace("12  /  RERANKER", "21  /  RERANKER").replace(
        "PRESENTER  김보현", "PRESENTER  박세현"
    )


def slide13():
    p = svg_base(13, "GROUNDED QA", "김보현", "김보현")
    slide_title(p, "EVIDENCE CONTRACT", "답변보다 먼저 근거의 경계를 설계했습니다", "검색 결과를 토큰 예산 안에 조립하고, 모델이 반환한 근거 ID를 서버가 검증합니다.", size=42)
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
        card_title(p,xs[i],330,no,head,accent,width=300,height=310,body_lines=body,icon_kind=kind,heading_size=23,body_size=17)
        if i<4:p.append(arrow(xs[i]+305,485,xs[i+1]-5,485,"#A9BAD9",3))
    p.append(panel(90,700,1740,210,fill=C["navy"],stroke="#31477A",rx=28,shadow=True))
    p.append(text(135,760,"사용자에게 보여주는 결과",18,800,C["cyan"],spacing=1.0))
    p.append(text(135,817,"답변과 함께 문서명 · 페이지 · 원문 위치를 보여줍니다",26,800,"#FFFFFF"))
    p.append(text(135,865,"근거를 찾지 못하면 인공지능을 호출하지 않고 정해진 안내만 보여줍니다.",18,500,"#BFCBE5"))
    label_tag(p,1380,755,"서버가 확인하는 범위",fill="#243864",color=C["lime"],width=360)
    p.append(text(1380,825,"근거 번호와 문서 접근 권한을 확인합니다.",18,600,"#FFFFFF"))
    return finish(p)


def slide14():
    p = svg_base(14, "HUMAN REVIEW", "김보현", "김보현 · 최재정")
    slide_title(p, "TYPE-SPECIFIC REVIEW", "정보마다 검토 방법과 반영 위치가 다릅니다", "공통점은 검토 대기로 저장한다는 것뿐이며, 승인 뒤의 동작은 정보 종류별로 나뉩니다.", size=45)
    cards = [
        (80, "01", "결정사항 · 일정", "승인 · 수정 승인 · 거절", ("확정 목록", "보고서·업무 문서"), C["blue"], False),
        (660, "02", "금액", "승인 · 수정 승인 · 거절", ("완료된 확정본", "대시보드·질의응답·산출물"), C["cyan"], False),
        (1240, "03", "계약 이행 태스크 후보", "승인 · 거절", ("승인하면 실제 태스크 생성", "거절하면 후보에서 제외"), C["lime"], True),
    ]
    for x, no, heading, review, outputs, accent, dark in cards:
        fill = C["navy"] if dark else C["panel"]
        fg = "#FFFFFF" if dark else C["text"]
        body = "#C6D2EA" if dark else C["body"]
        p.append(panel(x, 325, 520, 525, fill=fill, stroke=accent, rx=30, shadow=True))
        p.append(number_badge(x + 30, 355, no, accent, dark=dark))
        p.append(text(x + 30, 445, heading, 29 if len(heading) < 11 else 25, 800, fg))
        p.append(text(x + 30, 505, "사람이 할 수 있는 것", 14, 800, accent, spacing=1.2))
        p.append(panel(x + 30, 530, 460, 76, fill="#1D315F" if dark else "#F7F9FD", stroke="#3A5289" if dark else C["border"], rx=16, shadow=False))
        p.append(text(x + 260, 578, review, 20, 800, fg, anchor="middle"))
        p.append(text(x + 30, 665, "승인 뒤 반영", 14, 800, accent, spacing=1.2))
        for i, value in enumerate(outputs):
            y = 700 + i * 58
            p.append(circle(x + 44, y - 6, 6, accent))
            p.append(text(x + 68, y, value, 19, 700, body))
        p.append(pill(x + 30, 792, 190, 38, "검토 대기로 저장", "#243866" if dark else C["soft_blue"], C["lime"] if dark else accent, size=14))
    p.append(panel(80, 900, 1680, 78, fill=C["navy"], stroke=C["navy"], rx=20, shadow=False))
    p.append(text(120, 949, "핵심", 16, 800, C["cyan"], spacing=1.2))
    p.append(text(235, 949, "모든 제안을 한 소비처로 보내지 않고, 정보 종류에 맞는 기능으로만 반영합니다.", 23, 800, "#FFFFFF"))
    return finish(p)


def slide15():
    p = svg_base(15, "ACTION TO TASK", "김보현", "최재정")
    slide_title(p, "CONTROLLED AUTOMATION", "계약 이행 태스크 후보는 승인 전까지 태스크가 아닙니다", "계약·변경계약 문서에서 찾은 행동·의무 후보만 한 건씩 검토해 실제 태스크로 만듭니다.", size=42)
    steps=[
        ("01","행동·의무 후보",("계약·변경계약 문서", "규칙으로 근거 구간 찾기"),C["blue"],"document"),
        ("02","인공지능 선택",("찾아둔 항목 중 선택", "새 태스크를 자유 생성하지 않음"),C["cyan"],"search"),
        ("03","검토 대기 저장",("행위자·기한·근거", "task_suggestions"),C["lime"],"structure"),
        ("04","승인 · 거절",("승인하면 실제 태스크 생성", "거절하면 후보 제외"),C["blue2"],"check"),
    ]
    xs=[100,540,980,1420]
    for i,s in enumerate(steps):
        no,head,body,accent,kind=s
        card_title(p,xs[i],350,no,head,accent,width=360,height=330,body_lines=body,icon_kind=kind,dark=(i==3),heading_size=25,body_size=18)
        if i<3:p.append(arrow(xs[i]+370,515,xs[i+1]-10,515,"#A9BADA",4))
    p.append(panel(100,760,1680,150,fill=C["navy"],stroke="#31477A",rx=28,shadow=True))
    p.append(text(145,815,"태스크 후보의 동작",18,800,C["cyan"],spacing=1.0))
    p.append(text(145,865,"후보를 한 건씩 확인하고, 승인하면 실제 태스크를 만들며 거절하면 후보 목록에서 제외합니다.",23,700,"#FFFFFF"))
    return finish(p)


def slide16():
    p = svg_base(16, "AMOUNT SNAPSHOT", "김보현", "김보현")
    slide_title(p, "SAFE RE-ANALYSIS", "금액을 다시 분석해도 집계는 흔들리지 않습니다", "새 분석의 검토가 끝날 때까지 직전 완료 스냅샷을 계속 사용합니다.", size=46)
    # DB 레코드처럼 보이는 현재 활성 스냅샷
    p.append(panel(80,305,610,565,fill=C["panel"],stroke=C["blue"],rx=30,shadow=True))
    p.append(text(120,360,"ACTIVE SNAPSHOT",16,800,C["blue"],spacing=1.5))
    p.append(text(120,415,"현재 소비 중",32,800,C["text"]))
    rows=[("review_status","APPROVED / EDITED"),("consumers","Dashboard · QA · Deliverable"),("switch_policy","검토 완료 전 유지"),("source","latest completed analysis")]
    for i,(k,v) in enumerate(rows):
        y=475+i*78
        p.append(rect(120,y,530,1,C["border"]))
        p.append(text(120,y+40,k,14,800,C["muted"],spacing=.8))
        p.append(text(315,y+40,v,17,700,C["text"]))
    p.append(panel(120,795,530,48,fill=C["soft_blue"],stroke=C["border"],rx=14,shadow=False))
    p.append(text(385,826,"ACTIVE POINTER 유지",15,800,C["blue"],anchor="middle",spacing=1.0))
    # 신규 분석 작업 콘솔
    p.append(panel(750,305,520,565,fill="#F8FAFD",stroke=C["cyan"],rx=30,shadow=True))
    p.append(text(790,360,"RE-ANALYSIS JOB",16,800,C["cyan"],spacing=1.5))
    stages=[("01","PENDING","새 Analysis"),("02","IN REVIEW","승인 · 수정 · 거절"),("03","COMPLETE","미결 행 0")]
    for i,(no,state,desc) in enumerate(stages):
        y=425+i*112
        p.append(number_badge(790,y,no,C["cyan"]))
        p.append(text(875,y+24,state,19,800,C["text"]))
        p.append(text(875,y+55,desc,15,500,C["body"]))
        if i<2:p.append(line(821,y+42,821,y+93,"#9EB4D3",3))
    p.append(panel(790,760,440,78,fill=C["navy"],stroke=C["navy"],rx=18,shadow=False))
    p.append(text(820,790,"COMPLETENESS GATE",13,800,C["lime"],spacing=1.0))
    p.append(text(820,820,"추출 행 수 = 검토 완료 행 수",17,700,"#FFFFFF"))
    # 소비처와 원자 전환
    p.append(panel(1330,305,510,565,fill=C["navy"],stroke="#31477A",rx=30,shadow=True))
    p.append(text(1370,360,"CONSISTENT CONSUMERS",16,800,C["cyan"],spacing=1.4))
    consumers=[("대시보드","집계"),("근거 QA","검색 응답"),("산출물","XLSX · PDF")]
    for i,(head,desc) in enumerate(consumers):
        y=420+i*115
        p.append(panel(1370,y,430,88,fill="#1D315F",stroke="#3A5289",rx=18,shadow=False))
        p.append(text(1400,y+38,head,23,800,"#FFFFFF"))
        p.append(text(1765,y+38,desc,18,700,"#D6DFF0",anchor="end"))
        p.append(text(1400,y+69,"모두 같은 확정본 사용",15,700,C["cyan"]))
    p.append(panel(1275,744,550,54,fill=C["lime"],stroke="#A8C62A",rx=17,shadow=False))
    p.append(text(1550,779,"모든 검토가 끝나면 확정본 교체",22,800,C["rail"],anchor="middle"))
    p.append(arrow(1278,858,1625,858,C["lime"],9))
    p.append(circle(1690,858,55,C["lime"],stroke="#A8C62A",sw=4))
    p.append(text(1690,850,"동시",20,800,C["rail"],anchor="middle"));p.append(text(1690,880,"전환",20,800,C["rail"],anchor="middle"))
    p.append(text(80,930,"재분석 중에도 기존 승인 데이터가 화면·QA·산출물에 계속 제공되며, 완료 순간에만 소비 기준이 한 번 바뀝니다.",18,700,C["muted"]))
    return finish(p)


def slide17():
    p = svg_base(17, "DASHBOARD · OUTPUTS", "김보현", "김보현 · 최재정")
    slide_title(p, "FROM APPROVED DATA", "승인된 정보가 대시보드와 산출물로 이어집니다", "사람 검토를 통과한 동일 데이터를 화면과 문서가 함께 사용합니다.", size=45)
    # 실제 제품 대시보드 상단을 축약한 UI 미리보기
    p.append(panel(70,310,900,610,fill="#F7F9FD",stroke=C["border"],rx=28,shadow=True))
    p.append(text(105,350,"PROJECT OVERVIEW",13,800,C["blue"],spacing=1.4))
    p.append(pill(705,328,225,34,"화면 구성 예시",C["soft_blue"],C["blue"],size=13))
    p.append(text(105,390,"대시보드",28,800,C["text"]))
    p.append(text(105,420,"지금 확인할 문서와 우선 처리할 액션 태스크를 확인하세요.",14,500,C["body"]))
    kpis=[("전체 문서","24",C["blue"]),("처리 중","2",C["cyan"]),("추출 완료","20","#298451"),("처리 실패","2","#B34C4C"),("열린 태스크","7",C["blue2"])]
    for i,(label,value,accent) in enumerate(kpis):
        x=105+i*164
        p.append(panel(x,450,148,88,fill=C["panel"],stroke=accent,rx=16,shadow=False))
        p.append(text(x+16,482,label,13,700,C["muted"]))
        p.append(text(x+16,522,value,28,800,accent))
    # 실제 화면의 ‘확인이 필요한 일’ 강조 패널
    p.append(panel(105,565,495,305,fill=C["navy"],stroke="#31477A",rx=22,shadow=False))
    p.append(text(130,610,"확인이 필요한 일",22,800,"#FFFFFF"))
    p.append(pill(510,585,62,34,"6건","#243866",C["cyan"],size=14))
    reviews=[("문서","처리 실패","1","확인하기"),("문서","OCR 검수","2","검수하기"),("금액","승인 대기","3","검토하기")]
    for i,(kind,heading,count,action) in enumerate(reviews):
        y=640+i*68
        p.append(panel(130,y,445,54,fill="#1D315F",stroke="#3A5289",rx=13,shadow=False))
        p.append(pill(144,y+12,58,29,kind,"#293F73",C["cyan"],size=11))
        p.append(text(218,y+34,heading,16,800,"#FFFFFF"))
        p.append(text(425,y+34,count+"건",15,800,C["lime"],anchor="end"))
        p.append(text(552,y+34,action,13,700,"#C8D4EC",anchor="end"))
    # 실제 화면의 액션 태스크 카드
    p.append(panel(620,565,315,305,fill=C["panel"],stroke=C["border"],rx=22,shadow=False))
    p.append(text(645,610,"액션 태스크",22,800,C["text"]))
    p.append(text(910,610,"7건",14,800,C["blue"],anchor="end"))
    tasks=[("진행 중","계약 검토 의견 반영","김보현 · 9. 12."),("할 일","보고서 초안 검토","담당자 미정")]
    for i,(state,heading,meta) in enumerate(tasks):
        y=640+i*86
        p.append(panel(645,y,265,72,fill="#F8FAFD",stroke=C["border"],rx=14,shadow=False))
        p.append(pill(660,y+10,70,27,state,C["soft_blue"],C["blue"],size=11))
        p.append(text(660,y+56,heading,15,800,C["text"]))
        p.append(text(892,y+56,meta,11,600,C["muted"],anchor="end"))
    p.append(panel(645,825,265,30,fill=C["soft_blue"],stroke=C["border"],rx=10,shadow=False))
    p.append(text(777,846,"전체 보드 보기  →",13,800,C["blue"],anchor="middle"))
    # 오른쪽: 같은 승인 정보로 만드는 실제 산출물
    p.append(text(1030,345,"만들 수 있는 문서",17,800,C["blue"],spacing=1.4))
    outputs=[("01","주간 보고서","기간 내 문서·완료 태스크"),("02","프로젝트 현황","전체 재료와 향후 계획"),("03","결정사항 대장","승인된 결정 전체"),("04","회의 안건","승인됐지만 미결인 결정")]
    for i,(no,h,b) in enumerate(outputs):
        x=1030+(i%2)*390;y=390+(i//2)*225
        card_title(p,x,y,no,h,[C["blue"],C["cyan"],C["lime"],C["blue2"]][i],width=355,height=190,body_lines=(b,),heading_size=25,body_size=17)
    p.append(panel(1030,850,745,58,fill=C["soft_blue"],stroke=C["border"],rx=16,shadow=False))
    p.append(text(1065,888,"출력 형식",16,800,C["blue"]));p.append(text(1215,888,"엑셀 · 웹 문서 · 마크다운 · PDF",19,800,C["navy"]))
    return finish(p)



def slide18():
    p = svg_base(18, "OCR EVOLUTION", "박세현", "최재정")
    slide_title(
        p,
        "MINI PROJECT → TASQRA",
        "OCR 엔진은 비교로 고르고, 필요한 영역에만 적용했습니다",
        "미니프로젝트의 3종 측정 기준선을 본프로젝트의 텍스트층·OCR·하이브리드 분기로 확장했습니다.",
        size=40,
    )

    # 미니프로젝트에서 실제로 남긴 엔진 비교 기준선.
    p.append(panel(80, 305, 700, 300, fill=C["panel"], stroke=C["border"], rx=26, shadow=True))
    p.append(text(120, 350, "미니프로젝트  ·  OCR 엔진 3종 비교", 18, 800, C["blue"], spacing=.5))
    engines = [
        ("PaddleOCR", "98.1%", "15.5초", C["blue"], True),
        ("EasyOCR", "81.8%", "15.5초", C["cyan"], False),
        ("Tesseract", "64.4%", "0.9초", C["muted"], False),
    ]
    for i, (name, accuracy, latency, accent, selected) in enumerate(engines):
        y = 380 + i * 62
        p.append(panel(y= y, x=120, w=620, h=50, fill=C["navy"] if selected else "#F7F9FD", stroke=accent, rx=14, shadow=False))
        if selected:
            p.append(pill(135, y + 10, 58, 30, "선택", "#243866", C["lime"], size=11))
        p.append(text(215 if selected else 145, y + 32, name, 17, 800, "#FFFFFF" if selected else C["text"]))
        p.append(text(520, y + 32, accuracy, 19, 800, accent if not selected else C["cyan"], anchor="end"))
        p.append(text(710, y + 32, latency, 16, 700, "#C8D4EC" if selected else C["body"], anchor="end"))
    p.append(text(120, 585, "정답 텍스트 대비 CER 기반 정확도  ·  미니프로젝트 저장 기준선", 14, 600, C["muted"]))

    # 숫자에서 선택 이유와 한계를 분리한다.
    p.append(panel(820, 305, 1020, 300, fill=C["navy"], stroke="#31477A", rx=26, shadow=True))
    p.append(pill(860, 340, 160, 38, "선택 결론", "#243866", C["lime"], size=15))
    p.append(text(860, 435, "PaddleOCR", 38, 800, "#FFFFFF"))
    p.append(text(860, 485, "세 엔진 중 정답 정확도가 가장 높아 기본 OCR로 사용", 21, 700, "#FFFFFF"))
    choice_notes = [
        (860, "정확도 우선", "속도가 가장 빠르지는 않음", C["cyan"]),
        (1320, "처리 범위 축소", "모든 페이지를 무조건 OCR하지 않음", C["lime"]),
    ]
    for x, heading, body, accent in choice_notes:
        p.append(panel(x, 520, 430, 62, fill="#1D315F", stroke="#3A5289", rx=14, shadow=False))
        p.append(text(x + 18, 547, heading, 14, 800, accent))
        p.append(text(x + 18, 572, body, 14, 600, "#C8D4EC"))

    # 본프로젝트에서 실제 페이지를 읽는 분기와 좌표 복원 흐름.
    steps = [
        (80, "01", "기존 글자 보존", ("PDF 텍스트층을 먼저 읽고", "같은 이미지 OCR은 생략"), C["blue"]),
        (515, "02", "이미지 영역 OCR", ("텍스트층이 없는 이미지 블록만", "PaddleOCR로 보완"), C["cyan"]),
        (950, "03", "빈 페이지 전체 OCR", ("글자가 전혀 없으면 2배 렌더링", "작은 글자 인식 보완"), C["blue2"]),
        (1385, "04", "좌표·순서 복원", ("PDF 좌표로 되돌린 뒤", "단·표를 보존해 읽기 순서 계산"), C["lime"]),
    ]
    for i, (x, no, heading, body, accent) in enumerate(steps):
        p.append(panel(x, 665, 375, 235, fill=C["panel"], stroke=accent, rx=24, shadow=True))
        p.append(number_badge(x + 25, 690, no, accent))
        p.append(text(x + 25, 760, heading, 23, 800, C["text"]))
        p.append(multiline(x + 25, 805, body, 16, 600, C["body"], line_height=1.55))
        if i < 3:
            p.append(arrow(x + 382, 780, steps[i + 1][0] - 10, 780, "#9FB1D1", 3))
    p.append(text(960, 960, "미니프로젝트의 엔진 비교  →  필요한 영역만 OCR  →  수정 가능한 좌표·읽기 순서 보존", 18, 800, C["blue"], anchor="middle"))
    return finish(p)


def slide19():
    p = svg_base(19, "OCR REVIEW", "박세현", "최재정")
    slide_title(p, "TEXT INTEGRITY", "글자 인식 결과를 고치면 검색용 본문도 함께 고칩니다", "수정 범위, 본문, 뒤 문장의 위치, 문서 버전을 한 번에 바꿔 서로 어긋나지 않게 합니다.", size=43)
    p.append(panel(80,300,1760,335,fill="#F8FAFD",stroke=C["border"],rx=28,shadow=False))
    p.append(pill(115,325,145,36,"미니프로젝트",C["soft_blue"],C["blue"],size=13))
    p.append(text(280,350,"엔진 비교 · 좌표 정렬",16,800,C["body"]))
    p.append(arrow(520,343,600,343,"#9EB0CE",3))
    p.append(pill(625,325,145,36,"본프로젝트",C["navy"],C["cyan"],size=13))
    p.append(text(790,350,"박스 편집 · 선택 재OCR · 검색 본문 동기화",16,800,C["text"]))
    p.append(pill(1510,325,275,38,"시작  →  저장 완료",C["soft_blue"],C["navy"],size=15))
    stages=[
        ("01","박스 수정·재OCR",C["blue"]),("02","범위 검증",C["cyan"]),("03","본문 구간 교체",C["lime"]),
        ("04","뒤 문장 위치 조정",C["blue2"]),("05","문서 버전 올리기",C["cyan"]),("06","검수 재확정",C["lime"]),
    ]
    xs=[105,395,685,975,1265,1555]
    for i,(no,head,accent) in enumerate(stages):
        p.append(panel(xs[i],405,255,130,fill=C["panel"],stroke=accent,rx=24,shadow=True,sw=3))
        p.append(pill(xs[i]+20,425,58,32,no,C["soft_blue"],accent,size=14))
        p.append(text(xs[i]+127,500,head,16 if i in {0,3,4} else 19,800,C["text"],anchor="middle"))
        if i<5:p.append(arrow(xs[i]+262,470,xs[i+1]-8,470,"#9EB0CE",3))
    p.append(text(120,590,"수정한 글자 수만큼 뒤 문장들의 시작·끝 위치도 함께 옮깁니다.",18,700,C["body"]))
    p.append(panel(80,680,835,225,fill=C["navy"],stroke="#31477A",rx=28,shadow=True))
    p.append(text(125,735,"문제가 생기면 전체 취소",23,800,C["cyan"]))
    guards=[("이미 바뀐 문서","저장하지 않음"),("여러 곳 수정","뒤에서부터 교체"),("문서 버전","한 번만 증가")]
    for i,(k,v) in enumerate(guards):
        x=125+i*250
        p.append(panel(x,770,225,100,fill="#1D315F",stroke="#3A5289",rx=16,shadow=False))
        p.append(text(x+112,808,k,17,800,"#FFFFFF",anchor="middle"))
        p.append(text(x+112,846,v,15,600,"#C8D4EC",anchor="middle"))
    p.append(panel(1005,680,835,225,fill=C["panel"],stroke=C["lime"],rx=28,shadow=True))
    p.append(text(1050,735,"수정 뒤 검색 자료 다시 준비",23,800,"#87A800"))
    downstream=[("본문 반영","제외·복원 요소"),("검수 확정","완료 상태 저장"),("검색 준비","문서 나누기·의미 검색")]
    for i,(k,v) in enumerate(downstream):
        x=1050+i*250
        p.append(panel(x,770,225,100,fill="#F7F9FD",stroke=C["border"],rx=16,shadow=False))
        p.append(text(x+112,808,k,17,800,C["text"],anchor="middle"))
        p.append(text(x+112,846,v,15,600,C["body"],anchor="middle"))
    p.append(text(960,960,"화면에서 고친 내용과 검색에 쓰는 원문을 항상 같게 유지합니다",21,800,C["blue"],anchor="middle"))
    return finish(p)


def manual_slide20_embedding_selection():
    """최종 순서 확정 전, 사용자가 20번에 수동 삽입할 임베딩 모델 선택 결과 장을 만든다."""
    p = svg_base(20, "임베딩 모델 선택", "김보현", "김보현 · 박세현")
    slide_title(
        p,
        "9개 모델 동일 조건 비교",
        "BGE-m3-ko를 기본 임베딩 모델로 선택했습니다",
        "글자가 겹치지 않는 질문에서 상위 5개 안에 정답이 들어오는지 비교했습니다.",
        size=43,
    )

    # 왼쪽: 최종 5차의 9개 후보를 모두 보여 줘 일부 모델만 골라 비교했다는 오해를 막는다.
    p.append(panel(80, 310, 1160, 625, fill=C["panel"], stroke=C["border"], rx=28, shadow=True))
    conditions = [
        (120, 210, "후보 모델 9개"),
        (345, 300, "문서 10건 · 청크 649개"),
        (660, 300, "질문 133개 · 안겹침 64개"),
    ]
    for x, width, value in conditions:
        p.append(pill(x, 338, width, 38, value, C["soft_blue"], C["navy"], size=15))
    p.append(text(120, 415, "안겹침 질문 64개 · 상위 5개 정답 포함 결과", 18, 800, C["blue"], spacing=.5))

    models = [
        ("BGE-m3-ko", 41, 1024),
        ("KURE-v1", 37, 1024),
        ("arctic-l-v2.0", 37, 1024),
        ("bge-m3", 35, 1024),
        ("Qwen3-0.6B", 27, 1024),
        ("nomic-v2-moe", 27, 768),
        ("e5-base", 22, 768),
        ("e5-small-ko-v2", 19, 384),
        ("e5-large", 18, 1024),
    ]
    bar_x, bar_w = 425, 570
    for i, (model, hits, dimension) in enumerate(models):
        y = 448 + i * 49
        selected = i == 0
        if selected:
            p.append(rect(105, y - 25, 1110, 43, C["soft_blue"], rx=12, stroke="#B8C9F5", sw=1))
            p.append(pill(118, y - 19, 58, 30, "선택", C["blue"], "#FFFFFF", size=12))
        p.append(text(190 if selected else 120, y + 4, model, 17, 800 if selected else 700, C["text"]))
        p.append(text(395, y + 4, f"{dimension}D", 13, 700, C["muted"], anchor="end"))
        p.append(rect(bar_x, y - 14, bar_w, 24, "#E4EAF4", rx=12))
        p.append(rect(bar_x, y - 14, bar_w * hits / 41, 24, C["blue"] if selected else "#AAB8CF", rx=12))
        p.append(text(1195, y + 5, f"{hits}/64  {hits / 64 * 100:.1f}%", 16, 800, C["blue"] if selected else C["body"], anchor="end"))

    # 오른쪽: 후보 구성 이유와 선택 근거를 분리해, 유명 모델을 임의로 모은 비교가 아님을 보여 준다.
    p.append(panel(1280, 310, 560, 625, fill=C["navy"], stroke="#31477A", rx=28, shadow=True))
    p.append(pill(1325, 345, 142, 38, "최종 선택", "#243866", C["lime"], size=15))
    p.append(text(1325, 430, "BGE-m3-ko", 34, 800, "#FFFFFF"))
    p.append(text(1325, 505, "64.1%", 64, 800, C["cyan"]))
    p.append(text(1328, 542, "41/64 · 안겹침 질문 Success@5", 17, 700, "#C7D3EC"))
    p.append(text(1328, 575, "1024D · Apache-2.0", 15, 700, C["lime"]))

    p.append(panel(1325, 605, 470, 130, fill="#1D315F", stroke="#3A5289", rx=16, shadow=False))
    p.append(text(1350, 636, "후보를 고른 기준", 14, 800, C["cyan"], spacing=.5))
    p.append(multiline(
        1350,
        672,
        ("한국어 튜닝 ↔ 최신 다국어", "384·768·1024D ↔ 인코더·디코더", "로컬 실행 · 허용적 라이선스 확인"),
        15,
        700,
        "#FFFFFF",
        line_height=1.45,
    ))

    p.append(panel(1325, 755, 470, 62, fill="#1D315F", stroke="#3A5289", rx=16, shadow=False))
    p.append(text(1350, 780, "전체 질문에서도 1위", 12, 800, C["cyan"], spacing=.5))
    p.append(text(1570, 801, "102/133 · 76.7% · p=0.039", 16, 800, "#FFFFFF", anchor="middle"))
    p.append(panel(1325, 837, 470, 62, fill="#1D315F", stroke="#3A5289", rx=16, shadow=False))
    p.append(text(1350, 862, "과장하지 않은 결론", 12, 800, C["cyan"], spacing=.5))
    p.append(text(1570, 883, "KURE와 안겹침 질문 4문항 차이 · p=0.22", 15, 800, "#FFFFFF", anchor="middle"))

    p.append(text(960, 975, "Success@5  ·  상위 5개 안에 정답이 하나라도 있으면 성공  |  공개 Recall@5와 다른 내부 지표", 16, 700, C["muted"], anchor="middle"))
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
    items=[("활성 job 1개","PENDING/RUNNING 중복 방지"),("원문 snapshot","text_version + SHA-256 재검증"),("순차 analyzer","GPU 요청 폭주 방지"),("PARTIAL 저장","일부 성공 결과는 보존"),("timeout","정해진 시간을 넘으면 중단")]
    for i,(h,b) in enumerate(items):
        y=425+i*82
        p.append(circle(1025,y,8,C["lime"] if i==3 else C["cyan"]));p.append(text(1055,y+7,h,20,800,"#FFFFFF"));p.append(text(1280,y+7,b,16,500,"#BFCBE5"))
    p.append(pill(1005,840,700,42,"PENDING  →  RUNNING  →  COMPLETED / PARTIAL / FAILED","#243866","#FFFFFF",size=17))
    return finish(p)


def slide21():
    p = svg_base(21, "실제 모델 평가", "박세현", "박세현")
    slide_title(p, "MEASURED RESULTS", "무엇을 평가했고, 결과가 어느 정도였는지 함께 봅니다", "제품 문서에 남은 실제 측정값만 사용했으며 두 업무는 서로 다른 학습 모델로 배포합니다.", size=43)
    results = [
        (80, "문서 종류 분류", "93.2%", 0.932, "정답 문서 유형을 맞힌 비율", ("평가 대상", "실제 문서 103건"), ("평가 방법", "5등분 교차검증"), ("결과 오차", "±2.5%p"), "Tasqra-classification", C["blue"]),
        (980, "문서 요약", "65.4%", 0.654, "평가 도구가 계산한 요약 품질", ("평가 대상", "실제 문서 26건"), ("평가 방법", "저장된 평가 도구"), ("결과 오차", "약 ±8%p"), "Tasqra-summation", C["cyan"]),
    ]
    for x, heading, value, ratio, label, sample, method, error, model, accent in results:
        p.append(panel(x, 315, 860, 585, fill=C["panel"], stroke=accent, rx=30, shadow=True))
        p.append(text(x + 40, 375, heading, 31, 800, C["text"]))
        p.append(text(x + 40, 500, value, 88, 800, accent))
        p.append(text(x + 43, 548, label, 21, 700, C["body"]))
        p.append(rect(x + 40, 585, 780, 24, "#E2E8F4", rx=12))
        p.append(rect(x + 40, 585, 780 * ratio, 24, accent, rx=12))
        details = [sample, method, error]
        for i, (k, v) in enumerate(details):
            bx = x + 40 + i * 260
            p.append(panel(bx, 655, 240, 118, fill="#F7F9FD", stroke=C["border"], rx=18, shadow=False))
            p.append(text(bx + 20, 693, k, 14, 800, C["muted"], spacing=.8))
            p.append(text(bx + 20, 738, v, 19, 800, C["text"]))
        p.append(text(x + 40, 835, "제품 적용 모델", 14, 800, accent, spacing=1.0))
        p.append(text(x + 230, 835, model, 20, 800, C["text"]))
    p.append(panel(80, 925, 1760, 60, fill=C["navy"], stroke=C["navy"], rx=18, shadow=False))
    p.append(text(960, 964, "요약 평가는 26건이라 오차가 큽니다. 다음 단계는 평가 문서를 늘려 다시 확인하는 것입니다.", 21, 800, "#FFFFFF", anchor="middle"))
    return finish(p)


def slide22():
    p = svg_base(22, "SEHYEON SLIDE", "박세현", "박세현")
    slide_title(p, "CONTENT HANDOFF", "박세현 작성 예정", "세현님이 정리한 최종 파인튜닝 자료로 교체할 슬라이드입니다.", size=48)
    p.append(panel(90,300,1740,600,fill=C["panel"],stroke=C["blue"],rx=30,shadow=True))
    p.append(panel(130,340,610,520,fill=C["navy"],stroke="#31477A",rx=28,shadow=False))
    p.append(text(175,400,"SLIDE 22",17,800,C["cyan"],spacing=1.7))
    p.append(text(175,495,"박세현",64,800,"#FFFFFF"))
    p.append(text(175,560,"작성 영역",42,800,C["cyan"]))
    p.append(text(175,625,"최종 자료 수신 후 이 페이지를",20,500,"#BFCBE5"))
    p.append(text(175,660,"동일 디자인 규칙으로 교체합니다.",20,500,"#BFCBE5"))
    p.append(pill(175,750,260,44,"CONTENT PENDING","#243866",C["lime"],size=16))
    p.append(text(790,380,"권장 구성",17,800,C["blue"],spacing=1.4))
    items=[("01","학습 목적","왜 파인튜닝했는지"),("02","데이터 조건","학습·평가 표본과 방식"),("03","평가 결과","비교 가능한 핵심 수치"),("04","배포 형태","실제 적용 모델과 제약")]
    for i,(no,head,desc) in enumerate(items):
        x=790+(i%2)*480;y=430+(i//2)*190
        p.append(panel(x,y,430,150,fill="#F8FAFD",stroke=C["border"],rx=22,shadow=False))
        p.append(number_badge(x+25,y+25,no,C["blue"] if i%2==0 else C["cyan"]))
        p.append(text(x+25,y+88,head,23,800,C["text"]))
        p.append(text(x+25,y+123,desc,16,500,C["body"]))
    p.append(text(960,955,"슬라이드 번호와 발표 흐름은 유지하고, 내용만 세현님 최종본으로 교체",17,700,C["muted"],anchor="middle"))
    return finish(p)


def slide23():
    p = svg_base(23, "STRUCTURED EXTRACTION", "박세현", "김보현 · 최재정 · 박세현")
    slide_title(p, "THREE SAFETY STRATEGIES", "결정·일정·계약 이행 후보는 서로 다른 방법으로 찾습니다", "정보 종류에 맞는 후보 생성과 검증을 거친 뒤, 각각의 검토 목록에 대기 상태로 저장합니다.", size=41)
    cards=[
        ("01","결정사항",("입력","문서 구간"),("처리","인공지능 추출 + 원문 비교"),("결과","확정 / 검토 대기 / 취소"),C["blue"],"document"),
        ("02","일정",("입력","프로그램이 찾은 날짜 후보"),("처리","인공지능은 날짜 역할만 구분"),("결과","기간 / 마감 / 회의 / 주요 일정"),C["cyan"],"structure"),
        ("03","계약 이행 태스크 후보",("입력","규칙으로 찾은 행동·의무 문장"),("처리","인공지능은 후보 ID 중 선택"),("결과","계약·변경계약 문서만 대상"),C["lime"],"tasks"),
    ]
    xs=[80,660,1240]
    for i,(no,head,input_row,process_row,output_row,accent,kind) in enumerate(cards):
        dark=i==2
        fill=C["navy"] if dark else C["panel"]
        p.append(panel(xs[i],305,520,545,fill=fill,stroke=accent,rx=30,shadow=True))
        p.append(number_badge(xs[i]+30,335,no,accent,dark=dark))
        p.append(circle(xs[i]+440,375,38,"#24345F" if dark else C["soft"],stroke=accent,sw=2))
        p.append(icon(kind,xs[i]+440,375,34,accent,3))
        p.append(text(xs[i]+30,430,head,26 if i==2 else 31,800,"#FFFFFF" if dark else C["text"]))
        for j,(label,value) in enumerate((input_row,process_row,output_row)):
            y=490+j*112
            p.append(text(xs[i]+30,y,label,14,800,accent,spacing=1.2))
            p.append(text(xs[i]+30,y+39,value,17,700,"#FFFFFF" if dark else C["body"]))
            if j<2:p.append(line(xs[i]+30,y+69,xs[i]+490,y+69,"#354B7E" if dark else C["border"],2))
        p.append(pill(xs[i]+30,795,210,38,"각 검토 목록에 저장","#243866" if dark else C["soft_blue"],C["lime"] if dark else accent,size=13))
        if i<2:p.append(arrow(xs[i]+530,575,xs[i+1]-10,575,"#A8B8D7",3))
    p.append(panel(80,890,1680,75,fill=C["navy"],stroke="#31477A",rx=20,shadow=False))
    p.append(text(120,936,"유형별 검토 저장소",16,800,C["cyan"],spacing=1.2))
    p.append(text(405,936,"결정·일정 목록",19,700,"#FFFFFF"));p.append(text(770,936,"금액 목록",19,700,"#FFFFFF"));p.append(text(1090,936,"계약 이행 태스크 후보 목록",19,700,"#FFFFFF"))
    return finish(p)


def slide24():
    p = svg_base(24, "LONG DOCUMENT FIX", "박세현", "박세현")
    slide_title(p, "INVISIBLE CHARACTER", "눈에 보이지 않는 특수문자 516개 때문에 인용문 확인이 실패했습니다", "원인을 찾고, 원문 위치를 보존해 정리한 뒤, 인용문 확인 방식을 보완했습니다.", size=41)
    # 왼쪽의 세로 단계만 따라가면 원인 → 수정 → 결과가 읽힌다.
    flow=[
        ("01","문제 발견","특수문자 516개",("사람 눈에는 같은 문장", "프로그램은 다른 문장으로 판단"),C["blue"]),
        ("02","원문 정리","같은 길이의 공백으로 변경",("글자 수와 원문 위치 유지", "탭과 줄바꿈은 그대로 보존"),C["cyan"]),
        ("03","확인 방식 보완","공백·특수문자 차이 허용",("틀린 인용만 제거", "원문 시작·끝 위치 복원"),C["lime"]),
    ]
    for i,(no,head,key,body,accent) in enumerate(flow):
        y=315+i*205
        p.append(panel(100,y,650,170,fill=C["navy"] if i==2 else C["panel"],stroke=accent,rx=26,shadow=True))
        p.append(number_badge(130,y+28,no,accent,dark=(i==2)))
        p.append(text(225,y+58,head,27,800,"#FFFFFF" if i==2 else C["text"]))
        p.append(text(130,y+110,key,21,800,accent if i<2 else C["lime"]))
        p.append(multiline(430,y+100,body,16,600,"#C8D4EC" if i==2 else C["body"],line_height=1.45))
        if i<2:p.append(arrow(425,y+177,425,y+198,"#9EB0CE",3))
    # 오른쪽은 전후 문장을 위아래로 배치해 한 번에 한 쌍만 비교한다.
    p.append(panel(830,315,990,590,fill="#F8FAFD",stroke=C["border"],rx=28,shadow=True))
    p.append(text(875,365,"실제 문장 변화",18,800,C["blue"],spacing=1.2))
    p.append(panel(875,405,900,150,fill="#FFF3F3",stroke="#E9A2A2",rx=20,shadow=False))
    p.append(text(910,445,"수정 전 · 원문",16,800,"#B34C4C"))
    p.append(panel(910,465,830,54,fill="#2A1D2A",stroke="#5A364F",rx=12,shadow=False))
    p.append(text(935,501,"…계약에 관한 법률」  \\x01  제5조의2…",22,700,"#FFFFFF"))
    p.append(arrow(1325,570,1325,620,C["blue"],4))
    p.append(text(1370,603,"같은 길이의 공백으로 변경",17,800,C["blue"]))
    p.append(panel(875,635,900,150,fill="#F0FAF4",stroke="#86C99B",rx=20,shadow=False))
    p.append(text(910,675,"수정 후 · 정리한 원문",16,800,"#298451"))
    p.append(panel(910,695,830,54,fill="#163129",stroke="#2D6B54",rx=12,shadow=False))
    p.append(text(935,731,"…계약에 관한 법률」      제5조의2…",22,700,"#FFFFFF"))
    p.append(panel(875,815,900,58,fill=C["soft_blue"],stroke=C["border"],rx=16,shadow=False))
    p.append(text(1325,853,"결과  ·  인용문 확인 성공 + 원문 위치 유지",20,800,C["navy"],anchor="middle"))
    p.append(text(960,960,"수정 기록  PR #89 · d47502e  |  글자 수를 유지해 기존 원문 좌표를 다시 계산하지 않습니다",17,700,C["muted"],anchor="middle"))
    return finish(p)


def slide25():
    p = svg_base(25, "검증 상태", "박세현", "팀")
    slide_title(p, "확인한 사실만 표시", "확인된 근거와 아직 확인하지 못한 결과를 나눴습니다", "파일 수나 계획된 절차를 테스트 통과 결과처럼 말하지 않습니다.", size=43)
    # 상단에는 현재 저장소에서 직접 다시 확인한 값만 쓴다.
    metrics=[("97","기능 목록 검사","엑셀·관리 문서 일치",C["blue"]),("48","서버 테스트 파일","파일 존재만 확인",C["cyan"]),("0","자동 테스트 기록","GitHub 실행 이력",C["lime"])]
    for i,(value,head,desc,accent) in enumerate(metrics):
        x=90+i*430
        p.append(panel(x,300,390,120,fill=C["panel"],stroke=accent,rx=22,shadow=True))
        p.append(text(x+25,370,value,48,800,accent if i<2 else "#87A800"))
        p.append(text(x+130,350,head,18,800,C["text"]));p.append(text(x+130,382,desc,15,500,C["body"]))
    p.append(panel(1380,300,450,120,fill=C["navy"],stroke="#31477A",rx=22,shadow=True))
    p.append(text(1415,344,"삭제한 주장",13,800,C["cyan"],spacing=1.2))
    p.append(text(1415,384,"근거 로그 없음 · 발표에서 제외",21,800,"#FFFFFF"))
    # 근거 매트릭스
    p.append(panel(90,465,820,420,fill="#F0FAF4",stroke="#82C999",rx=28,shadow=True))
    p.append(text(130,520,"지금 확인됨",26,800,"#288351"));p.append(text(865,520,"확인 방법",13,800,"#5D8A6A",anchor="end",spacing=1.0))
    confirmed=[("기능 목록 97건 일치","동기화 검사 실행"),("서버 테스트 파일 48개","저장소 파일 수 확인"),("글자 인식·본문 재조립","오류 방지 테스트 코드 존재"),("자동 테스트 실행 0건","GitHub 실행 이력 확인")]
    for i,(v,src) in enumerate(confirmed):
        y=565+i*72
        p.append(panel(125,y,750,54,fill="#FAFEFB",stroke="#CDE8D5",rx=12,shadow=False))
        p.append(circle(150,y+27,7,"#41A66A"));p.append(text(175,y+34,v,18,700,C["text"]));p.append(text(845,y+34,src,14,600,C["muted"],anchor="end"))
    p.append(panel(1010,465,820,420,fill="#FFF6ED",stroke="#E6B476",rx=28,shadow=True))
    p.append(text(1050,520,"아직 확인하지 못함",26,800,"#B66B1E"));p.append(text(1785,520,"이유",13,800,"#A97945",anchor="end",spacing=1.0))
    pending=[("최신 코드 전체 테스트","저장된 실행 결과 없음"),("자동 테스트 통과","실행 기록 자체가 없음"),("계획된 149개 절차","실행 전 계획 문서임"),("수정 후 실제 문서 처리","저장된 결과 없음")]
    for i,(v,reason) in enumerate(pending):
        y=565+i*72
        p.append(panel(1045,y,750,54,fill="#FFFBF7",stroke="#EFD6B9",rx=12,shadow=False))
        p.append(circle(1070,y+27,7,"#D08A3C"));p.append(text(1095,y+34,v,18,700,C["text"]));p.append(text(1765,y+34,reason,14,600,C["muted"],anchor="end"))
    p.append(panel(90,925,1740,58,fill=C["navy"],stroke=C["navy"],rx=17,shadow=False))
    p.append(text(960,963,"발표 원칙  ·  실행 결과가 없으면 ‘테스트 코드가 있다’까지만 말합니다",20,800,"#FFFFFF",anchor="middle"))
    return finish(p)



def slide26():
    p = svg_base(25, "DEMO", "박세현", "팀", dark=True)
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
    p = svg_base(26, "LIMITS · NEXT", "박세현", "팀")
    slide_title(p, "WHAT WE LEARNED", "현재 한계를 다음 우선순위로 바꿨습니다", "기능 개수보다 검색 확장성·모델 품질·검토 무결성·운영 증명을 먼저 개선합니다.", size=45)
    items=[
        ("01","검색 확장성","전체 1,339청크 R@1 36.9%","후보 생성·인덱스·리랭킹 재설계",C["blue"]),
        ("02","요약 품질","26건 기준 65.4% · 오차 큼","평가셋 확대와 재학습",C["cyan"]),
        ("03","계약 이행 후보 검토","현재 화면은 승인·거절만 지원","수정 승인·승인 취소·원문 변경 방어 보강",C["lime"]),
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
    p = svg_base(27, "CONCLUSION", "박세현", "팀", dark=True)
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
    p = svg_base(28, "Q&A", "팀", "팀", dark=True)
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


def apply_content_review(slide_no: int, content: str) -> str:
    """비주얼 배치는 유지하고, 발표 문구와 수치 근거만 검수한 최종 표현으로 바꾼다."""
    common = {
        "PRESENTER  ": "발표  ",
        "OWNER  ": "담당  ",
    }
    reviewed = {
        1: {
            "FINAL PROJECT": "최종 발표",
            "FINAL PROJECT PRESENTATION": "최종 프로젝트 발표",
            "AI 기반 프로젝트 문서 분석·검색·업무 연결 플랫폼": "인공지능이 문서를 분석하고 근거를 찾아 업무로 연결하는 서비스",
            "DOCUMENT  →  EVIDENCE  →  ACTION": "문서  →  근거 확인  →  업무 실행",
            "DOCUMENT  ·  EVIDENCE  ·  ACTION": "문서  ·  근거 확인  ·  업무 실행",
        },
        2: {
            "PROBLEM": "문제",
            "WHY TASQRA": "왜 TASQRA인가",
            "INFORMATION GAP": "정보와 실행의 단절",
        },
        3: {
            "SERVICE GOAL": "서비스 목표",
            "HUMAN IN THE LOOP": "인공지능 제안 · 사람 확인",
            "AI가 제안하고,": "인공지능이 제안하고,",
            "구조화한다": "항목별로 정리한다",
        },
        4: {
            "TEAM": "팀 구성",
            "ONE PRODUCT · THREE EXPERTISE": "하나의 제품 · 세 가지 전문 영역",
            "SEARCH &amp; PRODUCT INTELLIGENCE": "검색과 정보 활용",
            "OCR &amp; LLM INTELLIGENCE": "글자 인식과 인공지능 분석",
            "CORE PLATFORM &amp; WORKFLOW": "기본 플랫폼과 업무 흐름",
            "검색·RAG 품질 개선": "문서 근거 검색 품질 개선",
            "근거 기반 QA와 금액 검토": "근거를 보여주는 질의응답과 금액 검토",
            "OCR·텍스트 복원": "스캔 문서 글자 인식과 본문 복원",
            "로컬 LLM 비교·태스크별 LoRA 학습": "내부 언어 모델 비교·업무별 추가 학습",
            "구조화 추출·긴 문서 안정화": "정보 항목 추출·긴 문서 오류 개선",
            "워크스페이스·태스크 업무 흐름": "프로젝트 공간·태스크 업무 흐름",
        },
        5: {
            "USER FLOW": "사용 흐름",
            "END-TO-END WORKFLOW": "문서부터 업무 반영까지",
            "OCR·텍스트 정제": "문서 글자 읽기·본문 정리",
            "AI 분석·검색 색인": "인공지능 분석·검색 준비",
            "검색 색인을 만듭니다.": "검색할 수 있게 준비합니다.",
            "ACTION ITEM  ·  단건 검토 흐름": "계약 이행 태스크 후보  ·  한 건씩 검토",
            "액션아이템 추출": "행동·의무 후보 찾기",
            "액션 태스크 후보": "검토 대기로 저장",
            "FINAL OUTPUTS": "최종 산출물",
        },
        6: {
            "ARCHITECTURE": "서비스 구조",
            "SYSTEM MAP": "서비스 구성",
            "전체 시스템 아키텍처": "서비스가 움직이는 전체 구조",
            "동기 API와 비동기 Worker가 PostgreSQL·공유 파일을 중심으로 연결됩니다.": "화면 요청은 서버가 바로 처리하고, 오래 걸리는 작업은 별도 프로그램이 처리합니다.",
            "DOCKER COMPOSE · SHARED RUNTIME": "함께 실행되는 개발 환경",
            "CLIENT": "사용자 화면",
            "React / Vite": "웹 화면 (React)",
            "Browser UI": "브라우저 화면",
            "HTTP CLIENT": "서버 요청",
            "Axios REST": "HTTP 통신",
            "APPLICATION API": "요청을 받는 서버",
            "ROUTER": "요청 연결",
            "FastAPI endpoints": "FastAPI 요청 처리",
            "권한·요청 검증": "권한과 입력 확인",
            "SERVICE": "업무 처리",
            "상태 전이·오케스트레이션": "업무 순서와 상태 변경",
            "REPOSITORY": "데이터 저장",
            "SQLAlchemy": "데이터베이스 연결",
            "트랜잭션·영속화": "안전하게 묶어서 저장",
            "SYNC REQUEST PATH": "바로 처리하는 요청",
            "ASYNC EXECUTION": "오래 걸리는 작업",
            "Redis Queue": "작업 대기열 (Redis)",
            "broker · result": "작업 전달 · 결과 보관",
            "Celery Worker": "작업 프로그램 (Celery)",
            "late ack · retry": "실패하면 다시 실행",
            "SHARED INFRASTRUCTURE": "함께 쓰는 저장 공간",
            "PostgreSQL": "데이터베이스",
            "업무 데이터": "프로젝트 정보",
            "pgvector 1024D": "의미 검색 정보",
            "uploads": "문서 파일",
            "공유 로컬 파일": "함께 쓰는 파일",
            "Local AI": "내부 인공지능",
            "OpenAI 호환": "같은 요청 형식",
            ">REST<": ">요청<",
            ">enqueue<": ">작업 등록<",
            ">read / write<": ">읽기 / 저장<",
            "현재 개발 구성  ·  API와 Worker가 PostgreSQL · uploads · 모델 캐시를 공유  ·  S3/Kubernetes/오토스케일링 미포함": "현재 개발 환경의 구성입니다. 클라우드 저장소와 자동 확장은 아직 포함하지 않았습니다.",
        },
        7: {
            "DATA MODEL": "데이터 구조",
            "RELATIONAL CORE": "데이터 연결 관계",
            "핵심 데이터 구조": "데이터가 서로 연결되는 방식",
            "Project와 Document를 중심으로 검색·분석·업무 데이터가 외래키로 연결됩니다.": "한 프로젝트에 여러 문서와 태스크가 연결되고, 각 문서에는 본문 조각과 분석 결과가 연결됩니다.",
            "1:N members": "여러 구성원",
            "1:N documents": "여러 문서",
            "1:N chunks / analyses": "여러 조각 · 분석",
            "1:N tasks / reviews": "여러 태스크 · 검토",
            "USER · MEMBER": "사용자 · 구성원",
            "PROJECT": "프로젝트",
            "DOCUMENT": "문서",
            "CHUNK · ANALYSIS": "문서 조각 · 분석 결과",
            "TASK · REVIEW": "태스크 · 검토",
            "OWNER · EDITOR · VIEWER": "관리자 · 편집자 · 조회자",
            "권한 · 문서 · 태스크의 루트": "권한 · 문서 · 태스크의 기준",
            "원문 경로와 메타데이터": "원문 파일과 문서 정보",
            "추출본문 · OCR · 분석 이력": "추출 본문 · 글자 검수 · 분석 기록",
            "본문 구간과 1024D 벡터": "본문 구간과 의미 검색 정보",
            "모델 · 버전 · 원문 좌표": "분석 모델 · 문서 버전 · 원문 위치",
            "결정 · 일정 · 액션 · 금액": "결정 · 일정 · 계약 이행 후보 · 금액",
            ">PK<": ">기준<",
            ">FK<": ">연결<",
            "FILE STORAGE": "파일 저장",
            "DB BLOB이 아니라 공유 로컬 경로": "파일은 공용 폴더에 저장",
            "DOCUMENT TEXT": "추출한 본문",
            "Document 1:1 ExtractedText": "문서마다 추출 본문 1개 저장",
        },
        8: {
            "STATE DESIGN": "상태 관리",
            "SEPARATE LIFECYCLES": "작업별 상태 분리",
            "상태를 분리한 운영 설계": "작업별 진행 상태를 따로 관리합니다",
            "문서 추출·OCR 검수·LLM 분석을 하나의 상태로 섞지 않았습니다.": "문서 읽기·글자 검수·인공지능 분석의 진행 상태를 따로 저장합니다.",
            "DOCUMENT EXTRACTION": "문서 읽기",
            "OCR REVIEW": "글자 인식 검수",
            "OCR 검수": "글자 인식 검수",
            "ANALYSIS JOB": "인공지능 분석",
            "LLM 분석": "인공지능 분석",
            "PENDING": "대기",
            "EXTRACTING": "읽는 중",
            "EXTRACTED": "읽기 완료",
            "FAILED → 대기 재시도": "실패하면 다시 대기",
            "IN_PROGRESS": "검수 중",
            "COMPLETED": "완료",
            "대상 없음 → NOT_REQUIRED": "검수할 내용이 없으면 완료",
            "RUNNING": "분석 중",
            "완료 / PARTIAL / FAILED": "완료 / 일부 완료 / 실패",
            "text_version + 원문 revision 검증": "분석 전후에 원문이 같은지 확인",
            "STATE OWNER": "상태 저장 위치",
            "Document": "문서",
            "OCR Review": "글자 검수",
            "AnalysisJob": "분석 작업",
            "한 작업의 실패가 다른 수명주기의 성공 상태를 되돌리지 않습니다.": "한 작업이 실패해도 이미 끝난 다른 작업의 상태는 유지됩니다.",
            "NO SHARED STATUS FLAG": "상태를 하나로 묶지 않음",
        },
        9: {
            "RAG": "근거 검색",
            "근거 검색 색인과 검색": "문서를 나누고, 뜻이 비슷한 근거를 찾습니다",
            "INDEX → RETRIEVE": "검색 준비 → 근거 찾기",
            "RAG 색인과 검색": "문서를 검색할 수 있게 준비하고 근거를 찾는 과정",
            "문서 구조와 원문 위치를 보존한 청크에서 근거를 찾습니다.": "문서를 읽기 좋은 단위로 나누고, 문서명·페이지·원문 위치와 함께 결과를 보여줍니다.",
            "확정 본문": "검토가 끝난 본문",
            "OCR 검수 결과": "글자 검수 결과",
            "text_version": "본문 버전",
            "구조 청킹": "문단별로 나누기",
            "최대 480토큰": "최대 480개 단위",
            "앞 문맥 48토큰": "앞 내용 48개 겹침",
            "임베딩": "뜻을 숫자로 바꾸기",
            "1024차원": "의미 검색용 숫자",
            "pgvector": "비슷한 뜻 찾기",
            "HNSW 코사인": "뜻이 가까운 순서",
            "ef_search 100": "검색 범위 설정 100",
            "페이지·문서명": "문서명 · 페이지",
            "원문 좌표": "원문 위치",
            "질의를 별도 임베딩 → 권한 있는 프로젝트 범위 → 같은 embedding_model의 가까운 청크 조회": "질문을 같은 방식으로 바꾼 뒤, 권한이 있는 프로젝트 안에서 뜻이 가까운 문서 조각을 찾습니다.",
            "HNSW는 근사검색이며, 모델 변경 시 기존 청크는 재임베딩이 필요합니다.": "검색 모델을 바꾸면 기존 문서도 새 모델에 맞게 다시 준비해야 합니다.",
            "실모델 설정 조건": "현재 코드 설정",
        },
        10: {
            "HYBRID SEARCH": "두 검색 함께 사용",
            "ONE SEARCH BOX": "검색창 하나",
            "하이브리드 검색": "글자가 같은 결과와 뜻이 비슷한 결과를 함께 찾습니다",
            "서로 다른 점수를 더하지 않고, 두 검색의 순위를 RRF로 결합합니다.": "각 검색에서 앞에 나온 결과에 점수를 주어 최종 순서를 정합니다.",
            "ILIKE로 연속 문자열 포함 보장": "입력한 글자가 이어진 문장 찾기",
            "word_similarity로 내부 순위": "글자가 더 비슷한 순서로 정렬",
            "숫자·코드·정확 표현에 강점": "숫자·코드·정확한 표현을 잘 찾음",
            "질의·청크 임베딩": "질문과 문장의 뜻 비교",
            "pgvector 코사인 거리": "뜻이 가까운 순서로 정렬",
            "표현이 달라도 문맥 탐색": "표현이 달라도 뜻이 비슷하면 찾음",
            "RRF": "순위 합산",
            "Σ 1 / (60 + 순위)": "앞에 나온 결과에 더 높은 점수",
            "후보 폭": "비교 범위",
            "두 검색에서 각각 기본 30개": "두 검색에서 상위 30개씩 비교",
            "단일 UX": "사용 방법",
            "사용자는 검색 방식을 고르지 않음": "사용자는 검색창 하나만 사용",
            "전문 검색엔진·점수 정규화·가중합 아님": "별도 검색엔진이나 점수 비율 조정은 아직 없음",
        },
        11: {
            "SEARCH SCALE": "검색 규모 실험",
            "MEASURED LIMIT": "실제 실험 결과",
            "검색 범위가 커질수록 첫 정답 순위가 무너졌습니다": "검색 대상이 많아지자 첫 번째 결과의 정답률이 떨어졌습니다",
            "동일 모델·동일 평가셋에서 후보 청크 수만 바꾼 결과입니다.": "같은 모델과 질문 214개를 사용하고, 비교할 문서 조각 수만 바꾼 결과입니다.",
            "후보 청크 수": "비교한 문서 조각 수",
            "R@1": "첫 결과",
            "R@5": "상위 5개",
            "후보 30 · 첫 결과": "문서 조각 30개 비교",
            "전체 1,339 · 첫 결과": "문서 조각 1,339개 비교",
            "BGE-m3-ko · 질의 214": "모델 BGE-m3-ko · 질문 214개",
            "문서 30 · 정답 1청크/질의": "문서 30개 · 질문마다 정답 1개",
            "R@k = 상위 k 안에 정답 포함": "비율 = 정답이 표시 범위 안에 있는 질문 수",
            "※ 후보 30의 90.2%는 제품 문서 수 제한 정책이 아니라 검색 후보 범위 실험값입니다.": "※ 2026-08-20 최종 학습 기록값입니다. 문서 수 제한 정책이 아니라 검색 범위 실험입니다.",
        },
        12: {
            "RERANKER": "검색 결과 재정렬",
            "CANDIDATE REORDERING": "실제 실험 결과",
            "학습 리랭커는 후보 안에서 첫 정답을 끌어올렸습니다": "재정렬 모델을 학습해 정답을 더 앞에 배치했습니다",
            "동일 조건의 R@1 비교이며, 후보에 없는 정답은 복구할 수 없습니다.": "이미 찾은 후보의 순서만 바꾸므로, 후보에 없는 정답은 새로 찾을 수 없습니다.",
            "임베딩 단독": "처음 검색 결과",
            "BGE 학습 전": "재정렬 학습 전",
            "BGE 학습 후": "재정렬 학습 후",
            ">R@1<": ">첫 결과 정답률<",
            "학습 전 → 후 R@1": "학습 전 → 후 개선",
            "적용 경로": "처리 순서",
            "벡터·키워드 후보": "뜻·글자 검색 후보",
            "→ RRF 융합": "→ 두 검색 순위 합치기",
            "→ 상위 후보 전문 재정렬": "→ 본문을 다시 읽어 최종 순서 정하기",
            "실행 조건": "사용 조건",
            "기본 비활성 · GPU 권장 · 실패 시 원래 순서": "기본은 꺼짐 · 그래픽 장치 권장 · 오류 시 기존 순서 사용",
            "R@5  72.43% → 71.50% → 80.84%   ·   학습 후 MRR@10 0.6235   ·   측정 지연 0.192초": "상위 5개 정답 포함률  72.43% → 71.50% → 80.84%   ·   한 번 처리 0.192초",
        },
        13: {
            "GROUNDED QA": "근거가 있는 질의응답",
            "EVIDENCE CONTRACT": "근거 사용 규칙",
            "답변보다 먼저 근거의 경계를 설계했습니다": "답변을 만들기 전에 근거 사용 규칙부터 정했습니다",
            "검색 결과를 토큰 예산 안에 조립하고, 모델이 반환한 근거 ID를 서버가 검증합니다.": "검색한 원문을 정리해 모델에 주고, 답변이 가리킨 근거 번호를 서버가 다시 확인합니다.",
            "하이브리드 검색": "글자·의미 검색",
            "최대 24개 후보": "최대 24개 문서 조각",
            "전문 재조회": "원문 다시 읽기",
            "짧은 snippet이 아닌": "짧은 미리보기가 아닌",
            "청크 원문 사용": "문서 조각 원문 사용",
            "컨텍스트 조립": "읽을 자료 구성",
            "최대 8개 · 4,000토큰": "최대 8개 · 4,000개 단위",
            "LLM JSON": "답변과 근거 번호",
            "answer · answerable": "답변 · 답변 가능 여부",
            "evidence_ids": "사용한 근거 번호",
            "ID 존재·범위·중복": "근거 번호·권한·중복",
            "원문 메타데이터 매핑": "문서명·페이지 연결",
            "근거가 없으면 LLM을 호출하지 않고 고정 응답을 반환합니다.": "근거가 없으면 인공지능을 호출하지 않고 정해진 안내를 보여줍니다.",
            "의미적 사실 검증 아님": "답변 내용 자체를 검증하는 것은 아님",
            "서버 검증 범위는 근거 ID 계약과 권한입니다.": "서버는 근거 번호가 실제로 있고 사용 권한이 있는지만 확인합니다.",
        },
        14: {
            "HUMAN REVIEW": "사람 검토",
            "APPROVAL BOUNDARY": "업무 반영 전 확인",
            "AI 제안과 실제 업무 사이에 사람 검토를 둡니다": "인공지능 제안은 사람이 확인한 뒤 업무에 반영합니다",
            "자동 반영이 아니라 PENDING 제안을 승인 가능한 상태로 저장합니다.": "자동 반영하지 않고, 모든 제안을 검토 대기 상태로 저장합니다.",
            "SUGGESTION QUEUE": "검토할 제안 목록",
            "PENDING": "검토 대기",
            "DECISION": "결정",
            "SCHEDULE": "일정",
            "AMOUNT": "금액",
            "ACTION": "계약 이행",
            "액션 태스크 후보": "계약 이행 태스크 후보",
            ">review<": ">사람 확인<",
            "APPROVED": "승인",
            "EDITED": "수정 승인",
            "REJECTED": "거절",
            "STATUS TRANSITION + AUDIT": "상태 변경과 변경 이력 저장",
            ">consume<": ">업무 반영<",
            "APPROVED CONSUMERS": "승인 정보를 쓰는 기능",
            "승인 CONSUMERS": "승인 정보를 쓰는 기능",
            "TASK": "태스크",
            "DASHBOARD": "대시보드",
            "DELIVERABLE": "산출물",
            "QA": "질의응답",
            "근거 질의응답": "근거 질의응답",
            "승인 / 수정 승인": "승인 또는 수정 승인",
            "FILTER CONTRACT": "반영 기준",
            "검토 대기 / 거절 제외": "검토 대기와 거절은 제외",
        },
        15: {
            "ACTION TO TASK": "계약 이행 후보 → 태스크",
            "CONTROLLED AUTOMATION": "사람이 승인하는 자동화",
            "액션아이템은 승인 전까지 태스크가 아닙니다": "계약 이행 태스크 후보는 사람이 승인해야 태스크가 됩니다",
            "계약·변경계약 문서의 후보를 단건 검토한 뒤 실제 Task를 생성합니다.": "계약 문서에서 찾은 후보를 한 건씩 확인한 뒤 실제 태스크를 만듭니다.",
            "규칙 후보": "의무 문장 찾기",
            "PENDING 저장": "검토 대기로 저장",
            "모델 선택": "인공지능이 후보 선택",
            "후보 ID 중 선택": "찾아둔 후보 안에서 선택",
            "일반 규정 제외": "단순 안내 문장은 제외",
            "대기 저장": "검토 대기로 저장",
            "task_suggestions": "태스크 후보 목록",
            "단건 승인·거절": "한 건씩 승인·거절",
            "승인 시 실제 Task": "승인하면 태스크 생성",
            "origin=AI_APPROVED": "인공지능 제안에서 생성됨",
            "UI 범위": "현재 화면에서 할 수 있는 것",
            "현재 화면은 승인·거절을 지원합니다. 수정 승인·승인 취소·오래된 원문 방어는 다음 개선 범위입니다.": "현재는 승인과 거절만 할 수 있습니다. 수정 후 승인, 승인 취소, 원문 변경 확인은 다음 개선 항목입니다.",
        },
        16: {
            "AMOUNT SNAPSHOT": "금액 확정본",
            "SAFE RE-ANALYSIS": "재분석 중에도 기존 결과 유지",
            "새 분석의 검토가 끝날 때까지 직전 완료 스냅샷을 계속 사용합니다.": "새 분석을 모두 검토할 때까지 기존 확정 결과를 계속 사용합니다.",
            "ACTIVE SNAPSHOT": "현재 사용 중인 확정본",
            "현재 소비 중": "현재 사용 중",
            "PENDING": "대기",
            "APPROVED / EDITED": "승인 또는 수정 승인",
            "review_status": "검토 상태",
            "승인 / 수정 승인": "승인 또는 수정 승인",
            "consumers": "사용하는 기능",
            "Dashboard · QA · Deliverable": "대시보드 · 질의응답 · 산출물",
            "switch_policy": "전환 기준",
            "source": "선택 기준",
            "latest completed analysis": "가장 최근에 검토가 끝난 결과",
            "ACTIVE POINTER 유지": "기존 확정본 계속 사용",
            "RE-ANALYSIS JOB": "새 분석 검토",
            "IN REVIEW": "검토 중",
            "COMPLETE": "검토 완료",
            "새 Analysis": "새 분석 결과",
            "미결 행 0": "모든 항목 검토 완료",
            "COMPLETENESS GATE": "전환 조건",
            "검토 완료NESS GATE": "전환 조건",
            "추출 행 수 = 검토 완료 행 수": "추출된 모든 항목의 검토가 끝남",
            "CONSISTENT CONSUMERS": "같은 확정본을 보는 기능들",
            "검색 응답": "질의응답",
            "근거 QA": "근거 질의응답",
            "XLSX · PDF": "엑셀 · PDF",
            "same active_snapshot_id": "모두 같은 확정본 사용",
            "원자": "동시",
            "gate 통과 후 pointer 교체": "모든 검토가 끝난 뒤 확정본 교체",
            "재분석 중에도 기존 승인 데이터가 화면·QA·산출물에 계속 제공되며, 완료 순간에만 소비 기준이 한 번 바뀝니다.": "검토가 끝나는 순간 대시보드·질의응답·산출물이 새 확정본으로 함께 바뀝니다.",
        },
        17: {
            "DASHBOARD · OUTPUTS": "대시보드 · 산출물",
            "FROM APPROVED DATA": "승인 정보 활용",
            "사람 검토를 통과한 동일 데이터를 화면과 문서가 함께 소비합니다.": "사람이 승인한 같은 정보를 화면과 문서에 함께 사용합니다.",
            "PROJECT DASHBOARD": "프로젝트 대시보드",
            "PENDING · EXTRACTED": "대기 · 추출 완료",
            "DELIVERABLES": "만들 수 있는 문서",
            "XLSX · HTML · MD · PDF": "엑셀 · 웹 문서 · 마크다운 · PDF",
        },
        18: {
            "OCR EVOLUTION": "문서 글자 읽기",
            "PARK SEHYEON SECTION": "페이지에 맞는 읽기 방법 선택",
            "텍스트층을 버리지 않는 OCR 파이프라인": "PDF에 이미 들어 있는 글자를 살려서 읽습니다",
            "페이지 특성에 따라 TEXT_LAYER·OCR·HYBRID를 선택하고 읽기 순서를 복원합니다.": "글자가 있으면 그대로 쓰고, 스캔 이미지는 글자를 인식하며, 둘 다 있으면 읽는 순서에 맞춰 합칩니다.",
            "TEXT_LAYER": "기존 글자 사용",
            "기존 텍스트 보존": "PDF의 기존 글자 보존",
            "텍스트 블록 추출": "들어 있는 글자 읽기",
            "불필요한 OCR 생략": "이미지 글자 인식 생략",
            ">OCR<": ">스캔 글자 인식<",
            "스캔 페이지 보완": "스캔 페이지의 글자 읽기",
            "큰 이미지 + 부족한 텍스트층": "이미지가 크고 기존 글자가 부족함",
            "전체 페이지 OCR": "페이지 전체 글자 인식",
            "HYBRID": "두 결과 합치기",
            "두 결과를 좌표순 결합": "두 결과 합치기",
            "텍스트와 이미지 OCR": "기존 글자와 이미지 글자",
            "같은 좌표계로 정렬": "페이지 위치에 맞춰 정렬",
            "페이지 본문 + OCR 검수 박스 + content_start/end 원문 오프셋": "페이지 본문 + 사람이 고칠 수 있는 글자 영역 + 원문에서의 시작·끝 위치",
            "TEXT_LAYER / OCR / HYBRID": "기존 글자 / 스캔 글자 / 두 결과 합치기",
            "기존 글자 사용 / OCR / 두 결과 합치기": "기존 글자 / 스캔 글자 / 두 결과 합치기",
        },
        19: {
            "OCR REVIEW": "글자 인식 검수",
            "TEXT INTEGRITY": "화면과 검색 본문을 함께 수정",
            "OCR 박스를 고치면 본문과 오프셋도 함께 바뀝니다": "글자 인식 결과를 고치면 검색용 본문도 함께 고칩니다",
            "화면의 수정과 검색 원문이 어긋나지 않도록 범위·버전·revision을 한 트랜잭션에서 갱신합니다.": "수정 범위, 본문, 뒤 문장의 위치, 문서 버전을 한 번에 바꿔 서로 어긋나지 않게 합니다.",
            "SINGLE TRANSACTION": "한 번에 모두 처리",
            "BEGIN  →  COMMIT": "시작  →  저장 완료",
            "뒤 오프셋 이동": "뒤 문장 위치 조정",
            "revision 증가": "문서 버전 올리기",
            "수정 범위 뒤쪽의 content_start / content_end를 같은 delta만큼 이동": "수정한 글자 수만큼 뒤 문장들의 시작·끝 위치를 함께 옮깁니다.",
            "ROLLBACK GUARD": "문제가 생기면 전체 취소",
            "stale version": "이미 바뀐 문서",
            "전체 롤백": "전체 변경 취소",
            "여러 범위": "여러 곳 수정",
            "DOWNSTREAM REFRESH": "수정 뒤 다시 준비",
            "is_confirmed": "검수 완료 상태",
            "청킹·임베딩 enqueue": "문서 나누기·검색 준비 다시 실행",
            "OCR UI 수정과 검색용 원문을 하나의 무결성 경계로 관리": "화면에서 고친 내용과 검색에 쓰는 원문을 항상 같게 유지합니다",
        },
        20: {
            "ASYNC SAFETY": "오래 걸리는 작업",
            "FAILURE ISOLATION": "실패해도 안전하게 다시 처리",
            "비동기 작업의 실패 경계를 분리했습니다": "오래 걸리는 작업은 실패해도 안전하게 다시 처리합니다",
            "OCR·청킹은 재시도하고, LLM 분석은 원문 변경과 부분 실패를 job 상태로 통제합니다.": "문서 읽기와 나누기는 다시 시도하고, 인공지능 분석은 원문 변경과 일부 실패를 따로 기록합니다.",
            "OCR · CHUNK": "문서 읽기 · 나누기",
            "late ack": "작업 확인 지연",
            "작업 유실 시 requeue": "작업이 사라지면 대기열에 다시 넣음",
            "exponential backoff": "재시도 간격 늘리기",
            "최대 60초 · 추가 2회": "최대 60초 간격 · 2번 더 시도",
            "후속 enqueue 격리": "다음 단계만 다시 실행",
            "OCR 성공을 다시 돌리지 않음": "완료된 글자 인식은 반복하지 않음",
            "OCR 완료 후 LLM 분석은 자동 연쇄되지 않습니다.": "문서 읽기가 끝나도 인공지능 분석을 자동으로 이어서 실행하지 않습니다.",
            "LLM ANALYSIS JOB": "인공지능 분석 작업",
            "활성 job 1개": "동시에 실행할 분석 1개",
            "PENDING/RUNNING 중복 방지": "같은 분석이 두 번 실행되지 않게 함",
            "원문 snapshot": "분석 시작 때의 원문 저장",
            "text_version + SHA-256 재검증": "분석 전후 원문이 같은지 확인",
            "순차 analyzer": "분석을 차례로 실행",
            "GPU 요청 폭주 방지": "그래픽 장치 과부하 방지",
            "PARTIAL 저장": "일부 성공 결과 저장",
            "timeout": "제한 시간",
            "앱 timeout + Celery hard limit": "정해진 시간을 넘으면 중단",
            "PENDING  →  RUNNING  →  COMPLETED / PARTIAL / FAILED": "대기  →  실행 중  →  완료 / 일부 완료 / 실패",
        },
        22: {
            "SEHYEON SLIDE": "박세현 발표 자료",
            "CONTENT HANDOFF": "최종 자료 반영 예정",
            "세현님이 정리한 최종 파인튜닝 자료로 교체할 슬라이드입니다.": "세현님이 정리한 최종 학습 결과로 교체할 슬라이드입니다.",
            "SLIDE 22": "22번 슬라이드",
            "CONTENT PENDING": "최종 자료 대기 중",
            "학습 목적": "추가 학습을 한 이유",
            "데이터 조건": "사용한 학습·평가 자료",
            "평가 결과": "실제 비교 결과",
            "배포 형태": "제품에 적용한 모델",
            "왜 파인튜닝했는지": "왜 추가 학습했는지",
            "학습·평가 표본과 방식": "자료 수와 평가 방법",
            "비교 가능한 핵심 수치": "근거가 남은 실제 수치",
            "실제 적용 모델과 제약": "적용 모델과 남은 한계",
        },
        23: {
            "STRUCTURED EXTRACTION": "정보 항목 찾기",
            "THREE SAFETY STRATEGIES": "정보마다 다른 방법 사용",
            "결정·일정·액션아이템은 같은 방식으로 뽑지 않습니다": "정보 종류에 따라 다른 방법으로 찾아냅니다",
            "정보 유형에 맞는 후보 생성과 검증을 거친 뒤 모두 PENDING으로 저장합니다.": "결정사항, 일정, 계약 이행 태스크 후보를 각자 맞는 방법으로 찾은 뒤 사람이 확인할 수 있게 저장합니다.",
            "INPUT": "입력",
            "PROCESS": "처리",
            "OUTPUT": "결과",
            "모델 추출 + 원문 유사도": "인공지능이 찾고 원문과 비교",
            "DECIDED / PENDING / REVERSED": "확정 / 검토 대기 / 취소",
            "Python 날짜 후보": "프로그램이 찾은 날짜 후보",
            "모델은 후보 역할만 라벨링": "인공지능이 날짜의 역할만 구분",
            "기간 / 마감 / 회의 / 마일스톤": "기간 / 마감 / 회의 / 주요 일정",
            "액션아이템": "해야 할 일",
            "규칙 기반 의무 후보": "규칙으로 찾은 의무 문장",
            "모델은 후보 ID 중 선택": "인공지능은 후보 안에서만 선택",
            "SAVE AS PENDING": "검토 대기로 저장",
            "COMMON REVIEW STORE": "공통 검토 목록",
            "검토 테이블 PENDING": "검토 대기 목록",
            "Analysis 이력": "분석 기록",
            "검토 테이블 검토 대기": "검토 대기 목록",
        },
        24: {
            "LONG DOCUMENT FIX": "긴 문서 오류 해결",
            "INVISIBLE CHARACTER": "실제 오류 원인",
            "보이지 않는 제어문자 516개가 근거 대조를 깨뜨렸습니다": "눈에 보이지 않는 특수문자 516개 때문에 인용문 확인이 실패했습니다",
            "사람 눈에는 같은 문장이지만 모델 인용과 원문 문자열 비교는 실패했습니다.": "사람에게는 같은 문장으로 보였지만, 프로그램은 서로 다른 문장으로 판단했습니다.",
            "C0·DEL 탐지": "특수문자 발견",
            "문자 길이 보존": "글자 수 유지",
            "SPAN": "위치",
            "원문 좌표 복원": "원문 위치 유지",
            "ERROR SIGNATURE": "실패 원인",
            "quote_not_in_source": "인용문을 원문에서 찾지 못함",
            "BEFORE · RAW TEXT": "수정 전 · 원문",
            "모델 인용에는 \\x01이 없어 문자열 대조 실패": "인공지능의 인용에는 특수문자가 없어 원문 확인 실패",
            "AFTER · SANITIZED TEXT": "수정 후 · 정리한 원문",
            "같은 길이의 공백으로 치환해 원문 span 복원": "같은 길이의 공백으로 바꿔 원문 위치 유지",
            "추출 경계 정리": "문서를 읽은 직후 정리",
            "C0·DEL → 한 글자 공백": "특수문자 → 한 글자 공백",
            "offset · char_count 유지": "글자 수와 위치 유지",
            "근거 대조 개선": "인용문 확인 방식 개선",
            "공백·제어문자 차이 허용": "공백·특수문자 차이는 허용",
            "PR #89 · d47502e  |  탭·줄바꿈·캐리지리턴은 문단 구조를 위해 보존": "수정 기록  PR #89 · d47502e  |  탭과 줄바꿈은 문단 구조를 위해 유지",
        },
        26: {
            "RECORDED PRODUCT DEMO": "녹화한 제품 시연",
            "DEMO": "제품 시연",
            "발표 직전 녹화본을 삽입할 16:9 영역입니다.": "발표 직전에 녹화한 실제 제품 영상을 넣을 자리입니다.",
            "OCR 검수": "문서 글자 확인",
            "근거 QA": "근거가 있는 질의응답",
        },
        27: {
            "LIMITS · NEXT": "한계 · 다음 과제",
            "WHAT WE LEARNED": "확인한 한계",
            "현재 한계를 다음 우선순위로 바꿨습니다": "확인한 한계를 다음 개선 순서로 정했습니다",
            "기능 개수보다 검색 확장성·모델 품질·검토 무결성·운영 증명을 먼저 개선합니다.": "기능을 더 늘리기보다, 문서가 많아도 검색 품질을 유지하고 결과를 안전하게 검토하는 일을 먼저 합니다.",
            "검색 확장성": "검색 대상이 많을 때",
            "전체 1,339청크 R@1 36.9%": "문서 조각 1,339개에서 첫 결과 정답률 36.9%",
            "후보 생성·인덱스·리랭킹 재설계": "검색 범위를 좁히고 최종 순서를 정하는 방식 개선",
            "26건 기준 65.4% · 오차 큼": "실제 26건에서 65.4% · 약 ±8%p",
            "평가셋 확대와 재학습": "평가 자료 확대와 다시 학습",
            "검토 UX": "계약 이행 후보 검토",
            "액션 후보 수정·취소·stale 방어 제한": "현재 화면은 승인·거절만 지원",
            "결정·일정 수준으로 상태 전이 강화": "수정 승인·승인 취소·원문 변경 확인 보강",
            "운영 검증": "자동 검증과 운영 확인",
            "최신 전체 PASS·CI·모니터링 부재": "최신 전체 테스트·자동 테스트·상태 확인 도구 없음",
            "재현 가능한 CI와 관측 지표 구축": "누구나 다시 실행할 수 있는 자동 테스트와 운영 지표 만들기",
            "우선순위  ·  검색 R@1 90%를 문서 수 제한 없이 증명하는 것": "최우선 목표  ·  문서 수를 제한하지 않고 첫 검색 결과 정답률 90% 달성 여부 확인",
        },
        28: {
            "CONCLUSION": "결론",
            "FROM DOCUMENTS TO DECISIONS": "문서에서 판단과 실행까지",
            "문서를 저장하는 도구에서, 판단과 실행을 잇는 플랫폼으로": "문서를 보관하는 도구를 넘어, 판단 근거를 찾고 실제 업무로 연결합니다",
            "하이브리드 검색": "글자와 의미를 함께 찾는 검색",
            "원문 위치가 있는 QA": "원문 위치를 보여주는 질의응답",
            "PENDING 검토": "검토 대기 제안 확인",
            "승인된 정보만 소비": "승인된 정보만 사용",
            "4종 산출물": "보고서와 업무 문서",
            "AI가 제안하고, 사람이 확정하고, 승인된 정보가 실행으로 이어집니다.": "인공지능이 제안하고, 사람이 확정하고, 승인된 정보가 실행으로 이어집니다.",
        },
        29: {
            "Q&amp;A": "질의응답",
            "문서·OCR": "문서·글자 인식",
            "RAG·검색": "근거 검색",
            "LLM·검토": "인공지능 분석·사람 검토",
            "FINAL PROJECT PRESENTATION": "최종 프로젝트 발표",
        },
    }
    for old, new in common.items():
        content = content.replace(old, new)
    for old, new in reviewed.get(slide_no, {}).items():
        content = content.replace(old, new)
    return content


def add_pilot_title_accent(slide_no: int, content: str) -> str:
    """파일럿에서 재사용한 2·4·5번에도 같은 제목 강조선을 덧붙인다."""
    if slide_no not in {2, 4, 5}:
        return content
    y = 375 if slide_no == 2 else 350
    accent = rect(110, y, 118, 7, C["blue"], rx=4) + rect(236, y, 24, 7, C["cyan"], rx=4)
    return content.replace("</svg>", accent + "</svg>")


def reframe_slide(content: str, display_no: int, presenter: str) -> str:
    """콘텐츠의 기존 검수 키와 무관하게 새 표시 번호·발표자를 적용한다."""
    content, header_count = re.subn(r">\d{2}  /  ", f">{display_no:02d}  /  ", content, count=1)
    assert header_count == 1, f"slide {display_no}: header number not found"
    if "PRESENTER  " in content:
        content, presenter_count = re.subn(
            r">PRESENTER  [^<]+</text>",
            f">PRESENTER  {presenter}</text>",
            content,
            count=1,
        )
        assert presenter_count == 1, f"slide {display_no}: presenter not found"
    elif ">발표  " in content:
        content, presenter_count = re.subn(
            r">발표  [^<]+</text>",
            f">발표  {presenter}</text>",
            content,
            count=1,
        )
        assert presenter_count == 1, f"slide {display_no}: reviewed presenter not found"
    return content


def first21_slides():
    """22번 이후 파일을 건드리지 않고 새 발표 순서 1~21만 조립한다."""
    # (새 번호, 기존 콘텐츠 검수 키, 생성 함수, 발표자)
    items = [
        (1, 1, v2.slide1, "김보현"),
        (2, 2, v2.slide2, "김보현"),
        (3, 3, slide3, "김보현"),
        (4, 5, v2.slide5, "김보현"),
        (5, 4, v2.slide4, "김보현"),
        (6, None, slide6, "김보현"),
        (7, 7, slide7, "김보현"),
        (8, 8, slide8, "김보현"),
        (9, 20, slide20, "김보현"),
        (10, 18, slide18, "김보현"),
        (11, 19, slide19, "김보현"),
        (12, 9, slide9, "김보현"),
        (13, 10, slide10, "김보현"),
        (14, 11, slide11, "김보현"),
        (15, 13, slide13, "김보현"),
        (16, 14, slide14, "김보현"),
        (17, 15, slide15, "김보현"),
        (18, 16, slide16, "김보현"),
        (19, 17, slide17, "김보현"),
        (20, None, manual_slide20_embedding_selection, "김보현"),
        (21, 12, slide12, "박세현"),
    ]
    slides = []
    for display_no, review_key, builder, presenter in items:
        content = builder()
        if review_key is not None:
            content = apply_content_review(review_key, content)
            content = add_pilot_title_accent(review_key, content)
        if display_no == 5:
            marker = "기능 슬라이드마다 실제 담당자 표기"
            assert content.count(marker) == 1
            content = content.replace(marker, "김보현 1~20  →  박세현 21번부터")
        slides.append(reframe_slide(content, display_no, presenter))
    assert len(slides) == 21
    return slides


def write_first21_svgs():
    """slide-01~21과 전용 미리보기만 갱신한다. slide-22 이후는 읽거나 쓰지 않는다."""
    OUT.mkdir(parents=True, exist_ok=True)
    slides = first21_slides()
    for idx, content in enumerate(slides, start=1):
        path = OUT / f"slide-{idx:02d}.svg"
        path.write_text(content, encoding="utf-8")
        ET.parse(path)
    parts = [
        '<!doctype html><html><head><meta charset="utf-8"><style>',
        'body{margin:0;background:#dce4f1;font-family:Arial,sans-serif}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:18px;padding:18px}.item{background:white;padding:6px;box-shadow:0 5px 18px #0e162f22}.item img{width:100%;display:block}.item b{display:block;padding:6px;color:#16234a}',
        '</style></head><body><div class="grid">',
    ]
    for idx in range(1, 22):
        parts.append(f'<div class="item"><b>{idx:02d}</b><img src="slide-{idx:02d}.svg"></div>')
    parts.append('</div></body></html>')
    (OUT / "preview-01-21.html").write_text("".join(parts), encoding="utf-8")
    print(f"SVG slides written: {OUT} (1-21 only)")


def all_slides():
    # review_key는 25번 삭제 전의 문구 검수 키다. 마지막 4장의 기존 검수 규칙을 보존한다.
    items = [
        (1, v2.slide1()), (2, v2.slide2()), (3, slide3()), (4, v2.slide4()), (5, v2.slide5()),
        (6, slide6()), (7, slide7()), (8, slide8()), (9, slide9()), (10, slide10()),
        (11, slide11()), (12, slide12()), (13, slide13()), (14, slide14()), (15, slide15()),
        (16, slide16()), (17, slide17()), (18, slide18()), (19, slide19()), (20, slide20()),
        (21, slide21()), (22, slide22()), (23, slide23()), (24, slide24()),
        (26, slide26()), (27, slide27()), (28, slide28()), (29, slide29()),
    ]
    # 최신 근거에 맞춰 단일 멀티태스크 표현을 태스크별 LoRA로 교정한다.
    review_key, team_slide = items[3]
    items[3] = (review_key, team_slide.replace("로컬 LLM 비교·멀티태스크 학습", "로컬 LLM 비교·태스크별 LoRA 학습"))
    assert len(items) == 28
    slides = []
    for review_key, content in items:
        reviewed = apply_content_review(review_key, content)
        slides.append(add_pilot_title_accent(review_key, reviewed))
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
    for idx in range(1,29):parts.append(f'<div class="item"><b>{idx:02d}</b><img src="slide-{idx:02d}.svg"></div>')
    parts.append('</div></body></html>')
    (OUT/'preview.html').write_text(''.join(parts),encoding='utf-8')
    print(f"SVG slides written: {OUT} (28)")


def write_manual_slide_svg(slide_no: int):
    """순서 확정 전 사용자가 직접 교체할 17·20·21번 SVG를 만든다."""
    builders = {
        17: (17, slide17),
        20: (20, manual_slide20_embedding_selection),
        21: (12, manual_slide21_reranker),
    }
    review_key, builder = builders[slide_no]
    target = OUT / f".manual-slide-{slide_no:02d}.svg"
    target.parent.mkdir(parents=True, exist_ok=True)
    content = apply_content_review(review_key, builder())
    target.write_text(content, encoding="utf-8")
    ET.parse(target)
    print(f"Manual slide SVG written: {target}")


def package_pptx():
    count=28
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
    (stage/'docProps/core.xml').write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Tasqra 최종 발표 28장</dc:title><dc:creator>김보현 · 박세현 · 최재정</dc:creator><cp:lastModifiedBy>Kiro</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-09-08T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-08T00:00:00Z</dcterms:modified></cp:coreProperties>''',encoding='utf-8')
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
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['svg','first21','pptx','all','manual','manual17','manual20','manual21'],nargs='?',default='svg');args=parser.parse_args()
    if args.mode in {'svg','all'}:write_svgs()
    if args.mode == 'first21':write_first21_svgs()
    if args.mode in {'pptx','all'}:package_pptx()
    if args.mode == 'manual':
        for slide_no in (17, 20, 21):write_manual_slide_svg(slide_no)
    if args.mode.startswith('manual') and args.mode != 'manual':write_manual_slide_svg(int(args.mode[-2:]))


if __name__=='__main__':main()
