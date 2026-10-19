#!/usr/bin/env python3
"""Сборка страницы ролика поверх kit: обязательное ставится само, режиссёр пишет только содержание.

19.10.2026, Валера: «то звуки потеряются, то музыка, то переходов нет, то субтитры сливаются… не могу каждое видео
докручивать руками». До этого каждая page.py сама перечисляла склейки, смену плана, тихие звуки и музыку — и что
забыли, того в ролике не было: в пачке 1790–1827 тихих звуков и музыки ноль, в IMG_3292 v2 нет музыки. Montage.build
ставит обязательное всегда, и забыть его нельзя:

  склейка дубля   → splice() и наезд (tk.splice_punches), если страница не поставила их сама;
  смена плана     → каждые ~2,4 с (tk.framing) — мимо перебивок, окон вырезки, вспышки хука и угаров;
  вспышка хука    → вспышка с отъездом и звуком на первом слове основы (project.json → hook_flash; место — лучший
                    кандидат events.hook_candidates или m.hook(t); без неё — m.hook(None, "почему"));
  угар            → кусок edit.json → blooper: серый кадр, виньетка, штамп «НЕ ВОШЛО»; мат в субтитрах — «***»;
  тихие звуки     → по движениям самой страницы (splice, whip, slam, enter, card, doc, draw, bars, вход перебивки)
                    плюс свои события m.soft(t, вид) — раскладывает kit.soft_track по правилам п.9;
  музыка          → music.pick: свой трек ролику из фонотеки YouTube без указания автора (project.json → music);
  лицо            → перебивки во весь кадр вместе не больше 1 − face_min ролика (Валера: «в 50+% видео моё лицо»);
  «Чертёж»        → m.blueprint(piece) (scripts/blueprint.py): за спиной — окно вырезки; на груди — поверх; сплит — лист
                    с окном, сцена в окне, субтитры под подбородком в окне; во весь кадр — перебивка с переходами.
                    ИИ-клипы и серии фото — в рамке листа, если project.json → insert_style = "blueprint".

  from montage import Montage
  m = Montage(STEM, VARIANT)
  t = m.t                                     # секунда исходника → секунда дубля (kit.Take.t)
  m.behind(html); m.front(html); m.js(js); m.css(css)
  m.punch(t(1.94), t(2.70))                   # акцент камеры уровня стиля
  m.sound("uz", "impact-bass-1", t(1.94), 0.9)
  m.fg(a, b); m.hide(a, b); m.wide(a, b)      # окно вырезки, без субтитров, без крупного плана
  m.footage("ft-india", "a_india", at, dur)   # перебивка Flow; m.slides(...) — серия картинок
  m.build("Заголовок", cta_at=t(85.7), text_fixes={...}, accent_words=[...])

Время везде — шкала дубля (как у build_page). Что Montage поставил сам, он печатает: это часть отчёта.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import formats  # noqa: E402
import kit  # noqa: E402
from common import ROOT, WORK_DIR  # noqa: E402

MARK = '<meta name="reels-montage" content="2026-10-19" />'
HOOK_SOUND = "whoosh-cinematic"
HOOK_ZOOM = 0.22           # вспышка хука: кадр бьёт на базу + 0.22 и отъезжает за HOOK_PULL
HOOK_PULL = 0.9
BLOOPER_LOOK = "grayscale(1) contrast(1.15) brightness(0.9)"
SOFT_EVERY = 6.0           # тихих звуков не реже одного на 6 с ролика (принятый стиль IMG_3303 v5 — раз в 2,4 с)

# движения страницы → вид тихого звука (kit.SOFT_KINDS)
_TIMED = re.compile(r"\b(splice|whip)\(\s*([\d.]+)\s*\)")
_AT = re.compile(r"\b(slam|enter|card|doc|draw|bars)\(\s*(?:\"[^\"]*\"|'[^']*'|`[^`]*`|\[[^\]]*\])\s*,\s*([\d.]+)")
_CUT_FLASH = re.compile(r'tl\.fromTo\("#flash", \{ opacity: 0 \}, \{ opacity: 0\.5[^;]*?, ([\d.]+)\);')
_KIND = {"splice": "cut", "whip": "frame", "slam": "stamp", "enter": "text", "card": "text", "doc": "text",
         "draw": "line", "bars": "line"}


def page_events(js: str) -> list:
    """Тихие события по движениям страницы: [(t, вид)] — только там, где время записано числом."""
    out = [(float(m.group(2)), _KIND[m.group(1)]) for m in _TIMED.finditer(js)]
    out += [(float(m.group(2)), _KIND[m.group(1)]) for m in _AT.finditer(js)]
    out += [(round(float(m.group(1)) + 0.033, 3), "cut") for m in _CUT_FLASH.finditer(js)]    # вход перебивки
    return sorted(set(out))


class Montage:
    def __init__(self, stem: str, variant: str | None = None):
        import projects
        self.stem, self.variant = stem, variant
        self.tk = kit.Take(stem, variant)
        self.t = self.tk.t
        self.duration = self.tk.duration
        self.project = projects.of_or_default(stem)
        self.cfg = self.project.config
        self.width, self.height = formats.size(self.tk.fmt)
        self._behind, self._front, self._js, self._css = [], [], [], []
        self.sounds, self.punches, self.fg_windows, self.hidden, self.wide_windows = [], [], [], [], []
        self.cutaways, self.extra_soft, self.notes = [], [], []
        self.splits, self._bp, self._fig = [], False, 0
        self.hook_at, self.hook_why = "auto", ""

    # ---------------------------------------------------------------- содержание (пишет режиссёр)

    def behind(self, html: str):
        self._behind.append(html)

    def front(self, html: str):
        self._front.append(html)

    def js(self, js: str):
        self._js.append(js.rstrip("\n") + "\n")

    def css(self, css: str):
        self._css.append(css)

    def punch(self, a: float, b: float, level: float | None = None, ease_in: float = 0.08, ease_out: float = 0.25):
        self.punches.append([round(a, 2), round(b, 2), level or self.tk.punch, ease_in, ease_out])

    def sound(self, sid: str, name: str, at: float, level: float = 1.0, **kw):
        self.sounds.append(kit.audio(sid, name, at, level, **kw))

    def soft(self, at: float, kind: str):
        self.extra_soft.append((round(at, 3), kind))

    def fg(self, a: float, b: float):
        self.fg_windows.append((round(a, 2), round(b, 2)))

    def hide(self, a: float, b: float):
        self.hidden.append([round(a, 2), round(b, 2)])

    def wide(self, a: float, b: float):
        self.wide_windows.append((round(a, 2), round(b, 2)))

    def cutaway(self, html: str, js: str, at: float, dur: float):
        """Своя перебивка во весь кадр (человека нет): html — в behind, учитывается в доле лица."""
        self.behind(html)
        self.js(js)
        self.cutaways.append((round(at, 2), round(at + dur, 2)))

    def _look(self, label: str, kw: dict) -> dict:
        """Рамка мотива проекта для клипа и фото во весь кадр (insert_style), если страница не задала свою."""
        if self.cfg.get("insert_style") == "blueprint" and "overlay" not in kw:
            import blueprint as bp
            self._fig += 1
            overlay, clip = bp.look(label, self._fig)
            kw = {**kw, "overlay": overlay, "clip_css": clip}
        return kw

    def footage(self, fid: str, name: str, at: float, dur: float, label: str = "", **kw):
        kw = self._look(label, kw)
        self.cutaway(*kit.footage(fid, self.stem, name, at, dur, fmt=self.tk.fmt, **kw), at, dur)

    def slides(self, sid: str, images: list, at: float, durs: list, label: str = "", **kw):
        kw = self._look(label, kw)
        self.cutaway(*kit.slides(sid, images, at, durs, fmt=self.tk.fmt, **kw), at, sum(durs))

    def blueprint(self, piece):
        """Приём «Чертежа» (blueprint.Piece) в его раскладке — всё, что раскладке нужно, ставит сборка."""
        import blueprint as bp
        if not self._bp:
            self.css(bp.CSS)
            self._bp = True
        a, b = piece.t0, piece.t1
        if piece.layout == "behind":                 # линии на шторе, человек поверх
            self.behind(piece.html)
            self.js(piece.js)
            self.fg(a - 0.05, b + 0.4)
            self.wide(a - 0.3, b + 0.4)
        elif piece.layout == "chest":
            self.front(piece.html)
            self.js(piece.js)
        elif piece.layout == "full":
            at, until = a - 0.25, b + 0.35
            html, js = bp.full_sheet(piece, at, until)
            self.cutaway(html, js, at, until - at)
        else:                                        # сплит: лист и сцена — в build, по лицу в этом окне
            self.front(piece.html)
            self.splits.append(piece)
            self.wide(a - 0.3, b + 0.4)

    def _face(self, a: float, b: float) -> tuple:
        """Лицо на экране (x0, y0, x1, y1) в окне [a, b] — по слежению с камерой; камеры ещё нет — типичное."""
        import verify_page
        track = verify_page.face_track(ROOT / "studio" / self.tk.project)
        seen = [f for f in track if a <= f[0] <= b] or track
        if not seen:
            self.notes.append("сплит — по типичному лицу: камеры ещё нет; после compose собери page.py ещё раз")
            return (330.0, 440.0, 750.0, 1060.0)
        q = lambda i, k: sorted(f[i] for f in seen)[min(len(seen) - 1, int(k * len(seen)))]     # noqa: E731
        return (q(1, 0.5), q(2, 0.5), q(3, 0.5), q(4, 0.9))   # подбородок — по наклонам вниз: под ним линия субтитров

    def hook(self, at: float | None, why: str = ""):
        """Конец хука — первое слово основы, шкала дубля. None — без вспышки, причина обязательна (в отчёт)."""
        if at is None and not why:
            raise ValueError("Без вспышки после хука — скажи почему: m.hook(None, \"причина\")")
        self.hook_at, self.hook_why = at, why

    # ---------------------------------------------------------------- обязательное (ставит сборка)

    def _hook_time(self) -> float | None:
        if not self.cfg.get("hook_flash"):
            return None
        if self.hook_at != "auto":
            return self.hook_at
        import events
        words = [dict(w, n=events.norm(w["word"])) for w in self.tk.words if events.norm(w["word"])]
        found = events.hook_candidates(words)
        return found[0][0] if found else None

    def _hook_parts(self, at: float) -> tuple:
        html = (f'        <div id="hook-flash" style="position: absolute; left: 0; top: 0; width: {self.width}px; '
                f'height: {self.height}px; background: #fff; opacity: 0;"></div>')
        js = (f'      // вспышка с отъездом после хука (Валера 19.10.2026): белый удар, кадр крупнее и отъезд за {HOOK_PULL} с\n'
              f'      tl.fromTo("#hook-flash", {{ opacity: 0 }}, {{ opacity: 0.9, duration: 0.05, ease: "none", '
              f'immediateRender: false }}, {at - 0.07:.3f});\n'
              f'      tl.to("#hook-flash", {{ opacity: 0, duration: 0.32, ease: "power2.out" }}, {at - 0.02:.3f});\n'
              f'      tl.fromTo(".cam", {{ filter: BLUR(10) }}, {{ filter: BLUR(0), duration: 0.2, ease: "power2.out", '
              f'immediateRender: false }}, {at - 0.02:.3f});\n')
        punch = [round(at - 0.02, 2), round(at + HOOK_PULL, 2), round(self.tk.base_zoom + HOOK_ZOOM, 2), 0.0, HOOK_PULL]
        return html, js, punch

    def _blooper_parts(self, k: int, a: float, b: float, cutout: bool) -> tuple:
        videos = '["#aroll", "#cutout"]' if cutout else '"#aroll"'
        html = (f'        <div id="bl{k}-v" style="position: absolute; left: 0; top: 0; width: {self.width}px; '
                f'height: {self.height}px; opacity: 0; background: radial-gradient(ellipse at 50% 45%, rgba(0,0,0,0) 45%, '
                f'rgba(0,0,0,0.6) 100%);"></div>\n'
                f'        <div id="bl{k}" class="g" style="left: 0; top: 285px; width: {self.width}px; text-align: center;">'
                f'<span class="stamp" style="display: inline-block; font-size: 84px;">не вошло</span></div>')
        js = (f'      // угар (edit.json → blooper): серый кадр, виньетка, штамп; маты под «пипом» и «***» в субтитрах\n'
              f'      tl.set({videos}, {{ filter: "{BLOOPER_LOOK}" }}, {a:.3f});\n'
              f'      tl.set({videos}, {{ filter: "none" }}, {b:.3f});\n'
              f'      tl.set("#bl{k}-v", {{ opacity: 1 }}, {a:.3f});\n'
              f'      tl.set("#bl{k}-v", {{ opacity: 0 }}, {b:.3f});\n'
              f'      slam("#bl{k}", {a + 0.12:.2f}, {{ rot: -6 }});\n'
              f'      leave("#bl{k}", {max(a + 0.5, b - 0.3):.2f}, {{ rot: -6 }});\n')
        return html, js

    def _sounds_with(self, extra: list) -> bool:
        try:
            kit.check_sounds(self.sounds + extra)
            return True
        except ValueError:
            return False

    def build(self, title: str, cta_at: float | None = None, text_fixes: dict | None = None,
              accent_words: list | None = None, keep_case: list | None = None, track: str | None = None,
              framing: bool = True, cutout: bool = True, director_extra: dict | None = None, **page_kw) -> str:
        """Собирает studio/<проект>/index.html и work/<имя>/director.json; печатает, что поставлено само."""
        import events
        tk, dur = self.tk, self.duration
        kit.check_sounds(self.sounds)                       # свои звуки режиссёра — сначала по правилам п.9
        auto_front, auto_js, auto_punch = [], [], []

        hook = self._hook_time()
        if hook is not None:
            html, js, punch = self._hook_parts(hook)
            auto_front.append(html)
            auto_js.append(js)
            auto_punch.append(punch)
            sound = kit.audio("hook", HOOK_SOUND, round(max(0.0, hook - 0.25), 2), 0.8)
            if self._sounds_with([sound]):
                self.sounds.append(sound)
                self.notes.append(f"вспышка с отъездом после хука на {hook:.2f} с + {HOOK_SOUND}")
            else:
                self.extra_soft.append((hook, "cut"))
                self.notes.append(f"вспышка с отъездом после хука на {hook:.2f} с; {HOOK_SOUND} не встал рядом с ударами "
                                  f"страницы — вместо него тихий накат")
        elif self.cfg.get("hook_flash"):
            self.notes.append(f"вспышки после хука нет: {self.hook_why or 'не нашлось границы фразы в 2–14 с'}")

        for k, (a, b) in enumerate(tk.bloopers):
            html, js = self._blooper_parts(k, a, b, cutout)
            auto_front.append(html)
            auto_js.append(js)
            self.notes.append(f"угар {a:.2f}–{b:.2f} с: серый кадр, штамп «не вошло»")

        fixes = dict(text_fixes or {})
        for i, w in enumerate(tk.words):                  # мат в субтитрах — «***», если режиссёр не решил иначе
            if str(i) not in fixes and events.is_mat(w.get("word", "")):
                fixes[str(i)] = "***"

        page_js = "".join(self._js)
        have = {round(float(x), 2) for x in re.findall(r"\bsplice\(\s*([\d.]+)\s*\)", page_js)}
        missing = [j for j in tk.splices if all(abs(j - h) > 0.05 for h in have)]
        if missing:
            auto_js.append("".join(f"      splice({j:.3f});\n" for j in missing))
            self.notes.append(f"склеек дубля спрятано сборкой: {len(missing)}")

        # перебивки и сплиты не налезают друг на друга: клип внутри окна листа, две вспышки подряд (19.10.2026, демо
        # IMG_3292: сплит вошёл, пока шёл клип «Индия»). Стык — можно: вспышки сливаются в одну
        spans = sorted([(a0, b0, "перебивка") for a0, b0 in self.cutaways]
                       + [(round(p.t0 - 0.25, 2), round(p.t1 + 0.3, 2), f"сплит {p.pid}") for p in self.splits])
        for (a0, b0, n0), (a1, b1, n1) in zip(spans, spans[1:]):
            if a1 < b0 - 0.05:
                raise ValueError(f"{n0} {a0:.2f}–{b0:.2f} с и {n1} {a1:.2f}–{b1:.2f} с налезают друг на друга — стыкуй "
                                 f"конец одной с началом другой (сплит входит за 0,25 с до первого шага) или разведи")
        sheets, lanes = [], []
        for piece in self.splits:
            import blueprint as bp
            geo = bp.split_geometry(self._face(piece.t0, piece.t1))
            html, js = bp.split_parts(piece, geo)
            sheets.append(html)
            auto_js.append(js)
            lanes.append([round(piece.t0 - 0.25, 2), round(piece.t1 + 0.3, 2), geo["lane"]])
            self.notes.append(f"сплит «Чертёж» {piece.t0:.2f}–{piece.t1:.2f} с: человек в окне {geo['hole']}, "
                              f"субтитры на y {geo['lane']}")
        if self.splits:
            import blueprint as bp
            self.css(bp.SPLIT_CSS)

        switch, whips = [], ""
        if framing:
            keep = list(self.wide_windows) + list(self.cutaways) + list(self.fg_windows) + [tuple(x) for x in tk.bloopers]
            if hook is not None:
                keep.append((hook - 0.3, hook + HOOK_PULL + 0.3))
            switch, whips = tk.framing(keep_wide=keep)
            auto_js.append(whips)
            self.notes.append(f"смена плана: {len(switch)} крупных")

        beats = page_js + "".join(auto_js)
        soft = sorted(set(page_events(beats)) | set(self.extra_soft))
        self.sounds += kit.soft_track(soft, self.sounds)
        n_soft = sum('id="sfx-soft' in s for s in self.sounds)
        if n_soft < dur / SOFT_EVERY:
            raise ValueError(f"Тихих звуков монтажа {n_soft} на {dur:.0f} с — меньше одного на {SOFT_EVERY:g} с: на странице мало "
                             f"движения (склеек, влётов, линий) — ролик выйдет «мёртвым», добавь удары или m.soft()")
        if self.cfg.get("music"):
            import music
            track = track or music.pick(self.stem, self.project.name)
            self.sounds.append(kit.background_music(self.stem, track, dur))
            self.notes.append(f"музыка: {track}")

        covered = sum(b - a for a, b in self.cutaways)
        face = 1 - covered / dur
        need = float(self.cfg.get("face_min", 0.6))
        if face < need:
            raise ValueError(f"Человек в кадре {face * 100:.0f}% ролика, а проект требует ≥ {need * 100:.0f}% "
                             f"(project.json → face_min): перебивок во весь кадр {covered:.1f} с — сократи или замени "
                             f"графикой поверх человека")
        self.notes.append(f"человек в кадре {face * 100:.0f}% ролика")

        cfg_cta = self.cfg.get("cta", True)
        if cfg_cta and cta_at is not None and not any(a <= cta_at and b >= dur - 0.05 for a, b in self.hidden):
            self.hidden.append([round(cta_at - 0.2, 2), round(dur, 2)])     # плашка в конце сама говорит «переходи»
        captions = tk.captions
        if captions and self.cfg.get("caption_accent_scale"):         # ключевые слова крупнее (project.json)
            captions = {**captions, "accent_scale": float(self.cfg["caption_accent_scale"])}
        if not accent_words:
            self.notes.append("ключевых слов в субтитрах нет (accent_words) — субтитры пойдут ровно, без ударов")
        page = kit.build_page(title, dur, "\n".join(self._behind), "\n".join(sheets + self._front + auto_front), beats,
                              self.sounds, self.fg_windows, cta_at if cta_at is not None else dur - 2.5,
                              extra_css="".join(self._css), fmt=tk.fmt, captions=captions, cutout=cutout,
                              cta=cfg_cta and cta_at is not None, **page_kw)
        mark = MARK + (f'\n    <meta name="reels-hook" content="без вспышки: {self.hook_why}" />' if hook is None else "")
        page = page.replace('<meta name="reels-sfx-norm"', mark + '\n    <meta name="reels-sfx-norm"', 1)
        if self.splits:
            import fx
            page = fx.FX(stage=True).finalize(page)          # сцена в обёртке #stage — её двигает сплит
        out = ROOT / f"studio/{tk.project}/index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(page, encoding="utf-8")

        director = {"_note": f"{self.stem}: собрано montage.py — обязательное (склейки, смена плана, вспышка хука, угар, "
                             f"тихие звуки, музыка) поставлено сборкой; содержание — work/{self.stem}/page.py.",
                    "punches": self.punches + tk.splice_punches() + switch + auto_punch,
                    "text_fixes": fixes, "keep_case": keep_case or [], "accent_words": accent_words or [],
                    "hide_captions": self.hidden, **(director_extra or {})}
        if lanes:
            director["caption_lanes"] = sorted((director.get("caption_lanes") or []) + lanes)
        path = WORK_DIR / self.stem / f"director{'.' + self.variant if self.variant else ''}.json"
        path.write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"✓ {out.relative_to(ROOT)} · {dur:.1f} с · тихих звуков {n_soft}")
        for note in self.notes:
            print(f"  · {note}")
        return page
