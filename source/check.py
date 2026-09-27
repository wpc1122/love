# -*- coding: utf-8 -*-
import json, urllib.request, sys

base = "http://127.0.0.1:3001"
site = json.load(open("/usr/tools/www/data/site.json", encoding="utf-8"))

print("title   :", site["title"])
print("names   :", site["name1"], "&", site["name2"])
print("together:", site["togetherDate"])
print("hero    :", site["hero"], "| mobile:", site["heroMobile"])
print("photos  :", len(site["photos"]))
print("music   :", [(m["title"], m["url"]) for m in site["music"]])
print("timeline:", [(t["date"], t["title"]) for t in site["timeline"]])

bad = []
urls = [site["hero"], site["heroMobile"]]
for p in site["photos"]:
    urls += [p["src"], p["full"]]
for m in site["music"]:
    urls.append(m["url"])
urls += ["/", "/favicon.svg", "/404.html"]

for u in urls:
    if not u:
        continue
    try:
        req = urllib.request.Request(base + u, method="GET")
        with urllib.request.urlopen(req, timeout=10) as r:
            code = r.status
            size = len(r.read()) if u != "/media/music/沉香.mp3" else r.headers.get("Content-Length")
    except Exception as e:
        code, size = "ERR", str(e)
    flag = "ok " if code == 200 else "FAIL"
    if code != 200:
        bad.append(u)
    print(f"  [{flag}] {code:>4}  {u}  {size}")

print("FAILED:", bad if bad else "none")
sys.exit(1 if bad else 0)
