# ① 책임: 분야별 ERD SVG를 A3 가로 인쇄용 HTML과 공식 제출용 PDF로 조립한다.
# ② 관계: 산출물/ERD/원본의 SVG 4개와 ERD_전체개요.svg를 읽고 같은 디렉터리에 HTML·PDF를 생성한다.
# ③ Spring 비교: 문서 원본을 주입받아 렌더링 결과를 만드는 서비스 계층과 같은 역할이며 제품 DB 코드는 변경하지 않는다.
from __future__ import annotations

import base64
import html
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ERD_DIR = ROOT / "산출물" / "ERD"
SOURCE_DIR = ERD_DIR / "원본"
HTML_PATH = ERD_DIR / "Tasqra_ERD_인쇄원본.html"
PDF_PATH = ERD_DIR / "Tasqra_ERD.pdf"
CHROME = Path("/usr/local/bin/chrome")
FONT_PATH = ROOT / "산출물" / "포트폴리오" / "NotoSansKR.ttf"

VERSION = "v1.0"
DATE = "2026-09-07"
COMMIT = "0b4168c6d236688d6ead6704db6e82d4da37f3f4"

DETAILS = [
    {
        "number": 1,
        "field": "사용자와 프로젝트",
        "file": "01_사용자와_프로젝트.svg",
        "tables": "users · refresh_tokens · projects · project_members · project_invitations",
        "cross": "분야 밖으로 나가는 FK 없음. users와 projects는 후속 상세도에서 회색 참조 테이블로 반복한다.",
    },
    {
        "number": 2,
        "field": "문서와 OCR 검수",
        "file": "02_문서와_OCR_검수.svg",
        "tables": "documents · document_pages · extracted_texts · document_chunks · OCR 이력",
        "cross": "사용자 교차 참조: documents.uploaded_by/reviewed_by, extracted_texts.confirmed_by, ocr_element_revisions.changed_by, OCR 작업 created_by → users.id",
    },
    {
        "number": 3,
        "field": "AI 분석과 제안",
        "file": "03_AI_분석과_제안.svg",
        "tables": "analyses · analysis_jobs · amount_items · decisions · schedule_items · task_suggestions",
        "cross": "교차 참조: 각 추출물의 decided_by → users.id, task_suggestions.created_task_id → tasks.id",
    },
    {
        "number": 4,
        "field": "태스크와 산출물",
        "file": "04_태스크와_산출물.svg",
        "tables": "tasks · task_activity_logs · deliverables (task_suggestions/amount_items 참조)",
        "cross": "문서·분석 교차 참조: task_suggestions 및 amount_items의 document_id → documents.id, analysis_id → analyses.id",
    },
]


def inline_svg(path: Path, css_class: str) -> str:
    source = path.read_text(encoding="utf-8-sig").strip()
    if not source.startswith("<svg") or not source.endswith("</svg>"):
        raise ValueError(f"Invalid SVG: {path}")
    source = source.replace("⋔ 다(多)", "N 다(多)")
    return re.sub(r"<svg\s", f'<svg class="{css_class}" ', source, count=1)


def detail_page(item: dict[str, object], page_number: int) -> str:
    svg = inline_svg(SOURCE_DIR / str(item["file"]), "erd-svg")
    return f"""
<section class="page detail-page">
  <header class="page-head">
    <div><span class="eyebrow">분야별 상세 ERD</span><h2>그림 {item['number']}. {html.escape(str(item['field']))}</h2></div>
    <div class="page-no">{page_number} / 6</div>
  </header>
  <div class="svg-wrap">{svg}</div>
  <footer class="cross-ref"><b>교차 참조</b> {html.escape(str(item['cross']))}</footer>
</section>"""


def build_html() -> str:
    overview = inline_svg(ERD_DIR / "ERD_전체개요.svg", "overview-svg")
    font_data = base64.b64encode(FONT_PATH.read_bytes()).decode("ascii")
    detail_html = "".join(detail_page(item, index + 3) for index, item in enumerate(DETAILS))
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tasqra 데이터베이스 ERD</title>
<style>
@font-face {{ font-family: "Tasqra Noto Sans KR"; src: url("data:font/ttf;base64,{font_data}") format("truetype"); font-style: normal; font-weight: 100 900; font-display: block; }}
@page {{ size: A3 landscape; margin: 0; }}
* {{ box-sizing: border-box; }}
html, body {{ margin: 0; padding: 0; background: #fff; color: #111; font-family: "Tasqra Noto Sans KR", sans-serif; }}
body {{ print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
.page {{ width: 420mm; height: 297mm; padding: 7mm; overflow: hidden; position: relative; page-break-after: always; break-after: page; background: #fff; }}
.page:last-child {{ page-break-after: auto; break-after: auto; }}
.eyebrow {{ display: block; margin-bottom: 1.5mm; color: #666; font-size: 8.5pt; font-weight: 700; letter-spacing: .08em; }}
h1, h2, h3, p {{ margin: 0; }}
.cover {{ padding: 16mm 18mm; display: grid; grid-template-columns: 1.22fr .78fr; gap: 18mm; }}
.cover-main {{ display: flex; flex-direction: column; justify-content: space-between; border-top: 2.2mm solid #111; padding-top: 13mm; }}
.cover h1 {{ font-size: 31pt; letter-spacing: -.04em; line-height: 1.12; }}
.cover-sub {{ margin-top: 6mm; max-width: 250mm; font-size: 13pt; line-height: 1.65; color: #444; }}
.meta {{ width: 100%; border-collapse: collapse; font-size: 10.5pt; }}
.meta th, .meta td {{ border-top: .35mm solid #aaa; padding: 3.4mm 2mm; text-align: left; vertical-align: top; }}
.meta th {{ width: 42mm; color: #555; font-weight: 600; }}
.commit {{ font-family: "IBM Plex Mono", Consolas, monospace; font-size: 8.7pt; word-break: break-all; }}
.cover-side {{ border: .4mm solid #777; padding: 10mm; display: flex; flex-direction: column; gap: 9mm; }}
.cover-side h2 {{ font-size: 15pt; border-bottom: .5mm solid #222; padding-bottom: 3mm; }}
.domain-list {{ margin: 0; padding-left: 6mm; line-height: 1.95; font-size: 11pt; }}
.legend-grid {{ display: grid; grid-template-columns: 14mm 1fr; gap: 3mm 4mm; align-items: center; font-size: 10pt; }}
.legend-symbol {{ height: 10mm; border: .35mm solid #777; display: grid; place-items: center; font-family: "Tasqra Noto Sans KR", sans-serif; font-weight: 700; }}
.legend-note {{ color: #555; font-size: 8.8pt; line-height: 1.55; }}
.version-stamp {{ color: #555; font: 9pt Consolas, monospace; }}
.page-head {{ height: 13mm; border-bottom: .4mm solid #555; padding: 0 1mm 2.5mm; display: flex; align-items: flex-start; justify-content: space-between; }}
.page-head h2 {{ font-size: 15pt; line-height: 1; }}
.page-no {{ color: #666; font: 9pt Consolas, monospace; }}
.overview-page {{ display: flex; flex-direction: column; }}
.overview-wrap {{ flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; padding-top: 4mm; }}
.overview-svg {{ width: 100%; height: 100%; }}
.detail-page {{ display: flex; flex-direction: column; }}
.svg-wrap {{ flex: 1; min-height: 0; display: flex; align-items: center; justify-content: center; padding: 1mm 0 2mm; }}
.erd-svg {{ width: 100%; height: 100%; }}
.erd-svg text, .overview-svg text {{ font-family: "Tasqra Noto Sans KR", sans-serif !important; }}
.cross-ref {{ min-height: 10mm; border-top: .35mm solid #999; padding: 2.3mm 1mm 0; color: #444; font-size: 8.2pt; line-height: 1.35; }}
.cross-ref b {{ color: #111; margin-right: 2mm; }}
/* 원본 SVG는 보존하고, 인쇄 HTML 안에서만 무채색으로 치환한다. */
.erd-svg [fill="#FBFCFD"] {{ fill: #fff !important; }}
.erd-svg [fill="#14202F"], .erd-svg [fill="#1F5285"] {{ fill: #111 !important; }}
.erd-svg [fill="#6B7887"], .erd-svg [fill="#93A0AE"] {{ fill: #666 !important; }}
.erd-svg [fill="#3A4553"], .erd-svg [fill="#3A2B29"], .erd-svg [fill="#2F3A47"] {{ fill: #333 !important; }}
.erd-svg [fill="#DFE5EC"] {{ fill: #e2e2e2 !important; }}
.erd-svg [fill="#F2B3AB"] {{ fill: #d1d1d1 !important; }}
.erd-svg [stroke="#D08F87"], .erd-svg [stroke="#B6C1CE"] {{ stroke: #999 !important; }}
.erd-svg [stroke="#AFB8C2"], .erd-svg [stroke="#7A8794"] {{ stroke: #777 !important; }}
.erd-svg [stroke="#ECEFF3"] {{ stroke: #e7e7e7 !important; }}
</style>
</head>
<body>
<section class="page cover">
  <div class="cover-main">
    <div>
      <span class="eyebrow">OFFICIAL DATABASE DESIGN ARTIFACT</span>
      <h1>Tasqra 데이터베이스 ERD</h1>
      <p class="cover-sub">분야별 상세 ERD는 가독성을 위해 분리함. 전체 개요는 핵심 데이터 흐름을 설명하고, 상세 페이지는 원본 SVG를 벡터 상태로 수록한다.</p>
    </div>
    <table class="meta">
      <tr><th>문서 버전</th><td>{VERSION}</td></tr>
      <tr><th>작성일</th><td>{DATE}</td></tr>
      <tr><th>기준 브랜치</th><td>Tasqra <b>main</b></td></tr>
      <tr><th>기준 커밋</th><td class="commit">{COMMIT}</td></tr>
      <tr><th>페이지 규격</th><td>A3 가로 · 흑백 무채색 · 6쪽</td></tr>
    </table>
  </div>
  <aside class="cover-side">
    <div><h2>상세 ERD 구성</h2><ol class="domain-list"><li>사용자와 프로젝트</li><li>문서와 OCR 검수</li><li>AI 분석과 제안</li><li>태스크와 산출물</li></ol></div>
    <div><h2>범례</h2><div class="legend-grid">
      <div class="legend-symbol">PK</div><div><b>PK</b> · Primary Key</div>
      <div class="legend-symbol">0..1</div><div>널 허용 · 선택 관계(0..1)</div>
      <div class="legend-symbol">N</div><div>다(多) · 1:N의 N측</div>
      <div class="legend-symbol">1</div><div>하나(1) · 1:1 또는 1:N의 1측</div>
      <div class="legend-symbol">FK</div><div>컬럼명과 관계선으로 표시</div>
    </div></div>
    <p class="legend-note">UK/UQ와 주요 CHECK는 상세 그림에 별도 기호가 없으므로 범례에 추가하지 않았다. 제약의 실행 기준은 Alembic이다.</p>
    <div class="version-stamp">Tasqra ERD · {VERSION}</div>
  </aside>
</section>

<section class="page overview-page">
  <header class="page-head"><div><span class="eyebrow">DATABASE OVERVIEW</span><h2>전체 개요 ERD</h2></div><div class="page-no">2 / 6</div></header>
  <div class="overview-wrap">{overview}</div>
</section>

{detail_html}

<script>
(() => {{
  const selected = Number(new URLSearchParams(location.search).get("page"));
  if (selected >= 1 && selected <= 6) {{
    document.querySelectorAll(".page").forEach((page, index) => {{
      page.style.display = index + 1 === selected ? "" : "none";
    }});
  }}
}})();
</script>
</body></html>"""


def main() -> None:
    ERD_DIR.mkdir(parents=True, exist_ok=True)
    output = build_html()
    HTML_PATH.write_text(output, encoding="utf-8", newline="\n")
    if not CHROME.exists():
        raise FileNotFoundError(f"Chrome not found: {CHROME}")
    command = [
        str(CHROME),
        "--headless=new",
        "--no-sandbox",
        "--disable-gpu",
        "--disable-dev-shm-usage",
        "--no-pdf-header-footer",
        "--run-all-compositor-stages-before-draw",
        f"--print-to-pdf={PDF_PATH}",
        HTML_PATH.resolve().as_uri(),
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, timeout=120)
    if result.returncode != 0 or not PDF_PATH.exists():
        raise RuntimeError(f"Chrome PDF generation failed ({result.returncode}): {result.stderr}")
    if not PDF_PATH.read_bytes().startswith(b"%PDF-"):
        raise RuntimeError("Generated file is not a PDF")
    print(f"HTML={HTML_PATH}")
    print(f"PDF={PDF_PATH}")
    print(f"PDF_BYTES={PDF_PATH.stat().st_size}")


if __name__ == "__main__":
    main()
