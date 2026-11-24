#!/usr/bin/env python3
"""한국 커뮤니티 연예 화제글 수집기 (토큰 절약용).

명령:
  list  [--limit N]          세 사이트 인기글 목록을 긁어서, 이미 다룬 URL은 빼고 TSV로 출력
  body  URL [URL ...]        글 본문 앞부분·작성시각·조회수를 짧게 출력 (사실 확인용)
  mark  URL [URL ...] --issue "이슈 키워드"   다룬 글을 data/community_seen.csv에 기록
  export JSON               작성한 글(JSON 리스트)을 outputs/ md + data/community_posts.csv(시트용)에 저장하고 seen 기록
    JSON 항목: site, issue, tone, url, posted, reaction, text, (related: 같은 이슈 다른 URL 리스트)

더쿠·에펨코리아는 Cloudflare 캡차가 있어서 수집 대상에서 제외한다.
"""
import csv
import re
import sys
import argparse
import datetime as dt
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "community_seen.csv"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
KST = dt.timezone(dt.timedelta(hours=9))

# 디시 실베는 전 갤러리 글이 섞이니 연예·방송 쪽 갤 말머리만 통과
DC_ENT_TAGS = ("싱갤", "연갤", "해연갤", "중갤", "주갤", "케갤", "기음갤", "여돌", "남돌",
               "아이돌", "드갤", "예갤", "방갤", "유갤", "연예", "걸그룹", "보갤", "배갤")


def get(url):
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "ko-KR"}, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding if "pann" in url else r.encoding
    return BeautifulSoup(r.text, "html.parser")


def num(s):
    d = re.sub(r"[^\d]", "", s or "")
    return int(d) if d else 0


def norm_url(u):
    """쿼리 정리해서 중복 판정용 표준 URL로 만든다."""
    m = re.search(r"pann\.nate\.com/talk/(\d+)", u)
    if m:
        return f"https://pann.nate.com/talk/{m.group(1)}"
    m = re.search(r"instiz\.net/pt/(\d+)", u)
    if m:
        return f"https://www.instiz.net/pt/{m.group(1)}"
    m = re.search(r"id=dcbest&(?:amp;)?no=(\d+)", u)
    if m:
        return f"https://gall.dcinside.com/board/view/?id=dcbest&no={m.group(1)}"
    return u


def src_pann():
    s = get("https://pann.nate.com/talk/ranking?rankingType=enter")
    out = []
    for li in s.select("ul.post_wrap > li, .cntList li"):
        a = li.select_one("h2 a, dt a")
        if not a or not re.search(r"/talk/\d+", a.get("href", "")):
            continue
        txt = li.get_text(" ", strip=True)
        out.append(dict(site="네이트판", title=a.get_text(strip=True),
                        url=norm_url("https://pann.nate.com" + a["href"]),
                        views=num((re.search(r"조회\s*([\d,]+)", txt) or [None, ""])[1]),
                        comments=num((re.search(r"\((\d+)\)", txt) or [None, ""])[1]),
                        time=""))
    return out


def src_dc(pages=2):
    out = []
    for p in range(1, pages + 1):
        s = get(f"https://gall.dcinside.com/board/lists/?id=dcbest&page={p}")
        for tr in s.select("tr.ub-content"):
            a = tr.select_one("td.gall_tit a")
            if not a or tr.get("data-type") == "icon_notice":
                continue
            tag = (a.select_one("strong").get_text(strip=True) if a.select_one("strong") else "")
            if not any(t in tag for t in DC_ENT_TAGS):
                continue
            title = a.get_text(" ", strip=True)
            dtag = tr.select_one("td.gall_date")
            out.append(dict(site="디시 실베", title=title,
                            url=norm_url(a["href"]),
                            views=num(tr.select_one("td.gall_count").get_text()),
                            comments=num((tr.select_one(".reply_num") or a).get_text()),
                            time=(dtag.get("title") or dtag.get_text(strip=True))[:16]))
    return out


def src_instiz(pages=3):
    out = []
    for p in range(1, pages + 1):
        s = get(f"https://www.instiz.net/pt?page={p}&category=1")
        for tr in s.select("tr[id^=list]"):
            a = tr.select_one("td.listsubject a")
            if not a:
                continue
            sbj = a.select_one(".sbj")
            cmt = sbj.select_one(".cmt2, .cmt3, .cmt") if sbj else None
            ctext = cmt.get_text(strip=True) if cmt else "0"
            if cmt:
                cmt.extract()
            sub = tr.get_text(" ", strip=True)
            out.append(dict(site="인스티즈", title=sbj.get_text(" ", strip=True) if sbj else a.get_text(strip=True),
                            url=norm_url(a["href"]),
                            views=num((re.search(r"조회\s*([\d,]+)", sub) or [None, ""])[1]),
                            comments=num(ctext),
                            time=(re.search(r"\d{1,2}:\d{2}", sub) or [""])[0]))
    return out


def load_seen():
    if not SEEN.exists():
        return set()
    with SEEN.open(encoding="utf-8") as f:
        return {row["url"] for row in csv.DictReader(f)}


def cmd_list(args):
    seen = load_seen()
    rows = []
    for fn in (src_pann, src_dc, src_instiz):
        try:
            rows += fn()
        except Exception as e:  # 한 사이트가 죽어도 나머지는 진행
            print(f"# {fn.__name__} 실패: {e}", file=sys.stderr)
    uniq = {}
    for r in rows:
        if r["url"] in seen:
            continue
        if r["url"] not in uniq or r["views"] > uniq[r["url"]]["views"]:
            uniq[r["url"]] = r
    # 사이트마다 조회수 규모가 달라서 사이트별 상위 N개씩 따로 뽑는다
    print("site\tviews\tcomments\ttime\ttitle\turl")
    for site in ("네이트판", "디시 실베", "인스티즈"):
        part = [r for r in uniq.values() if r["site"] == site]
        part.sort(key=lambda r: (r["comments"] * 20 + r["views"]), reverse=True)
        for r in part[: args.limit]:
            print(f"{r['site']}\t{r['views']}\t{r['comments']}\t{r['time']}\t{r['title'][:60]}\t{r['url']}")


def cmd_body(args):
    for u in args.urls:
        u = norm_url(u)
        try:
            s = get(u)
        except Exception as e:
            print(f"## {u}\n확인 불가: {e}\n")
            continue
        if "pann" in u:
            body = s.select_one("#contentArea")
            when = s.select_one(".info .date, span.date")
            info = s.select_one(".info")
            views = (re.search(r"조회\s*([\d,]+)", info.get_text()) or [None, ""])[1] if info else ""
            cm = s.select_one(".cmt_cnt, .num_cmt, #cmtCnt")
        elif "dcinside" in u:
            body = s.select_one(".write_div")
            when = s.select_one(".gall_date")
            v = s.select_one(".gall_count")
            views = v.get_text(strip=True) if v else ""
            cm = s.select_one(".gall_comment")
        else:
            body = s.select_one("#memo_content_1")
            when = s.select_one(".tb_left span, .date, #ingiinfo")
            views = (re.search(r"조회\s*([\d,]+)", s.get_text(" ")) or [None, ""])[1]
            cm = s.select_one("#cmt_count, .cmt_count")
        text = body.get_text(" ", strip=True) if body else ""
        imgs = len(body.select("img, video")) if body else 0
        print(f"## {u}")
        print(f"작성: {when.get_text(' ', strip=True)[:25] if when else '확인 불가'} | 조회: {views or '확인 불가'}"
              f" | 댓글: {cm.get_text(' ', strip=True)[:20] if cm else '확인 불가'} | 이미지: {imgs} | 본문 글자수: {len(text)}")
        print(text[: args.chars] if text else "(본문 텍스트 없음)")
        print()


def cmd_mark(args):
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    new = not SEEN.exists()
    seen = load_seen()
    now = dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    with SEEN.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["url", "issue", "marked_at"])
        for u in args.urls:
            u = norm_url(u)
            if u not in seen:
                w.writerow([u, args.issue, now])
                seen.add(u)


POSTS = ROOT / "data" / "community_posts.csv"
POST_COLS = ["collected_at", "site", "issue", "tone", "posted", "reaction", "url", "chars", "text"]


def cmd_export(args):
    import json
    items = json.load(open(args.json, encoding="utf-8"))
    now = dt.datetime.now(KST)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    seen = load_seen()
    items = [x for x in items if norm_url(x["url"]) not in seen]
    # 시트용 누적 CSV
    new = not POSTS.exists()
    with POSTS.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(POST_COLS)
        for x in items:
            w.writerow([stamp, x["site"], x["issue"], x["tone"], x["posted"], x["reaction"],
                        norm_url(x["url"]), len(x["text"]), x["text"]])
    # 날짜별 결과 파일 (하루에 여러 번 돌면 이어 붙임)
    out = ROOT / "outputs" / f"{now:%Y-%m-%d}-커뮤니티-X글.md"
    with out.open("a", encoding="utf-8") as f:
        if out.stat().st_size == 0:
            f.write(f"# 커뮤니티 연예 화제글 → X 초안 ({now:%Y-%m-%d})\n")
        f.write(f"\n## {now:%H:%M} 수집분 ({len(items)}건)\n")
        for i, x in enumerate(items, 1):
            f.write(f"\n### {i}. [{x['site']}] {x['issue']} ({x['tone']}, {len(x['text'])}자)\n")
            f.write(f"- 작성: {x['posted']} | 반응: {x['reaction']}\n\n```text\n{x['text']}\n```\n")
    # 중복 방지 기록
    for x in items:
        args.urls = [x["url"]] + x.get("related", [])
        args.issue = x["issue"]
        cmd_mark(args)
    print(f"저장: {out.relative_to(ROOT)} / {POSTS.relative_to(ROOT)} ({len(items)}건)")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("list"); a.add_argument("--limit", type=int, default=15, help="사이트별 개수"); a.set_defaults(fn=cmd_list)
    b = sp.add_parser("body"); b.add_argument("urls", nargs="+"); b.add_argument("--chars", type=int, default=600); b.set_defaults(fn=cmd_body)
    c = sp.add_parser("mark"); c.add_argument("urls", nargs="+"); c.add_argument("--issue", default=""); c.set_defaults(fn=cmd_mark)
    e = sp.add_parser("export"); e.add_argument("json"); e.set_defaults(fn=cmd_export)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
