#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# ① 이 파일의 책임
#    파인튜닝용 messages JSONL 이 규격(규격_및_RFP-PROPOSAL_판별.md)을 지키는지
#    검사한다. 9종 유형 enum, 필수 필드, assistant 가 유효 JSON 인지, due_date
#    형식 등을 줄 단위로 확인하고 어긋난 곳을 줄번호와 함께 보고한다.
# ② 다른 파일과의 관계
#    입력은 사람이/도구가 만든 *.jsonl. 통과해야 세현님께 넘긴다. 규격 문서가
#    사람이 읽는 계약서라면 이 파일은 그 계약을 기계로 강제하는 문지기다.
# ③ Spring 비교
#    Bean Validation(@NotNull·@Pattern) + JUnit 단정을 한데 묶은 것과 같다.
#    스키마 위반을 "예외 목록"으로 모아 마지막에 한 번에 실패시킨다.
# ---------------------------------------------------------------------------
"""사용법:  python3 validate_sft.py <파일.jsonl> [<파일2.jsonl> ...]
통과하면 종료코드 0, 하나라도 어긋나면 1. 요약과 위반 목록을 출력한다."""

import json
import re
import sys

DOC_TYPES = {
    "RFP", "PROPOSAL", "COST_SHEET", "CONTRACT", "CONTRACT_CHANGE",
    "REPORT", "MEETING_NOTES", "BILLING", "ETC",
}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _last_assistant(messages):
    """messages 배열에서 마지막 assistant 발화 내용을 돌려준다. 없으면 None."""
    for m in reversed(messages):
        if isinstance(m, dict) and m.get("role") == "assistant":
            return m.get("content")
    return None


def _check_classification(obj, errs, ln):
    if obj.get("document_type") not in DOC_TYPES:
        errs.append(f"{ln}행: document_type 값이 9종 밖 → {obj.get('document_type')!r}")
    if not str(obj.get("reason", "")).strip():
        errs.append(f"{ln}행: 분류에 reason 이 비어 있다")


def _check_suggestion_list(items, errs, ln):
    # 갭분석/액션아이템 공통: 배열이고 각 원소가 dict. 빈 배열은 정답으로 허용.
    for i, it in enumerate(items):
        if not isinstance(it, dict):
            errs.append(f"{ln}행 [{i}]: 배열 원소가 객체가 아니다")
            continue
        if not str(it.get("title", "")).strip():
            errs.append(f"{ln}행 [{i}]: title 이 비어 있다")
        if not str(it.get("reason", "")).strip():
            errs.append(f"{ln}행 [{i}]: reason 이 비어 있다")
        # 갭분석이면 source, 액션아이템이면 confidence/due_date 를 추가 검사
        if "source" in it and not isinstance(it["source"], list):
            errs.append(f"{ln}행 [{i}]: source 는 배열이어야 한다")
        if "due_date" in it and it["due_date"] is not None:
            if not DATE_RE.match(str(it["due_date"])):
                errs.append(f"{ln}행 [{i}]: due_date 는 null 또는 YYYY-MM-DD → {it['due_date']!r}")
        if "confidence" in it and it["confidence"] is not None:
            try:
                c = float(it["confidence"])
                if not 0.0 <= c <= 1.0:
                    errs.append(f"{ln}행 [{i}]: confidence 는 0~1 → {c}")
            except (TypeError, ValueError):
                errs.append(f"{ln}행 [{i}]: confidence 가 숫자가 아니다 → {it['confidence']!r}")


def validate_file(path):
    errs = []
    n = 0
    with open(path, encoding="utf-8") as f:
        for ln, raw in enumerate(f, 1):
            raw = raw.strip()
            if not raw:
                continue
            n += 1
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError as e:
                errs.append(f"{ln}행: JSON 파싱 실패 — {e}")
                continue
            msgs = rec.get("messages")
            if not isinstance(msgs, list) or not msgs:
                errs.append(f"{ln}행: messages 배열이 없다")
                continue
            roles = {m.get("role") for m in msgs if isinstance(m, dict)}
            if "user" not in roles or "assistant" not in roles:
                errs.append(f"{ln}행: user/assistant 발화가 모두 있어야 한다")
            content = _last_assistant(msgs)
            if content is None:
                errs.append(f"{ln}행: assistant 발화가 없다")
                continue
            try:
                out = json.loads(content)
            except json.JSONDecodeError as e:
                errs.append(f"{ln}행: assistant 내용이 유효 JSON 이 아니다 — {e}")
                continue
            if isinstance(out, dict) and "document_type" in out:
                _check_classification(out, errs, ln)
            elif isinstance(out, list):
                _check_suggestion_list(out, errs, ln)
            else:
                errs.append(f"{ln}행: assistant JSON 이 분류(객체)도 추천(배열)도 아니다")
    return n, errs


def main(argv):
    paths = argv[1:]
    if not paths:
        print("사용법: python3 validate_sft.py <파일.jsonl> ...", file=sys.stderr)
        return 2
    total, total_err = 0, 0
    for p in paths:
        n, errs = validate_file(p)
        total += n
        total_err += len(errs)
        status = "OK" if not errs else f"{len(errs)}건 위반"
        print(f"[{status}] {p} — 예시 {n}개")
        for e in errs:
            print(f"    - {e}")
    print(f"\n합계: 예시 {total}개, 위반 {total_err}건")
    return 0 if total_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
