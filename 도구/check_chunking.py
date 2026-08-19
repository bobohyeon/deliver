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


def check_preprocessing(ck) -> list[str]:
    """전처리(유니코드 정규화 · 반복 노이즈 제거)를 검사한다.

    2026-08-18 에 넣은 두 기능이다. 둘 다 눈으로는 안 보이는 방식으로 깨진다.
      · 정규화가 없으면 NFD 로 온 한글에서 제목 판정이 전부 실패한다.
      · 노이즈 제거 기본값이 느슨하면 본문까지 지운다(실제로 겪었다).
    """
    import unicodedata

    problems: list[str] = []

    def want(label: str, cond: bool, detail: str = "") -> None:
        if not cond:
            problems.append(label + (f" — {detail}" if detail else ""))

    # ── 1. 유니코드 정규화 ──────────────────────────────────────────────────
    doc = ("제 1 장 총칙\n\n이 계약은 조달청이 발주하는 사업에 적용한다.\n\n"
           "제 2 장 계약 및 대금\n\n4. 대금 지급\n\n준공 검사 완료 후 지급한다.")
    nfd = unicodedata.normalize("NFD", doc)
    want("NFD 본문이 NFC 보다 길어야 한다(시험 자체가 성립하는지)", len(nfd) > len(doc))

    nfc_units = ck.units_from_plain_text(doc)
    nfd_units = ck.units_from_plain_text(nfd)
    nfc_heads = [u.text for u in nfc_units if u.element_type == "HEADING"]
    nfd_heads = [u.text for u in nfd_units if u.element_type == "HEADING"]
    want("NFC 문서에서 제목을 찾아야 한다", len(nfc_heads) >= 3, f"{len(nfc_heads)}개")
    # 이것이 핵심이다. 정규화가 없으면 여기서 0 개가 된다.
    want("NFD 문서에서도 제목이 같아야 한다", nfd_heads == nfc_heads,
         f"NFC {nfc_heads} vs NFD {nfd_heads}")
    want("정규화한 텍스트는 NFC 여야 한다",
         all(u.text == unicodedata.normalize("NFC", u.text) for u in nfd_units))

    # 좌표는 정규화 **전** 문자열 기준이어야 한다. 아니면 원문 강조가 어긋난다.
    for unit in nfd_units:
        sliced = nfd[unit.content_start:unit.content_end]
        want(f"NFD 좌표가 원본 기준이어야 한다 (조각 {unit.content_start})",
             unicodedata.normalize("NFC", sliced) == unit.text,
             f"좌표본문 {sliced[:20]!r} vs 텍스트 {unit.text[:20]!r}")

    # ── 2. 반복 노이즈 제거 ────────────────────────────────────────────────
    boiler = "조달청 전자입찰 특별유의서에 따른다"
    docs = [f"- {n} -\n{boiler}\n제 {n} 장 개요\n\n본문 {n} 입니다. 사업 기간은 십이 개월이다."
            for n in (1, 2, 3, 4)]
    groups = [ck.units_from_plain_text(d) for d in docs]

    marked = ck.mark_repeated_as_noise(groups)
    noise = [u.text for g in marked for u in g if u.element_type == "HEADER_FOOTER"]
    want("반복 상용구를 노이즈로 잡아야 한다", boiler in noise, f"잡힌 것 {noise}")
    # 실제로 겪은 회귀다. 숫자만 다른 본문·제목이 묶여 문서가 통째로 지워졌다.
    want("본문을 노이즈로 잡으면 안 된다",
         not any("사업 기간은 십이 개월" in t for t in noise), f"잡힌 것 {noise}")
    want("제목을 노이즈로 잡으면 안 된다",
         not any("장 개요" in t for t in noise), f"잡힌 것 {noise}")

    # 문서마다 같은 제목이 나오는 경우. 조달공고는 서식이 같아서 흔하다.
    # 제목이 지워지면 청크가 어느 절에 속했는지 알 수 없게 된다.
    same_head = [f"제 1 장 총칙\n{boiler}\n본문 {w} 에 관한 내용이다." for w in ("가", "나", "다")]
    same_groups = [ck.units_from_plain_text(d) for d in same_head]
    same_noise = [u.text for g in ck.mark_repeated_as_noise(same_groups)
                  for u in g if u.element_type == "HEADER_FOOTER"]
    want("문서마다 반복되는 제목도 지우면 안 된다",
         not any("제 1 장 총칙" in t for t in same_noise), f"잡힌 것 {same_noise}")
    want("그 경우에도 상용구는 지워야 한다", boiler in same_noise, f"잡힌 것 {same_noise}")
    first = ck.chunk_units(ck.mark_repeated_as_noise(same_groups)[0],
                           counter=ck.CharRatioTokenCounter(), max_tokens=480,
                           min_tokens=ck.MIN_TOKENS, overlap_tokens=48)
    want("제목이 청크 맨 앞에 남아야 한다",
         bool(first) and first[0].text.startswith("제 1 장 총칙"),
         f"{first[0].text[:30]!r}" if first else "조각 없음")

    chunks = ck.chunk_units(marked[0], counter=ck.CharRatioTokenCounter(),
                            max_tokens=480, min_tokens=ck.MIN_TOKENS, overlap_tokens=48)
    joined = " ".join(c.text for c in chunks)
    want("노이즈를 뺀 뒤에도 청크가 남아야 한다", len(chunks) > 0)
    want("상용구가 청크에서 빠져야 한다", boiler not in joined)
    want("본문이 청크에 남아야 한다", "사업 기간은 십이 개월" in joined)

    # 기본값이 보수적인지. 누가 되돌리면 여기서 걸린다.
    want("mark_repeated_as_noise 기본값이 보수적이어야 한다",
         ck.NOISE_MIN_RATIO >= 0.8 and ck.NOISE_MAX_CHARS is not None,
         f"min_ratio={ck.NOISE_MIN_RATIO} max_chars={ck.NOISE_MAX_CHARS}")

    # 보고 함수가 지울 목록을 실제로 주는지.
    report = ck.repeated_noise_report(groups)
    want("repeated_noise_report 가 목록을 줘야 한다",
         any(boiler in sample for _k, _c, sample in report), f"{report}")
    return problems


def run(backend: Path, corpus: Path) -> int:
    chunking = load_chunking(backend)
    files = sorted(corpus.glob("*.md"))
    if not files:
        print(f"샘플 문서를 찾지 못했다: {corpus}")
        return 2

    print(f"CHARS_PER_TOKEN = {chunking.CHARS_PER_TOKEN} (chunking.py 현재 값)")
    print("=" * 78)

    max_tokens, overlap = 480, 48
    # 비교 기준. 실측 전 설정이다. 비율은 틀렸지만 조각 경계는 이것이 옳았고,
    # 그 경계에서 RAG-04 품질(정답 1위 53% / 39% / 55%)을 확인했다.
    LEGACY = (1.2, 48)
    CURRENT = (chunking.CHARS_PER_TOKEN, chunking.MIN_TOKENS)
    all_problems: list[str] = []
    checked = 0

    print(f"기준 비교 — 옛 설정 {LEGACY}  vs  지금 {CURRENT}")
    print(f"  흡수 기준: {round(LEGACY[0] * LEGACY[1])}자 미만"
          f"  vs  {round(CURRENT[0] * CURRENT[1])}자 미만")

    for path in files:
        content = path.read_text(encoding="utf-8")
        units = chunking.units_from_plain_text(content)

        print(f"\n{path.name}  ({len(content):,}자 · 줄 {len(units)}개)")
        print(f"  {'비율':>6} {'min':>4}  {'조각':>4}  {'최대글자':>8}  {'최대추정토큰':>12}  {'실토큰(1.89)':>13}")

        boundaries = {}
        for ratio, min_tokens in (LEGACY, CURRENT):
            counter = chunking.CharRatioTokenCounter(ratio)
            chunks = chunking.chunk_units(
                units,
                counter=counter,
                max_tokens=max_tokens,
                min_tokens=min_tokens,
                overlap_tokens=overlap,
            )
            checked += 1
            label = f"{path.name}@{ratio}/{min_tokens}"
            all_problems += check_invariants(chunks, content, max_tokens, label)
            boundaries[(ratio, min_tokens)] = [c.content_start for c in chunks]

            if chunks:
                widest = max(c.char_count for c in chunks)
                tokens = max(c.token_count for c in chunks)
                # 실제 토크나이저 비율(실측 1.89)로 되돌려 본 진짜 토큰 수.
                real = round(widest / 1.89)
            else:
                widest = tokens = real = 0
            print(f"  {ratio:>6} {min_tokens:>4}  {len(chunks):>4}  {widest:>8,}"
                  f"  {tokens:>12}  {real:>13,}")

        # 핵심 불변식: 조각 경계가 옛 설정과 같아야 한다.
        #
        # 왜 이걸 보는가. min_tokens 는 CHARS_PER_TOKEN 과 곱해져 "몇 자 미만을
        # 흡수하는가"로 동작한다. 그래서 비율만 고치면 흡수 정책이 조용히 넓어져
        # 짧은 절이 옆 절에 삼켜진다. 실제로 2026-08-18 에 그 회귀가 났다 —
        # "돈은 언제 받나요" 의 정답("4. 대금 지급")이 1위에서 2위로 밀렸다.
        # 조각 시작 위치가 같으면 그 회귀가 없다는 뜻이다.
        old, new = boundaries[LEGACY], boundaries[CURRENT]
        if old != new:
            all_problems.append(
                f"{path.name}: 조각 경계가 옛 설정과 다르다 — "
                f"옛 {len(old)}개 {old} vs 지금 {len(new)}개 {new}"
            )

    pre = check_preprocessing(chunking)
    checked += 1
    all_problems += pre
    print(f"\n전처리 검사 — 유니코드 정규화 · 반복 노이즈 제거"
          f"  {'통과' if not pre else f'실패 {len(pre)}건'}")

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
