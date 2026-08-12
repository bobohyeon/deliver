# -*- coding: utf-8 -*-
"""관리/API_계약서_v2.md 를 Tasqra 실제 구현과 대조한다.

이 파일의 책임: 계약서에 적힌 엔드포인트·에러코드·에러 응답 필드가 실제 코드와
  맞는지 세 방향으로 비교한다 (계약서만 · 코드만 · 양쪽). 손으로 50개를
  대조하면 반드시 빠뜨리므로 스크립트로 한다.
다른 파일과의 관계: 관리/API_계약서_v2.md 를 읽고 Tasqra 레포의
  backend/app/api/routes/*.py · core/error_codes.py · schemas/error.py 를 읽는다.
  도구/_check_traceability.py 와 같은 성격이다 — 문서와 실제의 어긋남을 잡는다.
Spring 비교: 없음. 다만 springdoc 이 만든 OpenAPI 문서와 손으로 쓴 API 문서를
  비교하는 것과 목적이 같다.

왜 필요한가
  계약서를 설계 단계에 먼저 썼고 구현이 그 뒤에 왔다. 구현하면서 이름과 경로가
  바뀐 곳이 있는데 계약서에 반영되지 않았다. 계약서대로 프런트를 만들면 404 가
  난다. 합의 전에 이 대조를 반드시 해야 한다.

사용:
    python3 도구/_check_api_contract.py --repo /path/to/Tasqra
    python3 도구/_check_api_contract.py --repo ../Tasqra --ref origin/main
"""

import argparse
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "관리" / "API_계약서_v2.md"

METHODS = ("GET", "POST", "PATCH", "PUT", "DELETE")


def git_show(repo: pathlib.Path, ref: str, path: str) -> str:
    try:
        return subprocess.run(["git", "show", f"{ref}:{path}"], cwd=repo,
                              capture_output=True, text=True,
                              check=True).stdout
    except subprocess.CalledProcessError:
        return ""


def git_files(repo: pathlib.Path, ref: str, pattern: str) -> list[str]:
    out = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref],
                         cwd=repo, capture_output=True, text=True).stdout
    return [p for p in out.splitlines() if re.search(pattern, p)]


# ── 경로 정규화 ──────────────────────────────────────────────────────────────
# 계약서는 {pid} · {did} 처럼 줄여 쓰고 코드는 {project_id} · {document_id} 를
# 쓴다. 이름이 다른 것은 문제가 아니므로 자리표시자를 {} 로 통일해 비교한다.
# 이름 차이는 따로 보고한다.

def norm(path: str) -> str:
    return re.sub(r"\{[^}]*\}", "{}", path.rstrip("/")) or "/"


# ── 코드에서 뽑기 ────────────────────────────────────────────────────────────

def endpoints_from_code(repo: pathlib.Path, ref: str) -> dict:
    found = {}
    for f in git_files(repo, ref, r"api/routes/.*\.py$"):
        src = git_show(repo, ref, f)
        if not src:
            continue
        m = re.search(r'APIRouter\(\s*prefix\s*=\s*["\']([^"\']+)["\']', src)
        prefix = m.group(1) if m else ""
        for d in re.finditer(
                r'@router\.(get|post|patch|put|delete)\(\s*["\']([^"\']*)["\']', src):
            method, tail = d.group(1).upper(), d.group(2)
            full = prefix + tail
            found[(method, norm(full))] = (full, f.split("/")[-1])
    return found


def error_codes_from_code(repo: pathlib.Path, ref: str) -> set[str]:
    src = git_show(repo, ref, "backend/app/core/error_codes.py")
    # Enum 멤버든 상수든 대문자_밑줄 이름을 뽑는다
    return set(re.findall(r"^\s{4}([A-Z][A-Z0-9_]{2,})\s*[:=]", src, re.M))


def error_fields_from_code(repo: pathlib.Path, ref: str) -> dict:
    src = git_show(repo, ref, "backend/app/schemas/error.py")
    out = {}
    for cls in re.finditer(r"class\s+(\w+)\([^)]*\):(.*?)(?=\nclass |\Z)",
                           src, re.S):
        name, body = cls.group(1), cls.group(2)
        out[name] = re.findall(r"^\s{4}(\w+)\s*:", body, re.M)
    return out


# ── 계약서에서 뽑기 ──────────────────────────────────────────────────────────

def endpoints_from_contract(text: str) -> dict:
    """| 번호 | METHOD | `경로` | 설명 | 기능ID | 우선 | 형태의 표를 읽는다."""
    found = {}
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip().strip("`") for c in s.strip("|").split("|")]
        if len(cells) < 3:
            continue
        method = cells[1].strip("*` ").upper()
        if method not in METHODS:
            continue
        path = cells[2].strip("*` ")
        if not path.startswith("/"):
            continue
        found[(method, norm(path))] = (path, cells[0])
    return found


def error_codes_from_contract(text: str) -> set[str]:
    # 표 안의 `CODE_NAME` 형태만 센다. 본문 산문의 대문자 단어는 제외한다.
    codes = set()
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        for m in re.finditer(r"`([A-Z][A-Z0-9_]{2,})`", line):
            codes.add(m.group(1))
    return codes


# ── 보고 ────────────────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{'=' * 76}\n{title}\n{'=' * 76}")


def main() -> None:
    ap = argparse.ArgumentParser(description="API 계약서와 구현 대조")
    ap.add_argument("--repo", required=True, help="Tasqra 레포 경로")
    ap.add_argument("--ref", default="origin/main", help="비교할 git ref")
    args = ap.parse_args()

    repo = pathlib.Path(args.repo).expanduser().resolve()
    if not (repo / ".git").exists():
        print(f"git 레포가 아니다: {repo}", file=sys.stderr)
        sys.exit(1)
    if not CONTRACT.exists():
        print(f"계약서가 없다: {CONTRACT}", file=sys.stderr)
        sys.exit(1)

    text = CONTRACT.read_text(encoding="utf-8")
    doc_ep = endpoints_from_contract(text)
    code_ep = endpoints_from_code(repo, args.ref)

    print(f"계약서   {CONTRACT.relative_to(ROOT)}  엔드포인트 {len(doc_ep)}개")
    print(f"구현     {repo.name} {args.ref}        엔드포인트 {len(code_ep)}개")

    both = sorted(set(doc_ep) & set(code_ep))
    only_doc = sorted(set(doc_ep) - set(code_ep))
    only_code = sorted(set(code_ep) - set(doc_ep))

    section("① 양쪽에 있다 — 경로 자리표시자 이름만 확인한다")
    print(f"  {len(both)}개")
    diff_names = []
    for key in both:
        d, c = doc_ep[key][0], code_ep[key][0]
        if d.rstrip("/") != c.rstrip("/"):
            diff_names.append((d, c))
    if diff_names:
        print(f"  자리표시자 이름이 다른 것 {len(diff_names)}개 "
              f"(동작은 같다. 문서 가독성 문제다)")
        for d, c in diff_names[:12]:
            print(f"    계약서 {d}")
            print(f"    구현   {c}")
    else:
        print("  이름까지 같다")

    section("② 계약서에만 있다 — 미구현이거나 경로가 바뀐 것")
    print(f"  {len(only_doc)}개")
    for method, path in only_doc:
        real, no = doc_ep[(method, path)]
        print(f"    {no:>3}  {method:6} {real}")

    section("③ 구현에만 있다 — 계약서에 빠진 것")
    print(f"  {len(only_code)}개")
    for method, path in only_code:
        real, src = code_ep[(method, path)]
        print(f"         {method:6} {real}   ({src})")

    # ── 에러코드
    doc_codes = error_codes_from_contract(text)
    code_codes = error_codes_from_code(repo, args.ref)
    section("④ 에러코드")
    print(f"  계약서 {len(doc_codes)}종 · 구현 {len(code_codes)}종")
    wrong = sorted(doc_codes - code_codes)
    missing = sorted(code_codes - doc_codes)
    print(f"\n  계약서에 있는데 구현에 없다 — {len(wrong)}개 (이름이 틀렸다)")
    for c in wrong:
        print(f"    {c}")
    print(f"\n  구현에 있는데 계약서에 없다 — {len(missing)}개")
    for c in missing:
        print(f"    {c}")

    # ── 에러 응답 필드
    section("⑤ 에러 응답 필드")
    for cls, fields in error_fields_from_code(repo, args.ref).items():
        print(f"  {cls}: {', '.join(fields)}")
    for name in ("error_code", "code", "request_id", "errors"):
        in_doc = bool(re.search(rf'["`]{name}["`]', text))
        print(f"  계약서에 {name:12} {'있다' if in_doc else '없다'}")

    section("정리")
    problems = len(only_doc) + len(only_code) + len(wrong)
    print(f"  고쳐야 할 것 — 경로 {len(only_doc) + len(only_code)}건 · "
          f"에러코드 이름 {len(wrong)}건 · 계약서에 빠진 코드 {len(missing)}건")
    print(f"  자리표시자 이름 차이 {len(diff_names)}건 (급하지 않다)")
    if problems:
        print("\n  계약서를 합의하기 전에 위를 고쳐야 한다.")
        print("  계약서대로 프런트를 만들면 ②의 경로에서 404 가 난다.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
