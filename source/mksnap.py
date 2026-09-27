#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成截图辅助页：加载后自动滚动到第 N 个时间轴事件。"""
import sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 1
s = open("/usr/tools/www/_many.html", encoding="utf-8").read()
inj = (
    "<script>(function(){"
    "document.documentElement.style.scrollBehavior='auto';"
    "function show(){document.querySelectorAll('.reveal,.tl-item').forEach(function(el){el.classList.add('in')});}"
    "function go(){var it=document.querySelectorAll('.tl-item')[%d];"
    "if(!it)return;var y=it.getBoundingClientRect().top+scrollY-innerHeight*0.45;"
    "scrollTo(0,y);dispatchEvent(new Event('scroll'));}"
    "setTimeout(show,200);setTimeout(go,300);setTimeout(go,900);setTimeout(go,1800);})();</script>" % (N - 1)
)
open("/usr/tools/www/_snap.html", "w", encoding="utf-8").write(s + inj)
print("snap ->", N)
