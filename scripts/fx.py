#!/usr/bin/env python3
"""Приёмы из рилса @tenfoldmarc «17 video effects claude can create» (instagram.com/reel/Def9pj5TWtA, 16.10.2026).

Валера: «спиздить все приёмы — этот чел гений». Разбор по кадрам — docs/ПРИЁМЫ-17.md. Здесь — каждый приём
функцией для page.py рядом с kit и viz. Функция возвращает FX: куски страницы (behind — за человеком, front —
перед ним), удары таймлайна (js), стили (css) и окна вырезки (windows — когда человек должен стоять поверх
слоя behind). Блоки — класса .g прямо в #behind/#front: их видят проверки страницы и монтажная студии (сдвиг,
выключение, текст). Несколько приёмов складывает merge(), в страницу — так же, как остальное:

    import fx
    fx.use_for(STEM)                   # тема проекта ролика (project.json → fx_theme), до сборки приёмов
    from fx import merge, checklist, wall, vertigo
    parts = merge(checklist("ck", "Всё, что нужно", ["Скинь дубль", "Нажми кнопку"], [t(3.1), t(4.0)], t(6.0)),
                  vertigo(t(12.0), t(13.2)))
    page = build_page(..., behind=behind + parts.behind, front=front + parts.front, beats=beats + parts.js,
                      fg_windows=windows + parts.windows, extra_css=parts.css)
    page = parts.finalize(page)        # приёмам со сценой (отъезд, пролёт) — обёртка #stage

Время — по шкале дубля (Take.t), как у всей графики. Всё движется таймлайном GSAP, без своих часов: рендер шагает
по кадрам, и страница обязана давать один и тот же кадр на одно время. Слои камеры (.cam) не трогаются —
их ведут ключи камеры; приёмы двигают видео внутри (#aroll, #cutout) или обёртку #stage и возвращают их в покой.
"""
import html as html_lib
import math

W, H = 1080, 1920
# Темы: приёмы референса в его стиле (default — жёлтый, Inter, тёмное стекло) или в стиле проекта. В CSS — метки
# @ИМЯ@, их значения даёт тема; цвета в таймлайне берутся из неё же (T()). Тему ставит fx.use() ДО сборки приёмов.
THEMES = {
    "default": {
        "ACCENT": "#F5E15A", "ACCENT_INK": "#141210", "ACCENT_GLOW": "rgba(245,225,90,0.6)",
        "SANS": '"InterX", "Manrope", sans-serif', "HEAD": '"InterX", "Manrope", sans-serif', "HEAD_CASE": "none",
        "MAST": '"Cormorant", serif', "MAST_WEIGHT": "500",
        "PLATE_BG": "rgba(18,18,20,0.62)", "PLATE_BORDER": "1.5px solid rgba(255,255,255,0.14)", "PLATE_RADIUS": "28px",
        "PLATE_TEXT": "#FFFFFF", "PLATE_MUTED": "rgba(255,255,255,0.4)", "PLATE_LINE": "rgba(255,255,255,0.08)",
        "LIGHT": "#FFFFFF", "LIGHT_MUTED": "rgba(255,255,255,0.75)", "PAPER": "#FBF8F0", "INK": "#1A1714",
        "PIN": "#C8291F", "TAPE": "rgba(245,225,90,0.85)", "SCRIBBLE": "#2B4BD8", "OK": "#3FB950",
        "SCENE": "linear-gradient(160deg, #6A3DF0 0%, #3A1FB8 45%, #1A1050 100%)",
        "RANSOM": [("#1F3FA8", "#fff", "'InterX'"), ("#fff", "#141210", "'Cormorant'"), ("#141210", "#fff", "'JBMono'"),
                   ("#F5E15A", "#141210", "'InterX'"), ("#C8291F", "#fff", "'Cormorant'")],
        "MARKS": ["#fff", "#FF8FB1", "#F5E15A", "#fff"],
    },
    # стиль проекта antishkola (projects/antishkola/rules.md п.14, IMG_3303 v5): крем #F2EBDD и красный #F0352C, жёлтого
    # нет; крупное — Oswald заглавными, подвод и мелкое — Manrope, цитаты и номера — Cormorant; без тёмных плашек —
    # плашка = бумага, как карточки-портреты
    "antishkola": {
        "ACCENT": "#F0352C", "ACCENT_INK": "#F2EBDD", "ACCENT_GLOW": "rgba(240,53,44,0.45)",
        "SANS": '"Manrope", sans-serif', "HEAD": '"Oswald", sans-serif', "HEAD_CASE": "uppercase",
        "MAST": '"Oswald", sans-serif', "MAST_WEIGHT": "700",
        "PLATE_BG": "#F1E9D8", "PLATE_BORDER": "none", "PLATE_RADIUS": "6px",
        "PLATE_TEXT": "#141210", "PLATE_MUTED": "rgba(20,18,16,0.42)", "PLATE_LINE": "rgba(20,18,16,0.12)",
        "LIGHT": "#F2EBDD", "LIGHT_MUTED": "rgba(242,235,221,0.8)", "PAPER": "#F1E9D8", "INK": "#141210",
        "PIN": "#F0352C", "TAPE": "rgba(242,235,221,0.88)", "SCRIBBLE": "#F0352C", "OK": "#F0352C",
        "SCENE": "radial-gradient(ellipse at 50% 35%, #F2EBDD 0%, #E3D6BC 55%, #B9A988 100%)",
        "RANSOM": [("#F0352C", "#F2EBDD", "'Oswald'"), ("#F2EBDD", "#141210", "'Cormorant'"), ("#141210", "#F2EBDD", "'Oswald'"),
                   ("#F2EBDD", "#F0352C", "'Manrope'"), ("#141210", "#F0352C", "'Cormorant'")],
        "MARKS": ["#F2EBDD", "#F0352C", "#F2EBDD", "#F0352C"],
    },
}
_theme = {"name": "default"}


def use(name: str) -> None:
    """Тема приёмов на эту страницу. Неизвестная — громкая ошибка, а не стиль референса молча."""
    if name not in THEMES:
        raise ValueError(f"fx: темы «{name}» нет — есть {', '.join(THEMES)}")
    _theme["name"] = name


def use_for(stem: str) -> str:
    """Тема из project.json проекта ролика (поле fx_theme). page.py зовёт её первой строкой приёмов — так тема
    не забывается: у antishkola без неё приёмы вышли бы жёлтыми, а жёлтого в стиле проекта нет (rules.md п.14)."""
    import projects
    name = projects.of_or_default(stem).config.get("fx_theme", "default")
    use(name)
    return name


def T(key: str):
    return THEMES[_theme["name"]][key]


CSS = {
    "base": """
      @font-face { font-family: "InterX"; src: url("assets/fonts/InterDisplay-ExtraBold.ttf"); font-weight: 800; }
      .fx { position: absolute; opacity: 0; }
      .fx-sans { font-family: @HEAD@; font-weight: 800; letter-spacing: -0.02em; text-transform: @HEAD_CASE@; }
      .fx-glass { background: @PLATE_BG@; border: @PLATE_BORDER@; border-radius: @PLATE_RADIUS@;
                  box-shadow: 0 30px 80px rgba(0,0,0,0.45); }
""",
    "stage": """
      #stage { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; transform-origin: 0 0; }
""",
    "toc": """
      .fx-toc { display: flex; gap: 26px; padding: 18px 22px; }
      .fx-toc ol { list-style: none; }
      .fx-toc li { position: relative; font-family: @SANS@; font-weight: 800; font-size: 25px; line-height: 1.36;
                   color: @PLATE_MUTED@; white-space: nowrap; }
      .fx-toc li b { display: inline-block; width: 38px; font-size: 17px; opacity: 0.7; }
      .fx-toc li u { position: absolute; left: -14px; top: 9px; width: 6px; height: 18px; border-radius: 3px;
                     background: @ACCENT@; opacity: 0; }
""",
    "check": """
      .fx-check { padding: 26px 30px; width: 700px; }
      .fx-check h4 { font-family: @SANS@; font-size: 22px; letter-spacing: 0.16em; text-transform: uppercase;
                     color: @PLATE_MUTED@; margin-bottom: 14px; display: flex; justify-content: space-between; }
      .fx-check .row { display: flex; align-items: center; gap: 22px; padding: 12px 0; font-family: @SANS@; font-weight: 800;
                       font-size: 40px; color: @PLATE_MUTED@; }
      .fx-check .row + .row { border-top: 1.5px solid @PLATE_LINE@; }
      .fx-check .box { position: relative; width: 50px; height: 50px; flex: none; border-radius: 25px;
                       border: 3px solid @PLATE_MUTED@; }
      .fx-check .fill { position: absolute; inset: -3px; border-radius: 25px; background: @ACCENT@; }
      .fx-check svg { position: absolute; inset: 0; }
""",
    "phone": """
      .fx-phone { width: 270px; height: 560px; border-radius: 52px; background: #0E0F12; padding: 16px;
                  box-shadow: 0 0 0 3px #2A2C31, 0 40px 90px rgba(0,0,0,0.6); }
      .fx-phone .scr { position: relative; width: 100%; height: 100%; border-radius: 38px; overflow: hidden;
                       background: linear-gradient(180deg, #17181C, #0F1013); padding: 70px 18px 18px; }
      .fx-phone .notch { position: absolute; left: 50%; top: 14px; width: 110px; height: 30px; margin-left: -55px;
                         border-radius: 16px; background: #000; }
      .fx-phone .who { position: absolute; left: 0; right: 0; top: 46px; text-align: center; font-family: @SANS@;
                       font-size: 17px; color: rgba(255,255,255,0.55); }
      .fx-phone .msg { margin-top: 12px; max-width: 86%; padding: 12px 16px; border-radius: 20px; font-family: @SANS@;
                       font-weight: 800; font-size: 21px; line-height: 1.25; opacity: 0; }
      .fx-phone .me { margin-left: auto; background: @ACCENT@; color: @ACCENT_INK@; border-bottom-right-radius: 6px; }
      .fx-phone .ai { background: #24262C; color: #EDEDED; border-bottom-left-radius: 6px; }
""",
    "chat": """
      .fx-chat { width: 900px; padding: 24px 26px 22px; border-radius: 30px; background: @PAPER@;
                 box-shadow: 0 30px 80px rgba(0,0,0,0.45); font-family: @SANS@; font-weight: 800; color: @INK@; }
      .fx-chat .hd { display: flex; align-items: center; gap: 10px; font-size: 24px; margin-bottom: 18px; }
      .fx-chat .hd i { width: 22px; height: 22px; border-radius: 11px; background: #D97757; }
      .fx-chat .drop { position: relative; height: 170px; border: 2.5px dashed rgba(0,0,0,0.2); border-radius: 20px;
                       display: flex; align-items: center; justify-content: center; gap: 14px; }
      .fx-chat .drop span { position: absolute; font-size: 22px; color: rgba(0,0,0,0.4); }
      .fx-chat .th { width: 96px; height: 140px; border-radius: 12px; background-size: cover; background-position: center;
                     box-shadow: 0 8px 20px rgba(0,0,0,0.25); opacity: 0; }
      .fx-chat .tag { position: absolute; right: 16px; top: 14px; padding: 6px 14px; border-radius: 10px; background: @ACCENT@;
                      color: @ACCENT_INK@; font-size: 18px; letter-spacing: 0.08em; opacity: 0; }
      .fx-chat .inp { margin-top: 16px; padding: 16px 20px; border-radius: 16px; border: 2px solid rgba(0,0,0,0.1);
                      font-family: "JBMono", monospace; font-size: 26px; color: @INK@; min-height: 64px; }
      .fx-chat .inp span { opacity: 0; }
""",
    "wall": """
      .fx-note { width: 250px; padding: 18px 18px 22px; background: @PAPER@; border-radius: 4px; font-family: @SANS@;
                 font-weight: 800; font-size: 27px; line-height: 1.12; color: @INK@; box-shadow: 0 16px 34px rgba(0,0,0,0.42); }
      .fx-note::before { content: ""; position: absolute; left: 50%; top: -12px; width: 22px; height: 22px; margin-left: -11px;
                         border-radius: 11px; background: @PIN@; box-shadow: inset -3px -3px 6px rgba(0,0,0,0.3); }
      .fx-shot { width: 230px; height: 300px; border-radius: 6px; background-size: cover; background-position: center;
                 border: 10px solid @PAPER@; box-shadow: 0 16px 34px rgba(0,0,0,0.45); }
""",
    "orbit": """
      .fx-orb { width: 150px; height: 266px; border-radius: 12px; overflow: hidden; background-size: cover;
                background-position: center; border: 6px solid @PAPER@;
                box-shadow: 0 20px 40px rgba(0,0,0,0.45); display: flex; align-items: flex-end; padding: 14px;
                font-family: @SANS@; font-weight: 800; font-size: 22px; line-height: 1.1; color: #fff; }
""",
    "chart": """
      .fx-days { display: flex; justify-content: space-between; width: 840px; font-family: @SANS@; font-weight: 800;
                 font-size: 30px; color: @LIGHT_MUTED@; text-shadow: 0 2px 12px rgba(0,0,0,0.6); }
      .fx-pill { padding: 10px 22px; border-radius: 30px; background: @ACCENT@; color: @ACCENT_INK@; font-family: @HEAD@;
                 font-weight: 800; text-transform: @HEAD_CASE@; font-size: 30px; letter-spacing: 0.06em;
                 box-shadow: 0 0 40px @ACCENT_GLOW@; }
""",
    "pull": """
      .fx-side { width: 300px; padding: 22px; border-radius: @PLATE_RADIUS@; background: @PAPER@; font-family: @SANS@;
                 font-weight: 800; box-shadow: 0 20px 50px rgba(30,25,15,0.18); }
      .fx-side .t { font-size: 18px; letter-spacing: 0.14em; color: rgba(0,0,0,0.4); text-transform: uppercase; margin-bottom: 10px; }
      .fx-side .r { display: flex; gap: 12px; align-items: center; font-size: 23px; color: @INK@; padding: 8px 0; opacity: 0.25; }
      .fx-side .r i { width: 24px; height: 24px; border-radius: 12px; background: @OK@; flex: none; }
      .fx-bar { height: 22px; border-radius: 11px; background: rgba(0,0,0,0.1); overflow: hidden; }
      .fx-bar i { display: block; height: 100%; width: 100%; background: @OK@; transform-origin: 0 50%; }
      .fx-count { font-family: "Cormorant"; font-weight: 600; font-size: 180px; color: @INK@; line-height: 1;
                  font-variant-numeric: lining-nums tabular-nums; }
""",
    "paper": """
      .fx-paper { left: 0; top: 0; width: 1080px; height: 1920px; background-color: @PAPER@;
                  background-image: radial-gradient(rgba(0,0,0,0.05) 1px, transparent 1.4px),
                                    linear-gradient(rgba(120,140,190,0.18) 2px, transparent 2px);
                  background-size: 7px 7px, 100% 64px; }
      .fx-tape { width: 240px; height: 70px; background: @TAPE@; box-shadow: 0 4px 10px rgba(0,0,0,0.12); }
      .fx-rans { display: flex; gap: 8px; }
      .fx-rans span { display: inline-block; padding: 4px 14px; font-size: 120px; line-height: 1; box-shadow: 0 6px 14px rgba(0,0,0,0.25); }
""",
    "cover": """
      .fx-mast { left: 0; width: 1080px; text-align: center; font-family: @MAST@; font-weight: @MAST_WEIGHT@; color: @LIGHT@;
                 text-transform: @HEAD_CASE@; letter-spacing: 0.08em; line-height: 0.8; text-shadow: 0 10px 40px rgba(0,0,0,0.35); }
      .fx-kick { font-family: @SANS@; font-weight: 800; font-size: 24px; letter-spacing: 0.32em; text-transform: uppercase;
                 color: @LIGHT@; text-shadow: 0 2px 12px rgba(0,0,0,0.6); }
      .fx-cline { font-family: "Cormorant"; font-style: italic; font-weight: 600; font-size: 44px; color: @LIGHT@; line-height: 1.05;
                  text-shadow: 0 2px 14px rgba(0,0,0,0.5); }
""",
    "glass": """
      .fx-glassw { left: 0; width: 1080px; text-align: center; font-family: @HEAD@; font-weight: 800; line-height: 0.9;
                   text-transform: @HEAD_CASE@; color: rgba(255,255,255,0.16); -webkit-text-stroke: 3px @LIGHT@;
                   text-shadow: 0 1px 0 rgba(255,255,255,0.6), 0 18px 50px rgba(0,0,0,0.35), 0 0 30px @ACCENT_GLOW@; }
""",
}


def _css(block: str) -> str:
    """Метки @ИМЯ@ → значения текущей темы. Метка без значения — громкая ошибка (иначе CSS молча сломан)."""
    import re as _re

    def sub(m):
        value = T(m.group(1))
        if not isinstance(value, str):
            raise ValueError(f"fx: метка @{m.group(1)}@ — не строка в теме {_theme['name']}")
        return value
    out = _re.sub(r"@([A-Z_]+)@", sub, block)
    if "@" in out.replace("@font-face", ""):
        raise ValueError("fx: в стилях осталась неразобранная метка")
    return out


class FX(dict):
    """Куски одного или нескольких приёмов. merge() складывает, finalize() доводит готовую страницу."""

    def __init__(self, behind="", front="", js="", css=("base",), windows=(), stage=False):
        super().__init__(behind=behind, front=front, js=js, css=list(css), windows=list(windows), stage=stage)

    behind = property(lambda self: self["behind"])
    front = property(lambda self: self["front"])
    js = property(lambda self: self["js"])
    windows = property(lambda self: self["windows"])

    @property
    def css(self) -> str:
        keys = list(dict.fromkeys(["base", *(["stage"] if self["stage"] else []), *self["css"]]))
        return "".join(_css(CSS[k]) for k in keys)

    def finalize(self, page: str) -> str:
        """Обёртка #stage (вся картинка, кроме передней графики) — для отъезда и пролёта сквозь кадр."""
        if not self["stage"]:
            return page
        a, b = '      <div id="cam-bg" class="cam">', '      <div id="front" class="layer">'
        if page.count(a) != 1 or page.count(b) != 1:
            raise ValueError("fx: в странице не нашлось слоёв камеры и переда — это не страница kit.build_page")
        return page.replace(a, '      <div id="stage">\n' + a, 1).replace(b, '      </div>\n' + b, 1)


def merge(*parts: FX) -> FX:
    out = FX()
    for p in parts:
        out["behind"] += ("\n" if out["behind"] and p["behind"] else "") + p["behind"]
        out["front"] += ("\n" if out["front"] and p["front"] else "") + p["front"]
        out["js"] += ("\n" if out["js"] and p["js"] else "") + p["js"]
        out["css"] += [c for c in p["css"] if c not in out["css"]]
        out["windows"] += p["windows"]
        out["stage"] = out["stage"] or p["stage"]
    return out


def _e(text: str) -> str:
    return html_lib.escape(str(text), quote=True)


def _all(fid: str) -> str:
    """Селектор всех частей приёма (их id начинаются с fid-) — в кавычках для JS."""
    return '"[id^=\'' + fid + '-\']"'


def _need(times, n, what):
    if len(times) != n:
        raise ValueError(f"{what}: {n} пунктов и {len(times)} времён — должно совпадать")
    if any(b < a for a, b in zip(times, times[1:])):
        raise ValueError(f"{what}: времена идут не по порядку: {times}")


def _out(sel: str, t: float, y: int = -40) -> str:
    return f'      leave("{sel}", {t:.2f}, {{ y: {y}, dur: 0.26 }});'


# ---------------------------------------------------------------- 7. чек-лист и оглавление

def checklist(fid: str, title: str, items: list, times: list, until: float, left: int = 190, top: int = 300,
              counter: bool = True) -> FX:
    """№7 checklist: тёмная стеклянная плашка, пункт отмечается жёлтым кругом с галочкой на своё слово."""
    _need(times, len(items), "checklist")
    rows = "".join(
        f'<div class="row" id="{fid}-r{i}"><div class="box"><div class="fill"></div>'
        f'<svg viewBox="0 0 50 50"><path d="M14 26 L22 34 L37 17" fill="none" stroke="{T("ACCENT_INK")}" stroke-width="5" '
        f'stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/></svg>'
        f'</div><span>{_e(x)}</span></div>' for i, x in enumerate(items))
    count = f'<span id="{fid}-n">0 из {len(items)}</span>' if counter else ""
    html = (f'        <div id="{fid}" class="g fx fx-glass fx-check" style="left: {left}px; top: {top}px;">'
            f'<h4><span>{_e(title)}</span>{count}</h4>{rows}</div>')
    t0 = times[0] - 0.6
    js = [f'      enter("#{fid}", {t0:.2f}, {{ fromY: -50, fromScale: 0.92, dur: 0.36, ease: "power3.out" }});']
    for i, t in enumerate(times):
        r = f"#{fid}-r{i}"
        js += [f'      tl.fromTo("{r} .fill", {{ scale: 0 }}, {{ scale: 1, duration: 0.18, ease: "back.out(2)" }}, {t:.2f});',
               f'      draw("{r} path", {t + 0.08:.2f}, 0.2);',
               f'      tl.to("{r}", {{ color: "{T("PLATE_TEXT")}", duration: 0.15 }}, {t:.2f});']
        if counter:
            js.append(f'      tl.set("#{fid}-n", {{ textContent: "{i + 1} из {len(items)}" }}, {t:.2f});')
    js.append(_out(f"#{fid}", until))
    return FX(front=html, js="\n".join(js), css=["base", "check"])


def toc(fid: str, items: list, times: list, until: float, top: int = 300, title: str = "") -> FX:
    """Оглавление всего ролика сверху (обёртка рилса): текущий пункт горит жёлтым, пройденные — белым."""
    _need(times, len(items), "toc")
    half = (len(items) + 1) // 2 if len(items) > 8 else len(items)
    cols = [items[:half], items[half:]] if half < len(items) else [items]
    lis, k = [], 0
    for col in cols:
        lis.append("<ol>" + "".join(f'<li id="{fid}-i{k + j}"><u></u><b>{k + j + 1:02d}</b>{_e(x)}</li>'
                                    for j, x in enumerate(col)) + "</ol>")
        k += len(col)
    head = (f'<div class="fx-sans" style="position:absolute; left:0; right:0; top:-110px; text-align:center; '
            f'font-size:56px; color:#fff; line-height:1;">{title}</div>') if title else ""
    html = (f'        <div id="{fid}" class="g fx fx-glass fx-toc" style="left: 540px; top: {top}px;">'
            f'{head}{"".join(lis)}</div>')
    js = [f'      tl.fromTo("#{fid}", {{ opacity: 0, y: -30, xPercent: -50 }}, {{ opacity: 1, y: 0, xPercent: -50, duration: 0.3, ease: "power3.out" }}, '
          f'{max(0.0, times[0] - 0.4):.2f});']
    for i, t in enumerate(times):
        if i:
            js.append(f'      tl.to("#{fid}-i{i - 1}", {{ color: "{T("PLATE_TEXT")}", x: 0, duration: 0.12 }}, {t:.2f});')
            js.append(f'      tl.set("#{fid}-i{i - 1} u", {{ opacity: 0 }}, {t:.2f});')
        js.append(f'      tl.to("#{fid}-i{i}", {{ color: "{T("ACCENT")}", x: 10, duration: 0.12 }}, {t:.2f});')
        js.append(f'      tl.set("#{fid}-i{i} u", {{ opacity: 1 }}, {t:.2f});')
    js.append(f'      tl.fromTo("#{fid}", {{ y: 0, xPercent: -50 }}, {{ opacity: 0, y: -30, xPercent: -50, duration: 0.25, '
              f'ease: "power2.in", immediateRender: false }}, {until:.2f});')
    return FX(front=html, js="\n".join(js), css=["base", "toc"])


# ---------------------------------------------------------------- 6. телефон, 3. интерфейс

def phone(fid: str, messages: list, times: list, until: float, side: str = "left", top: int = 560,
          who: str = "Claude") -> FX:
    """№6 phone mockup: телефон у лица, сообщения чата по одному; messages — [("me"|"ai", текст)]."""
    _need(times, len(messages), "phone")
    left = 590 if side == "right" else 110          # правый край 860: дальше — кнопки площадок
    msgs = "".join(f'<div class="msg {k}" id="{fid}-m{i}">{_e(x)}</div>' for i, (k, x) in enumerate(messages))
    html = (f'        <div id="{fid}" class="g fx fx-phone" style="left: {left}px; top: {top}px;">'
            f'<div class="scr"><div class="notch"></div><div class="who">{_e(who)}</div>{msgs}</div></div>')
    s = 1 if side == "right" else -1
    js = [f'      tl.fromTo("#{fid}", {{ opacity: 0, x: {380 * s}, rotation: {12 * s} }}, '
          f'{{ opacity: 1, x: 0, rotation: {4 * s}, duration: 0.45, ease: "power3.out" }}, {times[0] - 0.5:.2f});']
    for i, t in enumerate(times):
        js.append(f'      tl.fromTo("#{fid}-m{i}", {{ opacity: 0, y: 24, scale: 0.9 }}, '
                  f'{{ opacity: 1, y: 0, scale: 1, duration: 0.22, ease: "back.out(1.8)" }}, {t:.2f});')
    js.append(f'      tl.to("#{fid}", {{ opacity: 0, x: {380 * s}, rotation: {14 * s}, duration: 0.3, ease: "power2.in" }}, '
              f'{until:.2f});')
    return FX(front=html, js="\n".join(js), css=["base", "phone"])


def ui_chat(fid: str, thumbs: list, typed: str, t_in: float, t_drop: float, t_type: float, until: float,
            title: str = "Claude", tag: str = "RAW CLIPS", top: int = 290) -> FX:
    """№3 UI world: окно чата сверху, клипы падают в зону загрузки, в строке набирается команда.

    thumbs — картинки (assets/img/<имя>) миниатюр клипов; низ кадра остаётся спикеру («верх — контент»).
    """
    th = "".join(f'<div class="th" id="{fid}-t{i}" style="background-image: url(assets/img/{_e(x)});"></div>'
                 for i, x in enumerate(thumbs))
    letters = "".join(f'<span id="{fid}-c{i}">{_e(c) if c != " " else "&nbsp;"}</span>' for i, c in enumerate(typed))
    html = (f'        <div id="{fid}" class="g fx fx-chat" style="left: 90px; top: {top}px;">'
            f'<div class="hd"><i></i>{_e(title)}</div>'
            f'<div class="drop"><span id="{fid}-hint">Перетащи файлы сюда</span>{th}'
            f'<div class="tag" id="{fid}-tag">{_e(tag)}</div></div>'
            f'<div class="inp">{letters}</div></div>')
    js = [f'      enter("#{fid}", {t_in:.2f}, {{ fromY: -80, fromScale: 0.94, dur: 0.38, ease: "power3.out" }});',
          f'      tl.to("#{fid}-hint", {{ opacity: 0, duration: 0.12 }}, {t_drop:.2f});']
    for i in range(len(thumbs)):
        t = t_drop + i * 0.07
        js.append(f'      tl.fromTo("#{fid}-t{i}", {{ opacity: 0, y: -260, rotation: {(-1) ** i * 14} }}, '
                  f'{{ opacity: 1, y: 0, rotation: {(-1) ** i * 3}, duration: 0.32, ease: "back.out(1.4)" }}, {t:.2f});')
    js.append(f'      slam("#{fid}-tag", {t_drop + 0.07 * len(thumbs) + 0.15:.2f}, {{ fromScale: 1.6 }});')
    for i in range(len(typed)):
        js.append(f'      tl.set("#{fid}-c{i}", {{ opacity: 1 }}, {t_type + i * 0.045:.3f});')
    js.append(_out(f"#{fid}", until, -80))
    return FX(front=html, js="\n".join(js), css=["base", "chat"])


# ---------------------------------------------------------------- 2/8. стена, 1. орбита

WALL_SPOTS = [(110, 330, -7), (740, 300, 6), (150, 640, 5), (720, 620, -5), (420, 270, -2), (60, 920, -4), (790, 900, 7)]


def wall(fid: str, notes: list, times: list, until: float, kind: str = "note", spots: list | None = None) -> FX:
    """№2 couch wall / №8 headline wall: заметки или скриншоты прикалываются к стене ЗА человеком по одной.

    notes — тексты (kind="note") или картинки assets/img (kind="shot"). Окно вырезки ставится само.
    """
    _need(times, len(notes), "wall")
    spots = spots or WALL_SPOTS
    if len(notes) > len(spots):
        raise ValueError(f"wall: мест на стене {len(spots)}, заметок {len(notes)} — передай spots")
    parts = []
    for i, x in enumerate(notes):
        left, top, rot = spots[i]
        if kind == "shot":
            parts.append(f'        <div id="{fid}-{i}" class="g fx fx-shot" style="left: {left}px; top: {top}px; '
                         f'transform: rotate({rot}deg); background-image: url(assets/img/{_e(x)});"></div>')
        else:
            parts.append(f'        <div id="{fid}-{i}" class="g fx fx-note" style="left: {left}px; top: {top}px; '
                         f'transform: rotate({rot}deg);">{_e(x)}</div>')
    js = []
    for i, t in enumerate(times):
        rot = spots[i][2]
        js.append(f'      tl.fromTo("#{fid}-{i}", {{ opacity: 0, scale: 1.5, rotation: {rot * 3}, filter: BLUR(10) }}, '
                  f'{{ opacity: 1, scale: 1, rotation: {rot}, filter: BLUR(0), duration: 0.2, ease: "power4.out" }}, {t:.2f});')
    js.append(f'      tl.to({_all(fid)}, {{ opacity: 0, y: 40, duration: 0.25, ease: "power2.in", stagger: 0.03 }}, {until:.2f});')
    return FX(behind="\n".join(parts), js="\n".join(js), css=["base", "wall"], windows=[(times[0] - 0.05, until + 0.4)])


def orbit(fid: str, cards: list, t0: float, t1: float, center: tuple = (540, 860), rx: int = 400, ry: int = 70,
          turns: float = 0.75, fps: int = 15) -> FX:
    """№1 orbit: карточки-экраны летят по кругу вокруг головы — сзади за человеком, спереди перед ним.

    cards — картинки assets/img или словари {"img": …, "text": …}. У каждой карточки две копии: в слое behind
    и в слое front; видна та, что на своей половине круга. Путь считается здесь, по кадрам 1/fps.
    """
    n = len(cards)
    if not n:
        raise ValueError("orbit: нет карточек")
    behind, front, js = [], [], []
    steps = max(2, int((t1 - t0) * fps))
    for i, c in enumerate(cards):
        c = c if isinstance(c, dict) else {"img": c}
        style = f'background-image: url(assets/img/{_e(c["img"])});' if c.get("img") else \
            "background: linear-gradient(160deg, #2C2F38, #121318);"
        inner = _e(c.get("text", ""))
        for layer, out in (("b", behind), ("f", front)):
            out.append(f'        <div id="{fid}-{layer}{i}" class="g fx fx-orb" style="left: 0; top: 0; {style}">{inner}</div>')
        for layer in ("b", "f"):
            keys = []
            for s in range(steps + 1):
                a = 2 * math.pi * (i / n + turns * s / steps)
                z = math.cos(a)                                    # 1 — ближе к зрителю
                x = center[0] + rx * math.sin(a) - 75
                y = center[1] + ry * z - 133
                sc = 0.72 + 0.34 * (z + 1) / 2
                on = (z >= 0) == (layer == "f")
                keys.append(f"x: {x:.0f}, y: {y:.0f}, scale: {sc:.3f}, opacity: {1 if on else 0}, "
                            f"rotationY: {math.degrees(math.sin(a)) * 0.4:.0f}")
            dur = (t1 - t0 - 0.1) / steps          # ключи кончаются за 3 кадра до скрытия: иначе на сдвиге кадра залипнет
            frames = ", ".join("{ " + k + f', duration: {dur:.4f}, ease: "none" }}' for k in keys[1:])
            js.append(f'      tl.set("#{fid}-{layer}{i}", {{ transformPerspective: 800, {keys[0]} }}, {t0:.2f});')
            js.append(f'      tl.to("#{fid}-{layer}{i}", {{ keyframes: [{frames}] }}, {t0:.2f});')
            js.append(f'      tl.set("#{fid}-{layer}{i}", {{ opacity: 0 }}, {t1:.2f});')
    return FX(behind="\n".join(behind), front="\n".join(front), js="\n".join(js), css=["base", "orbit"],
              windows=[(t0, t1)])


# ---------------------------------------------------------------- 4. рамка, 15. вертиго, 9. пролёт, 11. отъезд

def frame_break(fid: str, t0: float, t1: float, box: tuple = (150, 470, 930, 1500), back: str = "#0D0E10") -> FX:
    """№4 frame break: кадр сжимается в карточку, а человек остаётся во весь рост и «выходит» за её края.

    Сжимается только дубль (#aroll, clip-path), вырезка над ним — в прежнем размере. box — (x0, y0, x1, y1) на
    экране; в координаты дубля его переводит камера страницы в момент t0 (дубль внутри камеры с наездом).
    """
    x0, y0, x1, y1 = box
    inset = (f"`inset(${{(({y0}) - c[1]) / c[2]}}px ${{{W} - (({x1}) - c[0]) / c[2]}}px "
             f"${{{H} - (({y1}) - c[1]) / c[2]}}px ${{(({x0}) - c[0]) / c[2]}}px round ${{46 / c[2]}}px)`")
    js = "\n".join([
        f'      tl.set("#root", {{ backgroundColor: "{back}" }}, {t0:.2f});',
        f'      {{ const c = cam[Math.min(cam.length - 1, Math.round({t0:.3f} * window.CAMERA_FPS))];',
        f'        tl.fromTo("#aroll", {{ clipPath: "inset(0px 0px 0px 0px round 0px)" }}, '
        f'{{ clipPath: {inset}, duration: 0.45, ease: "power3.inOut", immediateRender: false }}, {t0:.2f}); }}',
        f'      tl.to("#aroll", {{ clipPath: "inset(0px 0px 0px 0px round 0px)", duration: 0.35, ease: "power3.inOut" }}, '
        f'{t1 - 0.35:.2f});',
    ])
    return FX(js=js, windows=[(t0, t1)])


def vertigo(t0: float, t1: float, amount: float = 0.86, origin: tuple = (540, 900)) -> FX:
    """№15 vertigo (наезд-отъезд Хичкока): комната отъезжает, человек остаётся того же размера.

    Двигается только дубль за вырезкой; уменьшенный человек в дубле прячется за вырезанным. amount не ниже
    1/база_камеры: иначе по краям откроется чёрное (у antishkola база 1.2 → не ниже 0.84). origin — точка
    экрана (лицо), в дубль её переводит камера в момент t0.
    """
    if not 0.7 <= amount < 1:
        raise ValueError(f"vertigo: amount {amount} — от 0.7 до 1 (меньше — края кадра откроются)")
    o = f"`${{({origin[0]} - c[0]) / c[2]}}px ${{({origin[1]} - c[1]) / c[2]}}px`"
    js = "\n".join([
        f'      {{ const c = cam[Math.min(cam.length - 1, Math.round({t0:.3f} * window.CAMERA_FPS))];',
        f'        tl.fromTo("#aroll", {{ scale: 1, transformOrigin: {o} }}, {{ scale: {amount}, duration: {t1 - t0 - 0.2:.2f}, '
        f'ease: "power1.inOut", immediateRender: false }}, {t0:.2f}); }}',
        f'      tl.to("#aroll", {{ scale: 1, duration: 0.2, ease: "power2.in" }}, {t1 - 0.2:.2f});',
    ])
    return FX(js=js, windows=[(t0, t1)])


def zoom_through(t: float, depth: float = 2.4) -> FX:
    """№9 zoom-through cut: кадр влетает в камеру со смазом, на склейке новый выходит из глубины. t — склейка."""
    js = "\n".join([
        f'      tl.fromTo("#stage", {{ scale: 1, x: 0, y: 0, filter: BLUR(0) }}, {{ scale: {depth}, x: {-(depth - 1) * 540:.0f}, '
        f'y: {-(depth - 1) * 860:.0f}, filter: BLUR(22), duration: 0.16, ease: "power3.in", immediateRender: false }}, {t - 0.16:.2f});',
        f'      tl.fromTo("#stage", {{ scale: 0.7, x: {0.3 * 540:.0f}, y: {0.3 * 860:.0f}, filter: BLUR(18) }}, '
        f'{{ scale: 1, x: 0, y: 0, filter: BLUR(0), duration: 0.22, ease: "power3.out", immediateRender: false }}, {t:.2f});',
    ])
    return FX(js=js, stage=True)


def pullback(fid: str, t0: float, t1: float, steps: list, count: tuple = (0, 100), box: tuple = (420, 520, 960, 1480),
             back: str = "#F4F1EA") -> FX:
    """№11 pull-back reveal: кадр отъезжает и оказывается окном монтажки — слева шаги, снизу полоса, счётчик.

    Вся картинка (дубль, вырезка, графика за спиной) — в обёртке #stage; интерфейс — в переднем слое.
    steps — пункты списка слева, отмечаются по очереди до t1; count — счётчик (от, до).
    """
    x0, y0, x1, y1 = box
    s = (x1 - x0) / W
    rows = "".join(f'<div class="r" id="{fid}-s{i}"><i></i>{_e(x)}</div>' for i, x in enumerate(steps))
    html = "\n".join([
        f'        <div id="{fid}-side" class="g fx fx-side" style="left: 110px; top: {y0}px; width: 290px;">'
        f'<div class="t">задачи</div>{rows}</div>',
        f'        <div id="{fid}-bar" class="g fx fx-bar" style="left: {x0}px; top: {y1 + 40}px; width: {x1 - x0}px;"><i></i></div>',
        f'        <div id="{fid}-n" class="g fx fx-count" style="left: 110px; top: {y0 - 210}px;">{count[0]}</div>',
    ])
    rise = t0 + 0.55
    js = [f'      tl.set("#root", {{ backgroundColor: "{back}" }}, {t0:.2f});',
          f'      tl.fromTo("#stage", {{ scale: 1, x: 0, y: 0, clipPath: "inset(0px round 0px)" }}, '
          f'{{ scale: {s:.4f}, x: {x0}, y: {y0}, clipPath: "inset(0px round 60px)", duration: 0.55, ease: "power3.inOut", '
          f'immediateRender: false }}, {t0:.2f});',
          f'      enter("#{fid}-side", {rise:.2f}, {{ fromX: -120, dur: 0.35, ease: "power3.out" }});',
          f'      enter("#{fid}-bar", {rise:.2f}, {{ fromY: 60, dur: 0.3, ease: "power3.out" }});',
          f'      enter("#{fid}-n", {rise:.2f}, {{ fromY: -40, dur: 0.3, ease: "power3.out" }});',
          f'      tl.fromTo("#{fid}-bar i", {{ scaleX: 0 }}, {{ scaleX: 1, duration: {t1 - rise - 0.4:.2f}, ease: "power1.inOut" }}, {rise:.2f});',
          f'      tl.fromTo("#{fid}-n", {{ textContent: {count[0]} }}, {{ textContent: {count[1]}, snap: {{ textContent: 1 }}, '
          f'duration: {t1 - rise - 0.4:.2f}, ease: "power1.inOut", immediateRender: false }}, {rise:.2f});']
    for i in range(len(steps)):
        js.append(f'      tl.to("#{fid}-s{i}", {{ opacity: 1, duration: 0.12 }}, '
                  f'{rise + (t1 - rise - 0.4) * (i + 1) / (len(steps) + 1):.2f});')
    js += [f'      tl.to(["#{fid}-side", "#{fid}-bar", "#{fid}-n"], {{ opacity: 0, duration: 0.2 }}, {t1 - 0.4:.2f});',
           f'      tl.to("#stage", {{ scale: 1, x: 0, y: 0, clipPath: "inset(0px round 0px)", duration: 0.4, ease: "power3.inOut" }}, '
           f'{t1 - 0.4:.2f});']
    return FX(front=html, js="\n".join(js), css=["base", "pull"], stage=True)


# ---------------------------------------------------------------- 10. рост, 12. зелёный экран

def chart_grow(fid: str, t0: float, t1: float, label: str = "РОСТ ↗", days: str = "ПН ВТ СР ЧТ ПТ СБ ВС",
               top: int = 350) -> FX:
    """№10 chart grow: за головой — дни недели и светящаяся линия, которая лезет вверх; на пике — плашка."""
    pts = [(0, 330), (120, 300), (240, 310), (360, 250), (480, 230), (600, 140), (720, 60), (840, 0)]
    d = "M" + " L".join(f"{x},{y}" for x, y in pts)
    labels = "".join(f"<span>{_e(x)}</span>" for x in days.split())
    behind = "\n".join([
        f'        <div id="{fid}-d" class="g fx fx-days" style="left: 120px; top: {top}px;">{labels}</div>',
        f'        <svg id="{fid}-c" class="g fx fx-line" style="left: 120px; top: {top + 80}px; overflow: visible;" width="840" height="340">'
        f'<path d="{d}" fill="none" stroke="{T("ACCENT")}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round" '
        f'pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" style="filter: drop-shadow(0 0 14px {T("ACCENT_GLOW")});"/>'
        f'<circle cx="840" cy="0" r="16" fill="{T("ACCENT")}" opacity="0" id="{fid}-dot"/></svg>',
        f'        <div id="{fid}-p" class="g fx fx-pill" style="left: 720px; top: {top - 62}px;">{_e(label)}</div>',
    ])
    grow = min(1.4, t1 - t0 - 0.6)
    js = "\n".join([
        f'      enter("#{fid}-d", {t0:.2f}, {{ fromY: -30, dur: 0.3 }});',
        f'      tl.set("#{fid}-c", {{ opacity: 1 }}, {t0:.2f});',
        f'      draw("#{fid}-c path", {t0 + 0.1:.2f}, {grow:.2f});',
        f'      tl.to("#{fid}-dot", {{ attr: {{ opacity: 1 }}, duration: 0.1 }}, {t0 + 0.1 + grow:.2f});',
        f'      slam("#{fid}-p", {t0 + 0.1 + grow:.2f}, {{ fromScale: 1.7 }});',
        f'      tl.to(["#{fid}-d", "#{fid}-c", "#{fid}-p"], {{ opacity: 0, y: -40, duration: 0.25, ease: "power2.in" }}, {t1:.2f});',
    ])
    return FX(behind=behind, js=js, css=["base", "chart"], windows=[(t0, t1 + 0.3)])


def backdrop(fid: str, t0: float, t1: float, css_bg: str | None = None, inner: str = "") -> FX:
    """№12 green screen: человек стоит на нарисованном фоне (градиент темы, интерфейс) вместо комнаты."""
    css_bg = css_bg or T("SCENE")
    behind = (f'        <div id="{fid}" class="g fx fx-scene" style="left: 0; top: 0; width: 1080px; height: 1920px; background: {css_bg};">'
              f'{inner}</div>')
    js = "\n".join([f'      tl.set("#{fid}", {{ opacity: 1 }}, {t0:.2f});', f'      tl.set("#{fid}", {{ opacity: 0 }}, {t1:.2f});'])
    return FX(behind=behind, js=js, windows=[(t0, t1)])


# ---------------------------------------------------------------- 13. бумага, 14. каракули

OUTLINE = ("drop-shadow({d}px 0 0 #fff) drop-shadow(-{d}px 0 0 #fff) drop-shadow(0 {d}px 0 #fff) "
           "drop-shadow(0 -{d}px 0 #fff)")


def _outline(t0: float, t1: float, width: int, boil: bool, shadow: bool = False) -> list:
    tail = " drop-shadow(10px 16px 0 rgba(0,0,0,0.18))" if shadow else ""
    js = []
    if boil:                                   # «кипящий» контур: 8 раз в секунду чуть другая толщина
        k, t = 0, t0
        while t < t1:
            js.append(f'      tl.set("#cutout", {{ filter: "{OUTLINE.format(d=width + (k % 2))}{tail}" }}, {t:.3f});')
            k, t = k + 1, t + 0.125
    else:
        js.append(f'      tl.set("#cutout", {{ filter: "{OUTLINE.format(d=width)}{tail}" }}, {t0:.2f});')
    js.append(f'      tl.set("#cutout", {{ filter: "none" }}, {t1:.2f});')
    return js


def paper_cut(fid: str, t0: float, t1: float, word: str, top: int = 300) -> FX:
    """№13 paper cut: коллаж — бумага в клетку, человек вырезан с белым полем и тенью, слово из вырезанных букв,
    скотч и каракули маркером."""
    palette = T("RANSOM")
    letters = "".join(f'<span id="{fid}-l{i}" style="background:{b}; color:{c}; font-family:{f};">'
                      f'{_e(ch)}</span>' for i, (ch, (b, c, f)) in enumerate(zip(word, palette * 10)))
    behind = "\n".join([
        f'        <div id="{fid}-bg" class="g fx fx-paper"></div>',
        f'        <div id="{fid}-tp" class="g fx fx-tape" style="left: 700px; top: 980px; transform: rotate(-24deg);"></div>',
        f'        <svg id="{fid}-sc" class="g fx fx-scribble" style="left: 640px; top: 640px;" width="380" height="300"><path d="M10 40 C80 0 120 90 '
        f'180 40 S300 10 360 60 M20 140 C90 100 140 190 200 140 S310 110 370 160 M30 240 C100 200 150 290 210 240 S320 210 '
        f'370 260" fill="none" stroke="{T("SCRIBBLE")}" stroke-width="9" stroke-linecap="round" pathLength="1" stroke-dasharray="1" '
        f'stroke-dashoffset="1"/></svg>',
    ])
    front = f'        <div id="{fid}-w" class="g fx fx-rans" style="left: 540px; top: {top}px;">{letters}</div>'
    js = [f'      tl.set("#{fid}-bg", {{ opacity: 1 }}, {t0:.2f});',
          f'      tl.fromTo("#{fid}-tp", {{ opacity: 0, scale: 1.4 }}, {{ opacity: 1, scale: 1, duration: 0.15 }}, {t0 + 0.15:.2f});',
          f'      tl.set("#{fid}-sc", {{ opacity: 1 }}, {t0:.2f});', f'      draw("#{fid}-sc path", {t0 + 0.2:.2f}, 0.6);',
          f'      tl.set("#{fid}-w", {{ opacity: 1, xPercent: -50 }}, {t0:.2f});']
    for i in range(len(word)):
        rot = (-1) ** i * (3 + i % 3 * 2)
        js.append(f'      tl.fromTo("#{fid}-l{i}", {{ opacity: 0, scale: 1.8, rotation: {rot * 3} }}, {{ opacity: 1, scale: 1, rotation: {rot}, duration: 0.1, '
                  f'ease: "power4.out" }}, {t0 + 0.1 + i * 0.09:.2f});')
    js += _outline(t0, t1, 10, boil=False, shadow=True)
    js.append(f'      tl.set(["#{fid}-bg", "#{fid}-tp", "#{fid}-sc", "#{fid}-w"], {{ opacity: 0 }}, {t1:.2f});')
    return FX(behind=behind, front=front, js="\n".join(js), css=["base", "paper"], windows=[(t0, t1)])


DOODLES = {
    "clapper": "M10 50 L110 50 L110 120 L10 120 Z M10 50 L20 18 L118 18 L110 50 M40 18 L30 50 M70 18 L60 50 M100 18 L90 50",
    "heart": "M60 110 C10 70 0 40 25 22 C45 8 60 25 60 38 C60 25 75 8 95 22 C120 40 110 70 60 110 Z",
    "star": "M60 8 L74 44 L112 46 L82 70 L94 108 L60 86 L26 108 L38 70 L8 46 L46 44 Z",
    "arrow": "M10 100 C40 40 80 30 112 26 M86 12 L114 26 L92 48",
    "spark": "M60 10 L60 40 M60 80 L60 110 M10 60 L40 60 M80 60 L110 60 M25 25 L45 45 M75 75 L95 95 M95 25 L75 45 M45 75 L25 95",
}


def doodle(fid: str, t0: float, t1: float, marks: list | None = None) -> FX:
    """№14 doodle boil: белый «кипящий» контур вокруг человека и рисованные значки, дрожащие как мультфильм.

    marks — [(значок из DOODLES, x, y, цвет)]. Дрожь — смена шума фильтра 8 раз в секунду (feTurbulence seed).
    """
    c = T("MARKS")
    marks = marks or [("clapper", 150, 520, c[0]), ("heart", 800, 470, c[1]), ("star", 830, 1130, c[2]), ("spark", 120, 1050, c[3])]
    filt = (f'<svg width="0" height="0" style="position:absolute"><filter id="{fid}-boil"><feTurbulence id="{fid}-tu" '
            f'type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="1"/><feDisplacementMap in="SourceGraphic" '
            f'scale="5"/></filter></svg>')
    parts = [f"        {filt}"]
    for i, (name, x, y, color) in enumerate(marks):
        if name not in DOODLES:
            raise ValueError(f"doodle: значка «{name}» нет — есть {', '.join(DOODLES)}")
        parts.append(f'        <svg id="{fid}-{i}" class="g fx fx-doodle" style="left: {x}px; top: {y}px; filter: url(#{fid}-boil);" '
                     f'width="160" height="160" viewBox="0 0 120 120"><path d="{DOODLES[name]}" fill="none" stroke="{color}" '
                     f'stroke-width="6" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" '
                     f'stroke-dashoffset="1"/></svg>')
    js = []
    for i in range(len(marks)):
        t = t0 + 0.12 + i * 0.18
        js += [f'      tl.set("#{fid}-{i}", {{ opacity: 1 }}, {t:.2f});', f'      draw("#{fid}-{i} path", {t:.2f}, 0.35);']
    k, t = 0, t0
    while t < t1:
        js.append(f'      tl.set("#{fid}-tu", {{ attr: {{ seed: {k % 4 + 1} }} }}, {t:.3f});')
        k, t = k + 1, t + 0.125
    js += _outline(t0, t1, 4, boil=True)
    js.append(f'      tl.set({_all(fid)}, {{ opacity: 0 }}, {t1:.2f});')
    return FX(front="\n".join(parts), js="\n".join(js), windows=[(t0, t1)])


# ---------------------------------------------------------------- 16. обложка, 17. стеклянный текст

def cover(fid: str, t0: float, t1: float, word: str, kicker: str = "", lines: tuple = (), top: int = 330,
          size: int = 250) -> FX:
    """№16 cover story: человек — обложка журнала. Название крупной антиквой за головой, сверху строка выпуска,
    по бокам — анонсы курсивом."""
    behind = f'        <div id="{fid}-m" class="g fx fx-mast" style="top: {top}px; font-size: {size}px;">{_e(word)}</div>'
    front = []
    if kicker:
        front.append(f'        <div id="{fid}-k" class="g fx fx-kick" style="left: 0; width: 1080px; text-align: center; '
                     f'top: {top - 44}px;">{_e(kicker)}</div>')
    for i, x in enumerate(lines):
        left = 110 if i % 2 == 0 else 610                 # правый анонс кончается до кнопок (x 865)
        front.append(f'        <div id="{fid}-c{i}" class="g fx fx-cline" style="left: {left}px; top: {1000 + i // 2 * 170}px; '
                     f'width: 250px;">{_e(x)}</div>')
    js = [f'      tl.fromTo("#{fid}-m", {{ opacity: 0, y: 60, scale: 1.18, filter: BLUR(10) }}, {{ opacity: 1, y: 0, scale: 1, filter: BLUR(0), '
          f'duration: 0.6, ease: "power3.out" }}, {t0:.2f});']
    if kicker:
        js.append(f'      enter("#{fid}-k", {t0 + 0.25:.2f}, {{ fromY: -20, dur: 0.3 }});')
    for i in range(len(lines)):
        js.append(f'      enter("#{fid}-c{i}", {t0 + 0.45 + i * 0.15:.2f}, {{ fromX: {-60 if i % 2 == 0 else 60}, dur: 0.32 }});')
    js.append(f'      tl.to({_all(fid)}, {{ opacity: 0, duration: 0.22, ease: "power2.in" }}, {t1:.2f});')
    return FX(behind=behind, front="\n".join(front), js="\n".join(js), css=["base", "cover"], windows=[(t0, t1 + 0.25)])


def glass_word(fid: str, t0: float, t1: float, word: str, top: int = 340, size: int = 180) -> FX:
    """№17 glass type: объёмное «стеклянное» слово за спиной, развёрнутое в перспективу, с бликом."""
    behind = (f'        <div id="{fid}" class="g fx fx-glassw" style="top: {top}px; font-size: {size}px;">{_e(word)}</div>')
    js = "\n".join([
        f'      tl.fromTo("#{fid}", {{ opacity: 0, transformPerspective: 900, rotationX: 6, rotationY: -70, z: -300, filter: BLUR(14) }}, {{ opacity: 1, rotationY: -24, z: 0, '
        f'filter: BLUR(0), duration: 0.55, ease: "power3.out" }}, {t0:.2f});',
        f'      tl.to("#{fid}", {{ rotationY: -14, duration: {max(0.3, t1 - t0 - 0.55):.2f}, ease: "none" }}, {t0 + 0.55:.2f});',
        f'      tl.to("#{fid}", {{ opacity: 0, rotationY: 30, filter: BLUR(14), duration: 0.28, ease: "power2.in" }}, {t1:.2f});',
    ])
    return FX(behind=behind, js=js, css=["base", "glass"], windows=[(t0, t1 + 0.3)])
