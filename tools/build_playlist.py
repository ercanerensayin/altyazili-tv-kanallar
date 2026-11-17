#!/usr/bin/env python3
"""Altyazılı TV için kanal listesi üretir.

iptv-org/iptv (streams/*.m3u) ve iptv-org/database (data/*.csv) depolarından,
yalnızca uygulamanın çevirebildiği dillerdeki kanalları alır ve "Dil / Tür"
gruplarına ayırır. Kullanım: build_playlist.py <iptv-dizini> <database-dizini> <çıktı-dizini>
"""
import csv, glob, os, re, sys
from collections import defaultdict

LANGS = [  # (iptv-org kodu, Türkçe ad, dosya adı)
    ("eng", "İngilizce", "ingilizce"), ("deu", "Almanca", "almanca"),
    ("fra", "Fransızca", "fransizca"), ("spa", "İspanyolca", "ispanyolca"),
    ("ita", "İtalyanca", "italyanca"), ("por", "Portekizce", "portekizce"),
    ("nld", "Felemenkçe", "felemenkce"), ("rus", "Rusça", "rusca"),
    ("ara", "Arapça", "arapca"), ("jpn", "Japonca", "japonca"),
]
CATS = {  # sıralama: konuşması net olan türler önde
    "news": "Haber", "documentary": "Belgesel", "education": "Eğitim",
    "science": "Bilim", "business": "Ekonomi", "culture": "Kültür",
    "travel": "Gezi", "outdoor": "Doğa", "cooking": "Yemek",
    "lifestyle": "Yaşam", "auto": "Otomobil", "sports": "Spor",
    "movies": "Film", "series": "Dizi", "entertainment": "Eğlence",
    "comedy": "Komedi", "classic": "Klasik", "family": "Aile",
    "kids": "Çocuk", "animation": "Animasyon", "music": "Müzik",
    "religious": "Dini", "legislative": "Meclis", "public": "Kamu",
    "weather": "Hava durumu", "shop": "Alışveriş", "relax": "Dinlendirici",
    "interactive": "Etkileşimli", "general": "Genel",
}
SKIP_CATS = {"xxx", "shop", "relax", "interactive", "music"}  # konuşma yok / uygunsuz
CAT_ORDER = {c: i for i, c in enumerate(CATS)}

def read_csv(db, name):
    with open(os.path.join(db, "data", name), newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main(iptv, db, out):
    channels = {r["id"]: r for r in read_csv(db, "channels.csv")}
    blocked = {r["channel"] for r in read_csv(db, "blocklist.csv")}
    feeds, main_feed = {}, {}
    for r in read_csv(db, "feeds.csv"):
        langs = [l for l in r["languages"].split(";") if l]
        feeds[(r["channel"], r["id"])] = langs
        if r["is_main"].upper() == "TRUE":
            main_feed[r["channel"]] = langs
    logos = {}
    for r in read_csv(db, "logos.csv"):
        if r["url"] and (r["channel"], r["feed"]) not in logos:
            logos[(r["channel"], r["feed"])] = r["url"]

    wanted = {code for code, _, _ in LANGS}
    entries = defaultdict(list)  # lang -> [(cat, name, block)]
    seen = set()
    for path in sorted(glob.glob(os.path.join(iptv, "streams", "*.m3u"))):
        with open(path, encoding="utf-8", errors="replace") as f:
            lines = [l.rstrip("\n") for l in f]
        opts = []
        info = None
        for line in lines:
            if line.startswith("#EXTINF"):
                info, opts = line, []
            elif line.startswith("#EXTVLCOPT") and info:
                opts.append(line)
            elif line and not line.startswith("#") and info:
                url = line.strip()
                m = re.search(r'tvg-id="([^"]*)"', info)
                tid = m.group(1) if m else ""
                title = info.split(",", 1)[1].strip() if "," in info else url
                info_line, info = info, None
                if not tid or url in seen:
                    continue
                cid, _, fid = tid.partition("@")
                ch = channels.get(cid)
                if not ch or cid in blocked or ch["is_nsfw"].upper() == "TRUE" or ch["closed"]:
                    continue
                langs = feeds.get((cid, fid)) or main_feed.get(cid) or []
                cats = [c for c in ch["categories"].split(";") if c]
                if any(c in SKIP_CATS for c in cats):
                    continue
                cat = min(cats, key=lambda c: CAT_ORDER.get(c, 99)) if cats else "general"
                if cat not in CATS:
                    cat = "general"
                logo = logos.get((cid, fid)) or logos.get((cid, ""), "")
                for lang in langs:
                    if lang not in wanted:
                        continue
                    seen.add(url)
                    entries[lang].append((cat, title, tid, logo, opts, url))

    os.makedirs(out, exist_ok=True)
    total = 0
    all_lines = ["#EXTM3U"]
    summary = []
    for code, tr, slug in LANGS:
        items = sorted(entries[code], key=lambda e: (CAT_ORDER.get(e[0], 99), e[1].lower()))
        lang_lines = ["#EXTM3U"]
        for cat, title, tid, logo, opts, url in items:
            group = f"{tr} / {CATS[cat]}"
            attrs = f'tvg-id="{tid}"' + (f' tvg-logo="{logo}"' if logo else "")
            block = [f'#EXTINF:-1 {attrs} group-title="{group}",{title}', *opts, url]
            lang_lines += block
            all_lines += block
        with open(os.path.join(out, f"{slug}.m3u"), "w", encoding="utf-8") as f:
            f.write("\n".join(lang_lines) + "\n")
        total += len(items)
        summary.append(f"{tr}: {len(items)}")
    with open(os.path.join(out, "altyazili-tv.m3u"), "w", encoding="utf-8") as f:
        f.write("\n".join(all_lines) + "\n")
    print(f"Toplam {total} kanal | " + ", ".join(summary))

if __name__ == "__main__":
    main(*sys.argv[1:4])
