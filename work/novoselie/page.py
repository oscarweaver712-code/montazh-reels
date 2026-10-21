"""novoselie v5 — новоселье «Вкудесника» лайф-влогом в направлении «Широкий» (21.10.2026).

v3–v4 («Редакция»: Inter + курсив, обводка, слова за головой по вырезке) заказчик забраковал целиком: «вырезка — хуйня,
текст — хуйня, обводку убирай нахуй, пока V2 лучшее». Монтаж v2 (доли, рывки, стоп-кадр, петля) не меняется. Текст — по
доске work/novoselie/board/type_board_2.jpg, вариант 2 «Широкий» (исходник — type_board_2.make.py, строка 2), один в один:
крупное слово Unbounded SemiBold строчными (трекинг −0.05em), подводка Onest Medium, субтитры Onest SemiBold 54 px, акцент
жёлтым #FFD60A; обводки нет — мягкая тень и затемнение края кадра под текстом. Вырезки нет: крупное слово стоит в свободном
месте кадра — над головой, лицо не закрывает (projects/vkudesnik/rules.md, «Стиль монтажа» п.3).
Факты: «конфеты с ликёром» — подпись самого бренда к прошлому ролику с этого новоселья (@vkudesnik_).
"""
import sys
from pathlib import Path

from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import verify_page  # noqa: E402
from montage import Montage  # noqa: E402

STEM = "novoselie"
BEAT = 60 / 123.0
m = Montage(STEM)
tk = m.tk
W, S = tk.words, tk.scenes
FACES = verify_page.face_track(ROOT / "studio" / STEM)


def word(i: int, text: str) -> float:
    """Начало слова i на шкале дубля; слово не то — громкая ошибка (пересобрали сборку — номера сдвинулись)."""
    got = W[i]["word"].strip(" .,!?").lower()
    if got != text:
        raise ValueError(f"слово [{i}] — «{W[i]['word']}», а ждал «{text}»: сверь номера после пересборки")
    return round(W[i]["start"], 2)


def scene(t: float) -> float:
    hit = min(S, key=lambda x: abs(x - t))
    if abs(hit - t) > 0.1:
        raise ValueError(f"стыка сцен около {t:.2f} с нет (есть {S})")
    return hit


def whip_at(t: float) -> str:
    """Смаз на стыке — на 4 мс раньше: время стыка округлено до мс, кадр стыка — чуть раньше (см. montage.cover_cuts)."""
    return f"      whip({t - 0.004:.3f});"


def face_top(a: float, b: float) -> int:
    """Самый высокий верх лица в окне [a, b] (по слежению с камерой, без 10% выбросов) — крупное слово встаёт выше."""
    tops = sorted(f[2] for f in FACES if a <= f[0] <= b)
    if not tops:
        raise ValueError(f"лица в {a:.2f}–{b:.2f} с нет — некуда ставить слово над головой")
    return int(tops[len(tops) // 10])


# доска type_board_2, строка 2 «Широкий»: тень вместо обводки, затемнение края кадра под текстом
YEL = "#FFD60A"
SOFT = "text-shadow: 0 2px 6px rgba(0,0,0,0.28), 0 8px 34px rgba(0,0,0,0.38);"
HERO_TRACK = -0.05                                   # трекинг крупного слова, em
m.css(f'''
      @font-face {{ font-family: "Unbounded SemiBold"; src: url("assets/fonts/Unbounded-SemiBold.ttf"); font-weight: 600; }}
      @font-face {{ font-family: "Onest Medium"; src: url("assets/fonts/Onest-Medium.ttf"); font-weight: 500; }}
      .cap {{ {SOFT} }}
      .t-lead {{ text-align: center; font-family: "Onest Medium"; font-weight: 500; line-height: 1.02; color: #FFFFFF;
                {SOFT} white-space: nowrap; }}
      .t-hero {{ text-align: center; font-family: "Unbounded SemiBold"; font-weight: 600; letter-spacing: {HERO_TRACK}em;
                line-height: 1.02; color: #FFFFFF; {SOFT} white-space: nowrap; }}
      .t-hero span {{ display: inline-block; opacity: 0; }}
      .t-y {{ color: {YEL}; }}
      .t-left {{ text-align: left; }}
      .scrim {{ left: 0; top: 0; width: 1080px; height: 900px; background: linear-gradient(rgba(0,0,0,0.34), rgba(0,0,0,0)); }}
      .low {{ left: 0; top: 1020px; width: 1080px; height: 900px; background: linear-gradient(rgba(0,0,0,0), rgba(0,0,0,0.30)); }}
''')


# безопасная зона 9:16 (formats.GREY_ZONES): по бокам x 102–978, сверху до y 260 — вкладки TikTok; справа ниже y 727 —
# кнопки Instagram (до x 865), ниже y 1031 — кнопки YouTube с подписями (до x 834); низ с y 1370 — ник и подпись
SAFE_L, SAFE_R, SAFE_TOP = 110, 970, 270
LEAD_GAP = 8                                         # от подводки до крупного слова, px (на доске 6–10)
_UNB = TTFont(ROOT / "presets" / "fonts" / "Unbounded-SemiBold.ttf")
_ADV, _CMAP, _UPM = _UNB["hmtx"], _UNB.getBestCmap(), _UNB["head"].unitsPerEm


def column(top: int, height: int, centered: bool = False) -> tuple:
    """(left, width) колонки текста: ниже кнопок площадок — уже; текст по центру — симметрично от x 540."""
    bottom = top + height
    right = 824 if bottom > 1031 else 856 if bottom > 727 else SAFE_R
    if centered:
        half = min(540 - SAFE_L, right - 540)
        return 540 - half, 2 * half
    return SAFE_L, right - SAFE_L


def hero_em(text: str) -> float:
    """Ширина строки Unbounded SemiBold в кеглях — по метрикам самого шрифта, с трекингом страницы."""
    return sum(_ADV[_CMAP[ord(ch)]][0] for ch in text) / _UPM + HERO_TRACK * len(text)


def fit(text: str, size: int, width: int) -> int:
    """Кегль крупного слова, при котором оно влезает в колонку (запас 2% на тень и округление)."""
    return min(size, int(0.98 * width / hero_em(text)))


def text(tid: str, cls: str, top: int, size: int, body: str, attrs: str = "") -> str:
    left, width = column(top, int(size * 1.02), "t-left" not in cls)
    return (f'        <div id="{tid}" class="g {cls}" style="top: {top}px; left: {left}px; width: {width}px; '
            f'font-size: {size}px;"{attrs}>{body}</div>')


def hero(tid: str, top: int, size: int, body: str, cls: str = "") -> tuple:
    """Крупное слово, ужатое под колонку на своей высоте: (html, кегль)."""
    size = fit(body, size, column(top, int(size * 1.02), "t-left" not in cls)[1])
    return text(tid, f"t-hero {cls}".strip(), top, size, body), size


SCRIMS = []


def scrim(sid: str, a: float, b: float) -> None:
    """Затемнение верха кадра под крупное слово: проявляется с ним и уходит с ним."""
    SCRIMS.append(f'        <div id="{sid}" class="g scrim" data-safe="затемнение верха под текст — у лица уже прозрачное"></div>')
    m.js(f'''      tl.to("#{sid}", {{ opacity: 1, duration: 0.2, ease: "power1.out" }}, {a:.2f});
      tl.to("#{sid}", {{ opacity: 0, duration: 0.2, ease: "power1.in" }}, {b:.2f});''')


def over_head(tid: str, lead: str, big: list, a: float, b: float, lead_at: float, size: int, lead_size: int = 46) -> None:
    """Подводка и крупное слово над головой (или смена слов big[(t, текст)] на том же месте); лицо не закрывают."""
    lead_h = round(lead_size * 1.02)
    bottom = face_top(a, b) - 28
    room = bottom - SAFE_TOP - lead_h - LEAD_GAP
    if room < 60:
        raise ValueError(f"{tid}: над головой {bottom - SAFE_TOP} px — крупному слову места нет")
    cap = min(size, int(room / 1.02))
    sizes = [fit(w, cap, column(bottom - round(cap * 1.02), round(cap * 1.02), True)[1]) for _, w in big]
    hero_top = bottom - round(max(sizes) * 1.02)
    html, js = [text(f"{tid}-l", "t-lead", hero_top - LEAD_GAP - lead_h, lead_size, lead)], []
    js.append(f'      enter("#{tid}-l", {lead_at:.2f}, {{ fromY: 24, fromScale: 0.92, dur: 0.22 }});')
    js.append(f'      leave("#{tid}-l", {b:.2f}, {{ y: -30, dur: 0.2 }});')
    for k, ((t, w), sz) in enumerate(zip(big, sizes)):
        # слово сменяется словом: прошлое уходит быстро и до удара следующего — два слова друг на друге не стоят
        end, dur = (big[k + 1][0] - 0.12, 0.1) if k + 1 < len(big) else (b, 0.16)
        html.append(text(f"{tid}-{k}", "t-hero", hero_top, sz, w))
        js.append(f'      slam("#{tid}-{k}", {t:.2f}, {{ fromScale: 1.3, blur: 10 }});')
        js.append(f'      leave("#{tid}-{k}", {end:.2f}, {{ y: -40, dur: {dur} }});')
    m.front("\n".join(html))
    m.js("\n".join(js))
    scrim(f"{tid}-s", min(lead_at, big[0][0]) - 0.05, b)


# ---------------------------------------------------------------- открытие: три вспышки в долю, заголовок прыгает по лицам
open_end = scene(4 * BEAT)
# лица: тост — в левом верхнем углу (до y 366), объятие — внизу (с y 985), смех — y 313–729 по всей ширине; заголовок
# прыгает по свободным местам одним кеглем и по левому краю: ниже y 727 справа кнопки Instagram — 134 px доски не влезают
spots = [(400, 0.02, BEAT * 2), (300, BEAT * 2, BEAT * 3), (760, BEAT * 3, open_end)]   # тост, объятие, смех
o_size = min(fit("новоселье", 134, column(top + 47 + LEAD_GAP, 137)[1]) for top, _, _ in spots)
for k, (top, a, b) in enumerate(spots):
    big, _ = hero(f"o{k}b", top + 47 + LEAD_GAP, o_size, "новоселье", "t-left")
    m.front(text(f"o{k}a", "t-lead t-left", top, 46, "устроила команде") + "\n" + big)
    m.js(f'''      slam("#o{k}a", {a:.3f}, {{ fromScale: 1.2, blur: 8, dur: 0.12 }});
      slam("#o{k}b", {(BEAT if k == 0 else a) + 0.02:.3f}, {{ fromScale: 1.35, blur: 10, dur: 0.14 }});
      leave(["#o{k}a", "#o{k}b"], {b - 0.1:.3f}, {{ y: -30, dur: 0.09 }});''')
m.js(f'''      flash({open_end:.3f});
{whip_at(scene(2 * BEAT))}
{whip_at(scene(3 * BEAT))}''')
m.hide(0.0, round(open_end, 2))
m.sound("open", "impact-bass-1", 0.0, 0.7)

# ---------------------------------------------------------------- завязка: фуршетик, тортик, закусочки — словами по голосу
m.punch(word(7, "новоселье"), round(word(8, "в") + 0.3, 2), 1.08)
f_out = round(S[3] - 0.25, 2)
rows = [("ck0", "фуршетик,", "t-left", 16), ("ck1", "тортик,", "t-left", 17), ("ck2", "закусочки", "t-left t-y", 18)]
ck = min(fit(w, 104, column(950, 106)[1]) for _, w, _, _ in rows)          # одним кеглем, как на доске
m.front("\n".join(text(cid, f"t-hero {cls}", 950 + k * (round(ck * 1.02) + 4), ck, w)
                   for k, (cid, w, cls, _) in enumerate(rows)))
m.js("\n".join(f'      slam("#{cid}", {word(i, w.strip(",")):.2f}, {{ fromScale: 1.3, blur: 10 }});' for cid, w, _, i in rows)
     + f'\n      leave(["#ck0", "#ck1", "#ck2"], {f_out:.2f}, {{ x: -60, y: 0, dur: 0.2 }});')
m.hide(round(word(16, "фуршетик") - 0.05, 2), round(S[3] - 0.02, 2))

# ---------------------------------------------------------------- проходка рывком, встреча, «добро пожаловать в новый офис»
walk, walk_end = scene(S[4]), scene(S[5])
m.js(f'{whip_at(walk)}\n{whip_at(walk_end)}')
m.sound("walk", "whoosh", walk - 0.08, 0.9)
m.sound("hello", "notification", walk_end + 0.3, 0.5)
m.js(whip_at(scene(S[6])))
welcome, welcome_end = scene(S[7]), scene(S[8])
big, _ = hero("wl-b", 280 + 47 + LEAD_GAP, 134, "в новый офис")
m.front(text("wl-a", "t-lead", 280, 46, "добро пожаловать") + "\n" + big)
m.js(f'''      slam("#wl-a", {word(25, "добро"):.2f}, {{ fromScale: 1.2, blur: 8, dur: 0.14 }});
      slam("#wl-b", {word(27, "в"):.2f}, {{ fromScale: 1.35, blur: 10 }});
      leave(["#wl-a", "#wl-b"], {welcome_end - 0.22:.2f}, {{ y: -40, dur: 0.18 }});''')
scrim("wl-s", word(25, "добро") - 0.05, welcome_end - 0.22)
m.hide(round(word(25, "добро") - 0.05, 2), round(welcome_end - 0.02, 2))
m.punch(word(25, "добро"), round(word(26, "пожаловать") + 0.4, 2), 1.08)
enter_in = scene(S[8])
m.js(whip_at(enter_in))
m.sound("enter", "whoosh-cinematic", enter_in - 0.1, 0.5)

# ---------------------------------------------------------------- мем: стоп-кадр на конфете с ликёром
taste = scene(S[10])
freeze = round(taste + (26.42 - 25.6), 2)            # дальше кадр стоит (pack.json: hold)
meme_end = scene(S[11])
big, _ = hero("mm-b", 330 + 51 + LEAD_GAP, 136, "с ликёром?!", "t-y")
m.front(text("mm-a", "t-lead", 330, 50, "конфеты оказались") + "\n" + big)
m.js(f'''      flash({freeze:.2f});
      slam("#mm-a", {freeze + 0.04:.2f}, {{ fromScale: 1.2, blur: 8, dur: 0.14 }});
      slam("#mm-b", {freeze + 0.22:.2f}, {{ fromScale: 1.5, blur: 12 }});
      leave(["#mm-a", "#mm-b"], {meme_end - 0.2:.2f}, {{ y: -40, dur: 0.16 }});''')
scrim("mm-s", freeze, meme_end - 0.2)
m.punch(freeze, round(meme_end - 0.05, 2), 1.18, ease_in=0.06, ease_out=0.1)
m.sound("scratch", "error", freeze, 0.7)

# ---------------------------------------------------------------- отзывы: ключевое слово над головой
s_joy, s_new, s_style, s_love, s_prod, s_time, s_wish = (scene(S[11]), scene(S[12]), scene(S[13]), scene(S[14]),
                                                        scene(S[15]), scene(S[16]), scene(S[17]))
over_head("joy", "ой, ну я", [(word(34, "в"), "в восторге")], s_joy, s_new - 0.08, s_joy + 0.05, 170)
m.hide(round(s_joy, 2), round(s_new - 0.02, 2))
m.sound("joy", "pop", s_joy + 0.05, 0.6)

adj = [(word(39, "современный"), "современный"), (word(40, "ухоженный"), "ухоженный"), (word(41, "чистый"), "чистый")]
over_head("new", "новый офис —", adj, adj[0][0], s_style - 0.12, adj[0][0], 170)
m.hide(round(adj[0][0] - 0.05, 2), round(s_style - 0.02, 2))

lvl = word(47, "уровень")
sty_out = round(word(46, "комфортный") - 0.05, 2)
over_head("sty", "офис просто очень", [(word(45, "стильный"), "стильно")], word(45, "стильный"), sty_out,
          word(45, "стильный"), 170)
m.hide(round(word(45, "стильный") - 0.05, 2), sty_out)
over_head("lvl", "поднялся", [(lvl, "уровень")], lvl, s_love - 0.12, lvl + 0.35, 170)
m.hide(round(lvl - 0.05, 2), round(s_love - 0.02, 2))

over_head("team", "в любимой", [(word(60, "команде"), "команде")], word(59, "любимой"), s_prod - 0.12,
          word(59, "любимой"), 170)
m.hide(round(word(59, "любимой") - 0.05, 2), round(s_prod - 0.02, 2))
m.sound("team", "sparkle", word(60, "команде"), 0.5)

prod_out = round(word(64, "качественной") + 0.75, 2)
over_head("prod", "много красивой", [(word(63, "продукции"), "продукции")], word(62, "красивой"), prod_out,
          word(62, "красивой"), 170)
m.hide(round(word(62, "красивой") - 0.05, 2), prod_out)
m.sound("prod", "click", word(63, "продукции"), 0.7)

over_head("time", "всё было", [(word(77, "вовремя"), "вовремя")], word(75, "все"), s_wish - 0.12,
          word(75, "все"), 170)
m.hide(round(word(75, "все") - 0.05, 2), round(s_wish - 0.02, 2))
m.punch(word(77, "вовремя"), round(s_wish - 0.05, 2), 1.08)        # большой палец

wish_out = round(word(84, "успехов") - 0.25, 2)
over_head("wish", "этому сезону", [(word(81, "процветания"), "процветания")], word(79, "этому"), wish_out,
          word(79, "этому"), 170)
m.hide(round(word(79, "этому") - 0.05, 2), round(word(82, "и") - 0.05, 2))     # «и только успехов» — снова субтитром
m.sound("wish", "ping", word(81, "процветания"), 0.5)

# ---------------------------------------------------------------- «Успехов, успехов, ещё раз успехов!» — над головой
# повтор в речи — повтор на экране: «успехов,» дважды, «ещё раз» подводкой, последнее «успехов!» жёлтым; на груди не
# влезает — подпись Instagram закрывает кадр с y 1370
us_a, us_b = word(85, "успехов"), S[-1] - 0.2
bottom = face_top(us_a, us_b) - 28
us_size = min(110, int((bottom - SAFE_TOP - 47 - LEAD_GAP - 12) / (3 * 1.02)))
us_size = min(fit(w, us_size, column(bottom - 3 * us_size, us_size, True)[1]) for w in ("успехов,", "успехов!"))
h = round(us_size * 1.02)
tops = [bottom - 3 * h - 12 - 47 - LEAD_GAP, bottom - 2 * h - 6 - 47 - LEAD_GAP, bottom - h - 47 - LEAD_GAP, bottom - h]
m.front("\n".join([text("us0", "t-hero", tops[0], us_size, "успехов,"), text("us1", "t-hero", tops[1], us_size, "успехов,"),
                   text("us-l", "t-lead", tops[2], 46, "ещё раз"), text("us2", "t-hero t-y", tops[3], us_size, "успехов!")]))
m.js(f'''      slam("#us0", {us_a:.2f}, {{ fromScale: 1.5, blur: 10 }});
      slam("#us1", {word(86, "успехов"):.2f}, {{ fromScale: 1.5, blur: 10 }});
      enter("#us-l", {word(87, "еще"):.2f}, {{ fromY: 24, fromScale: 0.92, dur: 0.18 }});
      slam("#us2", {word(89, "успехов"):.2f}, {{ fromScale: 1.5, blur: 10 }});
      leave(["#us0", "#us1", "#us-l", "#us2"], {us_b:.2f}, {{ y: -40, dur: 0.16 }});''')
scrim("us-s", us_a - 0.05, us_b)
m.hide(round(us_a - 0.05, 2), round(S[-1], 2))
m.sound("us", "impact-bass-2", word(89, "успехов"), 0.6)

# ---------------------------------------------------------------- петля: команда поднимает стаканы → первый тост
m.js(whip_at(S[-1]))

# затемнения — под текстом и субтитрами (#caps — первый в #front, поэтому они в behind: без вырезки он сразу над видео);
# низ кадра темнее под субтитрами всю историю после открытия — светлый пол (анкета: «читаемые на светлом полу»)
m.behind("\n".join(SCRIMS) + '\n        <div id="low" class="g low" data-safe="затемнение низа под субтитры — у лица прозрачное" '
         'data-hold="подложка субтитров на всю историю, не графика"></div>')
m.js(f'''      tl.to("#low", {{ opacity: 1, duration: 0.3, ease: "power1.out" }}, {open_end:.3f});
      tl.to("#low", {{ opacity: 0, duration: 0.2, ease: "power1.in" }}, {S[-1] - 0.2:.3f});''')   # к петле — как в первом кадре

m.build("Новоселье «Вкудесника»", text_fixes={"67": "в этом", "75": "Всё", "87": "ещё"},
        accent_words=[], track="mx-house-02.mp3", music_start=0.41, music_fade=0.3,
        framing=False, cutout=False, jump_whip=True)
