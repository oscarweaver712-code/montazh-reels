#!/usr/bin/env python3
"""Проверка страницы графики до рендера: ничего не залипнет на экране, все ассеты на месте.

Пара к verify_render.py: тот смотрит готовый mp4, этот — страницу, пока рендер ещё не
потрачен. Ловит то, что глазами по снимкам не видно:

  • элемент залипает. Рендер HyperFrames шагает по таймлайну кадр за кадром, а GSAP
    рисует на каждом шаге только те твины, у которых что-то сдвинулось. Если уход
    (set или короткий to) срабатывает, пока появление ещё доигрывает, на следующем кадре
    появление дописывает opacity 1, а уход больше не перерисовывается — слово висит до
    конца ролика, следующие бегут поверх. Снимок прыгает сразу в нужное время, рисует
    твины по порядку, и там всё чисто — поэтому только снимкам верить нельзя;
  • запас по кадрам. То же перекрытие, которое сейчас проскакивает между кадрами: сдвинь
    дубль на кадр — и залипнет. Это тоже ошибка, а не везение;
  • ошибка JS на странице, селектор, который ничего не нашёл, картинка или звук по
    несуществующему пути;
  • звуки: громче нормы (замер файла + громкость на странице), убранный звук, одно семейство
    подряд, файл больше двух раз (правила Валеры, 12.10.2026). Страницу, собранную до этих норм,
    рендер не возьмёт — её page.py надо пересобрать; сводка --all такие только помечает.

Как проверяется: страница открывается в том же headless Chrome, которым рендерит
HyperFrames, видео и звук отключены. Таймлайн прогоняется трижды — по кадрам, как рендер;
по кадрам плюс точки сразу после каждой границы твина; прыжком из нуля в каждый кадр,
как снимок. Прозрачность, которая расходится с прыжком, и есть залипание.

  .venv/bin/python scripts/verify_page.py IMG_3317
  .venv/bin/python scripts/verify_page.py --all
"""
import argparse
import html
import json
import math
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT, WORK_DIR

STUDIO = ROOT / "studio"
CHROME_CACHE = Path.home() / ".cache" / "hyperframes" / "chrome" / "chrome-headless-shell"
FPS = 30
SPLICE_JUMP = 0.1    # на склейке крупность меняется хотя бы на столько (1.2 → 1.36 у Take.splice_punches)
HOLD_MAX = 5.0      # с: дольше графика без изменений — динамика проседает (Валера 13.10, IMG_1803)
FOOTAGE_MAX = 2     # ИИ-видео на ролик (Валера 17.10: «генерации видео в одном видео 1-2 в самых топовых местах, не больше»)
SOFT_EVERY = 6.0    # с: тихий звук монтажа не реже раза за это время (rules.md п.9; принятый IMG_3303 v5 — раз в 2,4 с)
MONTAGE_MARK = '<meta name="reels-montage"'
CAP_GAP_MAX = 3.0   # с: дольше речь без субтитров не идёт (Валера 16.10, IMG_3303 v3: «надолго пропали»)
ACCENT_EVERY = 12.0  # с: дольше субтитры без ключевого слова — «одинаково скучно идут» (Валера 19.10, IMG_3292 v2)

# Ставится до скриптов страницы: реестр таймлайнов (его даёт рантайм HyperFrames,
# без него страница падает на первой же строке) и сбор ошибок и предупреждений GSAP.
EARLY_JS = """
      window.__timelines = {};
      window.addEventListener("error", (e) => window.__HF_CHECK.errors.push(
        `${e.message} (${String(e.filename || "").split("/").pop()}:${e.lineno || "?"})`));
      const warn = console.warn.bind(console);
      console.warn = (...a) => { window.__HF_CHECK.warnings.push(a.map(String).join(" ")); warn(...a); };
"""

# Ставится после скрипта страницы. Результат пишется в <pre id="hf-check"> — его и
# забирает --dump-dom.
CHECK_JS = r"""
(() => {
  const C = window.__HF_CHECK;
  const res = { pageErrors: C.errors, warnings: C.warnings, stuck: [], risky: [], never: [] };
  const started = performance.now();
  try {
    const tl = (window.__timelines || {}).main;
    if (!tl) throw new Error("на странице нет таймлайна window.__timelines.main");
    const root = document.querySelector("[data-composition-id]");
    const duration = parseFloat(root && root.getAttribute("data-duration")) || tl.duration();
    const fps = C.fps;

    // ---- твины, которые трогают прозрачность; остальные (камера — тысячи ключей) не нужны
    const hasOpacity = (v) => !!v && typeof v === "object" && ("opacity" in v || "autoAlpha" in v);
    const touches = (v) => {
      if (!v) return false;
      if (hasOpacity(v) || hasOpacity(v.startAt)) return true;
      const kf = v.keyframes;
      if (Array.isArray(kf)) return kf.some(hasOpacity);
      return !!kf && typeof kf === "object" && (hasOpacity(kf) || Object.values(kf).some(hasOpacity));
    };
    const byEl = new Map();
    const idle = [];
    let tweens = 0;
    const walk = (timeline, offset) => {
      for (const child of timeline.getChildren(false, true, true)) {
        const start = offset + child.startTime();
        if (typeof child.getChildren === "function") { walk(child, start); continue; }
        if (!touches(child.vars)) {
          // смаз кадра на склейке (splice) нужен проверке склеек — его не глушим
          const camBlur = child.vars && "filter" in child.vars && child.targets().some((el) => el.classList && el.classList.contains("cam"));
          // движение сцены (#stage: сплит «Чертежа», отъезд, пролёт) двигает лицо — без него проверка лица видела
          // человека на старом месте, а лист сплита — «на лице» (19.10.2026)
          const stage = child.targets().some((el) => el.id === "stage");
          if (!camBlur && !stage) idle.push(child);
          continue;
        }
        if (child.timeline) { walk(child.timeline, start); continue; }     // stagger, keyframes
        tweens++;
        const v = child.vars;
        const tw = { start, end: start + child.totalDuration(),
                     kind: child.duration() === 0 ? "set" : (v.startAt ? "fromTo" : "to"),
                     to: v.opacity ?? v.autoAlpha ?? null };
        for (const el of child.targets()) {
          if (!(el instanceof Element)) continue;
          if (!byEl.has(el)) byEl.set(el, []);
          byEl.get(el).push(tw);
        }
      }
    };
    walk(tl, 0);
    idle.forEach((t) => t.kill());

    const label = (el) => {
      if (el.id) return "#" + el.id;
      if (el.classList.contains("cap")) return `субтитр «${el.textContent}»`;
      let p = el.parentElement;
      while (p && !p.id) p = p.parentElement;
      const cls = typeof el.className === "string" && el.className.trim()
        ? "." + el.className.trim().split(/\s+/).join(".") : "";
      const nth = el.parentElement ? [...el.parentElement.children].indexOf(el) + 1 : 1;
      return `${p ? "#" + p.id + " " : ""}${el.tagName.toLowerCase()}${cls}:nth-child(${nth})`;
    };
    const els = [...byEl.keys()];
    // Пока GSAP не тронул элемент, его прозрачность — из CSS; читать computed на каждом
    // кадре дорого, поэтому он запоминается один раз.
    const base = els.map((el) => parseFloat(getComputedStyle(el).opacity));
    const snap = () => Float32Array.from(els, (el, i) => {
      const s = el.style.opacity;
      return s === "" ? base[i] : parseFloat(s);
    });

    const N = Math.max(1, Math.round(duration * fps));
    const at = (k) => k / fps;
    // рендер HyperFrames шагает totalTime(t, false), не подавляя события. Это важно: set,
    // попавший ровно в кадр, при подавленных событиях перерисовывается ещё раз и прячет
    // залипание, а в настоящем рендере — нет (IMG_3309, «то» на 18.80)
    const real = [];
    for (let k = 0; k < N; k++) { tl.totalTime(at(k), false); real.push(snap()); }

    // те же кадры плюс точки сразу после каждой границы твина: так выглядел бы рендер,
    // если бы дубль сдвинулся и кадр попал в щель между уходом и концом появления
    const times = [];
    for (let k = 0; k < N; k++) times.push([at(k), k]);
    for (const list of byEl.values()) {
      for (const tw of list) {
        for (const t of [tw.start + 1e-4, tw.end + 1e-4]) if (t > 0 && t < duration) times.push([t, -1]);
      }
    }
    times.sort((a, b) => a[0] - b[0]);
    tl.totalTime(0, false);
    const edge = new Array(N);
    for (const [t, k] of times) { tl.totalTime(t, false); if (k >= 0) edge[k] = snap(); }

    // эталон: прыжок из нуля, как делает снимок — твины рисуются строго по порядку
    const ref = new Array(N);
    for (let k = 0; k < N; k++) { tl.totalTime(0, false); tl.totalTime(at(k), false); ref[k] = snap(); }

    const why = (list, t) => {
      // твин, который стоит раньше, а доигрывает позже следующего, — он и перебивает уход
      const near = list.filter((tw) => tw.start <= t + 1e-6).sort((a, b) => a.start - b.start);
      for (let i = 0; i < near.length; i++) {
        for (let j = i + 1; j < near.length; j++) {
          if (near[i].end > near[j].end + 1e-6) return { a: near[i], b: near[j] };
        }
      }
      return null;
    };
    const runs = (pass, seen) => {
      const found = [];
      els.forEach((el, i) => {
        if (seen && seen.has(el)) return;
        let k0 = -1;
        for (let k = 0; k <= N; k++) {
          const bad = k < N && Math.abs(pass[k][i] - ref[k][i]) > 0.05;
          if (bad && k0 < 0) k0 = k;
          if (!bad && k0 >= 0) {
            const list = byEl.get(el);
            found.push({ el: label(el), from: at(k0), to: at(k), got: pass[k0][i], want: ref[k0][i],
                         why: why(list, at(k0)), first: list[0].start });
            seen && seen.add(el);
            k0 = -1;
            if (seen) break;
          }
        }
      });
      return found;
    };
    const flagged = new Set();
    res.stuck = runs(real, flagged);
    res.risky = runs(edge, flagged);

    // ---- серые зоны площадок (formats.GREY_ZONES): буквы, которые стоят под их интерфейсом.
    // Меряются сами строки текста (Range), а не рамка блока: широкий блок с коротким словом по
    // центру — не заезд. Кадр — прыжком, как снимок, шаг C.zoneStep. Заезд на время входа
    // («впечатывание» с увеличением) не в счёт: только два замера подряд и глубже C.zoneDepth px.
    // data-safe="причина" на элементе или предке — осознанный заезд, отдельным списком.
    res.grey = []; res.greyAllowed = [];
    const zones = C.zones || [];
    if (zones.length) {
      const items = [];
      document.querySelectorAll(".g, .cap").forEach((el) => {
        const nodes = [];
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const n = walker.currentNode;
          // текст вложенного .g проверяется у него самого
          if (n.textContent.trim() && n.parentElement.closest(".g, .cap") === el) nodes.push(n);
        }
        if (nodes.length) {
          const safe = el.closest("[data-safe]");
          // окно с overflow: hidden (бегущая лента букв) прячет то, что за его краем, — там букв не видно
          const clips = [];
          for (let p = nodes[0].parentElement; p && p.id !== "root" && p !== document.body; p = p.parentElement) {
            if (getComputedStyle(p).overflow !== "visible") clips.push(p);
          }
          // data-safe-zones="низ" — осознанно только в этих зонах (начало названия), в остальных — заезд (19.10.2026:
          // «Чертёж» на груди прощал себе и боковую обрезку — подпись ушла за край, а проверка молчала)
          const only = safe && safe.getAttribute("data-safe-zones");
          items.push({ el, nodes, clips, allowed: safe ? safe.getAttribute("data-safe") : null,
                       zonesOk: only ? only.split(",").map((z) => z.trim()) : null });
        }
      });
      const visible = (el) => {
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.15) return false;
        }
        return true;
      };
      const step = C.zoneStep || 0.25, minDepth = C.zoneDepth || 8;
      const open = new Map(), done = [];
      const range = document.createRange();
      for (let t = 0; t < duration; t += step) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        const seen = new Set();
        for (const it of items) {
          if (!visible(it.el)) continue;
          // по высоте строка не выше рамки элемента: у крупного шрифта с плотной строкой (Oswald,
          // line-height 0.92) «область шрифта» выше заглавных — пустая полоса, а не буквы (IMG_1803 v4)
          const box = it.el.getBoundingClientRect();
          const cuts = it.clips.map((c) => c.getBoundingClientRect());
          for (const node of it.nodes) {
            range.selectNodeContents(node);
            for (const raw of range.getClientRects()) {
              const r = { left: raw.left, right: raw.right,
                          top: Math.max(raw.top, box.top), bottom: Math.min(raw.bottom, box.bottom) };
              for (const c of cuts) {
                r.left = Math.max(r.left, c.left); r.right = Math.min(r.right, c.right);
                r.top = Math.max(r.top, c.top); r.bottom = Math.min(r.bottom, c.bottom);
              }
              if (r.right - r.left < 2 || r.bottom - r.top < 2) continue;
              for (const z of zones) {
                const [x0, y0, x1, y1] = z.rect;
                const dx = Math.min(r.right, x1) - Math.max(r.left, x0);
                const dy = Math.min(r.bottom, y1) - Math.max(r.top, y0);
                const depth = Math.min(dx, dy);
                if (dx <= 0 || dy <= 0 || depth < minDepth) continue;
                const key = label(it.el) + "|" + z.name;
                if (seen.has(key)) { open.get(key).depth = Math.max(open.get(key).depth, Math.round(depth)); continue; }
                seen.add(key);
                const rec = open.get(key);
                if (rec) { rec.last = t; rec.count++; rec.depth = Math.max(rec.depth, Math.round(depth)); }
                else open.set(key, { el: label(it.el), zone: z.name, from: t, last: t, count: 1,
                                     depth: Math.round(depth), text: node.textContent.trim().slice(0, 40),
                                     allowed: it.zonesOk && !it.zonesOk.some((ok) => z.name.startsWith(ok)) ? null : it.allowed });
              }
            }
          }
        }
        for (const [key, rec] of [...open]) if (!seen.has(key)) { if (rec.count >= 2) done.push(rec); open.delete(key); }
      }
      for (const rec of open.values()) if (rec.count >= 2) done.push(rec);
      for (const rec of done) (rec.allowed ? res.greyAllowed : res.grey).push(rec);
    }

    // ---- фон за спиной (жалоба Валеры 12.10.2026: «фоны низкокачественные какие-то»): картинка во весь
    // кадр (#plate и всё в #behind с картинкой шире 900 px), видимая целиком, не должна стоять размытой —
    // в IMG_1803 v4 фон держал blur(2px) весь показ. Размытие в наплыве и уходе — да: считается только
    // от секунды подряд (4 замера по 0.25 с). data-safe="причина" — осознанно мягкий фон.
    res.softBg = [];
    const blurOf = (n) => { const m = /blur\(([\d.]+)px\)/.exec(getComputedStyle(n).filter || ""); return m ? parseFloat(m[1]) : 0; };
    const backs = [...document.querySelectorAll("#plate, #behind > *")].filter((el) => {
      const img = el.tagName === "IMG" ? el : el.querySelector("img");
      return img && img.getBoundingClientRect().width >= 900;
    });
    if (backs.length) {
      const open = new Map();
      for (let t = 0; t <= duration; t += 0.25) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        for (const el of backs) {
          let alpha = 1, soft = 0;
          for (let n = el; n && n !== document.body; n = n.parentElement) {
            alpha *= parseFloat(getComputedStyle(n).opacity);
            soft = Math.max(soft, blurOf(n));
          }
          el.querySelectorAll("img").forEach((img) => { soft = Math.max(soft, blurOf(img)); });
          const key = label(el), rec = open.get(key);
          if (alpha >= 0.9 && soft > 0.5) {
            if (rec) { rec.last = t; rec.count++; rec.blur = Math.max(rec.blur, soft); }
            else open.set(key, { el: key, from: t, last: t, count: 1, blur: soft,
                                 allowed: el.closest("[data-safe]") ? el.closest("[data-safe]").getAttribute("data-safe") : null });
          } else if (rec) { if (rec.count >= 4) res.softBg.push(rec); open.delete(key); }
        }
      }
      for (const rec of open.values()) if (rec.count >= 4) res.softBg.push(rec);
    }

    // ---- лицо (правило Валеры 12.10.2026: «карточки никогда не должны перекрывать лицо»): рамка
    // каждого видимого элемента поверх человека (#front .g — карточки, таблицы, плашки) против
    // рамки лица в этот момент (C.faces: [t, x0, y0, x1, y1] — по слежению и движению камеры).
    // Два замера подряд глубже 10 px — заезд. Единственное «не заезд»: пока виден ИИ-футаж во весь кадр
    // (kit.footage, класс .footage, 16.10.2026) — лица на экране нет вовсе: план сменили, а не закрыли.
    res.faceHits = [];
    // перебивка (ИИ-футаж, серия картинок) идёт без человека поверх: вырезка на ней кривая (Валера 16.10).
    // Окно вырезки, попавшее на перебивку, — ошибка: человек проступит поверх футажа
    res.fgOverCut = [];
    {
      const cuts = [...document.querySelectorAll(".footage")];
      const fg = document.getElementById("cam-fg");
      if (cuts.length && fg) {
        for (let t = 0; t <= duration + 1e-6; t += 0.25) {
          tl.totalTime(0, false); tl.totalTime(t, false);
          const shown = (el) => { for (let n = el; n && n !== document.body; n = n.parentElement)
            if (parseFloat(getComputedStyle(n).opacity) < 0.5) return false; return true; };
          if (cuts.some(shown) && parseFloat(getComputedStyle(fg).opacity) > 0.1) res.fgOverCut.push(+t.toFixed(2));
        }
      }
    }
    // где виден человек поверх (#cam-fg с вырезкой): с 22.10.2026 маска считается только там (matte.py --windows) —
    // окно, под которым маски нет, показало бы пустоту вместо человека, а текст за спиной встал бы поверх лица
    res.fgShown = [];
    {
      const fg = document.getElementById("cam-fg");
      if (fg && document.getElementById("cutout")) {
        const shown = () => { for (let n = fg; n && n !== document.body; n = n.parentElement)
          if (parseFloat(getComputedStyle(n).opacity) <= 0.1) return false; return true; };
        let open = null;
        tl.totalTime(0, false);
        for (let k = 0; k <= Math.round(duration * fps); k++) {
          const t = k / fps;
          tl.totalTime(t, false);
          if (shown()) { if (open === null) open = t; }
          else if (open !== null) { res.fgShown.push([+open.toFixed(3), +t.toFixed(3)]); open = null; }
        }
        if (open !== null) res.fgShown.push([+open.toFixed(3), +duration.toFixed(3)]);
      }
    }
    // доля ролика с человеком в кадре (Валера 19.10.2026: «хочу, чтобы в 50+% видео было моё лицо — личный бренд
    // качаем»): сколько замеров видна перебивка во весь кадр (футаж, серия картинок, чертёж data-fullframe)
    res.cutawayShare = 0;
    {
      const cuts = [...document.querySelectorAll(".footage, [data-fullframe]")];
      if (cuts.length) {
        const box = document.getElementById("root").getBoundingClientRect();
        const full = (el) => {
          for (let n = el; n && n !== document.body; n = n.parentElement)
            if (parseFloat(getComputedStyle(n).opacity) < 0.5) return false;
          const r = el.getBoundingClientRect();
          return r.width * r.height >= 0.95 * box.width * box.height;
        };
        let all = 0, hit = 0;
        for (let t = 0; t <= duration + 1e-6; t += 0.25, all++) {
          tl.totalTime(0, false); tl.totalTime(t, false);
          if (cuts.some(full)) hit++;
        }
        res.cutawayShare = hit / Math.max(1, all);
      }
    }
    const faces = C.faces || [];
    if (faces.length) {
      const fronts = [...document.querySelectorAll("#front .g")].filter((el) => el.id !== "flash");
      const vis = (el) => {
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.15) return false;
        }
        return true;
      };
      const open = new Map();
      const root = document.getElementById("root").getBoundingClientRect();
      // сцена в обёртке #stage (fx: отъезд, пролёт; «Чертёж» в сплите — человек в окне внизу листа, 19.10.2026):
      // лицо по камере — в координатах сцены, на экран его переводит текущая матрица обёртки
      const stageEl = document.getElementById("stage");
      const onScreen = (x0, y0, x1, y1) => {
        if (!stageEl) return [x0, y0, x1, y1];
        const tf = getComputedStyle(stageEl).transform;
        if (!tf || tf === "none") return [x0, y0, x1, y1];
        const m = new DOMMatrixReadOnly(tf), a = m.transformPoint({ x: x0, y: y0 }), b = m.transformPoint({ x: x1, y: y1 });
        return [Math.min(a.x, b.x), Math.min(a.y, b.y), Math.max(a.x, b.x), Math.max(a.y, b.y)];
      };
      const cutaways = [...document.querySelectorAll(".footage")];     // футаж и серия картинок — в любом слое
      const cutaway = () => cutaways.some((el) => {
        if (!el.classList.contains("footage") || !vis(el)) return false;
        const r = el.getBoundingClientRect();
        return r.width * r.height >= 0.95 * root.width * root.height;
      });
      for (const [t, ...box] of faces) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        const [fx0, fy0, fx1, fy1] = onScreen(...box);
        const seen = new Set();
        if (cutaway()) continue;          // футаж во весь кадр: лица нет — замер пропускается, открытые заезды ждут
        // субтитры — тоже: не на лице и не вплотную к подбородку (Валера 16.10: «сабы ниже подбородка, с отступом»)
        for (const el of [...fronts, ...document.querySelectorAll("#caps .cap")]) {
          if (!vis(el)) continue;
          const cap = el.classList.contains("cap");
          const r = el.getBoundingClientRect();
          const dx = Math.min(r.right, fx1) - Math.max(r.left, fx0);
          const dy = Math.min(r.bottom, fy1 + (cap ? 30 : 0)) - Math.max(r.top, fy0);
          if (dx <= 10 || dy <= 10) continue;
          const key = label(el);
          seen.add(key);
          const rec = open.get(key);
          if (rec) { rec.last = t; rec.count++; rec.depth = Math.max(rec.depth, Math.round(Math.min(dx, dy)));
                     rec.faceBottom = Math.max(rec.faceBottom, Math.round(fy1)); }
          else open.set(key, { el: key, from: t, last: t, count: 1, depth: Math.round(Math.min(dx, dy)),
                               faceBottom: Math.round(fy1), top: Math.round(r.top) });
        }
        for (const [key, rec] of [...open]) if (!seen.has(key)) { if (rec.count >= 2) res.faceHits.push(rec); open.delete(key); }
      }
      for (const rec of open.values()) if (rec.count >= 2) res.faceHits.push(rec);

      // текст за спиной не прячется за головой (Валера 16.10, IMG_3303 v2: «текст за головой нихуя не видно»):
      // голова — рамка лица (YuNet с запасом уже берёт лоб) плюс волосы над ней (0,2 высоты, сверено по IMG_1799) и чуть шире; строки текста (Range) слоя behind, пока
      // человек поверх (#cam-fg). Закрыта больше трети площади строк два замера подряд — провал; data-safe — нет
      res.occluded = [];
      // подписи «Чертежа» (.bp-lbl) — каждая сама по себе: одна спрятанная из пяти в общей площади приёма тонула
      // (19.10.2026, галерея: «Багдад» и «Европа» ушли за голову, проверка молчала)
      const behinds = [...document.querySelectorAll("#behind .g")].filter((el) => el.textContent.trim() && !el.querySelector(".bp-lbl"))
        .concat([...document.querySelectorAll("#behind .bp-lbl")]);
      const fgEl = document.getElementById("cam-fg");
      const openO = new Map();
      for (const [t, ...box] of faces) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        const [fx0, fy0, fx1, fy1] = onScreen(...box);
        if (cutaway() || !fgEl || parseFloat(getComputedStyle(fgEl).opacity) < 0.5) continue;
        const w = fx1 - fx0, h = fy1 - fy0;
        const hx0 = fx0 - 0.15 * w, hx1 = fx1 + 0.15 * w, hy0 = fy0 - 0.2 * h, hy1 = fy1;
        const seen = new Set();
        for (const el of behinds) {
          if (!vis(el) || el.closest("[data-safe]")) continue;
          const range = document.createRange();
          range.selectNodeContents(el);
          let area = 0, cov = 0;
          for (const q of range.getClientRects()) {
            if (q.width < 2 || q.height < 2) continue;
            area += q.width * q.height;
            const dx = Math.min(q.right, hx1) - Math.max(q.left, hx0), dy = Math.min(q.bottom, hy1) - Math.max(q.top, hy0);
            if (dx > 0 && dy > 0) cov += dx * dy;
          }
          if (!area || cov / area <= 0.35) continue;
          const key = label(el);
          seen.add(key);
          const rec = openO.get(key);
          if (rec) { rec.last = t; rec.count++; rec.share = Math.max(rec.share, cov / area); }
          else openO.set(key, { el: key, from: t, last: t, count: 1, share: cov / area });
        }
        for (const [k, rec] of [...openO]) if (!seen.has(k)) { if (rec.count >= 2) res.occluded.push(rec); openO.delete(k); }
      }
      for (const rec of openO.values()) if (rec.count >= 2) res.occluded.push(rec);
    }

    // ---- субтитры не двоятся (Валера 16.10.2026, IMG_3303 v3: «где-то дублировались субтитры»): «что соты у пчёл»
    // бежало субтитром прямо под подводом «соты у пчёл». Видимый субтитр и видимый текст графики (кроме подписи
    // портрета .card) не несут одно слово одновременно: слова от 4 букв — по первым пяти, числа — целиком.
    // Два замера подряд — провал. Текст на экране повторяет речь — на его время субтитр прячет hide_captions.
    // Буквы по одной (19.10.2026, демо IMG_3292: «икс, вэ, и, и, и» бежало субтитрами «x», «v», «i» под листом XVIII):
    // субтитр с латинской буквой-двумя, которые стоят в латинском слове на экране, — тоже двойной текст. Одна
    // кириллическая буква не в счёт: «и», «в», «у» — обычные слова
    res.dupes = [];
    {
      const caps = [...document.querySelectorAll("#caps .cap")];
      const texts = [...document.querySelectorAll("#front .g, #behind .g")]
        // шапка автора на весь ролик (data-header, «СлаваМонтаж» 22.10.2026: «Маркетолог на рынке США» в шапке) — подпись
        // бренда, а не повтор речи: её слова совпадают с субтитрами «маркетолог…» весь ролик
        .filter((el) => !el.classList.contains("cap") && !el.closest(".card") && !el.closest("[data-header]")
          && el.textContent.trim());
      const shown = (el) => {
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.5) return false;
        }
        return true;
      };
      const stems = (s) => (s.toLowerCase().replace(/ё/g, "е").match(/[a-zа-я]+|\d+/g) || [])
        .filter((w) => /\d/.test(w) || w.length >= 4).map((w) => (/\d/.test(w) ? w : w.slice(0, 5)));
      const latin = (s) => s.toLowerCase().match(/[a-z]+/g) || [];
      const open = new Map();
      if (caps.length && texts.length) {
        for (let t = 0; t <= duration + 1e-6; t += 0.25) {
          tl.totalTime(0, false); tl.totalTime(t, false);
          const said = new Map(), spelled = new Map();
          for (const c of caps) if (shown(c)) {
            for (const s of stems(c.textContent)) said.set(s, c.textContent.trim());
            for (const l of latin(c.textContent)) if (l.length <= 2) spelled.set(l, c.textContent.trim());
          }
          const seen = new Set();
          if (said.size || spelled.size) for (const el of texts) {
            if (!shown(el)) continue;
            let hit = stems(el.textContent).find((s) => said.has(s));
            const words = hit ? [] : latin(el.textContent);
            if (!hit) hit = [...spelled.keys()].find((l) => words.some((w) => w.includes(l)));
            if (!hit) continue;
            const key = label(el);
            seen.add(key);
            const rec = open.get(key);
            if (rec) { rec.last = t; rec.count++; }
            else open.set(key, { el: key, from: t, last: t, count: 1, cap: said.get(hit) || spelled.get(hit),
                                 text: el.textContent.trim().replace(/\s+/g, " ").slice(0, 40) });
          }
          for (const [k, rec] of [...open]) if (!seen.has(k)) { if (rec.count >= 2) res.dupes.push(rec); open.delete(k); }
        }
        for (const rec of open.values()) if (rec.count >= 2) res.dupes.push(rec);
      }
    }

    // ---- текст вылез (Валера 15.10.2026: «в конце фраза "Больше математики" — текст за рамки вылетал»):
    // «МАТЕМАТИКИ» шрифтом 104 px шире плашки CTA (590 px минус поля) и торчал за её правый край. Меряются
    // строки текста (Range) против рамки ближайшего предка с подложкой или обводкой — плашки, стикера,
    // штампа — и против кадра. Два замера подряд глубже 4 px; вылет на время влёта не в счёт.
    // data-spill="причина" на элементе или предке — осознанно за краем (бегущая строка).
    res.spills = [];
    {
      const stage = document.getElementById("root").getBoundingClientRect();
      const boxed = (n) => {
        const cs = getComputedStyle(n);
        const bg = /rgba?\(([^)]+)\)/.exec(cs.backgroundColor);
        const alpha = bg ? (bg[1].split(",").length > 3 ? parseFloat(bg[1].split(",")[3]) : 1) : 0;
        return alpha > 0.15 || parseFloat(cs.borderLeftWidth) > 0 || cs.backgroundImage !== "none";
      };
      const shownText = (n) => {
        for (let p = n; p && p !== document.body; p = p.parentElement) {
          const cs = getComputedStyle(p);
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.5) return false;
        }
        return true;
      };
      const items = [];
      document.querySelectorAll("#front .g, #behind .g, .cap").forEach((el) => {
        const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const n = walker.currentNode;
          if (!n.textContent.trim() || n.parentElement.closest(".katex-mathml")) continue;
          if (n.parentElement.closest(".g, .cap") !== el) continue;
          let box = null;
          for (let p = n.parentElement; p; p = p.parentElement) {
            if (boxed(p)) { box = p; break; }
            if (p === el) break;
          }
          // окно с overflow: hidden (бегущая лента букв) прячет то, что за краем, — это не вылет
          const clips = [];
          for (let p = n.parentElement; p && p !== document.body; p = p.parentElement) {
            if (p.id === "root") break;
            if (getComputedStyle(p).overflow !== "visible") clips.push(p);
          }
          items.push({ el, n, box, clips });
        }
      });
      const range = document.createRange();
      const open = new Map();
      for (let t = 0; t <= duration + 1e-6; t += 0.25) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        const seen = new Set();
        for (const it of items) {
          if (!shownText(it.n.parentElement)) continue;
          range.selectNodeContents(it.n);
          const b = it.box ? it.box.getBoundingClientRect() : null;
          let depth = 0, where = "";
          const cuts = it.clips.map((c) => c.getBoundingClientRect());
          for (const raw of range.getClientRects()) {
            const r = { left: raw.left, right: raw.right, top: raw.top, bottom: raw.bottom };
            for (const c of cuts) {
              r.left = Math.max(r.left, c.left); r.right = Math.min(r.right, c.right);
              r.top = Math.max(r.top, c.top); r.bottom = Math.min(r.bottom, c.bottom);
            }
            if (r.right - r.left < 2 || r.bottom - r.top < 2) continue;
            const off = Math.max(stage.left - r.left, r.right - stage.right, stage.top - r.top, r.bottom - stage.bottom);
            if (off > depth) { depth = off; where = "кадра"; }
            if (b) {
              const out = Math.max(b.left - r.left, r.right - b.right);
              if (out > depth) { depth = out; where = "плашки"; }
            }
          }
          if (depth <= 4) continue;
          // data-spill="причина" — осознанно за кадром (бегущая строка цифр уезжает за край)
          if (it.n.parentElement.closest("[data-spill]")) continue;
          const key = label(it.el) + "|" + it.n.textContent.trim().slice(0, 30);
          seen.add(key);
          const rec = open.get(key);
          if (rec) { rec.last = t; rec.count++; rec.depth = Math.max(rec.depth, Math.round(depth)); }
          else open.set(key, { el: label(it.el), text: it.n.textContent.trim().slice(0, 40), where, from: t, last: t,
                               count: 1, depth: Math.round(depth) });
        }
        for (const [key, rec] of [...open]) if (!seen.has(key)) { if (rec.count >= 2) res.spills.push(rec); open.delete(key); }
      }
      for (const rec of open.values()) if (rec.count >= 2) res.spills.push(rec);
    }

    // ---- дизайн-система (Валера 20.10.2026: «один раз собрать идеальную — шрифты и т. п.»): на странице проекта с
    // DESIGN.md (meta reels-design) видимый текст набран только шрифтами системы, а цвет текста, заливок (и ::before,
    // ::after), рамок и линий SVG — только её цветами и точками градиента, с любой прозрачностью. Элемент проверяется в
    // первый замер, когда виден. Тени не в счёт (они чёрные по системе), вспышки переходов и видео — тоже.
    res.design = [];
    if (C.design) {
      const pal = C.design.colors, fonts = new Set(C.design.fonts.map((f) => f.toLowerCase()));
      const ok = (c) => pal.some((p) => Math.abs(p[0] - c[0]) <= 6 && Math.abs(p[1] - c[1]) <= 6 && Math.abs(p[2] - c[2]) <= 6);
      const rgbs = (s) => [...String(s || "").matchAll(/rgba?\(([^)]*)\)/g)]
        .map((m) => m[1].split(/[\s,\/]+/).filter(Boolean).map(Number))
        .filter((v) => v.length >= 3 && !(v.length > 3 && v[3] <= 0.05));
      const paint = (v) => {                       // fill и stroke: цвет или url(#градиент) — тогда его точки
        const ref = /url\(["']?#([^"')]+)["']?\)/.exec(String(v || ""));
        if (!ref) return rgbs(v);
        const g = document.getElementById(ref[1]);
        return g ? [...g.querySelectorAll("stop")].flatMap((s) => rgbs(getComputedStyle(s).stopColor)) : [];
      };
      const own = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
      const shownD = (el) => {
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.3) return false;
        }
        return true;
      };
      const rgbText = (c) => `rgb(${c.slice(0, 3).join(", ")})`;
      const offs = (el) => {
        const cs = getComputedStyle(el), bad = [], svg = el instanceof SVGElement;
        if (own(el)) {
          const fam = cs.fontFamily.split(",")[0].replace(/["']/g, "").trim();
          if (!fonts.has(fam.toLowerCase())) bad.push(["шрифт", fam]);
          if (!svg) for (const c of rgbs(cs.color)) if (!ok(c)) bad.push(["цвет текста", rgbText(c)]);
        }
        if (svg && !(el instanceof SVGSVGElement) && !(el instanceof SVGGElement)) {
          for (const [k, v] of [["заливка", cs.fill], ["линия", cs.stroke]])
            for (const c of paint(v)) if (!ok(c)) bad.push([k, rgbText(c)]);
        }
        if (!svg) for (const pseudo of [null, "::before", "::after"]) {
          const ps = pseudo ? getComputedStyle(el, pseudo) : cs;
          if (pseudo && (ps.content === "none" || ps.content === "normal")) continue;
          for (const c of rgbs(ps.backgroundColor).concat(rgbs(ps.backgroundImage)))
            if (!ok(c)) bad.push([`фон${pseudo || ""}`, rgbText(c)]);
          if (parseFloat(ps.borderTopWidth) > 0 && ps.borderTopStyle !== "none")
            for (const c of rgbs(ps.borderTopColor)) if (!ok(c)) bad.push([`рамка${pseudo || ""}`, rgbText(c)]);
        }
        return bad;
      };
      const skipped = "#flash, #hook-flash, defs, linearGradient, radialGradient, pattern, video, img, audio, script";
      let todo = [...document.querySelectorAll("#front *, #behind *")].filter((el) => !el.closest(skipped));
      for (let t = 0; t <= duration + 1e-6 && todo.length; t += 0.5) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        const rest = [];
        for (const el of todo) {
          if (!shownD(el)) { rest.push(el); continue; }
          for (const [what, value] of offs(el)) res.design.push({ el: label(el), what, value, t });
        }
        todo = rest;
      }
    }

    // ---- пустые места (Валера 19.10.2026, демо IMG_3292 v2: «в какой-то момент нет никаких вставок, и при этом
    // субтитры идут одинаково скучно — динамика очень теряется»): 15 с без единой вставки. Вставка — любая графика
    // на экране (#front .g, #behind .g: текст, «Чертёж», клип, штамп, плашка), вспышки — нет. Сюда — участки
    // дольше секунды; порог — project.json → insert_gap_max
    res.bare = [];
    {
      const graphics = [...document.querySelectorAll("#front .g, #behind .g")].filter((el) => !/flash/.test(el.id));
      const seen = (el) => {
        let a = 1;
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden") return false;
          a *= parseFloat(cs.opacity);
        }
        return a >= 0.15;
      };
      let from = 0;
      for (let t = 0; t <= duration + 1e-6; t += 0.25) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        if (graphics.some(seen)) { if (t - from > 1) res.bare.push([from, t]); from = t + 0.25; }
      }
      if (duration - from > 1) res.bare.push([from, duration]);
    }

    // ---- динамика (Валера 13.10.2026: «плашка про миллион очень долго висела, мы теряли в динамике» —
    // таблица mille/-one в IMG_1803 v5 висела 13 с, из них 8 с без единого изменения). Графика поверх
    // и за человеком (#front .g, #behind .g; фоны и вспышка — нет) не стоит без изменений дольше
    // C.holdMax с подряд. Изменение — элемент сдвинулся, или внутри появилось, ушло, сменило цвет или
    // текст что-то (строка, слово, подсветка, счётчик). Медленный наезд внутри картинки — не изменение:
    // глазу он не новость. data-hold="причина" — осознанно долгий показ, отдельным списком.
    res.holds = []; res.holdsAllowed = [];
    {
      const holdMax = C.holdMax || 5;
      const graphics = [...document.querySelectorAll("#front .g, #behind .g")].filter((el) => el.id !== "flash");
      const shown = (el) => {
        let a = 1;
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden") return false;
          a *= parseFloat(cs.opacity);
        }
        return a >= 0.5;
      };
      const print = (el) => {
        const r = el.getBoundingClientRect();
        const inside = [...el.querySelectorAll("*")].map((n) => {
          const cs = getComputedStyle(n);
          return (parseFloat(cs.opacity) >= 0.5 && cs.visibility !== "hidden" ? "1" : "0") + cs.color + cs.backgroundColor;
        }).join("|");
        return [Math.round(r.left / 6), Math.round(r.top / 6), Math.round(r.width / 6), Math.round(r.height / 6),
                getComputedStyle(el).color, (el.textContent || "").trim().slice(0, 200), inside].join("·");
      };
      // смена у соседа (ближе 120 px) — смена и для плашки: глаз видит место на экране, а не элемент
      // (пара карточек «было / стало», подводка над впечатанным словом)
      const near = (r, q) => Math.max(q.left - r.right, r.left - q.right, q.top - r.bottom, r.top - q.bottom) <= 120;
      const runs = new Map();                     // элемент → {from, last, sig}
      const close = (el, rec) => {
        const hold = rec.last - rec.from;
        if (hold > holdMax + 1e-6) {
          const safe = el.closest("[data-hold]");
          const item = { el: label(el), from: rec.from, to: rec.last, hold, allowed: safe ? safe.getAttribute("data-hold") : null };
          (item.allowed ? res.holdsAllowed : res.holds).push(item);
        }
      };
      let before = new Map();                     // прошлый замер: элемент → рамка
      for (let t = 0; t <= duration + 1e-6; t += 0.25) {
        tl.totalTime(0, false); tl.totalTime(t, false);
        const now = new Map(), sigs = new Map(), moved = [];
        for (const el of graphics) {
          if (!shown(el)) { if (before.has(el)) moved.push(before.get(el)); continue; }
          const r = el.getBoundingClientRect();
          // внутри идёт клип («доска» ManimGX): видео в разборе не грузится, но кадр в нём меняется
          const playing = [...el.querySelectorAll("video.clip")].some((v) =>
            t >= parseFloat(v.dataset.start) && t < parseFloat(v.dataset.start) + parseFloat(v.dataset.duration));
          now.set(el, r); sigs.set(el, print(el) + (playing ? "·" + t : ""));
          const rec = runs.get(el);
          if (!rec || rec.sig !== sigs.get(el)) moved.push(r);
        }
        for (const el of graphics) {
          const rec = runs.get(el);
          if (!now.has(el)) { if (rec) { close(el, rec); runs.delete(el); } continue; }
          const r = now.get(el), sig = sigs.get(el);
          const touched = moved.some((q) => q !== r && near(r, q));
          if (rec && rec.sig === sig && !touched) { rec.last = t; continue; }
          if (rec) close(el, rec);
          runs.set(el, { from: t, last: t, sig });
        }
        before = now;
      }
      for (const [el, rec] of runs) close(el, rec);
    }

    // ---- графика видна раньше своего входа (21.10.2026, IMG_5688): fromTo с { opacity: 1 } в начальных значениях
    // GSAP по умолчанию ставит сразу при сборке таймлайна (immediateRender), и чёрная линза во весь кадр стояла с
    // первого кадра до своих 13.9 с. Проверка «висит без изменений» её не видела: рамку во весь кадр «обновляет»
    // любая смена текста внутри. Элемент .g скрыт стилем, пока его не покажет таймлайн, — значит, виден до первого
    // своего твина он только по ошибке.
    res.early = [];
    {
      const graphics = [...document.querySelectorAll("#front .g, #behind .g")].filter((el) => el.id !== "flash");
      const shown = (el) => {
        for (let n = el; n && n !== document.body; n = n.parentElement) {
          const cs = getComputedStyle(n);
          if (cs.display === "none" || cs.visibility === "hidden" || parseFloat(cs.opacity) < 0.15) return false;
        }
        return true;
      };
      for (const el of graphics) {
        const starts = tl.getTweensOf(el).map((tw) => tw.startTime());
        const first = starts.length ? Math.min(...starts) : 0;
        for (let t = 0; t < first - 0.1; t += 0.25) {
          tl.totalTime(0, false); tl.totalTime(t, false);
          if (shown(el)) { res.early.push({ el: label(el), t, first }); break; }
        }
      }
    }

    // ---- склейки (Валера 15.10.2026: «склейки не спрятаны за переходами вспышками»): на каждой склейке
    // дубля (C.splices) — переход: вспышка или смаз кадра в кадрах реза (kit: splice(t)); и ни одна
    // надпись или фон не висит через рез — уходит до него, новое влетает на нём. Висящее «СЕКРЕТНО»
    // поверх реза только подчёркивало, что банка в руке перескочила. data-splice="причина" — осознанно.
    res.splices = [];
    const splices = C.splices || [];
    if (splices.length) {
      const flashEl = document.getElementById("flash");
      const camEl = document.querySelector(".cam");
      const alpha = (el) => { let a = 1; for (let n = el; n && n !== document.body; n = n.parentElement) {
        const cs = getComputedStyle(n); if (cs.display === "none" || cs.visibility === "hidden") return 0; a *= parseFloat(cs.opacity); } return a; };
      const items = [...document.querySelectorAll(".g, #plate")].filter((el) => el.id !== "flash" && !el.closest("[data-splice]")
        && !(el.parentElement && el.parentElement.closest(".g")));
      for (const s of splices) {
        let peakFlash = 0, peakBlur = 0;
        for (let k = Math.round(s * fps) - 1; k <= Math.round(s * fps) + 2; k++) {
          tl.totalTime(0, false); tl.totalTime(k / fps, false);
          if (flashEl) peakFlash = Math.max(peakFlash, parseFloat(getComputedStyle(flashEl).opacity));
          if (camEl) peakBlur = Math.max(peakBlur, blurOf(camEl));
        }
        tl.totalTime(0, false); tl.totalTime(Math.max(0, s - 0.1), false);
        const pre = new Set(items.filter((el) => alpha(el) >= 0.15));
        tl.totalTime(0, false); tl.totalTime(s + 0.1, false);
        const across = items.filter((el) => pre.has(el) && alpha(el) >= 0.15).map(label);
        res.splices.push({ t: s, flash: peakFlash, blur: peakBlur, across });
      }
    }

    document.querySelectorAll(".g").forEach((el) => {
      const i = els.indexOf(el);
      const peak = i < 0 ? parseFloat(getComputedStyle(el).opacity) : Math.max(...real.map((f) => f[i]));
      if (!(peak > 0.01)) res.never.push(label(el));
    });
    Object.assign(res, { ok: true, frames: N, elements: els.length, tweens });
  } catch (e) {
    res.ok = false;
    res.crash = String(e && e.stack || e);
  }
  res.ms = Math.round(performance.now() - started);
  const pre = document.createElement("pre");
  pre.id = "hf-check";
  pre.textContent = JSON.stringify(res);
  document.body.replaceChildren(pre);
})();
"""


def find_chrome() -> str:
    """Тот же headless Chrome, которым рендерит HyperFrames (на Windows — .exe)."""
    found = sorted([*CHROME_CACHE.glob("*/chrome-headless-shell-*/chrome-headless-shell"),
                    *CHROME_CACHE.glob("*/chrome-headless-shell-*/chrome-headless-shell.exe")])
    if not found:
        raise RuntimeError(
            f"Нет браузера HyperFrames в {CHROME_CACHE}. Поставь его: "
            "npx --yes hyperframes@0.8.141 browser ensure")
    return str(found[-1])


SFX_NORM_MARK = 'name="reels-sfx-norm"'        # kit ставит в страницы с нормой звука


def music_problems(page: str, project: str | None) -> list:
    """Фоновая музыка (Валера 17.10.2026: «менять постоянно, но по громкости негромко, вот как сейчас хорошо»): трек
    фонотеки (yt-*), не громче громкости проекта (kit.bgm_level: project.json → music_level) от нормы материалов и не
    тот, что уже стоит в другом ролике."""
    import kit
    import materials
    tracks = []
    for tag in re.findall(r'<audio id="sfx-[^"]*" src="assets/materials/[^"]+"[^>]*>', page):
        name, volume = re.search(r'src="assets/materials/([^"]+)"', tag).group(1), re.search(r'data-volume="([\d.]+)"', tag)
        lane = re.search(r"data-automation='([^']+)'", tag)
        if lane:                                   # лента главнее data-volume: «под голосом» — её нижний ненулевой уровень
            try:
                values = [pt["v"] for ln in json.loads(lane.group(1))["lanes"] for pt in ln["points"] if pt["v"] > 0]
                tracks.append((name, str(min(values))))
                continue
            except (ValueError, KeyError, TypeError):
                pass
        if volume:
            tracks.append((name, volume.group(1)))
    if not tracks or project is None:
        return []
    stem = project.split("--")[0]
    problems, limit = [], kit.SFX_TARGET + 20 * math.log10(kit.bgm_level(stem)) + 0.5
    for name, volume in tracks:
        if not name.startswith(kit.BGM_PREFIXES):
            continue                           # свой звук человека из материалов — его громкость решает он
        try:
            level = materials.loudness(stem, name) + 20 * math.log10(max(float(volume), 1e-6))
        except Exception as e:                 # нет замера — громкость не проверить
            problems.append(f"{name}: не замерить громкость музыки — {e}")
            continue
        if level > limit:
            problems.append(f"{name}: музыка на {level:.1f} LUFS — громче, чем «негромко, как сейчас» ({limit - 0.5:.1f}); "
                            f"kit.background_music ставит уровень сам")
        mark = f'src="assets/materials/{name}"'
        others = sorted(d.name for d in STUDIO.glob("*/") if d.name.split("--")[0] != stem
                        and (d / "index.html").exists() and mark in (d / "index.html").read_text(encoding="utf-8"))
        if others:
            problems.append(f"{name}: этот трек уже стоит в {', '.join(others[:3])} — музыку меняем в каждом ролике "
                            f"(возьми другой лоу-фай, scripts/music.py)")
    return problems


def music_missing(page: str, project: str) -> str | None:
    """Проект просит фон в каждом ролике (project.json → music), а трека на странице нет — причина отказа.

    IMG_3292 v2 (17.10.2026): подходящего трека не нашлось, ИИ собрал ролик без музыки и сказал об этом
    только в отчёте — «музыки нет, какого хуя». Нет трека — ролик не готов: положить его (music.py add)
    или спросить человека, а не рендерить."""
    import kit
    import projects
    try:
        wants = projects.of(project.split("--")[0]).config.get("music")
    except projects.ProjectError:
        return None
    if not wants or re.search(rf'src="assets/materials/(?:{"|".join(map(re.escape, kit.BGM_PREFIXES))})[^"]+"', page):
        return None
    return ("нет фоновой музыки, а проект просит её в каждом ролике: скачай 2–3 лоу-фай из фонотеки YouTube или Mixkit → "
            "scripts/music.py add <имя> <файлы> → kit.background_music(…); нет трека — спроси человека, не рендерь без него")


def required_missing(page: str, project: str) -> list:
    """Обязательное проекта, которого на странице нет (19.10.2026, Валера: «то звуки потеряются, то музыка, то переходов
    нет»): тихие звуки монтажа (project.json → soft_sounds, rules.md п.9) и вспышка после хука у страниц montage.py
    (hook_flash; осознанно без неё — m.hook(None, "причина") пишет meta reels-hook)."""
    import projects
    try:
        cfg = projects.of(project.split("--")[0]).config
    except projects.ProjectError:
        return []
    out = []
    found = re.search(r'data-duration="([\d.]+)"', page)
    duration = float(found.group(1)) if found else 0.0
    soft = len(re.findall(r'<audio id="sfx-soft', page))
    if cfg.get("soft_sounds") and soft < duration / SOFT_EVERY:
        out.append(f"тихих звуков монтажа {soft} на {duration:.0f} с — нужно не реже одного на {SOFT_EVERY:g} с (rules.md п.9): "
                   f"montage.py ставит их сам по движениям страницы, вручную — kit.soft_track")
    if cfg.get("hook_flash") and MONTAGE_MARK in page and 'id="hook-flash"' not in page and 'name="reels-hook"' not in page:
        out.append("нет вспышки после хука, а проект её просит (project.json → hook_flash): m.hook(t) или "
                   "m.hook(None, \"почему без неё\")")
    return out


def sound_problems(page: str, project: str | None = None) -> list:
    """Звуки страницы по правилам: громкость по замеру файла не выше нормы, убранных нет, повторов нет."""
    import math

    import kit

    manifest = kit.sfx_manifest()
    problems = []
    for name, volume in re.findall(r'<audio id="sfx-[^"]*" src="assets/sfx/([\w.\-]+)\.mp3"[^>]*?data-volume="([\d.]+)"',
                                   page):
        if name in manifest.get("_removed", {}):
            problems.append(f"{name}: {manifest['_removed'][name]}")
            continue
        info = manifest.get(name) if not name.startswith("_") else None
        if not info or "loudness_m" not in info:
            problems.append(f"{name}: нет в presets/sfx или нет замера громкости")
            continue
        level = info["loudness_m"] + 20 * math.log10(max(float(volume), 1e-6))
        target = kit.SFX_TARGET + (kit.SOFT_DB if info.get("soft") else 0.0)
        if level > target + 0.5:
            problems.append(f"{name}: {level:.1f} LUFS — громче нормы {target:g}" +
                            (" для тихого звука монтажа" if info.get("soft") else " (на ~11 дБ тише голоса)"))

    problems += music_problems(page, project)
    try:
        kit.check_sounds([page])
    except ValueError as e:
        problems += [line.strip() for line in str(e).splitlines()[1:]]
    return problems


def missing_assets(project: Path, page: str) -> list:
    refs = set(re.findall(r'(?:src|href)="(assets/[^"]+)"', page))
    refs |= set(re.findall(r"""url\(["']?(assets/[^"')]+)""", page))
    refs |= set(re.findall(r'data-composition-src="([^"]+)"', page))      # визуализации каталога
    # скрипты проекта (camera.js, captions.js, layers.js, edits.js) кладёт compose.py: страница из page.py
    # без него падала «нет таймлайна» — теперь видно, какого файла нет и что запустить
    scripts = {f"{r} (его кладёт compose.py)" for r in re.findall(r'<script src="([\w.-]+\.js)"', page)
               if not (project / r).exists()}
    return sorted(r for r in refs if not (project / r).exists()) + sorted(scripts)


def stage_format(page: str) -> str | None:
    """Формат сцены страницы по её viewport (kit пишет width/height сцены)."""
    import formats

    found = re.search(r'<meta name="viewport" content="width=(\d+), height=(\d+)"', page)
    return formats.of_size(int(found.group(1)), int(found.group(2))) if found else None


def cutout_gaps(project: Path, page: str, shown: list) -> list:
    """Где человек поверх (#cam-fg) виден, а маски под ним нет: вырезки нет вовсе, она от другого дубля или
    посчитана по другим окнам (assets/cutout.json — что посчитал matte.cut_windows; нет записи — вся длина)."""
    if not shown:
        return []
    import matte
    hint = f"matte.py work/{take_dir(project).name}/aroll.mp4 --windows page (очередью)"
    if not (project / "assets" / "cutout.webm").exists():
        return [f"вырезки нет, а человек поверх — {len(shown)} окон с {shown[0][0]:.2f} с: {hint}"]
    record = project / "assets" / "cutout.json"
    try:
        state = json.loads(record.read_text(encoding="utf-8")) if record.exists() else None
    except ValueError:
        return [f"{record.relative_to(ROOT)} — не JSON: пересобери вырезку, {hint}"]
    aroll = take_dir(project) / "aroll.mp4"
    if state is not None and aroll.exists() and state.get("video") != matte.identity(aroll):
        return [f"вырезка посчитана по другому дублю (aroll.mp4 пересобран после неё) — {hint}"]
    covered = matte.coverage(state, float((state or {}).get("fps") or FPS))
    if covered is None:
        return []
    slack = 1.0 / FPS
    bare = []
    for a, b in shown:
        for c0, c1 in covered:                 # окно режется покрытием; что осталось — без маски
            if c0 - slack <= a < c1:
                a = max(a, c1)
        if b - a > slack:
            bare.append(f"{a:.2f}–{b:.2f} с: человек поверх, а маски нет — {hint}")
    return bare


def take_dir(project: Path) -> Path:
    """work/<имя>/ дубля, из которого собран проект: вариант для A/B (studio/<имя>--<стиль>/) — из того же."""
    return WORK_DIR / project.name.split("--")[0]


def face_track(project: Path, step: float = 0.25, margin: float = 12.0) -> list:
    """[(t, x0, y0, x1, y1)] — где лицо на сцене каждые step с: слежение (work/<имя>/aroll.faces.json)
    плюс движение камеры (camera.js). Ложные срабатывания детектора (рука, банка — IMG_1803:
    «лицо» до y 1763 и левее кадра) отбрасываются: кадр, далёкий от медианы соседей, не в счёт,
    рамка сглажена медианой. margin — запас вокруг лица, px. Нет слежения — пустой список."""
    import numpy as np

    faces_path = take_dir(project) / "aroll.faces.json"
    camera_path = project / "camera.js"
    if not faces_path.exists() or not camera_path.exists():
        return []
    data = json.loads(faces_path.read_text(encoding="utf-8"))
    found = re.search(r"window\.CAMERA = (\[.*\]);", camera_path.read_text(encoding="utf-8"), re.S)
    if not found:
        return []
    camera = json.loads(found.group(1))
    fps = float(data.get("fps") or 30)
    rows = np.array([f[:4] if f and f[4] >= 0.6 else [np.nan] * 4 for f in data["frames"]], dtype=float)
    n = len(rows)
    half = 7
    med = np.array([np.nanmedian(rows[max(0, k - half): k + half + 1], axis=0)
                    if not np.all(np.isnan(rows[max(0, k - half): k + half + 1])) else [np.nan] * 4
                    for k in range(n)])
    off = np.abs(rows[:, :2] - med[:, :2]).max(axis=1) > 0.25 * med[:, 3]
    rows[off] = np.nan
    track = []
    for k in range(0, n, max(1, int(round(step * fps)))):
        window = rows[max(0, k - 2): k + 3]
        if np.all(np.isnan(window)):
            continue
        cx, cy, w, h = np.nanmedian(window, axis=0)
        x, y, scale = camera[min(k, len(camera) - 1)]
        track.append((round(k / fps, 3), x + scale * (cx - w / 2) - margin, y + scale * (cy - h / 2) - margin,
                      x + scale * (cx + w / 2) + margin, y + scale * (cy + h / 2) + margin))
    return track


def run_timeline(page_path: Path, fps: int = FPS, timeout: float = 180, zones: list | None = None,
                 faces: list | None = None, splices: list | None = None, design: dict | None = None) -> dict:
    """Прогоняет таймлайн страницы в headless Chrome и возвращает разбор (см. CHECK_JS).

    zones — серые зоны площадок [(название, (x0, y0, x1, y1))]: текст в них попадёт в res["grey"].
    design — что разрешает DESIGN.md проекта (design.Design.allowed): цвет или шрифт мимо него — в res["design"].
    """
    page_path = Path(page_path).resolve()
    page = page_path.read_text(encoding="utf-8")
    # видео и звук для разбора не нужны — без них страница грузится за доли секунды
    page = re.sub(r'(<(?:video|audio)\b[^>]*?)\s+src="[^"]*"', r"\1", page)
    config = json.dumps({"fps": fps, "errors": [], "warnings": [], "zoneStep": 0.25, "zoneDepth": 8,
                         "holdMax": HOLD_MAX,
                         "zones": [{"name": name, "rect": list(rect)} for name, rect in (zones or [])],
                         "faces": [list(f) for f in (faces or [])], "splices": list(splices or []),
                         "design": design},
                        ensure_ascii=False)
    head = (f'<head>\n    <base href="{page_path.parent.as_uri()}/">\n'
            f'    <script>window.__HF_CHECK = {config};{EARLY_JS}    </script>')
    page, n_head = re.subn(r"<head>", lambda _: head, page, count=1)
    cut = page.rfind("</body>")
    if not n_head or cut < 0:
        raise ValueError(f"{page_path.name}: нет <head> или </body> — это не страница HyperFrames")
    page = page[:cut] + f"<script>{CHECK_JS}</script>\n" + page[cut:]

    with tempfile.TemporaryDirectory(prefix="reels_verify_page_") as tmp:
        wrapper = Path(tmp) / "page.html"
        wrapper.write_text(page, encoding="utf-8")
        cmd = [find_chrome(), "--headless", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", "--mute-audio", f"--user-data-dir={Path(tmp) / 'profile'}",
               "--virtual-time-budget=2000", "--dump-dom", wrapper.as_uri()]
        try:
            result = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Проверка страницы {page_path.parent.name} не уложилась в {timeout:.0f} с")
    found = re.search(r'<pre id="hf-check">(.*?)</pre>', result.stdout, re.S)
    if not found:
        raise RuntimeError(f"Chrome не вернул разбор страницы {page_path.parent.name}:\n"
                           f"{result.stderr.strip()[-600:]}")
    return json.loads(html.unescape(found.group(1)))


def load_director(project: Path) -> dict | None:
    """director.json ролика (варианта — director.<вариант>.json, если есть)."""
    work = take_dir(project)
    variant = project.name.split("--")[1] if "--" in project.name else None
    for path in ([work / f"director.{variant}.json"] if variant else []) + [work / "director.json"]:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def accent_gaps(project: Path, limit: float = ACCENT_EVERY) -> list:
    """Где субтитры идут дольше limit с без ключевого слова (Валера 19.10.2026, демо IMG_3292 v2: «субтитры супер
    одинаково скучно идут, динамика теряется» — на 58 с одно подсвеченное слово). От начала субтитров до первого
    ключевого, между ключевыми и от последнего до конца субтитров. Возвращает [(от, до)]."""
    caps_js = project / "captions.js"
    if not caps_js.exists():
        return []
    found = re.search(r"window\.CAPTIONS\s*=\s*(\[.*\]);", caps_js.read_text(encoding="utf-8"), re.S)
    chunks = json.loads(found.group(1)) if found else []
    if not chunks:
        return []
    marks = [chunks[0]["t0"]] + [c["t0"] for c in chunks if c.get("accent")] + [chunks[-1]["t1"]]
    return [(round(a, 2), round(b, 2)) for a, b in zip(marks, marks[1:]) if b - a > limit]


def caption_gaps(project: Path, limit: float = CAP_GAP_MAX) -> list:
    """Где речь идёт без субтитров дольше limit с (Валера 16.10.2026, IMG_3303 v3: «где-то слишком надолго пропали»).

    В v3 субтитры прятались на всё время схем на груди: круги вплотную — 6 с речи без текста, периметры — 6 с.
    Слово «с субтитром», если на его середине виден кусок из captions.js; подряд идущие слова без субтитра —
    один провал, пауза дольше секунды его рвёт. Возвращает [(от, до)] на шкале дубля.
    """
    caps_js, words_json = project / "captions.js", take_dir(project) / "aroll.words.json"
    if not caps_js.exists() or not words_json.exists():
        return []
    found = re.search(r"window\.CAPTIONS\s*=\s*(\[.*\]);", caps_js.read_text(encoding="utf-8"), re.S)
    chunks = json.loads(found.group(1)) if found else []
    if not chunks:
        return []                                   # стиль без субтитров — не про это
    words = json.loads(words_json.read_text(encoding="utf-8"))
    words = words["words"] if isinstance(words, dict) else words
    gaps, run = [], None
    for w in words:
        if not str(w.get("word", "")).strip(" -.,!?"):
            continue
        mid = (w["start"] + w["end"]) / 2
        if any(c["t0"] <= mid < c["t1"] for c in chunks):
            run = None
            continue
        if run and w["start"] - run[1] <= 1.0:
            run[1] = w["end"]
        else:
            run = [w["start"], w["end"]]
            gaps.append(run)
    return [(round(a, 2), round(b, 2)) for a, b in gaps if b - a > limit]


def take_splices(project: Path) -> list:
    """Секунды склеек на шкале дубля (по вырезам drop в aroll.json); нет дубля — пусто. Стыки сборки (scenes,
    scripts/pack.py) — смена сцены, а не склейка дубля: их не прячут, и в список они не входят."""
    meta = take_dir(project) / "aroll.json"
    if not meta.exists():
        return []
    data = json.loads(meta.read_text(encoding="utf-8"))
    scenes = [float(j) for j in data.get("scenes") or []]
    acc, out = 0.0, []
    for s0, s1 in data.get("segments", [])[:-1]:
        acc += s1 - s0
        if all(abs(acc - j) > 0.02 for j in scenes):
            out.append(round(acc, 3))
    return out


def take_pause_cuts(project: Path) -> list:
    """Склейки по вырезанным паузам (aroll.json → jumps, prep cut_pauses): их прячет смена плана, надпись через них
    висеть может — человек не перескакивает, пауза просто короче."""
    meta = take_dir(project) / "aroll.json"
    if not meta.exists():
        return []
    return [float(j) for j in json.loads(meta.read_text(encoding="utf-8")).get("jumps") or []]


def camera_jumps(project: Path, splices: list) -> dict:
    """{склейка: |зум после − зум до|} по camera.js — сменился ли план на резе."""
    path = project / "camera.js"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    found = re.search(r"window\.CAMERA = (\[.*\]);", text, re.S)
    fps_m = re.search(r"window\.CAMERA_FPS = ([\d.]+)", text)
    if not found:
        return {}
    cam, cfps = json.loads(found.group(1)), float(fps_m.group(1)) if fps_m else 30.0
    out = {}
    for t in splices:
        k = int(round(t * cfps))
        if 0 < k < len(cam):
            out[t] = abs(cam[k][2] - cam[k - 1][2])
    return out


def explain(item: dict) -> str:
    """«субтитр «мы»: висит 48.87–96.07 с — уход в 48.85 раньше конца появления (48.90)»."""
    text = f"{item['el']}: {item['got']:.2f} вместо {item['want']:.2f} на {item['from']:.2f}–{item['to']:.2f} с"
    pair = item.get("why")
    if pair:
        a, b = pair["a"], pair["b"]
        text += (f" — {b['kind']} в {b['start']:.2f} кончается раньше, чем {a['kind']} "
                 f"{a['start']:.2f}–{a['end']:.2f}")
    return text


def cta_leak(name: str, page_text: str) -> str | None:
    """Плашка «смотри у меня в профиле» в ролике проекта без CTA: текст провала, "" — чисто, None — не мерить.

    Плашка — про профиль Валеры; в ролике заказчика это утечка чужого проекта (14.10.2026).
    Страницы-образцы и проверки живут вне проектов — для них None.
    """
    import projects
    try:
        owner = projects.of(name.split("--")[0])
    except projects.ProjectError:
        return None
    if owner.config["cta"]:
        return None
    if 'id="cta"' in page_text:
        return (f"плашка «смотри у меня в профиле» в ролике проекта {owner.name}, а он без CTA "
                f"(project.json) — build_page(..., cta=False)")
    return ""


def verify(stem_or_dir: str, fps: int = FPS, strict: bool = True, matte_pending: bool = False) -> list:
    """Печатает отчёт по странице; возвращает список провалов (пустой — можно рендерить).

    strict — страница идёт в рендер: собранная до норм звука не проходит. Сводка --all — не строгая.
    matte_pending — черновик до маски (analyst.assemble): маска считается после страницы, по её окнам, —
    окна без маски печатаются, но не провал. Рендер так не идёт: render_reel проверяет без этого флага.
    """
    project = Path(stem_or_dir)
    if not project.is_dir():
        project = STUDIO / stem_or_dir
    page_path = project / "index.html"
    if not page_path.exists():
        raise FileNotFoundError(f"Нет страницы {page_path}")
    failed = []

    def check(ok: bool, title: str, details: list = ()):
        print(f"  {'✓' if ok else '✗'} {title}")
        for line in list(details)[:8]:
            print(f"      {line}")
        if len(details) > 8:
            print(f"      … и ещё {len(details) - 8}")
        if not ok:
            failed.append(title)

    print(f"Страница {project.name}")
    page_text = page_path.read_text(encoding="utf-8")
    gone = missing_assets(project, page_text)
    if matte_pending:                         # вырезка придёт после страницы — её отсутствие скажет проверка окон
        gone = [g for g in gone if g != "assets/cutout.webm"]
    check(not gone, "все картинки, звуки и шрифты на месте", gone)
    leak = cta_leak(project.name, page_text)
    if leak is not None:
        check(not leak, leak or "плашки «смотри у меня в профиле» нет: проект без CTA")
    if SFX_NORM_MARK in page_text:
        sounds = sound_problems(page_text, project.name)
        check(not sounds, "звуки: не громче нормы, без убранных и без одинаковых подряд", sounds)
    elif strict:
        check(False, "страница собрана до норм звука 12.10.2026 — пересобери её page.py "
                     "(старые звуки громче голоса и повторяются)")
    else:
        print("  · звуки по правилам до 12.10.2026 — при правке ролика пересобрать page.py")
    if strict:
        silent = music_missing(page_text, project.name)
        check(not silent, silent or "фоновая музыка на месте")
        absent = required_missing(page_text, project.name)
        check(not absent, "обязательное проекта на месте: тихие звуки, вспышка после хука", absent)

    started = time.time()
    splices = take_splices(project)
    import formats
    zones = formats.grey_zones(stage_format(page_text)) if stage_format(page_text) else []
    faces = face_track(project)
    # дизайн-система: страница помечена проектом, у которого есть DESIGN.md (montage.py) — проверка цветов и шрифтов
    palette, marked = None, re.search(r'<meta name="reels-design" content="([^"]+)"', page_text)
    if marked:
        import design as ds
        name = html.unescape(marked.group(1))
        try:
            system = ds.by_name(name)
        except ds.DesignError as e:
            system = None
            check(False, "DESIGN.md проекта читается", str(e).splitlines())
        else:
            if system is None:
                check(False, f"страница собрана по дизайн-системе {name}, а projects/{name}/DESIGN.md нет")
        palette = system.allowed() if system else None
    res = run_timeline(page_path, fps, zones=zones, faces=faces, splices=splices, design=palette)
    if not res.get("ok"):
        check(False, "таймлайн разобран", [res.get("crash", "?")])
        return failed
    errors = res["pageErrors"] + [w for w in res["warnings"] if "not found" in w or "Invalid" in w]
    check(not errors, "страница без ошибок JS и пустых селекторов", errors)
    check(not res["stuck"], "в рендере ничего не залипает", [explain(i) for i in res["stuck"]])
    check(not res["risky"], "запас по кадрам: при сдвиге на кадр тоже не залипнет",
          [explain(i) for i in res["risky"]])
    if faces:
        hits = [f"{h['el']} закрывает лицо {h['from']:.2f}–{h['last'] + 0.25:.2f} с на {h['depth']} px — "
                f"подбородок доходит до y {h['faceBottom']}: верх карточки ≥ {h['faceBottom'] + 20}" for h in res.get("faceHits", [])]
        if strict:
            check(not hits, "карточки и графика не закрывают лицо (лицо — по кадрам, с движением камеры)", hits)
        elif hits:
            print(f"  · графика поверх лица: {len(hits)} (при правке ролика — опустить или убрать)")
    hidden = [f"{o['el']} за головой {o['from']:.2f}–{o['last'] + 0.25:.2f} с: голова закрывает {o['share'] * 100:.0f}% "
              f"строки — выше, мельче, сбоку или на грудь" for o in res.get("occluded", [])]
    if strict:
        check(not hidden, "текст за спиной не прячется за головой (закрыто не больше трети)", hidden)
    elif hidden:
        print(f"  · текст за головой закрыт: {len(hidden)}")
    dupes = [f"{d['el']} «{d['text']}» и субтитр «{d['cap']}» вместе {d['from']:.2f}–{d['last'] + 0.25:.2f} с — "
             f"на время текста субтитр прячет hide_captions, или текст не повторяет речь" for d in res.get("dupes", [])]
    gaps = [f"{a:.2f}–{b:.2f} с: {b - a:.1f} с речи без субтитров — схема, картинка и футаж их не прячут, "
            f"hide_captions — только пока текст на экране повторяет сказанное" for a, b in caption_gaps(project)]
    if strict:
        check(not dupes, "субтитры не двоятся с текстом на экране", dupes)
        check(not gaps, f"субтитры не пропадают дольше {CAP_GAP_MAX:g} с, пока идёт речь", gaps)
    elif dupes or gaps:
        print(f"  · субтитры двоятся: {len(dupes)}, пропадают дольше {CAP_GAP_MAX:g} с: {len(gaps)} (при правке ролика — hide_captions)")
    clips = sorted(set(re.findall(r'src="assets/footage/([^"]+\.mp4)"', page_text)))
    allowed = (load_director(project) or {}).get("footage_ok")
    if len(clips) > FOOTAGE_MAX and allowed:
        print(f"  · ИИ-видео {len(clips)} — больше {FOOTAGE_MAX}, осознанно: {allowed}")
    elif strict or len(clips) <= FOOTAGE_MAX:
        check(len(clips) <= FOOTAGE_MAX, f"ИИ-видео не больше {FOOTAGE_MAX} на ролик — только в самых топовых местах",
              [f"{len(clips)}: {', '.join(clips)} — остальные места закрой серией фото (kit.slides) или графикой"]
              if len(clips) > FOOTAGE_MAX else [])
    try:
        import projects
        need = float(projects.of(project.name.split("--")[0]).config.get("face_min", 0.6))
    except Exception:
        need = 0.6
    face = 1 - res.get("cutawayShare", 0)
    if strict:
        check(face >= need, f"человек в кадре не меньше {need * 100:.0f}% ролика ({face * 100:.0f}%)",
              [] if face >= need else [f"перебивки во весь кадр занимают {(1 - face) * 100:.0f}% — сократи их или замени "
                                       f"графикой поверх человека (project.json → face_min)"])
    try:
        cfg = projects.of(project.name.split("--")[0]).config
    except Exception:
        cfg = {}
    gap_max = cfg.get("insert_gap_max")
    if cfg.get("caption_accent_scale") and strict:
        flat = [f"{a:.2f}–{b:.2f} с: {b - a:.1f} с субтитров без ключевого слова — добавь в accent_words слово этого места"
                for a, b in accent_gaps(project)]
        check(not flat, f"ключевое слово в субтитрах — не реже раза в {ACCENT_EVERY:g} с (ровные субтитры — скучно)", flat)
    if gap_max and strict:
        bare = [f"{a:.2f}–{b:.2f} с: {b - a:.1f} с без единой вставки — поставь приём по словам этого места "
                f"(«Чертёж», штамп, клип, карточка)" for a, b in res.get("bare", []) if b - a > float(gap_max)]
        check(not bare, f"нет пустых мест без вставок дольше {float(gap_max):g} с (project.json → insert_gap_max)", bare)
    if palette:
        seen_off, off = set(), []
        for d in res.get("design", []):
            key = (d["el"], d["what"], d["value"])
            if key not in seen_off:
                seen_off.add(key)
                off.append(f"{d['el']}: {d['what']} {d['value']} — нет в DESIGN.md ({d['t']:.1f} с)")
        if strict:
            check(not off, "цвета и шрифты — только из DESIGN.md проекта", off)
        elif off:
            print(f"  · мимо DESIGN.md: {len(off)} (при правке ролика — цвет или шрифт из системы)")
    unmasked = cutout_gaps(project, page_text, res.get("fgShown", []))
    if unmasked and matte_pending:
        print(f"  · маска по окнам ещё не посчитана ({len(unmasked)}): {unmasked[0]}")
    else:
        check(not unmasked, "под каждым окном «человек поверх» посчитана маска", unmasked)
    over = res.get("fgOverCut", [])
    check(not over, "на перебивке (футаж, серия картинок) нет человека поверх — окна вырезки до и после",
          [f"вырезка видна поверх перебивки на {over[0]:.2f}–{over[-1]:.2f} с ({len(over)} замеров)"] if over else [])
    if not faces and strict and (take_dir(project) / "aroll.faces.json").exists():
        check(False, "лицо по кадрам не прочитано — проверка «не закрывает лицо» не сделана")
    soft = [f"{b['el']} размыт на {b['blur']:.1f} px {b['from']:.2f}–{b['last'] + 0.25:.2f} с — размытие только в "
            f"наплыве и уходе, на показе фон резкий" for b in res.get("softBg", []) if not b.get("allowed")]
    if strict:
        check(not soft, "фон за спиной не стоит размытым, пока виден (размытие — только в наплыве)", soft)
    elif soft:
        print(f"  · размытый фон на показе: {len(soft)} (при правке ролика — убрать blur с конечного состояния)")
    early = [f"{e['el']} виден уже на {e['t']:.2f} с, а его первое движение — на {e['first']:.2f} с: fromTo ставит начальные "
             f"значения сразу — в начальных opacity 0 или immediateRender: false" for e in res.get("early", [])]
    check(not early, "графика не видна раньше своего входа", early)
    spills = [f"{s['el']} «{s['text']}» вылезает за край {s['where']} на {s['depth']} px, {s['from']:.2f}–{s['last'] + 0.25:.2f} с"
              for s in res.get("spills", [])]
    if strict:
        check(not spills, "текст не вылезает за край своей плашки и за кадр", spills)
    elif spills:
        print(f"  · текст вылезает за плашку или кадр: {len(spills)} (при правке ролика — уменьшить шрифт или расширить)")
    holds = [f"{h['el']} висит без изменений {h['hold']:.1f} с ({h['from']:.2f}–{h['to']:.2f} с) — оживи изнутри "
             f"(строка, подсветка), раздели или убери раньше" for h in res.get("holds", [])]
    if strict:
        check(not holds, f"графика не висит без изменений дольше {HOLD_MAX:g} с (динамика)", holds)
    elif holds:
        print(f"  · графика висит без изменений дольше {HOLD_MAX:g} с: {len(holds)} (при правке ролика — оживить или убрать раньше)")
    for h in res.get("holdsAllowed", []):
        print(f"  · осознанно долгий показ: {h['el']} {h['hold']:.1f} с — {h['allowed']}")
    if zones:
        grey = [f"{g['el']} «{g['text']}» — {g['zone']}, {g['from']:.2f}–{g['last'] + 0.25:.2f} с, глубина {g['depth']} px"
                for g in res.get("grey", [])]
        if strict:
            check(not grey, "текст не заезжает в серые зоны площадок (шапка, ник и подпись, кнопки справа)", grey)
        elif grey:
            print(f"  · текст в серых зонах площадок: {len(grey)} (при правке ролика — поправить или пометить data-safe)")
        for g in res.get("greyAllowed", []):
            print(f"  · осознанный заезд: {g['el']} «{g['text']}» — {g['zone']}: {g['allowed']}")
    if splices:
        jumps = camera_jumps(project, splices)
        pauses = take_pause_cuts(project)
        bad = []
        for sp in res.get("splices", []):
            if any(abs(sp["t"] - p) <= 0.02 for p in pauses):
                sp["across"] = []
            t = sp["t"]
            if sp["flash"] < 0.3 and sp["blur"] < 4:
                bad.append(f"склейка {t:.2f} с: ни вспышки, ни смаза — splice({t:.2f}) в beats")
            jump = jumps.get(t)
            if jump is not None and jump < SPLICE_JUMP:
                bad.append(f"склейка {t:.2f} с: крупность меняется на {jump:.2f} (нужно ≥ {SPLICE_JUMP}) — "
                           f"наезд Take.splice_punches() в director.json")
            if sp["across"]:
                bad.append(f"склейка {t:.2f} с: через рез висит {', '.join(sp['across'][:4])} — уход до склейки, "
                           f"новое — на ней")
        if strict:
            check(not bad, "склейки спрятаны: переход, смена крупности, ничего не висит через рез", bad)
        elif bad:
            print(f"  · склейки без перехода: {len(bad)} (при правке ролика — splice() и Take.splice_punches)")
    if res["never"]:
        print(f"  · ни разу не появляются: {', '.join(res['never'][:12])}")
    print(f"  · {res['elements']} элементов, {res['tweens']} твинов прозрачности, {res['frames']} кадров "
          f"за {time.time() - started:.1f} с")
    return failed


def main():
    ap = argparse.ArgumentParser(description="Проверка страницы графики до рендера")
    ap.add_argument("stems", nargs="*", help="имена роликов (IMG_3317) или папки проектов")
    ap.add_argument("--all", action="store_true", help="все проекты в studio/")
    ap.add_argument("--fps", type=int, default=FPS)
    args = ap.parse_args()
    stems = args.stems or []
    if args.all:
        stems += [p.parent.name for p in sorted(STUDIO.glob("*/index.html")) if not p.parent.name.startswith("_")]
    if not stems:
        ap.error("укажи ролик или --all")

    bad = {}
    for stem in stems:
        failed = verify(stem, args.fps, strict=not args.all)
        if failed:
            bad[stem] = failed
        print()
    if bad:
        print(f"✗ страницы с ошибками: {', '.join(bad)} — рендерить нельзя, пока не поправим")
        sys.exit(1)
    print("✓ страницы чистые, можно рендерить")


if __name__ == "__main__":
    main()
