# 청킹 규칙과 토큰 추정값(CHARS_PER_TOKEN)을 실제 문서로 검증한다.
#
# 이 파일의 책임: chunking.py 를 SQLAlchemy 없이 단독으로 돌려, 청크가 규칙을
#   지키는지와 CHARS_PER_TOKEN 변경이 실제 청크 크기에 어떤 영향을 주는지 본다.
# 다른 파일과의 관계: Tasqra 의 backend/app/services/chunking.py 를 import 한다
#   (그 파일은 re 와 structure.py 만 쓰므로 DB 없이 돈다). 샘플 문서는
#   도구/embed-test/corpus 를 쓴다.
# Spring 비교: 서비스 계층을 DB 없이 검증하는 단위 테스트에 해당한다. 다만
#   pytest 가 이 환경에 없어서 assert 를 직접 세어 보고한다.
#
# 사용법:
#   python3 check_chunking.py <Tasqra/backend 경로> [--corpus <폴더>]

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _norm(text: str) -> str:
    """공백 차이를 없앤다. 청크는 줄을 "\\n" 로 잇는데 원문은 "\\n\\n" 일 수 있다."""
    return re.sub(r"\s+", " ", text).strip()


def load_chunking(backend: Path):
    sys.path.insert(0, str(backend))
    from app.services import chunking  # noqa: PLC0415

    return chunking


def check_invariants(chunks, content: str, max_tokens: int, label: str) -> list[str]:
    """청크가 지켜야 할 것들. 깨지면 사유 문자열을 돌려준다."""
    problems: list[str] = []

    for index, chunk in enumerate(chunks):
        where = f"{label} 조각{index}"
        if chunk.seq != index:
            problems.append(f"{where}: seq 가 {chunk.seq} (연속이어야 함)")
        if chunk.char_count != len(chunk.text):
            problems.append(f"{where}: char_count {chunk.char_count} != 실제 {len(chunk.text)}")
        if chunk.token_count > max_tokens:
            problems.append(f"{where}: 토큰 {chunk.token_count} > 상한 {max_tokens}")
        if not chunk.text.strip():
            problems.append(f"{where}: 빈 청크")

        start, end = chunk.content_start, chunk.content_end
        if (start is None) != (end is None):
            problems.append(f"{where}: 좌표가 한쪽만 있다 ({start}, {end})")
        elif start is not None:
            if not (0 <= start < end <= len(content)):
                problems.append(f"{where}: 좌표가 범위를 벗어난다 [{start}, {end}) 본문 {len(content)}자")

        # 좌표가 가리키는 원문과 청크가 맞는지.
        #
        # 여기서 "좌표로 자른 것이 청크의 부분문자열인가" 로 검사하면 안 된다.
        # 청크 텍스트는 [제목 + 겹침 + 본문] 이고 겹침은 좌표 앞(이전 청크)에서
        # 빌려온 것이라 좌표 구간에 없다. 그래서 제목과 본문 사이가 벌어진다.
        # 실측으로 확인한 성질 두 개로 대신 본다.
        #   · 청크의 끝은 좌표 구간의 끝과 같다 (겹침은 앞에만 붙는다)
        #   · 좌표 구간 길이는 청크 길이를 넘지 않는다 (청크가 겹침만큼 더 길다)
        if start is not None:
            sliced = _norm(content[start:end])
            tail = _norm(chunk.text)[-40:]
            if tail and tail not in sliced:
                problems.append(f"{where}: 청크의 끝이 좌표 구간 안에 없다")
            # 줄바꿈이 "\n\n" -> "\n" 로 합쳐지며 몇 자 줄 수 있어 여유를 둔다.
            if (end - start) > chunk.char_count + 8:
                problems.append(
                    f"{where}: 좌표 구간 {end - start}자가 청크 {chunk.char_count}자보다 크다"
                )

    # 좌표는 문서 순서를 따라야 한다. 겹침(overlap)이 있으므로 "증가"가 아니라
    # "감소하지 않음"으로 본다.
    located = [c for c in chunks if c.content_start is not None]
    for previous, current in zip(located, located[1:]):
        if current.content_start < previous.content_start:
            problems.append(
                f"{label}: 좌표가 거꾸로 간다 조각{previous.seq}({previous.content_start})"
                f" -> 조각{current.seq}({current.content_start})"
            )
    return problems


def run(backend: Path, corpus: Path) -> int:
    chunking = load_chunking(backend)
    files = sorted(corpus.glob("*.md"))
    if not files:
        print(f"샘플 문서를 찾지 못했다: {corpus}")
        return 2

    print(f"CHARS_PER_TOKEN = {chunking.CHARS_PER_TOKEN} (chunking.py 현재 값)")
    print("=" * 78)

    max_tokens, min_tokens, overlap = 480, 48, 48
    all_problems: list[str] = []
    checked = 0

    for path in files:
        content = path.read_text(encoding="utf-8")
        units = chunking.units_from_plain_text(content)

        print(f"\n{path.name}  ({len(content):,}자 · 줄 {len(units)}개)")
        print(f"  {'비율':>6}  {'조각':>4}  {'최대글자':>8}  {'최대추정토큰':>12}  {'실토큰(1.89기준)':>16}")

        rows = []
        for ratio in (1.2, chunking.CHARS_PER_TOKEN):
            counter = chunking.CharRatioTokenCounter(ratio)
            chunks = chunking.chunk_units(
                units,
                counter=counter,
                max_tokens=max_tokens,
                min_tokens=min_tokens,
                overlap_tokens=overlap,
            )
            checked += 1
            all_problems += check_invariants(chunks, content, max_tokens, f"{path.name}@{ratio}")

            if chunks:
                widest = max(c.char_count for c in chunks)
                tokens = max(c.token_count for c in chunks)
                # 실제 토크나이저 비율(실측 1.89)로 되돌려 본 진짜 토큰 수.
                real = round(widest / 1.89)
            else:
                widest = tokens = real = 0
            rows.append((ratio, len(chunks), widest, tokens, real))
            print(f"  {ratio:>6}  {len(chunks):>4}  {widest:>8,}  {tokens:>12}  {real:>16,}")

        # 값을 키우면 청크가 줄거나 같아야 한다 (같은 글자를 더 큰 조각에 담으므로).
        before, after = rows[0], rows[-1]
        if after[0] > before[0] and after[1] > before[1]:
            all_problems.append(
                f"{path.name}: 비율을 {before[0]} -> {after[0]} 로 키웠는데 조각이"
                f" {before[1]} -> {after[1]} 로 늘었다 (줄거나 같아야 한다)"
            )

    print("\n" + "=" * 78)
    print("  임베딩 모델 max_seq_length = 1024 (embed_server.py DEFAULT_MAX_SEQ)")
    print(f"  최대 글자 {max_tokens} x {chunking.CHARS_PER_TOKEN} ="
          f" {round(max_tokens * chunking.CHARS_PER_TOKEN):,}자")
    print(f"  글자/토큰 비가 0.9 로 최악일 때도"
          f" {round(max_tokens * chunking.CHARS_PER_TOKEN / 0.9):,} 토큰 -> 1024 안")

    print("=" * 78)
    if all_problems:
        print(f"  실패 {len(all_problems)}건 (검사 {checked}회)\n")
        for line in all_problems:
            print("  ✗ " + line)
        return 1
    print(f"  통과 — 문서 {len(files)}건 x 비율 2가지 = {checked}회, 규칙 위반 없음")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("backend", type=Path, help="Tasqra/backend 경로")
    parser.add_argument("--corpus", type=Path, default=None)
    args = parser.parse_args()
    corpus = args.corpus or Path(__file__).parent / "embed-test" / "corpus"
    return run(args.backend.resolve(), corpus.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
