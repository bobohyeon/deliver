# =============================================================================
# 이 파일의 책임: 폴더에 흩어진 queries 계열 파일이 각각 무엇인지 식별한다.
#   (1) 행 수·열 이름·kind 분포·정답 번호 범위를 한 표로 낸다
#   (2) 내용 해시로 같은 파일끼리 묶는다. 이름만 다른 사본을 찾아낸다
#   (3) 우리 평가셋인지 KoViDoRe 같은 외부 벤치마크인지 구분한다.
#       둘을 섞으면 정답 개수가 달라 지표 정의가 어긋난다(3.4배 사고의 원인)
#   아무것도 고치지 않는다. 읽기만 한다.
# 다른 파일과의 관계: check_queries.py 는 한 파일이 채점 가능한지 보고, 이 파일은
#   여러 파일 중 어느 것을 써야 하는지 고른다. 그 앞 단계다.
#   run_eval.py 가 읽는 열 이름(query·gold_chunk_ids·kind)을 기준으로 판정한다.
# Spring 비교: 여러 프로파일 설정 파일이 섞였을 때 무엇이 실제로 적용되는지
#   확인하는 자리다. application-*.yml 이 여러 개일 때 어느 것이 로드되는지
#   먼저 확인하지 않고 값을 고치면 엉뚱한 파일을 고치게 된다.
#
# 왜 필요한가
#   작업 폴더에 queries.csv · queries_13.csv · queries_백업_73행.csv ·
#   queries_kovidore.csv · queries_ours.bak 이 함께 있었다. 커밋된 것은
#   queries.csv(73행) 하나뿐이라 나머지는 원격에서 보이지 않는다.
#   어느 것이 5차 측정(133건)에 쓴 것인지 이름만으로는 알 수 없다.
#   추측으로 커밋하면 기준선이 더 헝클어진다.
#
# 사용법
#   python id_queries.py                # 이 스크립트가 있는 폴더를 훑는다
#   python id_queries.py --dir .        # 폴더 지정
# =============================================================================

from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent

# run_eval.py 가 요구하는 열. 이게 다 있으면 우리 형식이다.
OURS_COLS = {"query", "gold_chunk_ids", "kind"}


def sniff(path: pathlib.Path) -> dict:
    raw = path.read_bytes()
    info = {
        "name": path.name,
        "bytes": len(raw),
        "sha": hashlib.sha256(raw).hexdigest()[:10],
        "lines": raw.count(b"\n") + (0 if raw.endswith(b"\n") or not raw else 1),
        "bom": raw.startswith(b"\xef\xbb\xbf"),
    }
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        info["error"] = "UTF-8 로 못 읽는다 (cp949 일 수 있다)"
        return info

    try:
        rows = list(csv.DictReader(text.splitlines()))
    except csv.Error as e:
        info["error"] = f"CSV 파싱 실패: {e}"
        return info

    info["rows"] = len(rows)
    info["cols"] = list(rows[0].keys()) if rows else []
    info["ours"] = OURS_COLS.issubset(set(info["cols"]))

    if not info["ours"]:
        return info

    kinds = collections.Counter((r.get("kind") or "").strip() for r in rows)
    info["kinds"] = dict(kinds)

    gold_max, gold_pairs, no_gold = 0, 0, 0
    for r in rows:
        parts = [p for p in (r.get("gold_chunk_ids") or "").replace(" ", "").split(",") if p]
        ids = [int(p) for p in parts if p.lstrip("-").isdigit()]
        if not ids:
            no_gold += 1
        gold_pairs += len(ids)
        gold_max = max([gold_max] + ids)
    info["gold_max"] = gold_max
    info["gold_pairs"] = gold_pairs
    info["no_gold"] = no_gold
    # run_eval.py 는 note 에 '예시' 가 있으면 조용히 건너뛴다
    info["skip_example"] = sum(1 for r in rows if "예시" in (r.get("note") or ""))
    return info


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="queries 계열 파일이 각각 무엇인지 식별한다 (읽기만 한다)")
    ap.add_argument("--dir", default=str(ROOT), help="훑을 폴더")
    args = ap.parse_args(argv)

    d = pathlib.Path(args.dir).expanduser()
    if not d.is_dir():
        print(f"폴더가 아니다: {d}", file=sys.stderr)
        return 2

    targets = sorted(
        p for p in d.iterdir()
        if p.is_file() and p.name.lower().startswith("quer")
        and p.suffix.lower() in {".csv", ".bak", ".txt", ""}
    )
    if not targets:
        print(f"queries 계열 파일이 없다: {d}")
        return 0

    print(f"폴더: {d}")
    print(f"찾은 파일 {len(targets)}개\n")

    infos = [sniff(p) for p in targets]

    for i in infos:
        print("-" * 70)
        print(f"{i['name']}")
        print(f"  줄 {i['lines']}  ·  {i['bytes']:,} bytes  ·  sha {i['sha']}"
              f"  ·  BOM {'있음' if i['bom'] else '없음'}")
        if "error" in i:
            print(f"  [!] {i['error']}")
            continue
        print(f"  데이터 행 {i.get('rows', 0)}개  ·  열 {i.get('cols')}")
        if not i.get("ours"):
            miss = OURS_COLS - set(i.get("cols", []))
            print(f"  [!] 우리 형식이 아니다. 없는 열: {sorted(miss)}")
            print("      run_eval.py 로 채점할 수 없다."
                  " 외부 벤치마크(KoViDoRe 등)일 수 있다.")
            continue
        ks = i.get("kinds", {})
        print(f"  kind: " + " · ".join(f"{k or '(빈칸)'} {v}" for k, v in ks.items()))
        print(f"  정답 짝 {i['gold_pairs']}개  ·  가장 큰 청크 번호 {i['gold_max']}")
        if i["no_gold"]:
            print(f"  [!] 정답이 없는 행 {i['no_gold']}개 — run_eval.py 가 건너뛴다")
        if i["skip_example"]:
            print(f"  [!] note 에 '예시' 가 든 행 {i['skip_example']}개"
                  " — run_eval.py 가 조용히 건너뛴다")
        # 5차 측정 기준선과 맞는지 본다
        n = i.get("rows", 0)
        ov = ks.get("overlap", 0)
        no = ks.get("no_overlap", 0)
        if n == 133 and ov == 69 and no == 64:
            print("  ==> 5차 측정 기준선과 일치한다 (133 = 겹침 69 · 안겹침 64)")
        elif n == 73 and ov == 39 and no == 34:
            print("  ==> 커밋된 판과 일치한다 (73 = 겹침 39 · 안겹침 34)")
        elif n == 133 or n == 73:
            print(f"  ==> 행 수는 {n} 인데 kind 분포가 기록과 다르다"
                  f" (겹침 {ov} · 안겹침 {no})")

    # 같은 내용인 파일 묶기
    print("-" * 70)
    groups = collections.defaultdict(list)
    for i in infos:
        groups[i["sha"]].append(i["name"])
    dups = {s: ns for s, ns in groups.items() if len(ns) > 1}
    if dups:
        print("내용이 완전히 같은 파일")
        for s, ns in dups.items():
            print(f"  sha {s}: {' = '.join(ns)}")
    else:
        print("내용이 완전히 같은 파일은 없다. 모두 서로 다르다.")

    ours = [i for i in infos if i.get("ours")]
    print()
    print("판단에 쓸 요약")
    print(f"  {'파일':32} {'행':>5} {'겹침':>5} {'안겹침':>6} {'정답짝':>6} {'최대번호':>7}")
    for i in ours:
        ks = i.get("kinds", {})
        print(f"  {i['name'][:32]:32} {i.get('rows',0):5d}"
              f" {ks.get('overlap',0):5d} {ks.get('no_overlap',0):6d}"
              f" {i['gold_pairs']:6d} {i['gold_max']:7d}")
    print()
    print("고르는 법 — 5차 표(안겹침 64 · 겹침 69 · 전체 133)와 맞는 파일이")
    print("기준선이다. 그 파일의 '가장 큰 청크 번호' 가 649 이하인지도 본다.")
    print("649 를 넘으면 그 평가셋은 649청크 코퍼스용이 아니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
