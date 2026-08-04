# Docker 설치 가이드 (Windows 기준)

> 목표: 내일(7/31) 오전에 팀원 3명 전원 `docker compose up` 가능 상태.
> Mac 사용자는 §5 참고.

---

## 1. 설치 순서 (Windows)

### ① 사전 확인 — 가상화 활성 여부 (여기서 대부분 막힘)

```
작업 관리자(Ctrl+Shift+Esc) → 성능 → CPU
→ 우측 하단 "가상화: 사용" 확인
```

- **"사용 안 함"이면 BIOS 진입 필요.** 재부팅 → BIOS(보통 F2/F10/DEL) → `Intel VT-x` 또는 `AMD-V` / `SVM Mode` 활성화 → 저장 후 재부팅
- 이 단계를 건너뛰면 Docker Desktop이 설치는 되고 **실행만 실패**해서 원인 찾느라 시간 낭비함

### ② WSL2 설치

관리자 권한 PowerShell에서:

```powershell
wsl --install
```

재부팅 후:

```powershell
wsl --update
wsl --set-default-version 2
wsl --status          # 기본 버전이 2인지 확인
```

### ③ Docker Desktop 설치

1. 공식 사이트에서 Docker Desktop for Windows 다운로드
2. 설치 시 **"Use WSL 2 instead of Hyper-V"** 체크 (기본 체크됨)
3. 설치 후 **재부팅**
4. Docker Desktop 실행 → 트레이의 고래 아이콘이 안정되면 준비 완료

### ④ 검증 (이 3개가 다 통과해야 완료)

```bash
docker --version
docker compose version      # 공백! (v2)
docker run hello-world
```

`hello-world`가 메시지를 출력하면 정상.

---

## 2. 주의사항

| # | 항목 | 내용 |
|---|---|---|
| 1 | **가상화 미활성** | 가장 흔한 실패 원인. §1-① 먼저 확인 |
| 2 | **관리자 권한** | 학원/회사 PC는 설치 권한이 없을 수 있음. 미리 확인 |
| 3 | **디스크 공간** | 최소 **15~20GB** 여유 확보. 이미지가 생각보다 큼 |
| 4 | **명령어 버전** | `docker compose`(공백, v2) ✅ / `docker-compose`(하이픈, v1) ❌ 구버전 |
| 5 | **VirtualBox 충돌** | 구버전 VirtualBox와 WSL2가 충돌할 수 있음. 있으면 최신으로 업데이트 |
| 6 | **WSL 메모리 과점유** | Docker가 램을 계속 먹으면 `C:\Users\{계정}\.wslconfig` 생성 후 아래 설정 |
| 7 | **줄바꿈(CRLF)** | Windows에서 만든 스크립트가 컨테이너(Linux)에서 깨짐 → §4 |
| 8 | **라이선스** | 개인/교육/소규모는 무료. 우리 프로젝트는 무료 범위 |
| 9 | **포트 충돌** | 로컬에 PostgreSQL이 이미 있으면 5432 충돌 → 포트 변경 |

`.wslconfig` 예시 (램 16GB 기준):

```ini
[wsl2]
memory=6GB
processors=4
```

---

## 3. ⚠️ 가장 중요한 원칙 — Docker에 프로젝트를 걸지 마

**팀원 중 한 명이라도 Docker 설치에 실패하면 D1이 통째로 날아갈 수 있어.** 그래서:

> **Docker 없이도 개발이 되는 상태를 반드시 병행해서 유지한다.**

```
방법 A (기본)  : docker compose up        → 환경 통일, 배포 준비
방법 B (폴백)  : 로컬 venv + uvicorn      → Docker 문제 시 즉시 우회
```

`.env`의 DB 접속 주소만 바꾸면 둘 다 동작하게 설계:

```
# Docker 사용 시
DATABASE_URL=postgresql://user:pass@db:5432/pdfbrief     # 호스트명 = 서비스명 "db"

# 로컬 실행 시
DATABASE_URL=postgresql://user:pass@localhost:5432/pdfbrief
```

**Docker 설치는 D1 오전에 각자 미리 끝내고, 안 되는 사람은 방법 B로 개발 시작.** 오후 킥오프 시간을 설치 지원에 쓰면 안 됨.

---

## 4. Git 줄바꿈 설정 (팀 전체 필수)

리포지토리 루트에 `.gitattributes`:

```
* text=auto eol=lf
*.sh text eol=lf
*.bat text eol=crlf
```

Windows에서 만든 파일이 컨테이너에서 `$'\r': command not found` 에러를 내는 걸 예방함.

---

## 5. Mac 사용자

```
1. Docker Desktop for Mac 다운로드 (Apple Silicon / Intel 버전 구분!)
2. 설치 → 실행
3. docker run hello-world 로 검증
```

주의: Apple Silicon(M1~)에서는 이미지 아키텍처 문제가 생길 수 있음. 문제 시 `platform: linux/amd64` 명시.

---

## 6. docker-compose.yml — D1에 만들 파일

### 이게 뭔가

**여러 개의 컨테이너를 YAML 파일 하나로 정의하고 한 번에 띄우는 도구.**

우리 프로젝트는 최소 2개가 필요해:
- PostgreSQL 컨테이너
- FastAPI 컨테이너

이걸 각자 손으로 설치하면 3명의 환경이 다 달라져서 "내 컴에선 되는데" 문제가 생김.
`docker compose up` 한 줄로 **3명이 완전히 동일한 DB 버전·포트·계정**을 쓰게 됨.

### 파일 (프로젝트 루트)

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build: ./backend
    env_file: .env
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app          # 코드 수정이 즉시 반영 (개발용)
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

volumes:
  pgdata:
```

`backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 (PyMuPDF 등에 필요)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 자주 쓰는 명령

```bash
docker compose up -d          # 백그라운드 실행
docker compose logs -f api    # api 로그 실시간
docker compose ps             # 상태 확인
docker compose down           # 중지 + 컨테이너 삭제 (데이터는 volume에 남음)
docker compose down -v        # ⚠️ volume까지 삭제 = DB 데이터 전부 날아감
docker compose up --build     # Dockerfile 수정 후 재빌드
docker compose exec db psql -U postgres -d pdfbrief   # DB 접속
```

### 핵심 포인트 3개

1. **컨테이너 간 통신은 서비스명이 호스트명**
   `api`에서 DB에 붙을 때 `localhost`가 아니라 **`db`** 를 씀. 이거 몰라서 헤매는 경우가 많음.
2. **`volumes: - ./backend:/app`** 덕분에 코드 수정 시 재빌드 불필요 (`--reload`와 조합)
   단, `requirements.txt`를 바꾸면 `--build` 필요.
3. **`down -v` 조심.** DB 데이터가 사라짐. 개발 중에 자주 쓰면 매번 데이터 다시 넣어야 함.

### 프론트엔드는 D1에 컨테이너화하지 마

React는 `npm run dev`로 로컬 실행이 훨씬 빠르고 편해.
**Docker에는 배포 단계(D6)에서 nginx로 빌드 결과만 서빙하도록 추가**하는 게 맞아. D1에 프론트까지 컨테이너에 넣으려다 시간 태우는 경우가 많음.
