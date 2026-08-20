# =============================================================================
# 이 파일의 책임: 하이브리드 검색(SRH-004)이 값을 만드는지 수치로 확인한다.
#   같은 질의를 세 방식에 던지고 **정답 조각이 몇 등에 오는지**를 나란히 놓는다.
#
#     ① 의미 검색      POST /api/search          (SRH-001)
#     ② 키워드 검색    POST /api/search/keyword  (SRH-003)
#     ③ 하이브리드     POST /api/search/hybrid   (SRH-004 · RRF)
#
#   답하려는 질문 둘
#     · **회귀** — 하이브리드가 의미 검색이 잘하던 것을 망치지 않는가
#     · **개선** — 벡터가 약한 자리(숫자·고유명사)에서 순위를 올리는가
#
#   왜 이 도구가 필요한가
#     "하이브리드가 리랭커 상한을 올린다" 를 세현님께 전달했는데, 그것은 계산이고
#     실측이 아니다. 후보 단계의 R@k 가 실제로 올라가는지는 재봐야 안다.
#     인수인계 9-G ① 실측에서 **정답 청크의 숫자값이 다른 청크에도 그대로 있는
#     질의가 26~27%** 였다. 그 구간이 벡터가 가장 약한 자리이고, 이 도구의
#     "숫자·고유명사" 사례가 바로 그것을 흉내낸다.
#
# 다른 파일과의 관계
#   도구/check_rag04_quality.py  같은 방식의 선행 도구(의미 검색 단독 회귀 검사)
#   도구/seed_rag_test.sql       이 도구가 전제하는 자료를 넣는다
#   컨테이너 안에서 돈다 — /app 을 sys.path 에 넣고 실제 SearchService 를 쓴다.
#
# ⚠ 정답을 스니펫이 아니라 chunk_id 로 판정한다
#   선행 도구는 스니펫에 특징어가 있는지로 봤는데, 스니펫은 220자(키워드는 160자)
#   로 잘리므로 **정답이 스니펫 밖에 있으면 못 찾은 것으로 오판한다.**
#   그래서 먼저 SQL 로 "그 말이 든 청크"의 id 를 구하고, 순위는 id 로 맞춘다.
#
# ⚠ 가짜 임베더로 돌리면 ①③이 무의미하다
#   벡터가 텍스트 해시라서 순서에 뜻이 없다. ②는 임베딩을 쓰지 않으므로 유효하다.
#   경고를 낸다.
#
# Spring 비교: 통합 테스트에 가깝다. 다만 단정(assert)으로 실패시키기보다
#   세 방식을 나란히 찍어 사람이 판단하게 한다 — 순위는 자료가 바뀌면 움직인다.
#
# 실행 방법 (PowerShell, Tasqra 폴더에서)
#   docker compose cp C:\dev\deliver\도구\check_hybrid_quality.py api:/tmp/h.py
#   docker compose exec api python /tmp/h.py
# =============================================================================

import sys

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from app.core.exceptions import BusinessError  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.dependencies import get_embedding_client  # noqa: E402
from app.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.repositories.project_repository import ProjectRepository  # noqa: E402
from app.schemas.search import (  # noqa: E402
    HybridSearchRequest,
    KeywordSearchRequest,
    SearchRequest,
)
from app.services.search_service import SearchService  # noqa: E402

# 몇 등까지 볼까. 리랭커가 top-10 을 받는다는 전제와 맞춘다.
LIMIT = 10

# (분류, 질의, 정답 청크를 가리키는 말)
#
# 분류가 판정 기준을 정한다.
#   semantic  의미 검색이 잘해야 하는 질의. 하이브리드가 **망치지 않아야** 한다
#   lexical   벡터가 약한 질의(숫자·고유명사). 하이브리드가 **올려야** 한다
#
# 정답을 가리키는 말은 **본문에 그대로 있는 문자열**이어야 한다. SQL 로 그 말이
# 든 청크를 찾아 정답 id 로 쓴다. 질의와 같을 필요는 없다.
CASES = [
    # --- 의미가 강한 질의 (자연어) — 회귀가 없어야 한다 -----------------------
    ("semantic", "돈은 언제 받을 수 있나요", "준공 검사 완료 후 30일"),
    ("semantic", "늦게 끝내면 무슨 불이익이 있나요", "지체상금"),
    ("semantic", "사람 인건비를 어떻게 계산했나요", "직접인건비"),
    ("semantic", "회의에서 무엇을 결정했나요", "이관 대상은 인사시스템과 회계시스템"),
    # --- 정확한 문자열 (숫자·고유명사) — 벡터가 약한 자리 --------------------
    #
    # "1천분의 1" 은 특히 좋은 사례다. 남의 프로젝트 문서에 "1천분의 2" 가 있어서
    # 숫자만 살짝 다른 조각이 존재한다 — 9-G ① 의 "숫자값 공유" 상황이다.
    # 그리고 남의 것이 나오면 프로젝트 격리가 깨진 것이라 함께 검증된다.
    ("lexical", "1천분의 1", "1천분의 1"),
    ("lexical", "263,062,800", "263,062,800"),
    ("lexical", "제12조", "제12조"),
    ("lexical", "한국소프트웨어산업협회", "한국소프트웨어산업협회"),
    ("lexical", "2026년 3월 19일", "2026년 3월 19일"),
]


def gold_chunk_ids(db, needle: str) -> set[int]:
    """그 말이 그대로 든 청크의 id. 정답 판정의 근거다."""
    rows = db.execute(
        text("SELECT id FROM document_chunks WHERE text LIKE :pat"),
        {"pat": f"%{needle}%"},
    ).scalars()
    return {int(r) for r in rows}


def rank_of(results, gold: set[int]) -> int | None:
    """정답이 몇 등인가(1부터). 없으면 None."""
    for i, item in enumerate(results, start=1):
        if item.chunk_id in gold:
            return i
    return None


def show(rank: int | None) -> str:
    return f"{rank}위" if rank else "없음"


def main() -> None:
    client = get_embedding_client()
    fake = "fake" in client.model_name.lower()

    print("=" * 78)
    print(f"임베딩 모델 = {client.model_name} · 차원 {client.dimension}")
    if fake:
        print("!! 가짜 임베더다. 의미·하이브리드의 순서에 뜻이 없다.")
        print("   키워드 결과만 유효하다. USE_FAKE_EMBEDDING=false 로 두고 다시 돌려라.")
    print("=" * 78)

    with SessionLocal() as db:
        user_id = db.execute(
            text("SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1")
        ).scalar()
        if user_id is None:
            raise SystemExit("사용자가 없다. seed_rag_test.sql 을 먼저 돌려라.")

        total = db.execute(text("SELECT count(*) FROM document_chunks")).scalar()
        if not total:
            raise SystemExit("청크가 없다. 청킹을 먼저 돌려라.")
        print(f"\n청크 {total}개")
        if total <= LIMIT:
            print(f"  ⚠ 청크가 {LIMIT}개 이하다. 의미 검색이 전부를 돌려주므로")
            print("     하이브리드가 후보를 넓히는 효과는 볼 수 없다. 순서 변화만 보인다.")

        service = SearchService(db, ChunkRepository(db), ProjectRepository(db), client)

        print("\n" + "-" * 78)
        print(f"{'분류':<9}{'질의':<26}{'의미':>7}{'키워드':>8}{'하이브리드':>11}   판정")
        print("-" * 78)

        regressed, improved, same, missing = [], [], [], []

        for kind, query, needle in CASES:
            gold = gold_chunk_ids(db, needle)
            if not gold:
                missing.append(f'"{query}" — «{needle}» 이 든 청크가 없다')
                print(f"{kind:<9}{query[:24]:<26}{'―':>7}{'―':>8}{'―':>11}   자료 없음")
                continue

            v = rank_of(
                service.search(user_id, SearchRequest(query=query, limit=LIMIT)).results,
                gold,
            )
            try:
                k = rank_of(
                    service.search_keyword(
                        user_id, KeywordSearchRequest(query=query, limit=LIMIT)
                    ).results,
                    gold,
                )
            except BusinessError:
                k = None  # 검색어가 너무 짧다 — 키워드 다리는 건너뛴다
            h = rank_of(
                service.search_hybrid(
                    user_id, HybridSearchRequest(query=query, limit=LIMIT)
                ).results,
                gold,
            )

            # 판정 — 없는 것은 최하위보다 나쁜 것으로 본다.
            worst = LIMIT + 1
            vv, hh = (v or worst), (h or worst)
            if hh < vv:
                verdict, bucket = f"개선 {vv - hh}칸 ↑", improved
            elif hh > vv:
                verdict, bucket = f"회귀 {hh - vv}칸 ↓", regressed
            else:
                verdict, bucket = "동일", same
            bucket.append(f'"{query}"  의미 {show(v)} -> 하이브리드 {show(h)}')

            print(
                f"{kind:<9}{query[:24]:<26}{show(v):>7}{show(k):>8}{show(h):>11}"
                f"   {verdict}"
            )

        print("-" * 78)
        print(f"\n개선 {len(improved)} · 동일 {len(same)} · 회귀 {len(regressed)}"
              f" · 자료없음 {len(missing)}")

        if improved:
            print("\n[개선] 하이브리드가 정답을 위로 올렸다")
            for line in improved:
                print("  + " + line)
        if regressed:
            print("\n[회귀] ⚠ 하이브리드가 정답을 아래로 내렸다 — 원인을 봐야 한다")
            for line in regressed:
                print("  - " + line)
        if missing:
            print("\n[자료없음] 사례를 자료에 맞게 고쳐야 한다")
            for line in missing:
                print("  ? " + line)

        print("\n" + "=" * 78)
        print("읽는 법")
        print("  · semantic 줄에 회귀가 있으면 RRF 가 의미 검색을 해치고 있다.")
        print("    후보 폭(SEARCH_HYBRID_CANDIDATES)이나 k(SEARCH_HYBRID_RRF_K)를 본다.")
        print("  · lexical 줄에서 '의미=없음, 키워드=1위' 면 벡터가 못 찾는 것을")
        print("    키워드가 구제한 것이다. 하이브리드가 그것을 살렸는지 본다.")
        print("  · 남의 프로젝트 문서(«남의 프로젝트»)가 어디에도 나오면 격리가 깨진 것이다.")

        # 회귀는 실패로 본다. 개선이 0이어도 실패는 아니다 — 자료가 작으면 그럴 수 있다.
        raise SystemExit(1 if regressed else 0)


if __name__ == "__main__":
    main()
