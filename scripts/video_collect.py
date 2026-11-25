#!/usr/bin/env python3
"""동물·음식 영상 수집기 (틱톡 워터마크 없는 원본).

명령:
  meta URL [URL ...]                 조회수·좋아요·길이·업로드일·계정 확인 (이미 받은 영상은 [중복] 표시)
  get  URL --cat 동물|음식 --title "한글 제목" [--still]
                                     워터마크 없는 원본 다운로드 → X 호환 H.264 mp4로 변환
                                     → outputs/videos/날짜/ 에 mp4 + 출처 txt 저장, 중복 기록
                                     --still : 대표 장면 jpg(짤)도 같이 저장
  pack                               오늘 폴더에서 마지막 zip 이후 새로 받은 mp4·jpg·txt를 zip 하나로 묶기
  seen                               지금까지 받은 영상 목록

틱톡은 yt-dlp의 원본 스트림(format_note에 watermarked 없는 것)을 받는다.
유튜브는 영상 서버(googlevideo) 접속이 막혀서 다운로드 불가.
"""
import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEEN = ROOT / "data" / "video_seen.csv"
KST = dt.timezone(dt.timedelta(hours=9))
YTDLP = ["yt-dlp", "--impersonate", "chrome", "--no-warnings"]


def vid_id(url):
    m = re.search(r"/video/(\d+)", url)
    return m.group(1) if m else url


def load_seen():
    if not SEEN.exists():
        return {}
    with SEEN.open(encoding="utf-8") as f:
        return {r["id"]: r for r in csv.DictReader(f)}


def info(url):
    out = subprocess.run(YTDLP + ["-j", url], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip().splitlines()[-1] if out.stderr else "실패")
    return json.loads(out.stdout)


def fmt_n(n):
    if n is None:
        return "확인 불가"
    return f"{n/10000:.1f}만" if n >= 10000 else str(n)


def cmd_meta(args):
    seen = load_seen()
    print("dup\tupload\tviews\tlikes\tsec\tuploader\ttitle\turl")
    for u in args.urls:
        try:
            d = info(u)
        except Exception as e:
            print(f"ERR\t\t\t\t\t\t{e}\t{u}")
            continue
        nowm = any(f.get("format_note") != "watermarked" and f.get("vcodec") not in (None, "none")
                   for f in d.get("formats", []))
        dup = "[중복]" if vid_id(u) in seen else ("" if nowm else "[워터마크만]")
        print(f"{dup}\t{d.get('upload_date','')}\t{d.get('view_count')}\t{d.get('like_count')}\t"
              f"{round(d.get('duration') or 0)}\t@{d.get('uploader','')}\t{(d.get('title') or '')[:50]}\t{d.get('webpage_url', u)}")


def pick_format(d):
    """워터마크 없는 영상 중 해상도 높은 것 (같으면 h264 우선)."""
    cands = [f for f in d.get("formats", [])
             if f.get("format_note") != "watermarked" and f.get("vcodec") not in (None, "none")]
    if not cands:
        return None
    cands.sort(key=lambda f: ((f.get("height") or 0), 1 if (f.get("vcodec") or "").startswith("h264") else 0),
               reverse=True)
    return cands[0]["format_id"]


def cmd_get(args):
    seen = load_seen()
    vid = vid_id(args.url)
    if vid in seen and not args.force:
        print(f"이미 받은 영상: {seen[vid]['file']}")
        return
    d = info(args.url)
    fid = pick_format(d)
    if not fid:
        print("워터마크 없는 원본 스트림이 없음 → 건너뜀")
        return
    now = dt.datetime.now(KST)
    outdir = ROOT / "outputs" / "videos" / f"{now:%Y-%m-%d}"
    outdir.mkdir(parents=True, exist_ok=True)
    nums = [int(m.group(1)) for p in outdir.glob(f"{args.cat}_*.mp4")
            if (m := re.match(rf"{args.cat}_(\d+)_", p.name))]
    n = max(nums, default=0) + 1  # 중간 파일을 지워도 번호가 겹치지 않게
    safe = re.sub(r"[^\w가-힣]+", "_", args.title).strip("_")[:30]
    up = d.get("uploader") or "unknown"
    up_safe = re.sub(r"[^\w.]+", "_", up)
    # 파일 이름에 출처 계정 포함: 동물_01_제목_@계정 (계정에 '.'이 있어 with_suffix 대신 문자열로 붙임)
    base = outdir / f"{args.cat}_{n:02d}_{safe}_@{up_safe}"
    F = lambda ext: base.parent / f"{base.name}{ext}"
    raw = F(".raw.mp4")
    r = subprocess.run(YTDLP + ["-f", fid, "-o", str(raw), args.url], capture_output=True, text=True, timeout=300)
    if r.returncode != 0 or not raw.exists():
        print("다운로드 실패:", r.stderr.strip().splitlines()[-1:] if r.stderr else "")
        return
    mp4 = F(".mp4")
    # X 호환: H.264 + AAC, 최대 1080x1920, faststart
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "26", "-vf", "scale='min(720,iw)':-2", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart",
                    "-metadata", f"title={args.title} (출처 @{up})", "-metadata", f"artist=@{up}",
                    "-metadata", f"comment=출처: @{up} / 원본: {d.get('webpage_url', args.url)}", str(mp4)], check=True)
    raw.unlink()
    if args.still:  # 짤 후보 5장 뽑고, 선명도 상위 3장만 남김 (동물이 있는지는 sheet로 한 번에 확인)
        from PIL import Image, ImageFilter, ImageStat
        dur = d.get("duration") or 4
        cands = []
        for i, r_ in enumerate((0.15, 0.35, 0.5, 0.65, 0.85), 1):
            jp = base.parent / f"{base.name}_후보{i}.jpg"
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(round(dur * r_, 1)), "-i", str(mp4),
                            "-frames:v", "1", "-q:v", "2", str(jp)], check=True)
            g = Image.open(jp).convert("L"); g.thumbnail((360, 640))
            cands.append((ImageStat.Stat(g.filter(ImageFilter.FIND_EDGES)).var[0], jp))
        cands.sort(reverse=True)
        for k, (_, jp) in enumerate(cands):
            if k < 3:
                jp.rename(base.parent / f"{base.name}_짤{k+1}.jpg")
            else:
                jp.unlink()
    credit = (f"{args.title}\n\n"
              f"카테고리: {args.cat}\n길이: {round(d.get('duration') or 0)}초\n"
              f"조회수: {fmt_n(d.get('view_count'))} / 좋아요: {fmt_n(d.get('like_count'))}\n"
              f"업로드: {d.get('upload_date','')}\n출처: @{d.get('uploader','')}\n원본: {d.get('webpage_url', args.url)}\n")
    F(".txt").write_text(credit, encoding="utf-8")
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    new = not SEEN.exists()
    with SEEN.open("a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["id", "url", "cat", "title", "views", "sec", "uploader", "file", "saved_at"])
        w.writerow([vid, d.get("webpage_url", args.url), args.cat, args.title, d.get("view_count"),
                    round(d.get("duration") or 0), d.get("uploader"), str(mp4.relative_to(ROOT)),
                    now.strftime("%Y-%m-%d %H:%M")])
    size = mp4.stat().st_size / 1e6
    print(f"저장: {mp4.relative_to(ROOT)} ({size:.1f}MB)" + (" + 짤 jpg" if args.still else ""))


def cmd_pack(args):
    import zipfile
    now = dt.datetime.now(KST)
    d = ROOT / "outputs" / "videos" / (args.date or f"{now:%Y-%m-%d}")
    if not d.exists():
        print("오늘 받은 파일 없음"); return
    zips = sorted(d.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    since = zips[-1].stat().st_mtime if zips else 0
    files = sorted(p for p in d.iterdir() if p.suffix in (".mp4", ".jpg", ".txt") and p.stat().st_mtime > since)
    if not files:
        print("새로 묶을 파일 없음"); return
    z = d / f"묶음_{now:%m%d_%H%M}.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:  # mp4는 이미 압축돼 있어서 저장만
        for f in files:
            zf.write(f, f.name)
    print(f"zip: {z.relative_to(ROOT)} ({len(files)}개, {z.stat().st_size/1e6:.1f}MB)")


CREATORS = ROOT / "data" / "creators.csv"
DUR = {"동물": (1, 29), "음식": (15, 55)}


def load_creators():
    """data/creators.csv (handle,cat,blocked). 없으면 seen 기록의 업로더로 시작."""
    rows = {}
    if CREATORS.exists():
        with CREATORS.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows[r["handle"]] = r
    for r in load_seen().values():
        if r.get("uploader") and r["uploader"] not in rows:
            rows[r["uploader"]] = {"handle": r["uploader"], "cat": r["cat"], "blocked": ""}
    with CREATORS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["handle", "cat", "blocked"]); w.writeheader(); w.writerows(rows.values())
    return [r for r in rows.values() if not r.get("blocked")]


def cmd_discover(args):
    """웹 검색 없이: 검증된 계정들의 최근 영상 목록을 훑어 조건 맞는 후보만 출력 (토큰 절약)."""
    import random
    seen = load_seen()
    creators = load_creators()
    random.shuffle(creators)
    out = []
    for c in creators[: args.max_creators]:
        r = subprocess.run(YTDLP + ["--flat-playlist", "-I", f"1:{args.per_creator}", "--print",
                                    "%(id)s\t%(view_count)s\t%(duration)s\t%(title)s",
                                    f"https://www.tiktok.com/@{c['handle']}"],
                           capture_output=True, text=True, timeout=120)
        for line in r.stdout.splitlines():
            try:
                vid, views, sec, title = line.split("\t", 3)
                views, sec = int(views), float(sec)
            except ValueError:
                continue
            lo, hi = DUR[c["cat"]]
            if vid in seen or not (lo <= sec <= hi) or views < args.min_views:
                continue
            if re.search(r"#(ai|sora|aiart|aigenerated)\b", title, re.I):
                continue
            up = dt.datetime.fromtimestamp(int(vid) >> 32, KST).strftime("%Y-%m-%d")  # 틱톡 ID에 업로드 시각이 들어 있음
            out.append((c["cat"], views, int(sec), up, c["handle"], title.replace("\n", " ")[:70],
                        f"https://www.tiktok.com/@{c['handle']}/video/{vid}"))
    print("cat\tviews\tsec\tupload\tuploader\tcaption\turl")
    for cat in DUR:
        per = {}
        picked = []
        for o in sorted([o for o in out if o[0] == cat], key=lambda o: -o[1]):
            if per.get(o[4], 0) >= 2:  # 한 계정은 최대 2개까지만 (다양성)
                continue
            per[o[4]] = per.get(o[4], 0) + 1
            picked.append(o)
        for o in picked[: args.top]:
            print("\t".join(map(str, o)))


def cmd_sheet(args):
    """마지막 zip 이후 새 짤들을 한 장짜리 미리보기(번호 붙임)로 묶어 저장 → 이미지 1장만 보고 고르기"""
    from PIL import Image, ImageDraw
    now = dt.datetime.now(KST)
    d = ROOT / "outputs" / "videos" / f"{now:%Y-%m-%d}"
    zips = sorted(d.glob("*.zip"), key=lambda p: p.stat().st_mtime)
    since = zips[-1].stat().st_mtime if zips else 0
    jpgs = sorted(p for p in d.glob("*_짤*.jpg") if p.stat().st_mtime > since)
    if not jpgs:
        print("새 짤 없음"); return
    th = [Image.open(p).convert("RGB") for p in jpgs]
    for im in th:
        im.thumbnail((200, 356))
    W = sum(im.width for im in th); H = max(im.height for im in th)
    sheet = Image.new("RGB", (W, H + 22), "white"); x = 0; dr = ImageDraw.Draw(sheet)
    for i, im in enumerate(th, 1):
        sheet.paste(im, (x, 22)); dr.text((x + 4, 4), str(i), fill="black"); x += im.width
    out = Path(args.out); sheet.save(out, quality=80)
    print(f"sheet: {out}")
    for i, p in enumerate(jpgs, 1):
        print(f"{i}\t{p.relative_to(ROOT)}")


def cmd_seen(args):
    for r in load_seen().values():
        print(f"{r['saved_at']}\t{r['cat']}\t{r['title']}\t{r['url']}")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    a = sp.add_parser("meta"); a.add_argument("urls", nargs="+"); a.set_defaults(fn=cmd_meta)
    g = sp.add_parser("get"); g.add_argument("url"); g.add_argument("--cat", choices=["동물", "음식"], required=True)
    g.add_argument("--title", required=True); g.add_argument("--still", action="store_true")
    g.add_argument("--force", action="store_true"); g.set_defaults(fn=cmd_get)
    k = sp.add_parser("pack"); k.add_argument("--date", help="YYYY-MM-DD (기본: 오늘)"); k.set_defaults(fn=cmd_pack)
    q = sp.add_parser("discover"); q.add_argument("--max-creators", type=int, default=25)
    q.add_argument("--per-creator", type=int, default=12); q.add_argument("--min-views", type=int, default=100000)
    q.add_argument("--top", type=int, default=8); q.set_defaults(fn=cmd_discover)
    h = sp.add_parser("sheet"); h.add_argument("--out", required=True); h.set_defaults(fn=cmd_sheet)
    s = sp.add_parser("seen"); s.set_defaults(fn=cmd_seen)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
