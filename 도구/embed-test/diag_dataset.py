# =============================================================================
# 이 파일의 책임: 남이 만든 JSONL 데이터셋이 임베딩 학습·평가에 쓸 수 있는
#   상태인지 진단한다. 모델을 내려받기 전에, 파일을 눈으로 훑기 전에 돌린다.
#   (1) 질의 필드가 있는지 전수로 확인한다 — 첫 줄만 보면 놓친다. 학습셋에
#       (질의, 정답) 쌍이 없으면 대조학습이 성립하지 않는데, 라이브러리가
#       조용히 건너뛰면 "학습은 됐는데 점수가 그대로" 로 보인다
#   (2) 질의 후보 필드가 문서 단위인지 청크 단위인지 판정한다. 문서 단위면
#       한 질의에 정답이 여러 개가 되어 점수가 구조적으로 낮게 나온다
#   (3) 전처리 흔적을 센다 — 숫자 사이 줄바꿈, ' / ' 치환, en dash, NFD
#   (4) 길이 분포와 512토큰 초과 개수를 낸다. 초과분은 조용히 잘린다
#   (5) 두 파일의 source 집합을 비교해 무엇이 걸러졌는지 보여준다
# 다른 파일과의 관계: check_queries.py 가 우리 queries.csv 를 검증하는 것과
#   같은 자리다. 다만 이쪽은 우리 형식이 아닌 외부 JSONL 을 받는다.
#   make_chunks.py 의 청킹 규칙과 비교할 수 있게 길이 통계를 같은 단위(자)로 낸다.
#   json·unicodedata 표준 라이브러리만 쓴다. numpy·torch 가 필요 없다.
# Spring 비교: 외부 시스템에서 받은 배치 입력을 적재 전에 검증하는 계층이다.
#   Spring Batch 의 ItemProcessor 앞에 Validator 를 두어 깨진 레코드를
#   적재 전에 걸러내고 건수를 리포트하는 것과 같다. 학습을 돌린 뒤에
#   "왜 안 오르지" 를 묻는 대신, 돌리기 전에 입력을 못 믿을 이유를 찾는다.
#
# 왜 필요한가
#   임베딩 정확도가 오르지 않을 때 원인은 셋 중 하나다 — 모델, 학습 설정,
#   데이터. 앞의 둘은 확인에 GPU 시간이 들지만 데이터는 몇 초면 된다.
#   그리고 실제로 데이터가 원인인 경우가 많다. 우리도 165c93d 에서
#   "세 모델이 다 틀렸는데 원인이 평가셋" 이었다.
#
# 사용법
#   python diag_dataset.py si_train/corpus.jsonl si_train/si_train.jsonl
#   python diag_dataset.py worksheet/*.jsonl
#   python diag_dataset.py --compare si_train/corpus.jsonl si_train/si_train.jsonl
# =============================================================================

from __future__ import annotations

import argparse
import collections
import json
import pathlib
import re
import sys
import unicodedata

# 우리 기준선에서 실측한 값이다 — 한국어 조달 문서에서 문자 수 / 토큰 수 = 1.89.
# 세현님 쪽 토크나이저가 다르면 어긋나므로 어림값으로만 쓴다.
CHARS_PER_TOKEN = 1.89
TOKEN_LIMIT = 512

# 질의 역할을 할 수 있는 필드 이름들. 대조학습 라이브러리들이 쓰는 관례다.
QUERY_KEYS = (
    "query", "question", "anchor", "summary", "title",
    "positive", "negative", "pos", "neg",
)
# 본문 역할을 하는 필드 이름들.
TEXT_KEYS = ("text", "body", "content", "passage", "chunk")


def _pct(sorted_vals, p):
    """정렬된 리스트에서 백분위수를 뽑는다. numpy 없이 쓰려고 직접 만들었다."""
    if not sorted_vals:
        return 0
    k = (len(sorted_vals) - 1) * (p / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def load(path):
    """JSONL 을 읽는다. 깨진 줄은 버리지 않고 세어서 보고한다."""
    rows, broken = [], []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                broken.append((i, str(e)[:60]))
    return rows, broken


def report_keys(rows):
    """키를 전수로 센다. 첫 줄에만 있는 필드, 일부 줄에만 있는 필드를 드러낸다."""
    counter = collections.Counter()
    for r in rows:
        for k in r.keys():
            counter[k] += 1
    n = len(rows)
    print(f"  키 (전수 {n}행 기준)")
    for k, c in counter.most_common():
        mark = "" if c == n else f"  <-- {n - c}행에 없다"
        print(f"    {k:12s} {c:6d}행 ({c / n * 100:5.1f}%){mark}")

    # 값이 비어 있는 필드는 있으나 마나다. heading="" 이 대표적이다.
    empties = []
    for k in counter:
        empty = sum(1 for r in rows if not str(r.get(k, "")).strip())
        if empty:
            empties.append((k, empty))
    if empties:
        print("  빈 값이 있는 필드")
        for k, empty in sorted(empties, key=lambda x: -x[1]):
            flag = "  <-- 사실상 없는 필드다" if empty == n else ""
            print(f"    {k:12s} {empty:6d}행이 빈 값 ({empty / n * 100:5.1f}%){flag}")
    return counter


def report_query_fields(rows, keys_present):
    """질의 필드가 있는지, 있으면 어느 단위인지 판정한다. 이게 이 도구의 핵심이다."""
    found = [k for k in QUERY_KEYS if k in keys_present]
    text_field = next((k for k in TEXT_KEYS if k in keys_present), None)

    if not found:
        print("  [!] 질의 후보 필드가 하나도 없다"
              f" (찾은 이름: {', '.join(QUERY_KEYS)})")
        print("      -> 지도학습 대조학습(질의,정답 쌍)은 이 파일로 불가능하다.")
        print("         비지도 방식이었거나, 학습 스크립트가 조용히 건너뛴 것이다.")
        return

    for k in found:
        vals = [str(r.get(k, "")).strip() for r in rows]
        vals = [v for v in vals if v]
        uniq = len(set(vals))
        cov = len(vals) / len(rows) if rows else 0
        print(f"  질의 후보 '{k}': 값 있는 행 {len(vals)}/{len(rows)}"
              f" ({cov * 100:.1f}%) · 서로 다른 값 {uniq}")
        # 필드가 있느냐보다 몇 행에 채워졌느냐가 중요하다. 학습에 쓸 수 있는
        # 쌍의 수가 곧 이 숫자다. 나머지 행은 코퍼스이거나 배치 내 오답이다.
        # 필드 존재만 보고 넘어가면 쌍이 27% 뿐인 것을 놓친다. 실제로 놓쳤다.
        if cov < 0.9:
            print(f"    [!] 학습·평가에 쓸 수 있는 쌍은 {len(vals)}개뿐이다."
                  f" 나머지 {len(rows) - len(vals)}행에는 질의가 없다.")
            if len(vals) < 1000:
                print(f"        쌍 {len(vals)}개는 파인튜닝에 적은 편이다."
                      " 명시적 오답(hard negative)까지 없으면 신호가 더 약해진다.")

        # 단위 판정 — 서로 다른 질의 수를 서로 다른 doc 수 / source 수와 견준다.
        if "doc" in keys_present:
            docs = len(set(str(r.get("doc", "")) for r in rows))
            per_doc = uniq / docs if docs else 0
            print(f"    서로 다른 doc {docs}개 -> doc 당 '{k}' {per_doc:.2f}개")
            if per_doc <= 1.2:
                print(f"    [!] '{k}' 는 문서 단위로 보인다.")
                print(f"        한 질의의 정답 청크가 평균 {len(rows) / docs:.1f}개다."
                      " 정답이 모호해 점수가 구조적으로 낮게 나온다.")
                print("        모델을 바꿔도 이 점수는 안 오른다. 평가셋 구조 문제다.")
            else:
                print(f"    '{k}' 는 청크 단위에 가깝다.")
                print("        다만 요약이 본문 어휘를 그대로 쓰면 점수가 과대평가된다.")

        # 질의가 본문과 같으면 그건 질의가 아니다.
        if text_field:
            same = sum(1 for r in rows
                       if str(r.get(k, "")).strip()
                       and str(r.get(k, "")).strip() == str(r.get(text_field, "")).strip())
            if same:
                print(f"    [!] '{k}' 가 '{text_field}' 와 완전히 같은 행 {same}개."
                      " 그 행은 학습 신호가 없다.")


def report_lengths(rows, keys_present):
    """길이 분포와 512토큰 초과를 낸다. 초과분은 경고 없이 잘려 나간다."""
    field = next((k for k in TEXT_KEYS if k in keys_present), None)
    if not field:
        print("  본문 필드를 찾지 못해 길이 분석을 건너뛴다.")
        return
    lens = sorted(len(str(r.get(field, ""))) for r in rows)
    if not lens:
        return
    over = sum(1 for L in lens if L / CHARS_PER_TOKEN > TOKEN_LIMIT)
    tiny = sum(1 for L in lens if L < 50)
    print(f"  '{field}' 길이(자): 최소 {lens[0]} · p50 {_pct(lens, 50):.0f}"
          f" · p90 {_pct(lens, 90):.0f} · p99 {_pct(lens, 99):.0f} · 최대 {lens[-1]}")
    print(f"    평균 {sum(lens) / len(lens):.0f}자"
          f" (어림 {sum(lens) / len(lens) / CHARS_PER_TOKEN:.0f}토큰,"
          f" 1토큰={CHARS_PER_TOKEN}자 가정)")
    if over:
        print(f"    [!] {TOKEN_LIMIT}토큰 초과 추정 {over}행 ({over / len(lens) * 100:.1f}%)"
              " -> 뒤가 잘린다. 잘린 부분에 정답이 있으면 절대 못 맞힌다.")
    else:
        print(f"    {TOKEN_LIMIT}토큰 초과 0행. 잘림 걱정은 없다.")
    if tiny:
        print(f"    50자 미만 {tiny}행. 너무 짧은 청크는 검색 노이즈가 된다.")


def report_preprocess(rows, keys_present):
    """전처리 흔적을 센다. 조달 문서에서 공고번호가 쪼개지는 것이 특히 해롭다."""
    field = next((k for k in TEXT_KEYS if k in keys_present), None)
    if not field:
        return
    texts = [str(r.get(field, "")) for r in rows]

    checks = [
        # 숫자 사이에 하이픈·en dash·쉼표가 끼는 경우까지 잡아야 한다.
        # '제\n2026\n–403호' 가 실제로 나온 형태다. 대시를 허용하지 않으면 놓친다.
        ("숫자 사이 줄바꿈", re.compile(r"\d\s*\n\s*[\-\u2013\u2014\u2212,.]?\s*\d"),
         "공고번호·금액이 쪼개졌다. 의미검색·키워드검색 둘 다 해롭다"),
        ("'제' 뒤 줄바꿈", re.compile(r"제\s*\n"),
         "'제 2026-403호' 같은 식별자가 끊겼다"),
        ("' / ' 치환 흔적", re.compile(r"\S\s/\s\S"),
         "줄바꿈이 슬래시로 바뀐 자리다. 문장이 끊겨 읽힌다"),
        ("en dash U+2013", re.compile("\u2013"),
         "하이픈이 아니다. '2026-403' 검색에 안 걸린다"),
        ("em dash U+2014", re.compile("\u2014"), "위와 같다"),
        ("연속 공백 2칸 이상", re.compile(r"\S {2,}\S"),
         "표를 텍스트로 옮긴 흔적이다"),
        ("전각 공백 U+3000", re.compile("\u3000"), "정규화하지 않으면 토큰이 갈린다"),
    ]
    print("  전처리 흔적 (해당 행 수 / 전체)")
    n = len(texts)
    for name, pat, why in checks:
        hit = sum(1 for t in texts if pat.search(t))
        if hit:
            print(f"    [!] {name:20s} {hit:5d}/{n} ({hit / n * 100:5.1f}%)  {why}")
        else:
            print(f"        {name:20s} {hit:5d}/{n}")

    # 유니코드 정규화 — NFD 로 들어오면 한글 자모가 분리되어 부분일치가 전부 깨진다.
    nfd = sum(1 for t in texts if not unicodedata.is_normalized("NFC", t))
    if nfd:
        print(f"    [!] NFC 정규화 안 된 행 {nfd}/{n}"
              " -> 한글 자모가 분리돼 있다. 제목 인식·부분일치가 전부 깨진다")
    else:
        print(f"        NFC 정규화             {nfd:5d}/{n}")

    # 줄바꿈이 과하면 청킹이 원문 줄 구조를 그대로 물고 온 것이다.
    nl = [t.count("\n") for t in texts]
    if nl:
        print(f"        본문 줄바꿈 평균 {sum(nl) / len(nl):.1f}개 · 최대 {max(nl)}개")


def report_source_format(rows):
    """source 형식을 본다. 우리 정수 청크번호와 호환되는지 판단하는 근거다."""
    srcs = [str(r.get("source", "")) for r in rows if r.get("source")]
    if not srcs:
        print("  source 필드가 없다.")
        return set()
    suffix = re.compile(r"#c(\d+)$")
    with_suffix = [s for s in srcs if suffix.search(s)]
    print(f"  source: {len(srcs)}개 · 서로 다른 값 {len(set(srcs))}개")
    if len(set(srcs)) != len(srcs):
        dup = len(srcs) - len(set(srcs))
        print(f"    [!] 중복 source {dup}개. 정답 지정이 모호해진다.")
    if with_suffix:
        print(f"    '#c<번호>' 형식 {len(with_suffix)}개"
              f" (예: ...{with_suffix[0][-12:]})")
        print("    -> 우리 queries.csv 의 gold_chunk_ids 는 정수 청크번호다."
              " 청킹 기준도 다르므로 평가셋 상호 이식은 불가하다.")
    return set(srcs)


def diagnose(path):
    print("=" * 74)
    print(f"파일: {path}")
    print("=" * 74)
    rows, broken = load(path)
    if not rows:
        print("  읽은 행이 0이다.")
        return set()
    print(f"  행 수: {len(rows)}")
    if broken:
        print(f"  [!] JSON 파싱 실패 {len(broken)}줄 (첫 줄 {broken[0][0]}: {broken[0][1]})")
    keys = report_keys(rows)
    print()
    report_query_fields(rows, keys)
    print()
    report_lengths(rows, keys)
    print()
    report_preprocess(rows, keys)
    print()
    srcs = report_source_format(rows)
    print()
    return srcs


def compare(path_a, path_b):
    """두 파일의 source 집합을 견준다. 코퍼스에서 무엇이 걸러졌는지 보는 용도다."""
    print("=" * 74)
    print(f"비교: {path_a}  ->  {path_b}")
    print("=" * 74)
    rows_a, _ = load(path_a)
    rows_b, _ = load(path_b)
    a = set(str(r.get("source", "")) for r in rows_a)
    b = set(str(r.get("source", "")) for r in rows_b)
    only_a, only_b = a - b, b - a
    print(f"  행: {len(rows_a)} -> {len(rows_b)}  (차이 {len(rows_b) - len(rows_a)})")
    print(f"  앞에만 있는 source {len(only_a)}개 · 뒤에만 있는 source {len(only_b)}개")

    if only_a:
        print(f"\n  걸러진 {len(only_a)}개의 정체 — 앞 파일에서 본문을 찾아 본다")
        by_src = {str(r.get("source", "")): r for r in rows_a}
        field = next((k for k in TEXT_KEYS if k in rows_a[0]), "text")
        lens = sorted(len(str(by_src[s].get(field, ""))) for s in only_a)
        print(f"    걸러진 것들의 길이(자): 최소 {lens[0]} · 중앙 {_pct(lens, 50):.0f}"
              f" · 최대 {lens[-1]}")
        kept = sorted(len(str(r.get(field, ""))) for r in rows_b)
        if kept:
            print(f"    남은 것들의 길이(자):   최소 {kept[0]} · 중앙 {_pct(kept, 50):.0f}"
                  f" · 최대 {kept[-1]}")
        # 고정 임계값으로 판정하면 두 분포가 걸치는 구간에서 결론이 안 나온다.
        # 걸러진 길이를 남은 길이와 직접 견주는 것이 맞다.
        if kept:
            if lens[-1] < kept[0]:
                print(f"    -> 걸러진 것이 모두 남은 것보다 짧다"
                      f" (경계 {lens[-1]}자 / {kept[0]}자)."
                      " 길이 하한으로 자른 규칙이다. 합리적이다.")
            elif _pct(lens, 50) < _pct(kept, 10):
                print("    -> 대체로 짧은 것이 걸러졌지만 예외가 섞였다."
                      " 길이 외의 규칙도 함께 걸렸다.")
            else:
                print("    -> 길이 기준이 아니다. 다른 규칙이다."
                      " 정답 청크가 지워졌는지 확인이 필요하다.")
        # 길이가 아니면 무엇인가. 가장 흔한 후보는 중복 제거다.
        # 조달 문서의 청렴서약·담합금지·공동수급 조항은 문서마다 글자까지 같다.
        # 걸러진 본문이 남은 쪽에 그대로 있으면 중복 제거로 설명된다.
        def norm(t):
            return re.sub(r"\s+", " ", str(t)).strip()

        kept_norm = collections.Counter(norm(r.get(field, "")) for r in rows_b)
        redundant = sum(1 for s in only_a if kept_norm.get(norm(by_src[s].get(field, ""))))
        if redundant:
            print(f"\n    걸러진 {len(only_a)}개 중 {redundant}개는 남은 쪽에"
                  " 같은 본문이 그대로 있다 -> 중복 제거로 설명된다.")
            if redundant == len(only_a):
                print("      전부 그렇다. 정답 청크가 사라진 것이 아니라"
                      " 같은 내용이 한 벌로 합쳐졌다. 해롭지 않다.")
        else:
            print(f"\n    걸러진 {len(only_a)}개는 남은 쪽에 같은 본문이 없다"
                  " -> 중복 제거가 아니다. 내용이 실제로 빠졌다.")

        # 몇 개 문서에서 빠졌는지 본다. 한 문서에 몰리면 그 문서만 손상된 것이다.
        drop_docs = collections.Counter(str(by_src[s].get("doc", "?")) for s in only_a)
        print(f"    걸러진 것이 속한 문서 {len(drop_docs)}개"
              f" (전체 {len(set(str(r.get('doc','?')) for r in rows_a))}개 중)")
        if len(drop_docs) <= 3:
            print("      [!] 소수 문서에 몰려 있다. 그 문서만 다르게 처리됐다.")
            for d, c in drop_docs.most_common():
                print(f"        {c:3d}개  {d[:56]}")

        print(f"\n    걸러진 source 예시 (최대 5개)")
        for s in sorted(only_a)[:5]:
            body = str(by_src[s].get(field, "")).replace("\n", "\\n")[:60]
            print(f"      {s[-40:]}  len={len(str(by_src[s].get(field, '')))}  {body}")

    # 키 차이도 본다 — heading 이 빠지는 식의 변화가 흔하다.
    ka = set().union(*(r.keys() for r in rows_a))
    kb = set().union(*(r.keys() for r in rows_b))
    if ka - kb:
        print(f"\n  뒤 파일에서 사라진 키: {', '.join(sorted(ka - kb))}")
    if kb - ka:
        print(f"  뒤 파일에서 생긴 키:   {', '.join(sorted(kb - ka))}")
    print()


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="외부 JSONL 데이터셋이 임베딩 학습·평가에 쓸 수 있는지 진단한다.")
    # --compare 만 단독으로 쓸 수 있어야 한다. 그래서 nargs="*" 다.
    ap.add_argument("files", nargs="*", help="진단할 .jsonl 경로")
    ap.add_argument("--compare", nargs=2, metavar=("A", "B"),
                    help="두 파일의 source 집합을 비교한다 (무엇이 걸러졌는지)")
    args = ap.parse_args(argv)

    if not args.files and not args.compare:
        ap.error("진단할 파일이나 --compare 중 하나는 있어야 한다")

    missing = [f for f in args.files if not pathlib.Path(f).exists()]
    if missing:
        print(f"없는 파일: {', '.join(missing)}", file=sys.stderr)
        return 2

    for f in args.files:
        diagnose(f)
    if args.compare:
        for p in args.compare:
            if not pathlib.Path(p).exists():
                print(f"없는 파일: {p}", file=sys.stderr)
                return 2
        compare(args.compare[0], args.compare[1])

    print("=" * 74)
    print("읽는 법 — [!] 표시만 보면 된다. 없으면 그 항목은 정상이다.")
    print("  1. '쓸 수 있는 쌍은 N개뿐이다' -> 학습·평가 규모가 이 N 이다.")
    print("     필드가 있는지가 아니라 몇 행에 채워졌는지가 실제 규모다.")
    print("  2. \"문서 단위로 보인다\" -> 정답이 모호해 모델을 바꿔도 안 오른다.")
    print("  3. '512토큰 초과' -> 잘린 자리에 정답이 있으면 절대 못 맞힌다.")
    print("  4. '길이 기준이 아니다' -> 무엇을 걸렀는지 확인해야 한다.")
    print("  점수를 다른 사람과 견줄 때는 반드시 같은 평가셋·같은 지표 정의로")
    print("  맞춘 뒤에 비교한다. 평가셋이 다르면 숫자는 비교 대상이 아니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
