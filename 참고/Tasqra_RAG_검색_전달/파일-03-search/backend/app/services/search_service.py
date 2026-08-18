# =============================================================================
# 이 파일의 책임: 의미 검색(RAG-04)을 조립한다. 질의를 벡터로 만들고, 프로젝트
#   범위 안에서 가까운 청크를 찾고, 결과마다 출처와 원문 인용을 붙인다(RAG-08).
#   자르는 규칙도 임베딩 방법도 모른다 — 그 둘은 주입받은 것에 맡긴다.
# 다른 파일과의 관계:
#   - embedding/protocol.py — 질의를 벡터로 만드는 계약. 구현체가 가짜인지
#     실제인지 이 파일은 모른다.
#   - repositories/chunk_repository.py — 벡터 검색. project_id 와
#     embedding_model 조건이 거기 들어 있다.
#   - schemas/search.py — 응답 모양.
#   - api/routes/search_router.py 가 이 서비스를 부른다. 권한 검사는 라우터가
#     Depends(get_project_access) 로 이미 끝낸 상태로 들어온다.
# Spring 비교: @Service 클래스다. 읽기만 하므로 @Transactional(readOnly = true)
#   에 해당한다. 다만 SET LOCAL 을 쓰기 때문에 트랜잭션 안이어야 한다.
# =============================================================================

from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.config import settings
from app.embedding.protocol import EmbeddingClientProtocol
from app.repositories.chunk_repository import ChunkRepository
from app.schemas.search import SearchRequest, SearchResponse, SearchResultItem

logger = logging.getLogger(__name__)


class SearchService:
    def __init__(
        self,
        db: Session,
        chunk_repository: ChunkRepository,
        embedding_client: EmbeddingClientProtocol,
    ) -> None:
        self._db = db
        self._chunks = chunk_repository
        self._embedder = embedding_client

    def search(self, project_id: int, request: SearchRequest) -> SearchResponse:
        started = time.perf_counter()

        # 질의 임베딩은 문서 임베딩과 따로 부른다. BGE-M3 계열은 양쪽이 같지만
        # E5 계열은 질의에 "query: " 접두어를 붙여야 한다. 그 차이를 서비스가
        # 알지 않도록 embed_query 로 분리해 뒀다.
        embedded = self._embedder.embed_query(request.query.strip())
        if not embedded.vectors:
            # 구현체가 빈 결과를 주는 경우. 방어적으로 막는다.
            logger.warning("질의 임베딩이 비어 있다 project_id=%s", project_id)
            return SearchResponse(
                query=request.query,
                embedding_model=embedded.model,
                took_ms=int((time.perf_counter() - started) * 1000),
                total=0,
                results=[],
            )

        rows = self._chunks.search_by_vector(
            project_id=project_id,
            vector=list(embedded.vectors[0]),
            # 지금 쓰는 모델로 만든 청크만 본다. 이 조건이 없으면 옛 모델이나
            # 가짜 임베더로 만든 청크가 섞여, 서로 다른 벡터 공간의 거리를
            # 에러 없이 계산해 버린다.
            embedding_model=embedded.model,
            limit=request.limit,
            document_id=request.document_id,
            ef_search=settings.SEARCH_EF_SEARCH,
        )

        results: list[SearchResultItem] = []
        for chunk, filename, distance in rows:
            # pgvector 의 <=> 는 코사인 거리(0~2)다. 사람이 읽기 쉬운 유사도로
            # 바꾼다. 정규화된 벡터에서 거리 0 = 유사도 1 이다.
            similarity = 1.0 - distance
            if request.min_similarity is not None and similarity < request.min_similarity:
                # 거리 오름차순이므로 여기부터는 전부 임계값 아래다.
                break
            results.append(
                SearchResultItem(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_filename=filename,
                    seq=chunk.seq,
                    page_number=chunk.page_number,
                    similarity=round(similarity, 6),
                    snippet=self._snippet(chunk.text),
                    char_count=chunk.char_count,
                    content_start=chunk.content_start,
                    content_end=chunk.content_end,
                )
            )

        took_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "의미 검색 project_id=%s 결과=%d 모델=%s %dms",
            project_id,
            len(results),
            embedded.model,
            took_ms,
        )
        return SearchResponse(
            query=request.query,
            embedding_model=embedded.model,
            took_ms=took_ms,
            total=len(results),
            results=results,
        )

    def explain(self, project_id: int, request: SearchRequest) -> str:
        """검색 실행계획을 돌려준다. 리비전 0014 검증용이다."""
        embedded = self._embedder.embed_query(request.query.strip())
        if not embedded.vectors:
            return "질의 임베딩이 비어 있어 계획을 낼 수 없다."
        return self._chunks.explain_search(
            project_id=project_id,
            vector=list(embedded.vectors[0]),
            embedding_model=embedded.model,
            limit=request.limit,
            ef_search=settings.SEARCH_EF_SEARCH,
        )

    # --- 내부 ---------------------------------------------------------------

    @staticmethod
    def _snippet(text: str) -> str:
        """원문 인용을 만든다 (RAG-08).

        청크는 최대 480토큰이라 그대로 담으면 목록 응답이 커진다. 앞부분을 잘라
        담고, 잘렸는지는 프론트가 char_count 와 비교해 판단한다.

        의미 검색은 질의 글자가 본문에 없어도 걸리는 것이 목적이라(RAG-04),
        키워드 하이라이트처럼 "질의가 나온 자리"를 잡을 수 없다. 그래서 앞부분을
        준다. 청크 맨 앞에는 제목이 오게 청킹해 뒀으므로(chunking.py 의 겹침
        처리) 앞부분이 그 청크의 주제를 가장 잘 나타낸다.
        """
        limit = settings.SEARCH_SNIPPET_CHARS
        # 줄바꿈을 공백으로 눌러 한 줄로 만든다. 프론트에서 목록으로 보여주므로
        # 원문 줄바꿈을 유지하면 카드 높이가 들쭉날쭉해진다.
        flat = " ".join(text.split())
        if len(flat) <= limit:
            return flat
        cut = flat[:limit]
        # 단어 중간에서 끊기지 않게 마지막 공백까지 되돌린다. 한국어는 공백이
        # 적어 되돌릴 자리가 없을 수 있으니, 너무 많이 깎이면 그대로 둔다.
        space = cut.rfind(" ")
        if space > limit * 0.7:
            cut = cut[:space]
        return cut + "…"
