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
    m = re.search(r"clien\.net/service/board/(\w+)/(\d+)", u)
    if m:
        return f"https://www.clien.net/service/board/{m.group(1)}/{m.group(2)}"
    m = re.search(r"mgallery/board/view/\?id=(\w+)&(?:amp;)?no=(\d+)", u)
    if m:
        return f"https://gall.dcinside.com/mgallery/board/view/?id={m.group(1)}&no={m.group(2)}"
    m = re.search(r"id=dcbest&(?:amp;)?no=(\d+)", u)
    if m:
        return f"https://gall.dcinside.com/board/view/?id=dcbest&no={m.group(1)}"
    return u


def src_pann(ranking="enter"):
    s = get(f"https://pann.nate.com/talk/ranking?rankingType={ranking}")
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


def src_dc(pages=2, ent_only=True):
    out = []
    for p in range(1, pages + 1):
        s = get(f"https://gall.dcinside.com/board/lists/?id=dcbest&page={p}")
        for tr in s.select("tr.ub-content"):
            a = tr.select_one("td.gall_tit a")
            if not a or tr.get("data-type") == "icon_notice":
                continue
            tag = (a.select_one("strong").get_text(strip=True) if a.select_one("strong") else "")
            if ent_only and not any(t in tag for t in DC_ENT_TAGS):
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


# 꿀팁 모드: 클리앙 팁과강좌는 전부, 나머지 사이트는 제목 키워드로 거른다
TIP_KW = re.compile(r"꿀팁|팁|방법|하는\s?법|노하우|정리|모음|총정리|추천|절약|아끼|환급|지원금|혜택|할인|무료|신청|"
                    r"부업|재테크|N잡|앱테크|짠테크|적금|청약|연말정산|세금|보험|"
                    r"설정|단축키|엑셀|AI|챗GPT|ChatGPT|앱|어플|크롬|아이폰|갤럭시|윈도|"
                    r"알아두면|모르면|필수|체크리스트|살림|청소|세탁|자취|생활", re.I)


def src_clien(pages=4, days=7):
    cutoff = (dt.datetime.now(KST) - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    out = []
    for p in range(pages):
        s = get(f"https://www.clien.net/service/board/lecture?po={p}")  # 최신순
        for r in s.select("div.list_item.symph_row"):
            a = r.select_one("a.list_subject")
            t = r.select_one(".subject_fixed")
            if not a or not t:
                continue
            cat = r.select_one(".category")
            ts = r.select_one(".timestamp")
            if not ts or ts.get_text(strip=True)[:10] < cutoff:
                continue
            out.append(dict(site="클리앙 팁", title=(f"[{cat.get_text(strip=True)}] " if cat else "") + t.get_text(strip=True),
                            url=norm_url("https://www.clien.net" + a["href"]),
                            views=num((r.select_one(".hit") or a).get_text()),
                            comments=num(r.get("data-comment-count")),
                            time=ts.get_text(strip=True)[:16] if ts else ""))
    return out


# 아이돌 모드: 제목에 아이돌 관련 키워드가 있는 글만
IDOL_KW = re.compile(r"아이돌|걸그룹|보이그룹|남돌|여돌|컴백|데뷔|음방|음악방송|1위|뮤비|MV|앨범|초동|차트|멜론|써클|"
                     r"팬싸|팬미팅|콘서트|투어|직캠|챌린지|센터|막내|리더|연습생|오디션|소속사|"
                     r"방탄|BTS|블랙핑크|블핑|에스파|aespa|아이브|IVE|뉴진스|르세라핌|세븐틴|스키즈|스트레이키즈|"
                     r"트와이스|투바투|TXT|엔시티|NCT|엑소|레드벨벳|아일릿|ILLIT|키키|KiiiKiii|베이비몬스터|베몬|"
                     r"라이즈|RIIZE|투어스|TWS|보넥도|제베원|엔하이픈|있지|ITZY|아이들|케플러|QWER|하츠투하츠|"
                     r"올데프|코르티스|CORTIS|A2O|리센느|RESCENE|빅뱅|지드래곤|아이유|태연|장원영|카리나|윈터|"
                     r"안유진|민지|하니|해린|정국|지민|뷔|제니|지수|로제|리사", re.I)


def src_dc_gall(gid, mgallery=True, label="디시 걸그룹갤"):
    base = "mgallery/board" if mgallery else "board"
    s = get(f"https://gall.dcinside.com/{base}/lists/?id={gid}&exception_mode=recommend")
    out = []
    for tr in s.select("tr.ub-content"):
        a = tr.select_one("td.gall_tit a")
        num_td = tr.select_one("td.gall_num")
        if not a or not num_td or not num_td.get_text(strip=True).isdigit():
            continue
        no = num_td.get_text(strip=True)
        d = tr.select_one("td.gall_date")
        out.append(dict(site=label, title=a.get_text(" ", strip=True),
                        url=f"https://gall.dcinside.com/{base}/view/?id={gid}&no={no}",
                        views=num(tr.select_one("td.gall_count").get_text()),
                        comments=num((tr.select_one(".reply_num") or a).get_text()),
                        time=(d.get("title") or d.get_text(strip=True))[:16] if d else ""))
    return out


def src_soompi():
    """해외 K팝 뉴스(영문). 조회수 없음 → views=0"""
    s = get("https://www.soompi.com/")
    out, seen = [], set()
    for a in s.find_all("a", href=re.compile(r"/article/\d+")):
        t = a.get_text(" ", strip=True)
        if len(t) < 25 or t in seen:
            continue
        seen.add(t)
        href = a["href"] if a["href"].startswith("http") else "https://www.soompi.com" + a["href"]
        out.append(dict(site="숨피(해외)", title=t, url=href.split("?")[0], views=0, comments=0, time=""))
    return out


def load_seen():
    if not SEEN.exists():
        return set()
    with SEEN.open(encoding="utf-8") as f:
        return {row["url"] for row in csv.DictReader(f)}


def cmd_list(args):
    seen = load_seen()
    rows = []
    if args.mode == "idol":
        fns = (src_pann, lambda: src_dc(3, ent_only=False), src_instiz, src_soompi)
        sites = ("네이트판", "디시 실베", "인스티즈", "숨피(해외)")
    elif args.mode == "tips":
        fns = (src_clien, lambda: src_pann("total"), lambda: src_pann("life"),
               lambda: src_dc(3, ent_only=False), src_instiz)
        sites = ("클리앙 팁", "네이트판", "디시 실베", "인스티즈")
    else:
        fns = (src_pann, src_dc, src_instiz)
        sites = ("네이트판", "디시 실베", "인스티즈")
    for fn in fns:
        try:
            got = fn()
            if args.mode == "tips":
                got = [r for r in got if r["site"] == "클리앙 팁" or TIP_KW.search(r["title"])]
            elif args.mode == "idol":
                got = [r for r in got if r["site"] == "숨피(해외)" or IDOL_KW.search(r["title"])]
            rows += got
        except Exception as e:  # 한 사이트가 죽어도 나머지는 진행
            print(f"# {getattr(fn, '__name__', 'src')} 실패: {e}", file=sys.stderr)
    uniq = {}
    for r in rows:
        if r["url"] in seen:
            continue
        if r["url"] not in uniq or r["views"] > uniq[r["url"]]["views"]:
            uniq[r["url"]] = r
    # 사이트마다 조회수 규모가 달라서 사이트별 상위 N개씩 따로 뽑는다
    print("site\tviews\tcomments\ttime\ttitle\turl")
    for site in sites:
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
        elif "soompi" in u:
            body = s.select_one("article .article-wrapper, .article-wrapper, article")
            when = s.select_one("time, .date-time")
            views, cm = "", None
        elif "clien" in u:
            body = s.select_one(".post_article")
            when = s.select_one(".post_author .view_count.date, .post_date")
            v = s.select_one(".view_info, .view_count:not(.date)")
            views = v.get_text(" ", strip=True)[:20] if v else ""
            cm = s.select_one(".post_reply .reply_count, #comment-head .comment_count")
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


CHART_DIR = ROOT / "data" / "charts"


def fetch_melon():
    s = get("https://www.melon.com/chart/index.htm")
    out = []
    for tr in s.select("tr.lst50, tr.lst100"):
        t = tr.select_one(".ellipsis.rank01 a"); a = tr.select_one(".ellipsis.rank02 a")
        out.append(dict(rank=num(tr.select_one(".rank").get_text()), title=t.get_text(strip=True) if t else "",
                        artist=a.get_text(strip=True) if a else ""))
    return out


def fetch_genie():
    out = []
    for pg in (1, 2):
        s = get(f"https://www.genie.co.kr/chart/top200?pg={pg}")
        for tr in s.select("tr.list"):
            nb = tr.select_one(".number")
            rank = re.match(r"\d+", (nb.contents[0] if nb and nb.contents else "").strip())
            out.append(dict(rank=int(rank.group()) if rank else 0,
                            title=tr.select_one("a.title").get_text(strip=True),
                            artist=tr.select_one("a.artist").get_text(strip=True)))
    return out


def cmd_chart(args):
    """멜론·지니 TOP 차트 스냅샷 저장 + 직전 스냅샷 대비 변동(신규 진입·급상승) 출력"""
    CHART_DIR.mkdir(parents=True, exist_ok=True)
    now = dt.datetime.now(KST)
    for name, fn in (("melon", fetch_melon), ("genie", fetch_genie)):
        try:
            cur = fn()
        except Exception as e:
            print(f"# {name} 실패: {e}"); continue
        prev_files = sorted(CHART_DIR.glob(f"*_{name}.csv"))
        prev = {}
        if prev_files:
            with prev_files[-1].open(encoding="utf-8") as f:
                prev = {(r["title"], r["artist"]): int(r["rank"]) for r in csv.DictReader(f)}
        snap = CHART_DIR / f"{now:%Y-%m-%d_%H%M}_{name}.csv"
        with snap.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["rank", "title", "artist"]); w.writeheader(); w.writerows(cur)
        print(f"## {name} TOP{args.top} ({now:%m-%d %H:%M}, 비교: {prev_files[-1].stem if prev_files else '없음'})")
        for r in cur[: args.top]:
            p = prev.get((r["title"], r["artist"]))
            ch = "NEW" if prev and p is None else ("-" if p is None or p == r["rank"] else f"{p - r['rank']:+d}")
            print(f"{r['rank']}\t{ch}\t{r['title']}\t{r['artist']}")
        if prev:
            jumps = [(prev[(r['title'], r['artist'])] - r['rank'], r) for r in cur if (r['title'], r['artist']) in prev]
            jumps = [j for j in jumps if j[0] >= 10]
            new = [r for r in cur if (r['title'], r['artist']) not in prev]
            print("급상승(10계단+): " + ", ".join(f"{r['artist']}-{r['title']}({d:+d}→{r['rank']}위)" for d, r in sorted(jumps, key=lambda x: -x[0])[:5]) or "급상승: 없음")
            print("신규 진입: " + ", ".join(f"{r['artist']}-{r['title']}({r['rank']}위)" for r in new[:5]) or "신규 진입: 없음")
        print()


POSTS = ROOT / "data" / "community_posts.csv"
POST_COLS = ["collected_at", "site", "issue", "tone", "posted", "reaction", "url", "chars", "text"]


def cmd_export(args):
    import json
    items = json.load(open(args.json, encoding="utf-8"))
    now = dt.datetime.now(KST)
    stamp = now.strftime("%Y-%m-%d %H:%M")
    seen = load_seen()
    # 차트 글은 같은 차트 URL을 매번 쓰므로 중복 검사·기록 대상에서 뺀다
    is_chart = lambda x: "차트" in x["site"]
    items = [x for x in items if is_chart(x) or norm_url(x["url"]) not in seen]
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
    label = args.prefix if args.prefix in ("꿀팁", "아이돌") else "연예"
    out = ROOT / "outputs" / f"{now:%Y-%m-%d}-커뮤니티-{label}-X글.md"
    if label == "연예" and (ROOT / "outputs" / f"{now:%Y-%m-%d}-커뮤니티-X글.md").exists():
        out = ROOT / "outputs" / f"{now:%Y-%m-%d}-커뮤니티-X글.md"  # 기존 파일명 유지
    with out.open("a", encoding="utf-8") as f:
        if out.stat().st_size == 0:
            f.write(f"# 커뮤니티 {label} 화제글 → X 초안 ({now:%Y-%m-%d})\n")
        f.write(f"\n## {now:%H:%M} 수집분 ({len(items)}건)\n")
        for i, x in enumerate(items, 1):
            f.write(f"\n### {i}. [{x['site']}] {x['issue']} ({x['tone']}, {len(x['text'])}자)\n")
            f.write(f"- 작성: {x['posted']} | 반응: {x['reaction']}\n\n```text\n{x['text']}\n```\n")
    # 모바일용: 건별 txt (복사해서 바로 붙여넣기)
    tdir = ROOT / "outputs" / "txt" / f"{now:%Y-%m-%d}"
    tdir.mkdir(parents=True, exist_ok=True)
    for i, x in enumerate(items, 1):
        safe = re.sub(r"[^\w가-힣]+", "_", x["issue"]).strip("_")[:30]
        (tdir / f"{now:%H%M}_{args.prefix}{i:02d}_{safe}.txt").write_text(x["text"] + "\n", encoding="utf-8")
    # 중복 방지 기록
    for x in items:
        if is_chart(x):
            continue
        args.urls = [x["url"]] + x.get("related", [])
        args.issue = x["issue"]
        cmd_mark(args)
    print(f"저장: {out.relative_to(ROOT)} / {POSTS.relative_to(ROOT)} ({len(items)}건)")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("list"); a.add_argument("--limit", type=int, default=15, help="사이트별 개수"); a.add_argument("--mode", choices=["celeb", "tips", "idol"], default="celeb"); a.set_defaults(fn=cmd_list)
    b = sp.add_parser("body"); b.add_argument("urls", nargs="+"); b.add_argument("--chars", type=int, default=600); b.set_defaults(fn=cmd_body)
    c = sp.add_parser("mark"); c.add_argument("urls", nargs="+"); c.add_argument("--issue", default=""); c.set_defaults(fn=cmd_mark)
    g = sp.add_parser("chart"); g.add_argument("--top", type=int, default=10); g.set_defaults(fn=cmd_chart)
    e = sp.add_parser("export"); e.add_argument("json"); e.add_argument("--prefix", default="연예", help="연예 / 꿀팁 / 아이돌"); e.set_defaults(fn=cmd_export)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
