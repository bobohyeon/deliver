# git 명령어 모음 — PowerShell 기준

Kiro 가 샌드박스에서 작업하고 푸시하면, **내 PC 에는 자동으로 오지 않는다.**
받아야 한다. 그 명령어와 자주 겪는 문제를 모아 둔다.

| | 로컬 경로 | 작업 브랜치 | 내가 커밋·푸시 |
|---|---|---|---|
| `deliver` (문서·도구) | `C:\dev\deliver` | `docs/design-artifacts-0805` | Kiro 도 하고 나도 한다 |
| `Tasqra` (제품 코드) | `C:\dev\Tesqra\Tasqra` | 기능별 브랜치 | **나만 한다** |

> PowerShell 은 **`cd` 가 실패해도 다음 줄을 그냥 실행한다.** 그래서 아래 예시는
> 디렉터리를 옮긴 뒤 항상 `git branch --show-current` 로 위치를 확인한다.
> 브랜치 이름이 안 찍히면 그 자리에서 멈춘다.

---

## 1. Kiro 가 푸시한 것을 받기 — 가장 자주 쓴다

```powershell
cd C:\dev\deliver
git branch --show-current          # docs/design-artifacts-0805 가 찍혀야 한다
git pull
```

`git pull` 은 `fetch`(원격 상태 가져오기) + `merge`(내 브랜치에 합치기) 를 한 번에
한다. 아무것도 안 바뀌었으면 `Already up to date.` 가 나온다.

### 받기 전에 무엇이 올 지 먼저 보고 싶으면

```powershell
cd C:\dev\deliver
git fetch
git log --oneline HEAD..origin/docs/design-artifacts-0805
```

`HEAD..origin/...` 은 *"내게 없고 원격에만 있는 커밋"* 이다. 목록이 비면 받을 게
없다. 파일 단위로 보려면 —

```powershell
git diff --stat HEAD..origin/docs/design-artifacts-0805
```

### 내 로컬에 안 커밋한 변경이 있는데 pull 하면?

같은 파일을 건드렸으면 git 이 거부한다. 세 가지 중 하나를 고른다.

```powershell
# ① 내 변경을 먼저 커밋한다 (권장)
git add .
git commit -m "내 작업 설명"
git pull

# ② 잠시 치워 두고 받은 뒤 다시 꺼낸다
git stash
git pull
git stash pop

# ③ 내 변경을 버린다 — 되돌릴 수 없다. 확실할 때만
git checkout -- .
git pull
```

---

## 2. 내가 커밋하고 푸시하기

```powershell
cd C:\dev\deliver
git branch --show-current

git status                         # 무엇이 바뀌었나
git add 산출물/기능명세서_v5_세분화.xlsx    # 파일을 지정하는 편이 안전하다
git commit -m "기능명세서 v5 — DSH-001·SRH-002-3 상태 갱신"
git push
```

- `git add .` 는 **폴더 전체**를 담는다. 실수로 올릴 게 섞이기 쉬워서 파일을
  지정하는 편이 낫다
- 커밋 메시지는 `-m "..."` 로 한 줄. 여러 줄이면 `-m` 을 여러 번 쓴다
- **`deliver` 는 public 이다.** 팀원이 준 자료·조달 원본 문서를 올리지 않는다

### 방금 커밋한 메시지를 고치고 싶으면 (푸시 전에만)

```powershell
git commit --amend -m "고친 메시지"
```

**푸시한 뒤에는 하지 않는다.** 이력이 갈라져서 다음 `pull` 이 꼬인다.

### 올린 것을 확인

```powershell
git log --oneline -5
git status                         # "nothing to commit, working tree clean"
```

---

## 3. Tasqra — 코드 올리기

Kiro 는 이 레포에 **직접 푸시하지 않는다.** 변경 파일과 명령어를 받아 내가 한다.

```powershell
cd C:\dev\Tesqra\Tasqra
git branch --show-current          # main 이 찍혀야 한다

git pull                           # 남의 작업을 먼저 받는다
git checkout -b fix/open-tasks-comment    # 새 브랜치를 판다
```

패치 파일을 받았다면 —

```powershell
git apply --check C:\dev\deliver\참고\Tasqra_RAG_검색_전달\15-open-tasks-comment-fix.patch
```

`--check` 는 **실제로 고치지 않고 붙는지만** 본다. 아무 출력이 없으면 성공이다.
그 다음 `--check` 를 떼고 한 번 더 돌린다.

```powershell
git apply C:\dev\deliver\참고\Tasqra_RAG_검색_전달\15-open-tasks-comment-fix.patch
git status
git diff                           # 무엇이 바뀌었는지 눈으로 확인
```

올린다.

```powershell
git add backend/app/main.py backend/app/schemas/dashboard.py backend/app/services/dashboard_service.py frontend/src/api/dashboard.js
git commit -m "docs: 열린 태스크를 못 세는 이유 정정 — decisions 가 아니라 tasks 테이블이 없다"
git push -u origin fix/open-tasks-comment
```

`-u origin <브랜치>` 는 **새 브랜치를 처음 올릴 때** 붙인다. 다음부터는 `git push`
만 하면 된다.

### 패치가 안 붙으면

```
error: patch failed: ... 
error: ... : patch does not apply
```

그 사이 누가 같은 파일을 고쳤다는 뜻이다. **억지로 밀지 않는다.** `git pull` 로
최신을 받은 뒤 Kiro 에게 그 상태로 패치를 다시 만들어 달라고 한다.

---

## 4. PR (Pull Request) 만들기

GitHub 웹에서 만드는 게 가장 쉽다 — 푸시하면 콘솔에 URL 이 찍힌다.

명령줄로 하려면 `gh` (GitHub CLI) 가 필요하다.

```powershell
gh auth status                     # 로그인돼 있나
gh auth login                      # 안 되어 있으면
```

만들기 —

```powershell
cd C:\dev\Tesqra\Tasqra
gh pr create --base main --head fix/open-tasks-comment --title "docs: 열린 태스크 주석 정정" --body "decisions 가 아니라 tasks 테이블이 없어서 못 센다는 것으로 4개 파일의 주석을 바로잡습니다. 로직 변경은 없습니다."
```

- `--base` 는 **합칠 대상**(보통 `main`), `--head` 는 **내 브랜치**
- `--body` 에 왜 이 변경이 필요한지 쓴다. 리뷰어가 코드를 안 봐도 알게
- `--draft` 를 붙이면 초안으로 올라간다(아직 리뷰받을 준비가 안 됐을 때)

보기·확인 —

```powershell
gh pr list                         # 열린 PR 목록
gh pr view 38                      # 38번 내용
gh pr view --web                   # 브라우저로 열기
gh pr checks                       # CI 통과했나
```

---

## 5. 자주 겪는 문제

### `fatal: not a git repository`

git 레포가 아닌 폴더에 있다. `cd` 가 실패했을 가능성이 높다.

```powershell
pwd                                # 지금 어디인가
cd C:\dev\deliver
git branch --show-current
```

### `Your branch is behind ... and can be fast-forwarded`

받을 게 있다는 뜻. `git pull` 하면 된다.

### `Your branch and 'origin/...' have diverged`

내 커밋과 원격 커밋이 갈라졌다. **`--force` 를 쓰지 않는다.** 상태를 먼저 본다.

```powershell
git log --oneline --graph --all -10
```

그리고 Kiro 에게 이 출력을 보여주고 물어본다. 잘못 풀면 남의 커밋이 사라진다.

### 브랜치를 잘못 만들었다

```powershell
git checkout main                  # 다른 브랜치로 옮긴 뒤
git branch -d 잘못만든브랜치         # 지운다 (커밋이 남아 있으면 거부한다)
```

### 지금 상태를 한눈에 보고 싶다

```powershell
git status                         # 안 커밋한 변경
git log --oneline -10              # 최근 커밋
git branch -a                      # 브랜치 전부 (원격 포함)
git remote -v                      # 원격 주소
```

---

## 6. 한글 파일명이 8진수로 보일 때

```
"\354\202\260\354\266\234\353\254\274/..."
```

git 기본 설정 때문이다. 한 번만 끄면 된다.

```powershell
git config --global core.quotepath false
```

이 레포는 폴더명이 전부 한글이라 켜 두면 파일명을 읽을 수 없다.
