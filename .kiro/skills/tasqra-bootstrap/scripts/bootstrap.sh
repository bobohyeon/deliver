#!/usr/bin/env bash
# Tasqra 세션 부트스트랩 — 두 레포를 최신화하고 현재 상태를 한 번에 찍는다.
#
# 이 파일의 책임
#     새 대화방이 맥락을 파악하는 데 드는 왕복을 없앤다. 사람이 붙여넣던 정보를
#     레포에서 직접 읽는다. **읽기 전용이다** — 커밋·푸시·브랜치 생성을 하지 않는다.
#
# 다른 파일과의 관계
#     .kiro/skills/tasqra-bootstrap/SKILL.md  이 스크립트를 언제 쓰는지 설명한다
#     도구/spec_sync.py                       기능명세서 어긋남 검사를 호출한다
#
# Spring 비교
#     `mvn -q validate` 자리다. 빌드하지 않고 전제조건과 정합성만 확인한다.
#
# 실패해도 멈추지 않는다 — 한 항목이 안 되어도 나머지 정보는 쓸모가 있다.

set -uo pipefail

ROOT="${TASQRA_ROOT:-/projects/sandbox}"
DELIVER="$ROOT/deliver"
TASQRA="$ROOT/Tasqra"
BRANCH="docs/design-artifacts-0805"

line() { printf '\n=== %s ===\n' "$1"; }

sync_repo() {  # $1=경로  $2=owner/repo
  if [ -d "$1/.git" ]; then
    git -C "$1" fetch --quiet --all 2>/dev/null && echo "  fetch 완료: $2"
  else
    echo "  클론: $2"
    git clone --quiet "https://github.com/$2.git" "$1" 2>&1 | tail -2
  fi
}

line "레포 최신화"
mkdir -p "$ROOT"
sync_repo "$DELIVER" "bobohyeon/deliver"
sync_repo "$TASQRA" "ParkSehyeon1009/Tasqra"

# ---- deliver (문서·도구. 커밋해도 되는 개인 레포) -------------------------
if [ -d "$DELIVER/.git" ]; then
  cur=$(git -C "$DELIVER" branch --show-current)
  if [ "$cur" != "$BRANCH" ]; then
    git -C "$DELIVER" checkout --quiet "$BRANCH" 2>/dev/null \
      || git -C "$DELIVER" checkout --quiet -b "$BRANCH" "origin/$BRANCH" 2>/dev/null
  fi
  git -C "$DELIVER" merge --quiet --ff-only "origin/$BRANCH" 2>/dev/null

  line "deliver — 브랜치 $(git -C "$DELIVER" branch --show-current)"
  git -C "$DELIVER" log --oneline -5
  dirty=$(git -C "$DELIVER" -c core.quotepath=false status --short)
  if [ -n "$dirty" ]; then
    printf '\n  ⚠ 커밋 안 된 변경이 있다 — 지우기 전에 커밋한다\n'
    echo "$dirty" | sed 's/^/    /'
  else
    echo "  (작업트리 깨끗)"
  fi
fi

# ---- Tasqra (제품 코드. 절대 커밋·푸시하지 않는다) -----------------------
if [ -d "$TASQRA/.git" ]; then
  git -C "$TASQRA" merge --quiet --ff-only origin/main 2>/dev/null
  line "Tasqra — 최근 머지된 PR 5개  ※ 커밋·푸시 금지"
  git -C "$TASQRA" log --merges --oneline -5
fi

line "Tasqra — 열린 PR"
gh api "repos/ParkSehyeon1009/Tasqra/pulls?state=open&per_page=10" \
  --jq '.[] | "  #\(.number)  \(.title)   [\(.head.ref)]"' 2>/dev/null \
  || echo "  (조회 실패 — gh 인증이나 네트워크를 확인한다)"

# ---- 기능명세서 정합성 ---------------------------------------------------
line "기능명세서 — xlsx(원본) 대 md(설계 근거판)"
if [ -f "$DELIVER/도구/spec_sync.py" ]; then
  ( cd "$DELIVER" && python3 도구/spec_sync.py ) | sed 's/^/  /'
  echo "  ※ 어긋나면 어느 쪽이 맞는지 Tasqra 코드로 판정한다"
else
  echo "  도구/spec_sync.py 가 없다"
fi

# ---- 임베딩 도구 (모델 없이 도는 것들) -----------------------------------
line "임베딩 도구 — 모델 없이 도는 것"
cat <<'TXT'
  diag_dataset.py   남의 JSONL 이 쓸 만한지 진단 (--ceiling 으로 R@1 이론 상한)
  convert_jsonl.py  남의 JSONL -> 우리 run_eval.py 입력 (--normalize 로 전처리 되돌림)
  check_queries.py  변환 결과가 채점 가능한지 검사
  id_queries.py     흩어진 queries* 파일이 각각 무엇인지 식별
  run_eval.py       실제 측정 — 모델 필요. 네트워크가 막혀 여기서는 못 돈다
TXT

line "다음"
cat <<'TXT'
  1. 관리/정정_이전대화방_인식오류.md 를 읽는다 (짧다. 항상 읽는다)
  2. 관리/인수인계.md 는 grep -n '^## ' 로 목차만 보고 필요한 절만 읽는다
  3. 위 출력에서 모르는 머지 PR 이 있으면 그것부터 확인한다
TXT
