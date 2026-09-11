"""세현님 원본 PNG 의 좌상단 번호만 새 발표 순서로 바꿔 교체용_PNG 에 저장한다.

① 이 파일의 책임
   - 원본 PNG 를 다시 만들지 않는다. **번호 글자 영역만 배경으로 덮고 새 번호를 그린다.**
   - 21번 슬라이드처럼 발표자가 바뀐 장은 `발표 ○○○` 표기도 함께 바꾼다.
   - 렌더 뒤 원본과 번호 글자의 위치·크기를 비교해 **어긋나면 실패로 끝낸다.**

② 다른 파일과의 관계
   - 입력 : `산출물/최종발표/세현님_원본_PNG/*.png` (사람이 받은 원본, 수정하지 않는다)
   - 출력 : `산출물/최종발표/전체본/교체용_PNG/slide-NN.png`
   - 폰트 : `산출물/포트폴리오/NotoSansKR.ttf` — 원본과 같은 글꼴이라야 티가 안 난다
   - `build_final_presentation_29.py` 는 내가 만드는 장(1~19·21·22)만 담당한다.
     **20번과 23~31번은 이 스크립트가 담당한다.** 두 곳이 같은 번호를 만들지 않는다.

   배경을 덮는 방법이 핵심이다. 배경색을 코드에 적지 않고 **같은 이미지의 빈 영역을
   잘라 붙인다**(`clipPath` + 같은 `<image>` 를 x 로 밀기). 그래서 배경이 단색이 아니거나
   원본 색을 몰라도 정확히 맞는다.

   **번호의 기준선과 글자 크기가 원본마다 다르다.** 실제로 `22_모델학습과정` 하나만
   4px 아래에 있었고 `29`·`30` 은 글자가 2px 크다. 그래서 파일마다 값을 따로 둔다.
   눈으로 보고 고치지 말고 `--verify` 결과로 맞춘다.

③ Spring 비교
   원본을 두고 필요한 부분만 덮어쓰는 구조라 `@ControllerAdvice` 가 응답 본문을 통째로
   다시 만들지 않고 특정 필드만 가공해 내보내는 것과 같다. 검증 단계는 변환 후
   `assertThat(actual).isEqualTo(expected)` 를 붙여 둔 통합테스트에 해당한다.
"""

from __future__ import annotations

import argparse
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "산출물/최종발표/세현님_원본_PNG"
OUT = ROOT / "산출물/최종발표/전체본/교체용_PNG"
FONT = ROOT / "산출물/포트폴리오/NotoSansKR.ttf"
CHROME = "/opt/playwright/chromium-1232/chrome-linux64/chrome"

NUM_COLOR = "#315BD8"      # 원본 번호 글자색
PRESENTER_COLOR = "#64748B"  # 원본 하단 발표자 글자색

# (원본 파일명, 새 번호, 번호 기준선 y, 번호 글자 크기, 발표자 교체값)
#
# y·size 는 원본을 픽셀로 재서 넣은 값이다. 기본은 60·17 이고 아래 둘만 다르다.
#   · 22_모델학습과정  : 번호가 4px 아래에 있다        -> y 64
#
# 처음에 `29_`·`30_` 도 글자가 크다고 봤는데 **측정 범위를 x 115 까지 잡아 슬래시가
# 섞인 탓**이었다. 숫자 자리만(x < 108) 재면 나머지와 같다. `--verify` 가 이걸 잡았다.
JOBS = [
    ("27_검색모델학습_신규.png",        20, 60, 17, "김보현"),
    ("28_재정렬모델학습_신규.png",      23, 60, 17, None),
    ("26_검색학습시행착오_신규.png",    24, 60, 17, None),
    ("21_실제모델평가_수정.png",        25, 60, 17, None),
    ("22_모델학습과정_수정.png",        26, 64, 17, None),
    ("23_적은데이터학습_신규.png",      27, 60, 17, None),
    ("24_교차검증_신규.png",            28, 60, 17, None),
    ("25_요약정확도측정_신규.png",      29, 60, 17, None),
    ("29_정보항목찾기_번호만변경.png",  30, 60, 17, None),
    ("30_긴문서오류해결_번호만변경.png", 31, 60, 17, None),
]


def _head_rows(path: Path, rows: int = 90) -> tuple[int, int, list[bytes]]:
    """PNG 위쪽 몇 줄만 풀어 픽셀로 돌려준다. 번호 글자만 보면 되므로 전체를 풀지 않는다."""
    data = path.read_bytes()
    pos, idat, width, ctype = 8, b"", None, None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        kind = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, _height, _depth, ctype = struct.unpack(">IIBB", chunk[:10])
        elif kind == b"IDAT":
            idat += chunk
            if len(idat) > 400_000:
                break
        pos += 12 + length
    bpp = {0: 1, 2: 3, 6: 4}[ctype]
    stride = width * bpp
    raw = zlib.decompressobj().decompress(idat, (stride + 1) * rows + 64)
    out: list[bytes] = []
    prev = bytearray(stride)
    i = 0
    for _y in range(rows):
        if i + 1 + stride > len(raw):
            break
        filt = raw[i]
        i += 1
        line = bytearray(raw[i:i + stride])
        i += stride
        if filt == 1:
            for x in range(bpp, stride):
                line[x] = (line[x] + line[x - bpp]) & 255
        elif filt == 2:
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif filt == 3:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif filt == 4:
            for x in range(stride):
                a = line[x - bpp] if x >= bpp else 0
                b = prev[x]
                c = prev[x - bpp] if x >= bpp else 0
                pred = a + b - c
                pa, pb, pc = abs(pred - a), abs(pred - b), abs(pred - c)
                near = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[x] = (line[x] + near) & 255
        out.append(bytes(line))
        prev = line
    return width, bpp, out


def number_bbox(path: Path) -> tuple[int, int, int, int] | None:
    """좌상단 번호 글자의 위·아래·좌·우 픽셀 범위. 파란 글자만 골라낸다."""
    _w, bpp, rows = _head_rows(path)
    ys: list[int] = []
    xs: list[int] = []
    for y, line in enumerate(rows):
        for x in range(70, 108):  # 슬래시를 빼고 숫자 자리만 본다
            r, g, b = line[x * bpp], line[x * bpp + 1], line[x * bpp + 2]
            if b > 120 and b - r > 50 and r < 150:
                ys.append(y)
                xs.append(x)
    if not ys:
        return None
    return min(ys), max(ys), min(xs), max(xs)


def build_svg(png: Path, work: Path, no: int, y: int, size: int, presenter: str | None) -> Path:
    """원본을 깔고, 번호 자리를 같은 이미지의 빈 배경으로 덮은 뒤 새 번호를 그린다."""
    cover_top = y - 24
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        ' width="1920" height="1080" viewBox="0 0 1920 1080">',
        '<defs><style>@font-face{font-family:NotoKR;src:url("font.ttf") format("truetype");}',
        ' text{font-family:NotoKR,Arial,sans-serif;}</style>',
        f'<clipPath id="cNo"><rect x="74" y="{cover_top}" width="34" height="34"/></clipPath>',
    ]
    if presenter:
        parts.append('<clipPath id="cPr"><rect x="74" y="1032" width="215" height="34"/></clipPath>')
    parts.append("</defs>")
    parts.append(f'<image xlink:href="{png.name}" x="0" y="0" width="1920" height="1080"/>')
    # x 를 -520 밀면 같은 줄의 글자 없는 배경이 번호 자리에 온다.
    parts.append(f'<g clip-path="url(#cNo)"><image xlink:href="{png.name}" x="-520" y="0" width="1920" height="1080"/></g>')
    if presenter:
        parts.append(f'<g clip-path="url(#cPr)"><image xlink:href="{png.name}" x="-520" y="0" width="1920" height="1080"/></g>')
    parts.append(
        f'<text x="80" y="{y}" font-size="{size}" font-weight="800" fill="{NUM_COLOR}" letter-spacing="2">{no}</text>'
    )
    if presenter:
        parts.append(
            f'<text x="80" y="1050" font-size="14" font-weight="700" fill="{PRESENTER_COLOR}"'
            f' letter-spacing="1">발표  {presenter}</text>'
        )
    parts.append("</svg>")
    svg = work / f"job-{no}.svg"
    svg.write_text("".join(parts), encoding="utf-8")
    return svg


def main() -> int:
    ap = argparse.ArgumentParser(description="세현님 원본 PNG 번호 교체")
    ap.add_argument("--chrome", default=CHROME)
    ap.add_argument("--only", type=int, nargs="*", help="새 번호만 골라 처리")
    args = ap.parse_args()

    if not FONT.exists():
        print(f"폰트가 없다: {FONT}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)

    jobs = [j for j in JOBS if not args.only or j[1] in args.only]
    failed: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        shutil.copyfile(FONT, work / "font.ttf")
        for name, no, y, size, presenter in jobs:
            src = SRC / name
            if not src.exists():
                print(f"원본이 없다: {name}", file=sys.stderr)
                failed.append(name)
                continue
            local = work / f"src-{no}.png"
            shutil.copyfile(src, local)
            svg = build_svg(local, work, no, y, size, presenter)
            dst = OUT / f"slide-{no}.png"
            subprocess.run(
                [args.chrome, "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                 "--force-device-scale-factor=1", "--window-size=1920,1080",
                 f"--screenshot={dst}", f"file://{svg}"],
                capture_output=True, check=False,
            )
            if not dst.exists():
                print(f"렌더 실패: slide-{no}.png", file=sys.stderr)
                failed.append(name)
                continue

            # 검증 — 원본과 번호 글자의 위치·크기가 같아야 한다.
            before, after = number_bbox(src), number_bbox(dst)
            if not before or not after:
                print(f"slide-{no}: 번호를 찾지 못했다", file=sys.stderr)
                failed.append(name)
                continue
            dy_top, dy_bot = after[0] - before[0], after[1] - before[1]
            ok = abs(dy_top) <= 1 and abs(dy_bot) <= 1
            mark = "OK " if ok else "어긋남"
            print(f"{mark} slide-{no:>2}.png  {name:<32} y {before[0]}~{before[1]} -> {after[0]}~{after[1]}")
            if not ok:
                failed.append(name)

    if failed:
        print(f"\n{len(failed)}개가 어긋났다. JOBS 의 y·size 를 고쳐 다시 돌린다.", file=sys.stderr)
        return 1
    print(f"\n{len(jobs)}개 완료 · 번호 위치가 원본과 일치한다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
