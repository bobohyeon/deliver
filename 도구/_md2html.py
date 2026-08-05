# -*- coding: utf-8 -*-
"""마크다운 산출물을 인쇄(PDF 저장)에 적합한 HTML로 변환한다.

브라우저에서 열어 Ctrl+P → 'PDF로 저장' 하면 표와 코드가 정리된 PDF가 나온다.
외부 라이브러리 없이 동작하도록 필요한 문법만 직접 처리한다.
지원: h1~h4 / 표 / 코드블록 / 인용 / 목록 / 굵게 / 인라인코드 / 구분선
"""
import html
import re
import sys
from pathlib import Path

CSS = """
@page { size: A4; margin: 14mm 12mm; }
* { box-sizing: border-box; }
body {
  font-family: "Malgun Gothic", "맑은 고딕", -apple-system, sans-serif;
  font-size: 10.5pt; line-height: 1.55; color: #1f2937;
  max-width: 940px; margin: 0 auto; padding: 24px;
}
h1 {
  font-size: 20pt; margin: 0 0 4px; padding-bottom: 10px;
  border-bottom: 3px solid #1e40af; color: #0f172a;
}
h2 {
  font-size: 14pt; margin: 26px 0 10px; padding: 7px 10px;
  background: #1e40af; color: #fff; border-radius: 4px;
  page-break-after: avoid;
}
h3 {
  font-size: 11.5pt; margin: 18px 0 8px; padding-left: 8px;
  border-left: 4px solid #1e40af; color: #1e3a8a;
  page-break-after: avoid;
}
h4 { font-size: 10.5pt; margin: 14px 0 6px; color: #374151; }
p { margin: 7px 0; }
table {
  width: 100%; border-collapse: collapse; margin: 10px 0 16px;
  font-size: 9.5pt; page-break-inside: avoid;
}
th, td {
  border: 1px solid #cbd5e1; padding: 6px 8px;
  text-align: left; vertical-align: top; word-break: break-word;
}
th { background: #eef2ff; color: #1e3a8a; font-weight: 600; }
tr:nth-child(even) td { background: #f8fafc; }
pre {
  background: #f5f6f8; border: 1px solid #d9dde3; border-left: 3px solid #64748b;
  border-radius: 4px; padding: 10px 12px; margin: 10px 0;
  font-family: Consolas, "D2Coding", monospace; font-size: 9pt;
  line-height: 1.45; white-space: pre-wrap; page-break-inside: avoid;
}
code {
  font-family: Consolas, "D2Coding", monospace; font-size: 9.2pt;
  background: #eef1f5; padding: 1px 4px; border-radius: 3px; color: #b91c1c;
}
pre code { background: none; padding: 0; color: inherit; }
blockquote {
  margin: 10px 0; padding: 9px 13px;
  background: #f1f5ff; border-left: 4px solid #93a9e8; border-radius: 0 4px 4px 0;
  color: #333c52;
}
blockquote p { margin: 4px 0; }
ul, ol { margin: 7px 0; padding-left: 22px; }
li { margin: 3px 0; }
hr { border: 0; border-top: 1px solid #dfe3e8; margin: 22px 0; }
strong { color: #0f172a; }
img {
  display: block; max-width: 100%; margin: 12px auto;
  border: 1px solid #cbd5e1; border-radius: 4px;
  page-break-inside: avoid;
}
figure { margin: 14px 0; page-break-inside: avoid; }
figcaption { font-size: 9pt; color: #6b7280; text-align: center; margin-top: 5px; }

/* 캡처 위에 요소 번호를 겹쳐 표시한다.
   이미지를 다시 인코딩하지 않으므로 화질 손실이 없고,
   번호는 텍스트로 그려져 PDF 에서 확대해도 깨지지 않는다. */
.shot {
  position: relative; display: block; width: fit-content;
  margin: 12px auto; page-break-inside: avoid;
}
.shot img { margin: 0; display: block; }
.pin {
  position: absolute; transform: translate(-50%, -50%);
  min-width: 16px; height: 16px; padding: 0 3px; box-sizing: border-box;
  border-radius: 999px; background: #dc2626; color: #fff;
  border: 1.4px solid #fff; box-shadow: 0 0 0 1px rgba(0, 0, 0, .3);
  font-family: Arial, Helvetica, sans-serif;
  font-size: 8pt; font-weight: 700; line-height: 13px; text-align: center;
  -webkit-print-color-adjust: exact; print-color-adjust: exact;
}
.doc-foot {
  margin-top: 30px; padding-top: 10px; border-top: 1px solid #dfe3e8;
  font-size: 8.5pt; color: #6b7280; text-align: center;
}
@media print {
  body { padding: 0; }
  h2 { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
  th, tr:nth-child(even) td { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
"""


def pinned_image(match: "re.Match") -> str:
    """번호가 달린 캡처를 만든다.

    문법:  ![설명](캡처/LIST.png){01:8,12  02:8,17}
           번호 : 가로위치% , 세로위치%    (배지의 중심 기준)

    이미지 파일 자체는 손대지 않고 번호만 위에 겹치므로 화질이 유지된다.
    """
    alt, src, spec = match.group(1), match.group(2), match.group(3)
    items = re.findall(r"(\S+?)\s*:\s*([\d.]+)\s*,\s*([\d.]+)", spec)
    tags = [
        f'<b class="pin" style="left:{x}%;top:{y}%">{html.escape(label)}</b>'
        for label, x, y in items
    ]
    return f'<span class="shot"><img src="{src}" alt="{alt}">' + "".join(tags) + "</span>"


def inline(text: str) -> str:
    """굵게 / 인라인코드 / 링크를 변환한다. 나머지는 이스케이프한다."""
    # 코드 조각을 먼저 뽑아내 보관한다 (내부 문법이 해석되지 않도록).
    slots: list[str] = []

    def keep_code(match: re.Match) -> str:
        slots.append(html.escape(match.group(1)))
        return f"\x00{len(slots) - 1}\x00"

    text = re.sub(r"`([^`]+)`", keep_code, text)
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)\{([^}]*)\}", pinned_image, text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)",
                  r'<img src="\2" alt="\1">', text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)

    for index, code in enumerate(slots):
        text = text.replace(f"\x00{index}\x00", f"<code>{code}</code>")

    return text


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def convert(md: str) -> str:
    lines = md.split("\n")
    out: list[str] = []
    index = 0
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            out.append("</ul>")
            in_list = False

    while index < len(lines):
        line = lines[index]
        stripped = line.strip()

        # --- 코드블록 ---
        if stripped.startswith("```"):
            close_list()
            index += 1
            body: list[str] = []
            while index < len(lines) and not lines[index].strip().startswith("```"):
                body.append(html.escape(lines[index]))
                index += 1
            index += 1
            out.append("<pre><code>" + "\n".join(body) + "</code></pre>")
            continue

        # --- 표 (다음 줄이 구분선인지로 판별) ---
        if (
            stripped.startswith("|")
            and index + 1 < len(lines)
            and re.fullmatch(r"\|[\s:\-|]+\|", lines[index + 1].strip())
        ):
            close_list()
            headers = split_row(stripped)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                rows.append(split_row(lines[index].strip()))
                index += 1

            out.append("<table><thead><tr>")
            out.extend(f"<th>{inline(h)}</th>" for h in headers)
            out.append("</tr></thead><tbody>")
            for row in rows:
                out.append("<tr>")
                out.extend(f"<td>{inline(c)}</td>" for c in row)
                out.append("</tr>")
            out.append("</tbody></table>")
            continue

        # --- 구분선 ---
        if re.fullmatch(r"-{3,}", stripped):
            close_list()
            out.append("<hr>")
            index += 1
            continue

        # --- 제목 ---
        heading = re.match(r"(#{1,4})\s+(.*)", stripped)
        if heading:
            close_list()
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            index += 1
            continue

        # --- 인용 (연속 줄을 하나로 묶는다) ---
        if stripped.startswith(">"):
            close_list()
            quote: list[str] = []
            while index < len(lines) and lines[index].strip().startswith(">"):
                quote.append(lines[index].strip().lstrip(">").strip())
                index += 1
            out.append("<blockquote>")
            for para in "\n".join(quote).split("\n\n"):
                if para.strip():
                    out.append(f"<p>{inline(para.strip())}</p>")
            out.append("</blockquote>")
            continue

        # --- 목록 ---
        item = re.match(r"[-*]\s+(.*)", stripped)
        if item:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(item.group(1))}</li>")
            index += 1
            continue

        # --- 빈 줄 / 본문 ---
        if not stripped:
            close_list()
        else:
            close_list()
            out.append(f"<p>{inline(stripped)}</p>")
        index += 1

    close_list()
    return "\n".join(out)


def build(md_path: Path, title: str, footer: str) -> Path:
    md = md_path.read_text(encoding="utf-8")
    body = convert(md)

    document = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
{body}
<div class="doc-foot">{html.escape(footer)}</div>
</body>
</html>
"""
    out_path = md_path.with_suffix(".html")
    out_path.write_text(document, encoding="utf-8")
    return out_path


if __name__ == "__main__":
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "화면정의서.md")
    doc_title = sys.argv[2] if len(sys.argv) > 2 else source.stem
    result = build(
        source,
        doc_title,
        "PDF Brief AI · 김보현 · 브라우저에서 Ctrl+P → 'PDF로 저장'",
    )
    print(f"생성: {result} ({result.stat().st_size:,} bytes)")
