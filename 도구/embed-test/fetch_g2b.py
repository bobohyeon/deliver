# =============================================================================
# 이 파일의 책임: 공공데이터포털(data.go.kr)의 조달청 나라장터 오픈API 로
#   입찰공고를 받아 corpus/ 에 넣을 텍스트와 input/ 에 넣을 첨부파일을 만든다.
#   코퍼스를 5건에서 20~30건으로 늘리는 것이 목적이다.
# 다른 파일과의 관계: 여기서 만든 파일을 convert_inputs.py 가 corpus/ 로
#   옮기고, make_chunks.py 가 청크로 자른다. 파일명에 두 자리 순서 접두어를
#   붙여 저장하므로 기존 청크 번호(1~127)가 밀리지 않는다.
# Spring 비교: RestTemplate 으로 외부 API 를 부르고 DTO 로 매핑하는 것과 같다.
#   다만 응답 필드 이름을 우리가 모르므로, 매핑을 먼저 정하지 않고
#   --probe 로 실제 응답을 보고 정한다.
#
# 왜 진단 기능이 먼저 있나
#   조달청 API 는 서비스·오퍼레이션 이름이 여러 개이고 문서와 실제가 다를 수
#   있다. 그래서 이 스크립트는 "무엇이 되는지 알아내는 것" 을 먼저 한다.
#   --probe 가 후보를 하나씩 던져보고 어떤 조합이 응답하는지 보여준다.
#   엔드포인트를 추측해서 박아두면 404 만 보고 원인을 못 찾는다.
#
# 가장 흔한 실패 원인 두 개
#   1. 인증키 인코딩. 포털이 Encoding 키와 Decoding 키를 따로 준다.
#      Decoding 키를 그대로 URL 에 붙이면 +, /, = 가 깨져 30번 에러가 난다.
#      이 스크립트는 두 방식을 다 시도한다.
#   2. 활용신청. 키가 있어도 그 서비스에 신청·승인이 안 됐으면 30번이 난다.
#      키는 계정당 하나지만 권한은 서비스별이다.
# =============================================================================
"""조달청 나라장터 오픈API 수집기.

먼저 이것부터 실행한다 (무엇이 되는지 알아낸다):
    set G2B_API_KEY=발급받은키
    python fetch_g2b.py --probe

되는 조합을 찾은 뒤:
    python fetch_g2b.py --list --service <서비스> --op <오퍼레이션> --rows 20
    python fetch_g2b.py --collect --service <서비스> --op <오퍼레이션> --rows 20
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
INPUT_DIR = ROOT / "input"
RAW_DIR = ROOT / "g2b_raw"

ENV_KEY = "G2B_API_KEY"
TIMEOUT = 30

# 조달청 기관코드. 공공데이터포털 조달청 서비스는 이 아래에 있다.
ORG = "1230000"

# ── 후보 조합 ────────────────────────────────────────────────────────────────
# 문서와 실제가 다를 수 있어 하나로 박지 않는다. --probe 가 하나씩 던져본다.
# 되는 것을 찾으면 그 이름을 --service / --op 로 고정해서 쓴다.
CANDIDATES = [
    # (서비스, 오퍼레이션, 설명)
    ("PubDataOpnStdService", "getDataSetOpnStdBidPblancInfo",
     "공공데이터개방표준 — 입찰공고"),
    ("PubDataOpnStdService", "getDataSetOpnStdScsbidInfo",
     "공공데이터개방표준 — 낙찰정보 (RAG-12 단가 선례에 쓸 값)"),
    ("PubDataOpnStdService", "getDataSetOpnStdCntrctInfo",
     "공공데이터개방표준 — 계약정보"),
    ("BidPublicInfoService", "getBidPblancListInfoServc",
     "입찰공고정보 — 용역"),
    ("BidPublicInfoService", "getBidPblancListInfoServcPPSSrch",
     "입찰공고정보 — 용역 (조달청 검색)"),
    ("BidPublicInfoService", "getBidPblancListInfoThng",
     "입찰공고정보 — 물품"),
    ("BidPublicInfoService04", "getBidPblancListInfoServcPPSSrch01",
     "입찰공고정보 버전 표기가 붙은 경우"),
]

# data.go.kr 공통 에러코드. 200 OK 로 오면서 본문에 들어오는 경우가 많다.
ERRORS = {
    "1": "APPLICATION_ERROR — 서비스 제공 상태가 비정상이다",
    "4": "HTTP_ERROR",
    "12": "NO_OPENAPI_SERVICE_ERROR — 그런 서비스·오퍼레이션이 없다. 이름이 틀렸다",
    "20": "SERVICE_ACCESS_DENIED_ERROR — 활용신청이 승인되지 않았다",
    "22": "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR — 일일 호출 한도 초과",
    "30": "SERVICE_KEY_IS_NOT_REGISTERED_ERROR — 키가 등록 안 됐거나 "
          "이 서비스에 활용신청을 안 했다. 인코딩 문제일 수도 있다",
    "31": "DEADLINE_HAS_EXPIRED_ERROR — 활용기간이 끝났다",
    "32": "UNREGISTERED_IP_ERROR — 등록되지 않은 IP 다",
    "99": "UNKNOWN_ERROR",
}


def read_key() -> str:
    key = os.environ.get(ENV_KEY, "").strip()
    if not key:
        print(f"환경변수 {ENV_KEY} 가 비어 있다.", file=sys.stderr)
        print(f"  PowerShell:  $env:{ENV_KEY}='발급받은키'", file=sys.stderr)
        print(f"  cmd:         set {ENV_KEY}=발급받은키", file=sys.stderr)
        print("  키를 코드나 커밋에 넣지 마라.", file=sys.stderr)
        sys.exit(1)
    return key


def build_url(scheme: str, service: str, op: str, key: str,
              encode_key: bool, params: dict) -> str:
    """URL 을 만든다.

    포털은 인증키를 두 가지로 준다.
      일반 인증키(Encoding)  이미 URL 인코딩된 문자열. 그대로 붙인다
      일반 인증키(Decoding)  원본. + / = 가 들어 있어 quote 해야 한다
    어느 것을 받았는지 모르므로 두 방식을 다 시도한다.
    """
    qs = urllib.parse.urlencode(params, encoding="utf-8")
    sk = urllib.parse.quote(key, safe="") if encode_key else key
    return f"{scheme}://apis.data.go.kr/{ORG}/{service}/{op}?serviceKey={sk}&{qs}"


def call(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, method="GET")
    req.add_header("Accept", "application/json, text/xml;q=0.9, */*;q=0.8")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", "replace")
    except urllib.error.URLError as exc:
        return 0, f"연결 실패 — {exc.reason}"


def diagnose(body: str) -> str | None:
    """응답 본문에서 에러를 찾아 사람 말로 바꾼다. 정상이면 None."""
    m = re.search(r"<returnReasonCode>(\d+)</returnReasonCode>", body)
    if not m:
        m = re.search(r"<resultCode>(\d+)</resultCode>", body)
    if m:
        code = str(int(m.group(1)))          # 0030 -> 30
        if code not in ("0", "00"):
            return f"에러 {code} — {ERRORS.get(code, '알 수 없는 코드')}"
    if "<resultCode>00</resultCode>" in body or '"resultCode":"00"' in body:
        return None
    msg = re.search(r"<returnAuthMsg>([^<]+)</returnAuthMsg>", body)
    if msg:
        return f"인증 메시지 — {msg.group(1)}"
    low = body.lower()
    if "<html" in low and "error" in low:
        return "HTML 오류 페이지가 돌아왔다. 경로가 틀렸을 가능성이 크다"
    return None


def extract_items(body: str) -> list[dict]:
    """JSON 이든 XML 이든 item 목록을 뽑는다."""
    body = body.strip()
    if body.startswith("{"):
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []
        node = data.get("response", data)
        node = node.get("body", node) if isinstance(node, dict) else node
        items = node.get("items") if isinstance(node, dict) else None
        if isinstance(items, dict):
            items = items.get("item")
        if isinstance(items, dict):
            items = [items]
        return items or []

    # XML — 의존성을 늘리지 않으려고 표준 라이브러리로 처리한다
    from xml.etree import ElementTree as ET
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        out.append({c.tag: (c.text or "").strip() for c in item})
    return out


# ─────────────────────────────────────────────── 진단

def probe(key: str, rows: int) -> int:
    print("=" * 74)
    print("조달청 오픈API 진단 — 무엇이 되는지 알아낸다")
    print(f"  키 길이 {len(key)}자 · " +
          ("이미 URL 인코딩된 키로 보인다 (%25 포함)" if "%" in key
           else "원본(Decoding) 키로 보인다"))
    print("  각 조합에 1건만 요청한다. 일일 한도를 거의 쓰지 않는다.")
    print("=" * 74)

    base = {"pageNo": "1", "numOfRows": str(rows), "type": "json"}
    ok: list[tuple[str, str, bool, str]] = []

    for service, op, desc in CANDIDATES:
        print(f"\n  {service} / {op}")
        print(f"    {desc}")
        found = False
        for scheme in ("http", "https"):
            for encode_key in (False, True):
                url = build_url(scheme, service, op, key, encode_key, base)
                status, body = call(url)
                tag = f"{scheme:5} 키{'인코딩' if encode_key else '원본  '}"
                if status == 0:
                    print(f"      {tag}  {body[:60]}")
                    continue
                err = diagnose(body)
                items = extract_items(body)
                if err:
                    print(f"      {tag}  HTTP {status} · {err}")
                elif items:
                    print(f"      {tag}  HTTP {status} · **성공 · item {len(items)}건**")
                    ok.append((service, op, encode_key, scheme))
                    found = True
                    break
                else:
                    head = body[:70].replace("\n", " ")
                    print(f"      {tag}  HTTP {status} · item 없음 · {head}")
            if found:
                break

    print("\n" + "=" * 74)
    if not ok:
        print("되는 조합이 없다. 아래를 확인한다.")
        print("  1. data.go.kr 로그인 > 마이페이지 > 개발계정 에서")
        print("     조달청 서비스에 활용신청을 했는지, 승인됐는지 본다")
        print("  2. 에러 30 이면 활용신청 문제이거나 키 인코딩 문제다")
        print("  3. 에러 12 이면 서비스·오퍼레이션 이름이 틀린 것이다.")
        print("     포털의 그 서비스 상세 화면에서 실제 이름을 보고")
        print("     --service / --op 로 직접 넣어 다시 시도한다")
        print("  4. 신청 직후에는 반영에 시간이 걸릴 수 있다")
        return 1

    print("되는 조합 —")
    for service, op, enc, scheme in ok:
        print(f"  {scheme} · {service} / {op} · "
              f"키 {'인코딩해서' if enc else '원본으로'} 보냄")
    s, o, enc, sc = ok[0]
    print(f"\n다음:  python fetch_g2b.py --list --service {s} --op {o}"
          + ("" if not enc else " --encode-key")
          + ("" if sc == "http" else " --https"))
    return 0


# ─────────────────────────────────────────────── 목록 조회

URLISH = re.compile(r"(url|Url|URL)$")
FILEISH = re.compile(r"(FileNm|fileNm|FileName)$")


def fetch(key: str, args, params_extra: dict | None = None) -> list[dict]:
    params = {"pageNo": str(args.page), "numOfRows": str(args.rows),
              "type": "json"}
    if params_extra:
        params.update(params_extra)
    if args.begin and args.end:
        # 서비스마다 날짜 파라미터 이름이 다르다. 되는 것을 쓰라고 알려준다.
        params["inqryDiv"] = "1"
        params["inqryBgnDt"] = args.begin
        params["inqryEndDt"] = args.end

    url = build_url("https" if args.https else "http", args.service, args.op,
                    key, args.encode_key, params)
    status, body = call(url)

    RAW_DIR.mkdir(exist_ok=True)
    raw = RAW_DIR / f"{args.op}_p{args.page}.txt"
    raw.write_text(body, encoding="utf-8")
    print(f"  원본 응답 저장: {raw.relative_to(ROOT)}")

    err = diagnose(body)
    if err:
        print(f"  실패 — HTTP {status} · {err}", file=sys.stderr)
        print("  --probe 로 되는 조합을 먼저 찾아라.", file=sys.stderr)
        sys.exit(1)

    items = extract_items(body)
    if not items:
        print(f"  item 이 없다. HTTP {status}. 위 원본 파일을 열어봐라.",
              file=sys.stderr)
        sys.exit(1)
    return items


def show_list(key: str, args) -> None:
    items = fetch(key, args)
    print(f"\n  받은 건수: {len(items)}\n")

    keys = sorted({k for it in items for k in it})
    print("  === 응답 필드 목록 ===")
    for k in keys:
        sample = next((str(it[k]) for it in items if it.get(k)), "")
        mark = ""
        if URLISH.search(k):
            mark = "   <- URL 로 보인다"
        elif FILEISH.search(k):
            mark = "   <- 파일명으로 보인다"
        print(f"    {k:<28} {sample[:44]}{mark}")

    urls = [k for k in keys if URLISH.search(k)]
    files = [k for k in keys if FILEISH.search(k)]
    print("\n  === 첨부파일을 받을 수 있나 ===")
    if urls:
        print(f"    URL 로 보이는 필드 {len(urls)}개 — {', '.join(urls[:8])}")
        print("    이 중 공고규격서·제안요청서 파일이면 --collect 로 받는다")
    else:
        print("    URL 필드가 없다. 이 오퍼레이션은 파일을 주지 않는다.")
        print("    다른 오퍼레이션을 --probe 로 찾거나, 공고 상세 URL 로")
        print("    나라장터에서 직접 내려받는다.")
    if files:
        print(f"    파일명 필드 {len(files)}개 — {', '.join(files[:8])}")

    print("\n  === 첫 건 전체 ===")
    for k, v in sorted(items[0].items()):
        print(f"    {k:<28} {str(v)[:60]}")


# ─────────────────────────────────────────────── 수집

def safe_name(text: str, limit: int = 70) -> str:
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", str(text)).strip()
    return re.sub(r"\s+", " ", text)[:limit] or "무제"


def collect(key: str, args) -> None:
    items = fetch(key, args)
    INPUT_DIR.mkdir(exist_ok=True)

    title_key = next((k for k in ("bidNtceNm", "ntceNm", "cntrctNm", "bidNtceNo")
                      if any(k in it for it in items)), None)
    if not title_key:
        title_key = sorted(items[0])[0]

    url_keys = sorted(k for k in items[0] if URLISH.search(k))
    made, got = 0, 0

    for i, it in enumerate(items, start=args.start_no):
        title = safe_name(it.get(title_key, f"공고{i}"))
        stem = f"{i:02d}_{title}"

        # 1. 필드를 사람이 읽는 텍스트로 남긴다. 이것만으로도 코퍼스가 된다.
        lines = [f"# {title}", ""]
        for k, v in sorted(it.items()):
            if v not in (None, "", "null"):
                lines.append(f"{k}: {v}")
        (INPUT_DIR / f"{stem}.md").write_text("\n".join(lines) + "\n",
                                              encoding="utf-8")
        made += 1

        # 2. 첨부파일이 있으면 받는다. 이게 진짜 공고 본문이다.
        if args.no_files:
            continue
        for k in url_keys:
            u = str(it.get(k) or "")
            if not u.startswith("http"):
                continue
            if not re.search(r"\.(pdf|hwp|hwpx|docx?|xlsx?|zip)(\?|$)", u, re.I):
                continue
            ext = re.search(r"\.([A-Za-z0-9]+)(\?|$)", u).group(1).lower()
            out = INPUT_DIR / f"{stem}_{k}.{ext}"
            try:
                req = urllib.request.Request(u, method="GET")
                req.add_header("User-Agent", "Mozilla/5.0")
                with urllib.request.urlopen(req, timeout=60) as resp:
                    out.write_bytes(resp.read())
                print(f"    받음 {out.name} ({out.stat().st_size:,} bytes)")
                got += 1
            except Exception as exc:                      # noqa: BLE001
                print(f"    실패 {k} — {type(exc).__name__}: {exc}")

    print(f"\n  텍스트 {made}건 · 첨부파일 {got}건 -> {INPUT_DIR}")
    print("\n  다음 순서 —")
    print("    1. input/ 을 열어 쓸 것만 남기고 지운다")
    print("    2. python convert_inputs.py     # input/ -> corpus/")
    print("    3. 기존 5건 파일명이 01_~05_ 인지 확인한다")
    print("       (안 되어 있으면 지금 붙인다. 순서가 바뀌면 청크 번호가 밀린다)")
    print("    4. python make_chunks.py")
    print("    5. python check_queries.py      # 1~127 이 그대로인지 확인")
    print("       여기서 '없는 청크 번호' 가 나오면 번호가 밀린 것이다")


def main() -> None:
    p = argparse.ArgumentParser(description="조달청 나라장터 오픈API 수집")
    p.add_argument("--probe", action="store_true",
                   help="어떤 서비스·오퍼레이션·키인코딩이 되는지 알아낸다")
    p.add_argument("--list", action="store_true",
                   help="응답 필드와 첨부파일 URL 유무를 보여준다")
    p.add_argument("--collect", action="store_true",
                   help="input/ 에 텍스트와 첨부파일을 저장한다")
    p.add_argument("--service", default="PubDataOpnStdService")
    p.add_argument("--op", default="getDataSetOpnStdBidPblancInfo")
    p.add_argument("--rows", type=int, default=10)
    p.add_argument("--page", type=int, default=1)
    p.add_argument("--begin", default="", help="조회 시작 (예 202601010000)")
    p.add_argument("--end", default="", help="조회 종료 (예 202612312359)")
    p.add_argument("--encode-key", action="store_true",
                   help="인증키를 URL 인코딩해서 보낸다 (Decoding 키를 받았을 때)")
    p.add_argument("--https", action="store_true", help="https 로 부른다")
    p.add_argument("--start-no", type=int, default=6,
                   help="파일명 순서 접두어 시작 번호. 기존 5건 뒤이므로 6 이 기본")
    p.add_argument("--no-files", action="store_true", help="첨부파일을 받지 않는다")
    args = p.parse_args()

    key = read_key()
    if args.probe:
        sys.exit(probe(key, min(args.rows, 5)))
    if args.list:
        show_list(key, args)
        return
    if args.collect:
        collect(key, args)
        return
    p.print_help()
    print("\n먼저 --probe 로 무엇이 되는지 알아내라.")


if __name__ == "__main__":
    main()
