# =============================================================================
# 이 파일의 책임: 뜻이 비슷한 내용 찾기(RAG-04)의 품질이 유지되는지 확인한다.
#   사람이 실제로 칠 것 같은 질의를 넣고, 정답 조각이 1등으로 나오는지 본다.
#
#   왜 필요한가: 2026-08-18 에 CHARS_PER_TOKEN 을 1.2 -> 1.89 로 고쳐서 청크가
#   길어졌다(문서 4건 청크 16개 -> 10개). 문맥이 늘어 좋아질 것으로 보지만,
#   한 조각에 여러 주제가 섞이면 나빠질 수도 있다. 눈으로 봐야 한다.
#
#   기준값 (청크 16개 · CHARS_PER_TOKEN=1.2 · dragonkue/BGE-m3-ko 로 측정)
#     "돈은 언제 받나요"            -> 4. 대금 지급     53%
#     "늦게 끝내면 무슨 불이익"      -> 5. 지체상금     39%
#     "사람 인건비를 어떻게 계산했나" -> 1. 직접인건비   55%
#
# 다른 파일과의 관계: 도구/seed_rag_test.sql 로 넣은 자료를 전제로 한다.
#   가짜 임베더(USE_FAKE_EMBEDDING=true)로 돌리면 무의미하다 — 경고를 낸다.
#
# 실행 방법 (PowerShell, Tasqra 폴더에서)
#   docker compose cp C:\dev\deliver\도구\check_rag04_quality.py api:/tmp/q.py
#   docker compose exec api python /tmp/q.py
# =============================================================================

import sys

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.dependencies import get_embedding_client  # noqa: E402
from app.repositories.chunk_repository import ChunkRepository  # noqa: E402
from app.repositories.project_repository import ProjectRepository  # noqa: E402
from app.schemas.search import SearchRequest  # noqa: E402
from app.services.search_service import SearchService  # noqa: E402

# (질의, 정답 조각에 반드시 들어 있어야 할 말, 기준 유사도)
CASES = [
    ("돈은 언제 받나요", "대금 지급", 0.53),
    ("늦게 끝내면 무슨 불이익", "지체상금", 0.39),
    ("사람 인건비를 어떻게 계산했나", "직접인건비", 0.55),
]


def main() -> None:
    client = get_embedding_client()
    print("=" * 74)
    print(f"임베딩 모델 = {client.model_name} · 차원 {client.dimension}")
    if "fake" in client.model_name.lower():
        print("!! 가짜 임베더다. 벡터가 텍스트 해시라서 순서에 의미가 없다.")
        print("   USE_FAKE_EMBEDDING=false 로 두고 임베딩 서버를 띄운 뒤 다시 돌려라.")
    print("=" * 74)

    with SessionLocal() as db:
        user_id = db.execute(
            text("SELECT id FROM users WHERE login_id <> 'test_other' ORDER BY id LIMIT 1")
        ).scalar()
        if user_id is None:
            raise SystemExit("사용자가 없다. seed_rag_test.sql 을 먼저 돌려라.")

        rows = db.execute(
            text(
                "SELECT embedding_model, count(*), max(char_count), max(token_count) "
                "FROM document_chunks GROUP BY 1 ORDER BY 2 DESC"
            )
        ).all()
        if not rows:
            raise SystemExit("청크가 없다. build_chunks_task 를 먼저 돌려라.")
        print("\n청크 현황")
        for model, count, widest, tokens in rows:
            print(f"  {model:<24} {count:>4}개 · 최대 {widest}자 / {tokens}토큰")

        service = SearchService(
            db,
            ChunkRepository(db),
            ProjectRepository(db),
            client,
        )

        passed, failed = 0, []
        for query, needle, baseline in CASES:
            print("\n" + "-" * 74)
            print(f'질의  "{query}"')
            print(f"기대  정답 조각에 «{needle}» 이 있고, 기준 유사도 {baseline:.0%}")

            response = service.search(user_id, SearchRequest(query=query, limit=3))
            if not response.results:
                failed.append(f'"{query}" — 결과가 없다')
                print("  결과 없음")
                continue

            for rank, item in enumerate(response.results, start=1):
                mark = "<-" if needle in item.snippet else "  "
                head = item.snippet.replace("\n", " ")[:46]
                print(f"  {rank}위 {item.similarity:>6.1%}  {item.document_filename[:18]:<18} {head} {mark}")

            top = response.results[0]
            if needle not in top.snippet:
                where = next(
                    (i for i, r in enumerate(response.results, 1) if needle in r.snippet),
                    None,
                )
                failed.append(
                    f'"{query}" — 1위에 «{needle}» 이 없다'
                    + (f" ({where}위에 있다)" if where else " (3위 안에 없다)")
                )
                continue

            # 유사도는 청크가 바뀌면 조금 움직인다. 기준보다 10%p 이상 떨어질
            # 때만 문제로 본다 — 순위가 맞으면 검색은 제 일을 한 것이다.
            if top.similarity < baseline - 0.10:
                failed.append(
                    f'"{query}" — 1위는 맞지만 유사도가 {top.similarity:.1%}'
                    f" (기준 {baseline:.0%} 보다 10%p 넘게 낮다)"
                )
                continue
            passed += 1

        print("\n" + "=" * 74)
        if failed:
            print(f"  실패 {len(failed)}건 · 통과 {passed}건\n")
            for line in failed:
                print("  x " + line)
            raise SystemExit(1)
        print(f"  통과 {passed}/{len(CASES)} — 청크를 키운 뒤에도 순위가 유지된다")


if __name__ == "__main__":
    main()
