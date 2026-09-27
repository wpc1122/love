#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
情侣静态站构建脚本
- 从旧站 server/data/*.json 读取个人数据
- 压缩图片为 WebP（缩略图 + 大图 + hero）
- 去重并搬运音乐
- 把数据注入模板生成单文件 index.html
"""
import base64
import json
import hashlib
import shutil
import subprocess
from pathlib import Path

import os
_def = "/usr/tools/www-build/source"
SRC = Path(os.environ.get("LOVE_SRC") or (_def if Path(_def).exists() else "/usr/tools/www"))
BUILD = Path("/usr/tools/www-build")   # 构建源（模板）
OUT = Path("/usr/tools/_new")           # 新站输出


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def read_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception:
        return default


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def lqip(path, w=22, q=38):
    """生成极小缩略图并内联为 base64，用作图片加载前的模糊占位"""
    try:
        p = Path(path)
        if not p.exists():
            return ""
        tmp = Path("/tmp/_lqip.webp")
        r = sh(f'convert "{p}" -strip -resize {w}x\\> -quality {q} "{tmp}"')
        if r.returncode != 0 or not tmp.exists():
            tmp = Path("/tmp/_lqip.jpg")
            sh(f'convert "{p}" -strip -resize {w}x\\> -quality {q} "{tmp}"')
            if not tmp.exists():
                return ""
        mime = "image/webp" if tmp.suffix == ".webp" else "image/jpeg"
        return "data:%s;base64,%s" % (mime, base64.b64encode(tmp.read_bytes()).decode())
    except Exception:
        return ""


def attach_lqip(site, root):
    """为照片与 hero 补上模糊占位（原地修改 site）"""
    root = Path(root)
    n = 0
    for p in site.get("photos", []):
        src = str(p.get("src") or p.get("full") or "").lstrip("/")
        v = lqip(root / src)
        if v:
            p["lqip"] = v
            n += 1
    for key in ("hero", "heroMobile"):
        src = str(site.get(key) or "").lstrip("/")
        v = lqip(root / src)
        if v:
            site[key + "Lqip"] = v
    return n


def webp(src, dst, width, quality):
    """生成 webp；失败则回退为 jpg"""
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = sh(f'convert "{src}" -strip -resize {width}x\\> -quality {quality} "{dst}"')
    if r.returncode != 0 or not dst.exists():
        dst = dst.with_suffix(".jpg")
        sh(f'convert "{src}" -strip -resize {width}x\\> -quality {quality} "{dst}"')
    return dst


def rebuild_from_site(live):
    """素材源缺失时：复用现成的 media/ 与 site.json，只重新生成 index.html"""
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)
    sh(f'cp -al "{live}/media" "{OUT}/media" 2>/dev/null || cp -a "{live}/media" "{OUT}/media"')
    (OUT / "data").mkdir(exist_ok=True)
    shutil.copy2(live / "data" / "site.json", OUT / "data" / "site.json")
    site = read_json(OUT / "data" / "site.json", {})
    site.pop("heroLqip", None)
    site.pop("heroMobileLqip", None)
    attach_lqip(site, OUT)
    (OUT / "data" / "site.json").write_text(
        json.dumps(site, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    emit(site)
    return site


def emit(site):
    """把 site 数据注入模板，生成 index.html 并做语法自检"""
    tpl = (BUILD / "template.html").read_text(encoding="utf-8")
    payload = json.dumps(site, ensure_ascii=False, separators=(",", ":")).replace(
        "</", "<\\/"
    )
    html = tpl.replace("__SITE_DATA__", payload)
    if "__SITE_DATA__" in html:
        raise SystemExit("template placeholder not replaced")

    # 语法自检：node --check 校验内联脚本
    import re as _re
    _m = _re.search(r"<script>(.*?)</script>", html, _re.S)
    if _m:
        tmp = OUT / "_check.js"
        tmp.write_text(_m.group(1), encoding="utf-8")
        r = sh(f"node --check {tmp}")
        tmp.unlink(missing_ok=True)
        if r.returncode != 0:
            raise SystemExit("JS syntax error: " + r.stderr[:400])

    (OUT / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(BUILD / "favicon.svg", OUT / "favicon.svg")
    shutil.copy2(BUILD / "robots.txt", OUT / "robots.txt")
    if (BUILD / "404.html").exists():
        shutil.copy2(BUILD / "404.html", OUT / "404.html")
    size = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(json.dumps({
        "mode": "reuse",
        "photos": len(site.get("photos", [])),
        "music": len(site.get("music", [])),
        "timeline": len(site.get("timeline", [])),
        "lqip": sum(1 for p in site.get("photos", []) if p.get("lqip")),
        "inlineKB": round(
            sum(len(p.get("lqip", "")) for p in site.get("photos", [])) / 1024
        ),
        "htmlKB": round(len(html.encode()) / 1024),
        "totalKB": round(size / 1024),
    }, ensure_ascii=False))


def main():
    data_dir = SRC / "server" / "data"
    uploads = SRC / "uploads"
    live = Path("/usr/tools/www")

    # 若原始素材已不在（旧站已清理），直接用线上站点的 site.json 复用媒体资源
    if not data_dir.exists() and (live / "data" / "site.json").exists():
        return rebuild_from_site(live)

    config = read_json(data_dir / "config.json", {})
    couple = read_json(data_dir / "couple.json", {})
    timeline = read_json(data_dir / "timeline.json", [])
    photos_meta = read_json(data_dir / "photos.json", [])
    music_meta = read_json(data_dir / "music.json", [])

    # 清空输出
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "media" / "photos").mkdir(parents=True, exist_ok=True)
    (OUT / "media" / "music").mkdir(parents=True, exist_ok=True)
    (OUT / "data").mkdir(parents=True, exist_ok=True)

    # ---------- 图片：去重 + 压缩 ----------
    title_map = {}
    for p in photos_meta:
        url = str(p.get("url", ""))
        base = url.rsplit("/", 1)[-1]
        title_map[base] = {
            "title": p.get("title", ""),
            "description": p.get("description", ""),
        }

    seen, photos = {}, []
    files = sorted(
        [f for f in uploads.glob("*.jpg")] + [f for f in uploads.glob("*.png")],
        key=lambda x: x.stat().st_mtime,
    )
    for f in files:
        d = md5(f)
        if d in seen:
            continue
        seen[d] = True
        stem = f.stem[:24]
        small = webp(f, OUT / "media" / "photos" / f"{stem}_s.webp", 720, 74)
        large = webp(f, OUT / "media" / "photos" / f"{stem}_l.webp", 1600, 78)
        meta = title_map.get(f.name, {})
        photos.append(
            {
                "src": "media/photos/" + small.name,
                "full": "media/photos/" + large.name,
                "title": meta.get("title", ""),
                "description": meta.get("description", ""),
            }
        )

    # ---------- hero 背景 ----------
    def hero_from(url, name, w):
        if not url:
            return ""
        base = str(url).rsplit("/", 1)[-1]
        src = uploads / base
        if not src.exists():
            return ""
        out = webp(src, OUT / "media" / f"{name}.webp", w, 78)
        return "media/" + out.name

    hero = hero_from(config.get("hero_background"), "hero", 1920)
    hero_m = hero_from(config.get("hero_background_portrait"), "hero-m", 900) or hero

    # ---------- 音乐：去重 + 搬运 ----------
    seen_m, music = {}, []
    for m in music_meta:
        url = str(m.get("url", ""))
        base = url.rsplit("/", 1)[-1]
        src = uploads / "music" / base
        if not src.exists():
            continue
        d = md5(src)
        if d in seen_m:
            continue
        seen_m[d] = True
        safe = "".join(c for c in (m.get("title") or "song") if c.isalnum() or c in "_-")[:30] or "song"
        dst = OUT / "media" / "music" / f"{safe}.mp3"
        shutil.copy2(src, dst)
        music.append(
            {
                "title": m.get("title", "未命名"),
                "artist": m.get("artist", ""),
                "url": "media/music/" + dst.name,
                "lyrics": m.get("lyrics", "") or "",
            }
        )
    # 未被 music.json 收录但存在于目录中的音频
    for src in sorted((uploads / "music").glob("*.mp3")):
        d = md5(src)
        if d in seen_m:
            continue
        seen_m[d] = True
        dst = OUT / "media" / "music" / src.name
        shutil.copy2(src, dst)
        music.append(
            {
                "title": src.stem,
                "artist": "",
                "url": "media/music/" + dst.name,
                "lyrics": "",
            }
        )

    # ---------- 时间轴 ----------
    tl = sorted(
        [
            {
                "date": t.get("event_date", ""),
                "title": t.get("title", ""),
                "description": t.get("description", ""),
                "icon": t.get("icon", "heart"),
            }
            for t in timeline
            if isinstance(t, dict)
        ],
        key=lambda x: x["date"],
    )

    # ---------- 事件槽位（events20.json：占位可替换，改这个文件再重跑即可） ----------
    slots = read_json(SRC / "events20.json", None) or read_json(BUILD / "events20.json", {})
    if slots.get("enabled") and isinstance(slots.get("events"), list) and slots["events"]:
        name2idx = {}
        for k, p in enumerate(photos):
            base = str(p.get("src") or "").rsplit("/", 1)[-1]
            if base:
                name2idx[base] = k
        new_tl = []
        for ev in slots["events"]:
            if not isinstance(ev, dict):
                continue
            ph = str(ev.get("photo", "") or "").strip()
            gi = None
            if ph:
                if ph.isdigit():
                    c = int(ph)
                    gi = c if 0 <= c < len(photos) else None
                else:
                    gi = name2idx.get(ph.rsplit("/", 1)[-1])
            item = {
                "date": ev.get("date", ""),
                "title": ev.get("title", ""),
                "description": ev.get("description", ""),
            }
            if gi is not None:
                item["photoGi"] = gi
            new_tl.append(item)
        if new_tl:
            tl = sorted(new_tl, key=lambda x: x["date"])

    site = {
        "title": config.get("site_title") or "我们的小站",
        "subtitle": config.get("site_subtitle") or "记录我们的爱情故事",
        "footer": config.get("footer_text")
        or f"© {couple.get('name1','')} & {couple.get('name2','')}",
        "primary": config.get("primary_color") or "#fb7185",
        "secondary": config.get("secondary_color") or "#c4b5fd",
        "hero": hero,
        "heroMobile": hero_m,
        "name1": couple.get("name1", ""),
        "name2": couple.get("name2", ""),
        "description": couple.get("description", ""),
        "story": couple.get("story", ""),
        "togetherDate": couple.get("together_date", ""),
        "anniversaryDate": couple.get("anniversary_date", ""),
        "countdownTitle": config.get("countdown_title") or "我们在一起已经",
        "galleryTitle": config.get("gallery_title") or "甜蜜瞬间",
        "timelineTitle": config.get("timeline_title") or "爱情旅程",
        "photos": photos,
        "music": music,
        "timeline": tl,
    }

    # ---------- 模糊占位（LQIP） ----------
    n_lqip = attach_lqip(site, OUT)

    # 保存原始数据副本，便于日后重新构建
    (OUT / "data" / "site.json").write_text(
        json.dumps(site, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    emit(site)


if __name__ == "__main__":
    main()
