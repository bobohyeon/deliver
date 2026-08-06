# -*- coding: utf-8 -*-
"""화면 캡처에서 일부를 잘라내고, 특정 영역만 선명하게 남긴 이미지를 만든다.

Pillow 를 쓸 수 없는 환경(네트워크 차단)이라 헤드리스 크롬으로 처리한다.
원본 PNG 를 base64 로 HTML 에 심고 CSS 로 자르기·흐리기·강조 테두리를 얹은 뒤
스크린샷을 찍는다. 글자는 이미 원본 픽셀에 있으므로 한글 글꼴이 필요 없다.

발표자료 C-1 시트의 그림 자리 비율이 3.68 : 2.91 = 1.2646 이므로, 잘라낼
영역을 모두 이 비율로 잡는다. 그래야 슬라이드에서 눌리거나 늘어나지 않는다.

사용:
    python3 도구/_crop_shot.py
"""

import base64
import pathlib
import struct
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SHOTS = ROOT / "산출물" / "캡처"
CHROME = "/usr/local/bin/chrome"

RATIO = 3.68 / 2.91                # C-1 그림 자리 비율
ACCENT = "#000000"                 # 강조 테두리 — 덱이 흑백이므로 검정


def load(name):
    """캡처를 읽어 (data URI, 폭, 높이) 를 준다."""
    path = SHOTS / f"{name}.png"
    if not path.exists():
        raise SystemExit(f"원본이 없다: {path}")
    raw = path.read_bytes()
    w, h = struct.unpack(">II", raw[16:24])
    return ("data:image/png;base64," + base64.b64encode(raw).decode("ascii"), w, h)


def fit(left, top, w, h, src_w, src_h):
    """(left, top, w, h) 를 RATIO 에 맞추고 원본 범위를 넘지 않게 당긴다.

    폭을 기준으로 높이를 맞춘다. 높이가 원본을 넘으면 반대로 맞춘다.
    """
    h2 = round(w / RATIO)
    if top + h2 > src_h:
        top = max(0, src_h - h2)
    if h2 > src_h:
        h2 = src_h
        w = round(h2 * RATIO)
    if left + w > src_w:
        left = max(0, src_w - w)
    return (left, top, w, h2)


def _html(src, crop, holes=(), blur=0.0, veil=0.0, gray=False, ring=3,
          pad_bg="#FFFFFF"):
    """holes = [(left, top, w, h)] 선명하게 남길 영역. crop 과 같은 좌표계."""
    uri, sw, sh = src
    cl, ct, cw, ch = crop
    g = "grayscale(1) " if gray else ""
    base_filter = f"filter:{g}blur({blur}px);" if (blur or gray) else ""
    hole_filter = f"filter:{g.strip()};" if gray else ""

    hole_html = ""
    for hl, ht, hw, hh in holes:
        hole_html += f"""
    <div class="hole" style="left:{hl - cl}px;top:{ht - ct}px;width:{hw}px;height:{hh}px">
      <img src="{uri}" style="left:{-hl}px;top:{-ht}px;{hole_filter}">
    </div>"""

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  html,body {{ margin:0; padding:0; background:{pad_bg}; }}
  .wrap {{ position:relative; width:{cw}px; height:{ch}px; overflow:hidden;
           background:{pad_bg}; }}
  .wrap > img.base {{ position:absolute; left:{-cl}px; top:{-ct}px;
           width:{sw}px; height:{sh}px; {base_filter} }}
  .veil {{ position:absolute; inset:0; background:rgba(255,255,255,{veil}); }}
  .hole {{ position:absolute; overflow:hidden; border-radius:8px;
           box-shadow:0 0 0 {ring}px {ACCENT}, 0 6px 18px rgba(0,0,0,.28); }}
  .hole > img {{ position:absolute; width:{sw}px; height:{sh}px; }}
</style></head><body>
  <div class="wrap">
    <img class="base" src="{uri}">
    <div class="veil"></div>{hole_html}
  </div>
</body></html>"""


def shoot(name, html, w, h, scale=2):
    """scale 2 로 찍으면 CSS 로 그린 테두리·둥근 모서리가 선명해진다."""
    tmp = pathlib.Path("/tmp") / f"_shot_{abs(hash(name))}.html"
    tmp.write_text(html, encoding="utf-8")
    dest = SHOTS / f"{name}.png"
    cmd = [
        CHROME, "--headless", "--no-sandbox", "--disable-gpu",
        "--hide-scrollbars", "--default-background-color=00000000",
        f"--force-device-scale-factor={scale}",
        f"--screenshot={dest}", f"--window-size={w},{h}",
        f"file://{tmp}",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not dest.exists():
        print(r.stderr[-800:], file=sys.stderr)
        raise SystemExit(f"실패: {name}")
    err = abs(w / h - RATIO) / RATIO * 100
    print(f"  {name:26} {w * scale}x{h * scale}  비율오차 {err:.2f}%  "
          f"{dest.stat().st_size:,}B")


def make(name, src, crop, holes, blur=2.2, veil=0.52, gray=False, ring=3):
    left, top, w, h = fit(*crop, src[1], src[2])
    shoot(name, _html(src, (left, top, w, h), holes, blur=blur, veil=veil,
                      gray=gray, ring=ring), w, h)


# ─────────────────────────────────────────────────────────────
# 문서 상세 화면 (DTL.png) — 요약 다운로드 · 삭제 버튼
# ─────────────────────────────────────────────────────────────
def detail():
    src = load("DTL")
    both = (1018, 152, 200, 58)          # 두 버튼을 함께 감싼다
    dl = (1021, 155, 119, 52)            # 요약 다운로드
    rm = (1147, 155, 68, 52)             # 삭제

    print("문서 상세 (DTL.png)")
    make("버튼강조_C1_넓게", src, (668, 76, 632, 500), [both], blur=2.4, veil=0.52)
    make("버튼강조_C1", src, (888, 76, 448, 354), [both], blur=2.0, veil=0.50)
    make("버튼강조_C1_흑백", src, (888, 76, 448, 354), [both],
         blur=2.0, veil=0.50, gray=True)
    # 표 자리에 쓰는 것들 — 비율을 맞추지 않고 원본 그대로 자른다
    shoot("버튼강조_상세화면",
          _html(src, (112, 96, 1136, 332), [both], blur=2.6, veil=0.55),
          1136, 332, scale=1)
    shoot("버튼강조_확대",
          _html(src, (1000, 137, 232, 88), [dl, rm], ring=2), 232, 88)
    shoot("분석이력표", _html(src, (150, 1132, 1056, 226)), 1056, 226, scale=1)


# ─────────────────────────────────────────────────────────────
# 문서 목록 화면 (LIST.png)
# ─────────────────────────────────────────────────────────────
# 강조 대상 좌표 (LIST.png 1336x1091 기준)
CAT_COL = (408, 340, 90, 638)            # 카테고리 열 — 머리글 + 배지 8개
SEARCH_IN = (60, 247, 988, 52)           # 검색 입력창
CAT_SEL = (1054, 247, 162, 52)           # 전체 카테고리 드롭다운
SEARCH_BT = (1220, 247, 70, 52)          # 검색 버튼
UPLOAD_BT = (1159, 174, 141, 44)         # 새 문서 업로드 버튼


def listing():
    src = load("LIST")
    print("문서 목록 (LIST.png)")

    # 1. 카테고리 배지 전체 — 세로로 긴 대상이라 파일명 열까지 함께 잡는다
    make("목록강조_카테고리열", src, (48, 330, 830, 0), [CAT_COL])

    # 2. 검색창 — 대상이 가로로 길어 크게 잡을 수밖에 없다
    make("목록강조_검색창", src, (38, 0, 1024, 0), [SEARCH_IN])

    # 3~5. 오른쪽 조작부 — 세 장을 같은 구도로 잡아 나란히 놓아도 어울리게
    right = (830, 130, 506, 0)
    make("목록강조_카테고리선택", src, right, [CAT_SEL])
    make("목록강조_검색버튼", src, right, [SEARCH_BT])
    make("목록강조_업로드버튼", src, right, [UPLOAD_BT])

    # 참고용 — 다섯 곳을 한 장에
    make("목록강조_전체", src, (0, 20, 1336, 0),
         [CAT_COL, SEARCH_IN, CAT_SEL, SEARCH_BT, UPLOAD_BT],
         blur=2.6, veil=0.55, ring=2)


def main():
    detail()
    print()
    listing()


if __name__ == "__main__":
    main()
