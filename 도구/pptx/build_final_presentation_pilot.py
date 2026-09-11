#!/usr/bin/env python3
"""
① 이 파일의 책임: Tasqra 최종 발표용 5장 디자인 파일럿을 SVG와 PPTX로 생성한다.
② 다른 파일과의 관계: 산출물/최종발표/파일럿에 슬라이드 SVG·PNG·PPTX를 만들며, PNG는 브라우저 렌더링 후 PPTX에 포함된다.
③ Spring 비교: 발표 슬라이드 정의가 View 템플릿, 이 스크립트가 이를 조립하는 ViewResolver 역할을 한다.
"""

from __future__ import annotations

import argparse
import html
import os
import shutil
import zipfile
from pathlib import Path

W, H = 1920, 1080
EMU_W, EMU_H = 12192000, 6858000

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "산출물" / "최종발표" / "파일럿"
PNG_DIR = Path(os.environ.get("TASQRA_PILOT_PNG_DIR", str(OUT)))
PPTX_PATH = OUT / "Tasqra_최종발표_5장_파일럿_v2.pptx"

C = {
    "navy": "#16234A",
    "rail": "#0E162F",
    "blue": "#315BD8",
    "blue2": "#5576E8",
    "cyan": "#3BC7F4",
    "lime": "#C9E85B",
    "canvas": "#F4F7FC",
    "panel": "#FFFFFF",
    "text": "#0F172A",
    "body": "#475569",
    "muted": "#64748B",
    "border": "#DCE5F1",
    "soft": "#EAF0FA",
    "soft_blue": "#E7EEFF",
}


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def rect(x, y, w, h, fill, rx=0, stroke="none", sw=0, opacity=1, extra=""):
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}" opacity="{opacity}" {extra}/>'
    )


def circle(cx, cy, r, fill, stroke="none", sw=0, opacity=1, extra=""):
    return (
        f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}" stroke="{stroke}" '
        f'stroke-width="{sw}" opacity="{opacity}" {extra}/>'
    )


def line(x1, y1, x2, y2, stroke, sw=2, dash=None, opacity=1):
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
        f'stroke-width="{sw}" stroke-linecap="round" opacity="{opacity}"{dash_attr}/>'
    )


def text(x, y, value, size=32, weight=400, fill=None, anchor="start", spacing=0, opacity=1, italic=False):
    fill = fill or C["text"]
    style = "italic" if italic else "normal"
    return (
        f'<text x="{x}" y="{y}" font-family="NotoKR, Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" font-style="{style}" fill="{fill}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}" opacity="{opacity}">{esc(value)}</text>'
    )


def multiline(x, y, lines, size=32, weight=400, fill=None, line_height=1.35, anchor="start"):
    fill = fill or C["text"]
    parts = [
        f'<text x="{x}" y="{y}" font-family="NotoKR, Arial, sans-serif" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">'
    ]
    for idx, value in enumerate(lines):
        dy = 0 if idx == 0 else size * line_height
        parts.append(f'<tspan x="{x}" dy="{dy}">{esc(value)}</tspan>')
    parts.append("</text>")
    return "".join(parts)


def pill(x, y, w, h, label, fill, color, stroke="none", size=22, weight=700):
    return "".join(
        [
            rect(x, y, w, h, fill, rx=h / 2, stroke=stroke, sw=2 if stroke != "none" else 0),
            text(x + w / 2, y + h / 2 + size * 0.34, label, size=size, weight=weight, fill=color, anchor="middle"),
        ]
    )


def icon(kind, cx, cy, size=58, stroke=None, sw=4):
    stroke = stroke or C["blue"]
    s = size / 2
    if kind == "document":
        x, y = cx - s * 0.55, cy - s * 0.68
        return (
            f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            f'<rect x="{x}" y="{y}" width="{s*1.1}" height="{s*1.36}" rx="5"/>'
            f'<path d="M {x+s*.68} {y} v {s*.34} h {s*.42}"/>'
            f'<line x1="{x+s*.22}" y1="{y+s*.65}" x2="{x+s*.84}" y2="{y+s*.65}"/>'
            f'<line x1="{x+s*.22}" y1="{y+s*.91}" x2="{x+s*.72}" y2="{y+s*.91}"/>'
            '</g>'
        )
    if kind == "search":
        return (
            f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round">'
            f'<circle cx="{cx-s*.15}" cy="{cy-s*.16}" r="{s*.48}"/>'
            f'<line x1="{cx+s*.20}" y1="{cy+s*.19}" x2="{cx+s*.64}" y2="{cy+s*.63}"/>'
            '</g>'
        )
    if kind == "check":
        return (
            f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            f'<circle cx="{cx}" cy="{cy}" r="{s*.66}"/>'
            f'<path d="M {cx-s*.34} {cy} l {s*.25} {s*.27} l {s*.48} {-s*.52}"/>'
            '</g>'
        )
    if kind == "tasks":
        x, y = cx - s * 0.65, cy - s * 0.60
        return (
            f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round" stroke-linejoin="round">'
            f'<rect x="{x}" y="{y}" width="{s*1.3}" height="{s*1.2}" rx="6"/>'
            f'<path d="M {x+s*.18} {y+s*.35} l {s*.10} {s*.10} l {s*.18} {-s*.20}"/>'
            f'<line x1="{x+s*.55}" y1="{y+s*.34}" x2="{x+s*1.05}" y2="{y+s*.34}"/>'
            f'<path d="M {x+s*.18} {y+s*.76} l {s*.10} {s*.10} l {s*.18} {-s*.20}"/>'
            f'<line x1="{x+s*.55}" y1="{y+s*.75}" x2="{x+s*1.05}" y2="{y+s*.75}"/>'
            '</g>'
        )
    if kind == "structure":
        return (
            f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round">'
            f'<line x1="{cx}" y1="{cy-s*.52}" x2="{cx}" y2="{cy}"/>'
            f'<line x1="{cx-s*.48}" y1="{cy+s*.45}" x2="{cx+s*.48}" y2="{cy+s*.45}"/>'
            f'<line x1="{cx-s*.48}" y1="{cy+s*.45}" x2="{cx}" y2="{cy}"/>'
            f'<line x1="{cx+s*.48}" y1="{cy+s*.45}" x2="{cx}" y2="{cy}"/>'
            f'<circle cx="{cx}" cy="{cy-s*.58}" r="{s*.18}" fill="{stroke}"/>'
            f'<circle cx="{cx-s*.52}" cy="{cy+s*.48}" r="{s*.18}" fill="{stroke}"/>'
            f'<circle cx="{cx+s*.52}" cy="{cy+s*.48}" r="{s*.18}" fill="{stroke}"/>'
            '</g>'
        )
    if kind == "users":
        return (
            f'<g fill="none" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="round">'
            f'<circle cx="{cx}" cy="{cy-s*.34}" r="{s*.25}"/>'
            f'<path d="M {cx-s*.54} {cy+s*.55} q 0 {-s*.58} {s*.54} {-s*.58} q {s*.54} 0 {s*.54} {s*.58}"/>'
            '</g>'
        )
    return circle(cx, cy, s * 0.18, stroke)


def base(light=True, page="01", label="INTRO"):
    bg = C["canvas"] if light else C["rail"]
    fg = C["text"] if light else "#FFFFFF"
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
        '<defs>',
        '<style>@font-face{font-family:NotoKR;src:url("../../포트폴리오/NotoSansKR.ttf") format("truetype");} text{font-family:NotoKR,Arial,sans-serif;}</style>',
        '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="14" stdDeviation="18" flood-color="#0E162F" flood-opacity="0.10"/></filter>',
        '<filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0" dy="7" stdDeviation="10" flood-color="#0E162F" flood-opacity="0.08"/></filter>',
        '</defs>',
        rect(0, 0, W, H, bg),
        text(110, 70, f"{page}  /  {label}", 18, 700, C["blue"] if light else C["cyan"], spacing=2.2),
        text(1810, 70, "TASQRA", 18, 800, fg, anchor="end", spacing=2.5, opacity=0.65),
    ]


def finish(parts):
    parts.append("</svg>")
    return "".join(parts)


def slide1():
    p = base(light=False, page="00", label="FINAL PROJECT")
    # Subtle background grid and light paths.
    for x in range(1120, 1880, 90):
        p.append(line(x, 115, x, 970, "#23315C", 1, opacity=0.34))
    for y in range(160, 980, 90):
        p.append(line(1060, y, 1880, y, "#23315C", 1, opacity=0.34))
    p += [
        pill(110, 135, 290, 48, "FINAL PROJECT PRESENTATION", "#1B2B59", C["cyan"], size=17),
        text(110, 315, "Tasqra", 142, 800, "#FFFFFF", spacing=-4),
        text(116, 430, "프로젝트 문서를,", 46, 500, "#DCE7FF"),
        text(116, 500, "근거 있는 실행으로", 60, 800, C["blue"]),
        line(116, 552, 770, 552, "#41507C", 2),
        text(116, 605, "공공 SI·용역 프로젝트를 위한", 26, 700, "#FFFFFF"),
        text(116, 648, "문서 분석·근거 검색·업무 연결 서비스", 26, 500, "#C9D4EC"),
        text(116, 710, "김보현  ·  박세현  ·  최재정", 25, 700, "#FFFFFF"),
        text(116, 760, "DOCUMENT  →  EVIDENCE  →  ACTION", 18, 700, C["cyan"], spacing=2.8),
        # Right composition panel.
        rect(1030, 120, 760, 840, "#111D3E", rx=46, stroke="#293965", sw=2),
        text(1080, 180, "DOCUMENT  ·  EVIDENCE  ·  ACTION", 15, 800, "#7186B8", spacing=1.8),
    ]
    # 연결선은 중앙 원과 노드 아래에 먼저 그려 글자와 겹치지 않게 한다.
    connectors = [
        (1230, 360, 1305, 430, C["cyan"]),
        (1588, 360, 1515, 430, C["blue2"]),
        (1230, 710, 1305, 640, C["lime"]),
        (1588, 710, 1515, 640, C["cyan"]),
    ]
    for x1, y1, x2, y2, accent in connectors:
        p.append(line(x1, y1, x2, y2, "#526696", 4, opacity=0.9))
        p.append(circle((x1 + x2) / 2, (y1 + y2) / 2, 7, accent))
    nodes = [
        (1175, 305, "document", "문서", C["cyan"]),
        (1645, 305, "search", "검색", C["blue2"]),
        (1175, 765, "structure", "분석", C["lime"]),
        (1645, 765, "tasks", "태스크", C["cyan"]),
    ]
    for x, y, kind, label, accent in nodes:
        p.append(circle(x, y, 78, "#17264F", stroke=accent, sw=3, extra='filter="url(#softShadow)"'))
        p.append(icon(kind, x, y - 10, 48, accent, 3))
        p.append(text(x, y + 51, label, 21, 700, "#FFFFFF", anchor="middle"))
    # 핵심인 사람의 검토를 마지막에 올려 연결선과 완전히 분리한다.
    p += [
        circle(1410, 535, 142, C["navy"], stroke=C["blue"], sw=5, extra='filter="url(#shadow)"'),
        circle(1410, 535, 111, "#1C2C59", stroke="#5E7AEC", sw=2),
        icon("check", 1410, 477, 62, C["cyan"], 4),
        text(1410, 570, "사람의 검토", 29, 800, "#FFFFFF", anchor="middle"),
        text(1410, 607, "확정된 정보만 연결", 18, 500, "#AFC0E8", anchor="middle"),
    ]
    return finish(p)


def title_block(p, kicker, title_lines, subtitle=None, *, title_size=56):
    p.append(text(110, 130, kicker, 20, 800, C["blue"], spacing=1.8))
    p.append(multiline(110, 205, title_lines, title_size, 800, C["text"], line_height=1.15))
    if subtitle:
        p.append(text(112, 340 if len(title_lines) > 1 else 295, subtitle, 25, 500, C["body"]))


def slide2():
    p = base(light=True, page="01", label="TARGET SELECTION")
    title_block(
        p,
        "WHY PUBLIC SI & SERVICE PROJECTS",
        ["공개 데이터가 많을 것이라는", "가설에서 시작했습니다"],
        "타깃 선정 당시의 판단과 프로젝트를 진행하며 확인한 한계를 구분했습니다.",
        title_size=50,
    )
    cards = [
        (110, "01", "search", "초기 가설", ["나라장터 등에 공개된 문서가 많아", "학습과 검증에 필요한 데이터를", "쉽게 확보할 수 있을 것으로 봤습니다."], C["blue"]),
        (680, "02", "document", "타깃 선정", ["공개 문서를 활용할 수 있는", "공공 SI 중심의 공공 용역 사업을", "프로젝트 대상으로 정했습니다."], C["cyan"]),
        (1250, "03", "check", "진행 후 확인", ["원문 문서는 많았지만 정답 표시가 된", "학습·평가용 샘플은 부족해", "직접 정리하고 평가 기준을 만들었습니다."], C["lime"]),
    ]
    for x, no, kind, heading, body, accent in cards:
        y, w, h = 420, 500, 345
        p.append(rect(x, y, w, h, C["panel"], rx=28, stroke=C["border"], sw=2, extra='filter="url(#softShadow)"'))
        p.append(rect(x, y, w, 12, accent, rx=6))
        p.append(pill(x + 32, y + 40, 64, 36, no, C["soft_blue"], C["blue"], size=17))
        p.append(circle(x + 423, y + 80, 46, C["soft"], stroke=accent, sw=2))
        p.append(icon(kind, x + 423, y + 80, 42, accent, 3))
        p.append(text(x + 34, y + 145, heading, 29, 800, C["text"]))
        p.append(multiline(x + 34, y + 202, body, 20, 500, C["body"], line_height=1.5))
        p.append(line(x + 34, y + 300, x + 466, y + 300, C["border"], 2))
        p.append(text(x + 34, y + 326, "HYPOTHESIS  →  SELECTION  →  LEARNING", 12, 800, C["muted"], spacing=1.2))
    p += [
        rect(110, 825, 1640, 140, C["navy"], rx=28, extra='filter="url(#softShadow)"'),
        circle(180, 895, 30, C["blue"]),
        icon("structure", 180, 895, 34, "#FFFFFF", 3),
        text(240, 882, "선정 후 확인한 문제 적합성", 18, 800, C["cyan"], spacing=1.1),
        text(240, 925, "발주·계약·과업·보고 문서가 이어지고, 중요한 정보에는 원문 근거와 사람의 확인이 필요했습니다.", 27, 700, "#FFFFFF"),
    ]
    return finish(p)


def slide3():
    p = base(light=True, page="02", label="SERVICE GOAL")
    title_block(p, "HUMAN IN THE LOOP", ["Tasqra는 문서에서 실행까지", "한 흐름으로 연결합니다"], title_size=48)
    # Connectors first.
    center = (960, 600)
    endpoints = [(400, 530), (1520, 530), (960, 805)]
    for ex, ey in endpoints:
        p.append(line(center[0], center[1], ex, ey, "#B8C7E6", 5))
        p.append(circle((center[0]+ex)/2, (center[1]+ey)/2, 8, C["cyan"]))
    # Center system.
    p += [
        circle(960, 600, 165, C["navy"], stroke="#D9E3FA", sw=18, extra='filter="url(#shadow)"'),
        circle(960, 600, 137, "#1D2E5C", stroke=C["blue"], sw=3),
        text(960, 550, "AI가 제안하고,", 22, 500, "#C4D0EC", anchor="middle"),
        text(960, 615, "사람이", 44, 800, "#FFFFFF", anchor="middle"),
        text(960, 668, "확정합니다", 42, 800, C["cyan"], anchor="middle"),
    ]
    cards = [
        (155, 415, 490, 260, "01", "search", "찾는다", ["문서 근거와 함께 필요한 정보를", "검색합니다."], C["blue"]),
        (1275, 415, 490, 260, "02", "structure", "구조화한다", ["결정사항·일정·액션아이템·금액을", "검토 가능한 정보로 정리합니다."], C["cyan"]),
        (715, 825, 490, 190, "03", "tasks", "연결한다", ["승인된 정보를 태스크·대시보드에", "반영하고 문서로 만듭니다."], C["lime"]),
    ]
    for x, y, w, h, no, kind, heading, body, accent in cards:
        p.append(rect(x, y, w, h, C["panel"], rx=28, stroke=C["border"], sw=2, extra='filter="url(#softShadow)"'))
        p.append(circle(x + 65, y + 70, 36, C["soft"], stroke=accent, sw=2))
        p.append(icon(kind, x + 65, y + 70, 34, accent, 3))
        p.append(text(x + 120, y + 55, no, 16, 800, accent, spacing=1.4))
        p.append(text(x + 120, y + 100, heading, 28, 800, C["text"]))
        body_y = y + (146 if h < 230 else 164)
        body_size = 18 if h < 230 else 20
        p.append(multiline(x + 42, body_y, body, body_size, 500, C["body"], line_height=1.45))
    return finish(p)


def slide4():
    p = base(light=True, page="03", label="TEAM")
    title_block(p, "ONE PRODUCT · THREE EXPERTISE", ["한 제품 흐름을 세 영역의 전문성으로", "완성했습니다"])
    cards = [
        (110, "김보현", "RAG 검색·정보 활용", "search", C["blue"], ["RAG 청킹·임베딩 색인", "하이브리드 검색·근거 QA", "금액 검토·대시보드·산출물"]),
        (680, "박세현", "LLM·임베딩 모델", "structure", C["cyan"], ["LLM 요약·분류 파인튜닝", "임베딩·리랭커 파인튜닝", "긴 문서 분석 오류 개선"]),
        (1250, "최재정", "OCR·핵심 업무 흐름", "tasks", C["lime"], ["OCR 추출·본문 복원", "OCR 검수·재OCR", "프로젝트·문서 처리·태스크 보드"]),
    ]
    for idx, (x, name, role, kind, accent, bullets) in enumerate(cards, start=1):
        y, w, h = 410, 500, 430
        p.append(rect(x, y, w, h, C["panel"], rx=30, stroke=C["border"], sw=2, extra='filter="url(#softShadow)"'))
        p.append(rect(x, y, w, 13, accent, rx=7))
        p.append(circle(x + 73, y + 85, 45, C["soft"], stroke=accent, sw=3))
        p.append(icon(kind, x + 73, y + 85, 40, accent if accent != C["lime"] else C["lime"], 3))
        p.append(text(x + 445, y + 68, f"0{idx}", 18, 800, C["muted"], anchor="end", spacing=1.8))
        p.append(text(x + 36, y + 165, name, 40, 800, C["text"]))
        p.append(text(x + 36, y + 205, role, 15, 800, C["blue"], spacing=1.05))
        p.append(line(x + 36, y + 238, x + 464, y + 238, C["border"], 2))
        for j, bullet in enumerate(bullets):
            by = y + 292 + j * 48
            p.append(circle(x + 46, by - 8, 5, accent))
            p.append(text(x + 68, by, bullet, 20, 500, C["body"]))
    p += [
        rect(110, 890, 1640, 96, C["navy"], rx=24),
        text(155, 948, "발표 흐름", 18, 800, C["cyan"], spacing=1.5),
        text(315, 950, "김보현", 25, 800, "#FFFFFF"),
        line(430, 941, 520, 941, C["blue2"], 4),
        circle(520, 941, 7, C["cyan"]),
        text(560, 950, "박세현", 25, 800, "#FFFFFF"),
        text(1670, 950, "기능 슬라이드마다 실제 담당자 표기", 18, 500, "#AFC0E8", anchor="end"),
    ]
    return finish(p)


def slide5():
    p = base(light=True, page="04", label="USER FLOW")
    title_block(p, "END-TO-END WORKFLOW", ["문서를 올리면, 검토 가능한 업무 정보로", "연결됩니다"])
    steps = [
        ("01", "document", "문서 업로드", ["프로젝트 문서를", "등록합니다."]),
        ("02", "structure", "OCR·텍스트 정제", ["검색·분석 가능한 형태로", "정리합니다."]),
        ("03", "search", "AI 분석·검색 색인", ["정보를 분석하고", "검색 색인을 만듭니다."]),
        ("04", "check", "사람의 검토", ["승인·수정·거절로", "제안을 확정합니다."]),
        ("05", "tasks", "업무 연결", ["태스크·대시보드·", "산출물에 반영합니다."]),
    ]
    xs = [125, 475, 825, 1175, 1525]
    y = 440
    for i in range(4):
        p.append(line(xs[i] + 120, y + 75, xs[i+1] - 40, y + 75, "#AEBDE0", 5))
        p.append(f'<path d="M {xs[i+1]-58} {y+61} L {xs[i+1]-40} {y+75} L {xs[i+1]-58} {y+89}" fill="none" stroke="#AEBDE0" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>')
    for idx, ((no, kind, heading, body), x) in enumerate(zip(steps, xs)):
        highlight = idx == 3
        accent = C["blue"] if highlight else (C["cyan"] if idx in (1, 4) else C["blue2"])
        panel_fill = C["navy"] if highlight else C["panel"]
        title_color = "#FFFFFF" if highlight else C["text"]
        body_color = "#C9D4EC" if highlight else C["body"]
        border = C["blue"] if highlight else C["border"]
        p.append(rect(x - 35, y, 280, 255, panel_fill, rx=26, stroke=border, sw=3 if highlight else 2, extra='filter="url(#softShadow)"'))
        p.append(circle(x + 105, y + 75, 52, C["blue"] if highlight else C["soft"], stroke=accent, sw=2))
        p.append(icon(kind, x + 105, y + 75, 45, "#FFFFFF" if highlight else accent, 3))
        p.append(pill(x - 13, y + 25, 55, 32, no, C["blue"] if highlight else C["soft_blue"], "#FFFFFF" if highlight else C["blue"], size=15))
        p.append(text(x + 105, y + 158, heading, 25, 800, title_color, anchor="middle"))
        p.append(multiline(x + 105, y + 202, body, 19, 500, body_color, line_height=1.45, anchor="middle"))
    # Bottom action panel.
    p += [
        rect(110, 755, 1090, 245, C["navy"], rx=30, extra='filter="url(#softShadow)"'),
        text(150, 810, "ACTION ITEM  ·  단건 검토 흐름", 18, 800, C["cyan"], spacing=1.4),
    ]
    action_labels = ["액션아이템 추출", "액션 태스크 후보", "단건 승인·거절", "태스크 생성"]
    action_xs = [235, 490, 750, 1015]
    for i, (label, ax) in enumerate(zip(action_labels, action_xs)):
        p.append(circle(ax, 900, 34, C["blue"] if i == 2 else "#243768", stroke=C["cyan"] if i == 2 else "#536898", sw=2))
        p.append(text(ax, 908, f"{i+1}", 18, 800, "#FFFFFF", anchor="middle"))
        p.append(text(ax, 956, label, 18, 600, "#FFFFFF", anchor="middle"))
        if i < 3:
            p.append(line(ax + 38, 900, action_xs[i+1] - 38, 900, "#5B6E9C", 4))
    # Outputs panel.
    p += [
        rect(1240, 755, 510, 245, C["panel"], rx=30, stroke=C["border"], sw=2, extra='filter="url(#softShadow)"'),
        text(1280, 810, "FINAL OUTPUTS", 18, 800, C["blue"], spacing=1.4),
        text(1280, 850, "승인된 정보로 만드는 산출물", 24, 700, C["text"]),
    ]
    output_pills = [(1280, 885, "주간 보고서"), (1498, 885, "프로젝트 현황"), (1280, 940, "결정사항 로그"), (1498, 940, "회의 안건")]
    for ox, oy, label in output_pills:
        p.append(pill(ox, oy, 190, 42, label, C["soft_blue"], C["navy"], size=17))
    return finish(p)


def write_svgs():
    OUT.mkdir(parents=True, exist_ok=True)
    slides = [slide1(), slide2(), slide3(), slide4(), slide5()]
    for idx, content in enumerate(slides, start=1):
        (OUT / f"slide-{idx}.svg").write_text(content, encoding="utf-8")
    contact = [
        '<!doctype html><html><head><meta charset="utf-8"><style>',
        'body{margin:0;background:#dce4f1;font-family:Arial,sans-serif;} .grid{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:24px;} img{width:100%;box-shadow:0 8px 24px #0e162f22;border-radius:8px;} .last{grid-column:1 / span 2;width:calc(50% - 12px);margin:auto;} ',
        '</style></head><body><div class="grid">',
    ]
    for idx in range(1, 6):
        cls = ' class="last"' if idx == 5 else ""
        contact.append(f'<img{cls} src="slide-{idx}.svg" alt="slide {idx}">')
    contact.append('</div></body></html>')
    (OUT / "preview.html").write_text("".join(contact), encoding="utf-8")
    print(f"SVG slides written to {OUT}")


def _rels_xml():
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def package_pptx():
    pngs = [PNG_DIR / f"slide-{idx}.png" for idx in range(1, 6)]
    missing = [str(p) for p in pngs if not p.exists()]
    if missing:
        raise SystemExit("PNG files missing: " + ", ".join(missing))

    stage = OUT / ".pptx-stage"
    if stage.exists():
        shutil.rmtree(stage)
    dirs = [
        "_rels", "docProps", "ppt/_rels", "ppt/slides/_rels", "ppt/slides", "ppt/slideMasters/_rels",
        "ppt/slideMasters", "ppt/slideLayouts/_rels", "ppt/slideLayouts", "ppt/theme", "ppt/media",
    ]
    for d in dirs:
        (stage / d).mkdir(parents=True, exist_ok=True)

    overrides = [
        '<Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>',
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>',
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>',
        '<Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>',
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>',
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>',
    ]
    for i in range(1, 6):
        overrides.append(f'<Override PartName="/ppt/slides/slide{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>')
    types = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Default Extension="png" ContentType="image/png"/>' + "".join(overrides) + '</Types>'
    (stage / "[Content_Types].xml").write_text(types, encoding="utf-8")
    (stage / "_rels/.rels").write_text(_rels_xml(), encoding="utf-8")

    core = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Tasqra 최종 발표 5장 파일럿</dc:title><dc:creator>김보현</dc:creator><cp:lastModifiedBy>Kiro</cp:lastModifiedBy><dcterms:created xsi:type="dcterms:W3CDTF">2026-09-08T00:00:00Z</dcterms:created><dcterms:modified xsi:type="dcterms:W3CDTF">2026-09-08T00:00:00Z</dcterms:modified></cp:coreProperties>'''
    app = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Microsoft Office PowerPoint</Application><PresentationFormat>Widescreen</PresentationFormat><Slides>5</Slides><Company>Tasqra</Company></Properties>'''
    (stage / "docProps/core.xml").write_text(core, encoding="utf-8")
    (stage / "docProps/app.xml").write_text(app, encoding="utf-8")

    sld_ids = "".join(f'<p:sldId id="{255+i}" r:id="rId{i+1}"/>' for i in range(1, 6))
    presentation = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst><p:sldIdLst>{sld_ids}</p:sldIdLst><p:sldSz cx="{EMU_W}" cy="{EMU_H}" type="screen16x9"/><p:notesSz cx="6858000" cy="9144000"/></p:presentation>'''
    (stage / "ppt/presentation.xml").write_text(presentation, encoding="utf-8")
    pres_rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">', '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    for i in range(1, 6):
        pres_rels.append(f'<Relationship Id="rId{i+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>')
    pres_rels.append('</Relationships>')
    (stage / "ppt/_rels/presentation.xml.rels").write_text("".join(pres_rels), encoding="utf-8")

    master = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld name="Blank Master"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld><p:sldLayoutIdLst><p:sldLayoutId id="1" r:id="rId1"/></p:sldLayoutIdLst><p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles></p:sldMaster>'''
    (stage / "ppt/slideMasters/slideMaster1.xml").write_text(master, encoding="utf-8")
    (stage / "ppt/slideMasters/_rels/slideMaster1.xml.rels").write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/></Relationships>''', encoding="utf-8")
    layout = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank"><p:cSld name="Blank"><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr></p:spTree></p:cSld></p:sldLayout>'''
    (stage / "ppt/slideLayouts/slideLayout1.xml").write_text(layout, encoding="utf-8")
    (stage / "ppt/slideLayouts/_rels/slideLayout1.xml.rels").write_text('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/></Relationships>''', encoding="utf-8")
    theme = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Tasqra"><a:themeElements><a:clrScheme name="Tasqra"><a:dk1><a:srgbClr val="0E162F"/></a:dk1><a:lt1><a:srgbClr val="FFFFFF"/></a:lt1><a:dk2><a:srgbClr val="16234A"/></a:dk2><a:lt2><a:srgbClr val="F4F7FC"/></a:lt2><a:accent1><a:srgbClr val="315BD8"/></a:accent1><a:accent2><a:srgbClr val="3BC7F4"/></a:accent2><a:accent3><a:srgbClr val="C9E85B"/></a:accent3><a:accent4><a:srgbClr val="5576E8"/></a:accent4><a:accent5><a:srgbClr val="475569"/></a:accent5><a:accent6><a:srgbClr val="DCE5F1"/></a:accent6><a:hlink><a:srgbClr val="315BD8"/></a:hlink><a:folHlink><a:srgbClr val="16234A"/></a:folHlink></a:clrScheme><a:fontScheme name="Tasqra"><a:majorFont><a:latin typeface="Noto Sans KR"/><a:ea typeface="Noto Sans KR"/><a:cs typeface="Arial"/></a:majorFont><a:minorFont><a:latin typeface="Noto Sans KR"/><a:ea typeface="Noto Sans KR"/><a:cs typeface="Arial"/></a:minorFont></a:fontScheme><a:fmtScheme name="Tasqra"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'''
    (stage / "ppt/theme/theme1.xml").write_text(theme, encoding="utf-8")

    for i, png in enumerate(pngs, start=1):
        shutil.copyfile(png, stage / f"ppt/media/image{i}.png")
        slide = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr><p:pic><p:nvPicPr><p:cNvPr id="2" name="Tasqra Slide {i}"/><p:cNvPicPr><a:picLocks noChangeAspect="1"/></p:cNvPicPr><p:nvPr/></p:nvPicPr><p:blipFill><a:blip r:embed="rId2"/><a:stretch><a:fillRect/></a:stretch></p:blipFill><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{EMU_W}" cy="{EMU_H}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic></p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'''
        rels = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/image{i}.png"/></Relationships>'''
        (stage / f"ppt/slides/slide{i}.xml").write_text(slide, encoding="utf-8")
        (stage / f"ppt/slides/_rels/slide{i}.xml.rels").write_text(rels, encoding="utf-8")

    if PPTX_PATH.exists():
        PPTX_PATH.unlink()
    with zipfile.ZipFile(PPTX_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in sorted(stage.rglob("*")):
            if file.is_file():
                zf.write(file, file.relative_to(stage).as_posix())
    shutil.rmtree(stage)
    print(f"PPTX written to {PPTX_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["svg", "pptx", "all"], nargs="?", default="svg")
    args = parser.parse_args()
    if args.mode in {"svg", "all"}:
        write_svgs()
    if args.mode in {"pptx", "all"}:
        package_pptx()


if __name__ == "__main__":
    main()
