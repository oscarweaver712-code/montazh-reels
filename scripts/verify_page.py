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
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT

STUDIO = ROOT / "studio"
CHROME_CACHE = Path.home() / ".cache" / "hyperframes" / "chrome" / "chrome-headless-shell"
FPS = 30

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
        if (!touches(child.vars)) { idle.push(child); continue; }
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
          items.push({ el, nodes, allowed: safe ? safe.getAttribute("data-safe") : null });
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
          for (const node of it.nodes) {
            range.selectNodeContents(node);
            for (const raw of range.getClientRects()) {
              const r = { left: raw.left, right: raw.right,
                          top: Math.max(raw.top, box.top), bottom: Math.min(raw.bottom, box.bottom) };
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
                                     allowed: it.allowed });
              }
            }
          }
        }
        for (const [key, rec] of [...open]) if (!seen.has(key)) { if (rec.count >= 2) done.push(rec); open.delete(key); }
      }
      for (const rec of open.values()) if (rec.count >= 2) done.push(rec);
      for (const rec of done) (rec.allowed ? res.greyAllowed : res.grey).push(rec);
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


def sound_problems(page: str) -> list:
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
        if level > kit.SFX_TARGET + 0.5:
            problems.append(f"{name}: {level:.1f} LUFS — громче нормы {kit.SFX_TARGET:g} (на ~11 дБ тише голоса)")
    try:
        kit.check_sounds([page])
    except ValueError as e:
        problems += [line.strip() for line in str(e).splitlines()[1:]]
    return problems


def missing_assets(project: Path, page: str) -> list:
    refs = set(re.findall(r'(?:src|href)="(assets/[^"]+)"', page))
    refs |= set(re.findall(r"""url\(["']?(assets/[^"')]+)""", page))
    refs |= set(re.findall(r'data-composition-src="([^"]+)"', page))      # визуализации каталога
    return sorted(r for r in refs if not (project / r).exists())


def stage_format(page: str) -> str | None:
    """Формат сцены страницы по её viewport (kit пишет width/height сцены)."""
    import formats

    found = re.search(r'<meta name="viewport" content="width=(\d+), height=(\d+)"', page)
    return formats.of_size(int(found.group(1)), int(found.group(2))) if found else None


def run_timeline(page_path: Path, fps: int = FPS, timeout: float = 180, zones: list | None = None) -> dict:
    """Прогоняет таймлайн страницы в headless Chrome и возвращает разбор (см. CHECK_JS).

    zones — серые зоны площадок [(название, (x0, y0, x1, y1))]: текст в них попадёт в res["grey"].
    """
    page_path = Path(page_path).resolve()
    page = page_path.read_text(encoding="utf-8")
    # видео и звук для разбора не нужны — без них страница грузится за доли секунды
    page = re.sub(r'(<(?:video|audio)\b[^>]*?)\s+src="[^"]*"', r"\1", page)
    config = json.dumps({"fps": fps, "errors": [], "warnings": [], "zoneStep": 0.25, "zoneDepth": 8,
                         "zones": [{"name": name, "rect": list(rect)} for name, rect in (zones or [])]},
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


def explain(item: dict) -> str:
    """«субтитр «мы»: висит 48.87–96.07 с — уход в 48.85 раньше конца появления (48.90)»."""
    text = f"{item['el']}: {item['got']:.2f} вместо {item['want']:.2f} на {item['from']:.2f}–{item['to']:.2f} с"
    pair = item.get("why")
    if pair:
        a, b = pair["a"], pair["b"]
        text += (f" — {b['kind']} в {b['start']:.2f} кончается раньше, чем {a['kind']} "
                 f"{a['start']:.2f}–{a['end']:.2f}")
    return text


def verify(stem_or_dir: str, fps: int = FPS, strict: bool = True) -> list:
    """Печатает отчёт по странице; возвращает список провалов (пустой — можно рендерить).

    strict — страница идёт в рендер: собранная до норм звука не проходит. Сводка --all — не строгая.
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
    check(not gone, "все картинки, звуки и шрифты на месте", gone)
    if SFX_NORM_MARK in page_text:
        sounds = sound_problems(page_text)
        check(not sounds, "звуки: не громче нормы, без убранных и без одинаковых подряд", sounds)
    elif strict:
        check(False, "страница собрана до норм звука 12.10.2026 — пересобери её page.py "
                     "(старые звуки громче голоса и повторяются)")
    else:
        print("  · звуки по правилам до 12.10.2026 — при правке ролика пересобрать page.py")

    started = time.time()
    import formats
    zones = formats.grey_zones(stage_format(page_text)) if stage_format(page_text) else []
    res = run_timeline(page_path, fps, zones=zones)
    if not res.get("ok"):
        check(False, "таймлайн разобран", [res.get("crash", "?")])
        return failed
    errors = res["pageErrors"] + [w for w in res["warnings"] if "not found" in w or "Invalid" in w]
    check(not errors, "страница без ошибок JS и пустых селекторов", errors)
    check(not res["stuck"], "в рендере ничего не залипает", [explain(i) for i in res["stuck"]])
    check(not res["risky"], "запас по кадрам: при сдвиге на кадр тоже не залипнет",
          [explain(i) for i in res["risky"]])
    if zones:
        grey = [f"{g['el']} «{g['text']}» — {g['zone']}, {g['from']:.2f}–{g['last'] + 0.25:.2f} с, глубина {g['depth']} px"
                for g in res.get("grey", [])]
        if strict:
            check(not grey, "текст не заезжает в серые зоны площадок (шапка, ник и подпись, кнопки справа)", grey)
        elif grey:
            print(f"  · текст в серых зонах площадок: {len(grey)} (при правке ролика — поправить или пометить data-safe)")
        for g in res.get("greyAllowed", []):
            print(f"  · осознанный заезд: {g['el']} «{g['text']}» — {g['zone']}: {g['allowed']}")
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
