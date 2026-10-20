"""novoselie — новоселье «Вкудесника» (20.10.2026): тестовый рилс бренда, сборка из 9 клипов (work/novoselie/pack.json).

Без ИИ-генераций: вся графика — текст, конфетти, сердца и галочки на CSS/SVG. Стиль проекта — караоке-субтитры капсом,
активное слово тёплым золотом, камера-штатив (клипы 720×1280, сняты с рук). Порядок и хук — plan.md.
Факты: «а конфеты с ликёром оказались» — подпись самого бренда к прошлому ролику с этого новоселья (@vkudesnik_);
«подарки с атмосферой настоящего праздника» — слоган с плаката бренда в кадре (стеклянная стена за интервью).
"""
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from montage import Montage  # noqa: E402

STEM = "novoselie"
m = Montage(STEM)
tk = m.tk
W = tk.words


def word(i: int, text: str) -> float:
    """Начало слова i на шкале дубля; слово не то — громкая ошибка (пересобрали сборку — номера сдвинулись)."""
    got = W[i]["word"].strip(" .,!?").lower()
    if got != text:
        raise ValueError(f"слово [{i}] — «{W[i]['word']}», а ждал «{text}»: сверь номера после пересборки")
    return round(W[i]["start"], 2)


def clip(name: str, sec: float) -> float:
    return round(tk.clip(name, sec), 2)


GOLD, CREAM, INK, RED = "#FFC93C", "#FFF4D6", "#2B1A0C", "#E0393E"
m.css(f'''
      @font-face {{ font-family: "Unbounded"; src: url("assets/fonts/Unbounded-ExtraBold.ttf"); font-weight: 800; }}
      @font-face {{ font-family: "Caveat"; src: url("assets/fonts/Caveat-Bold.ttf"); font-weight: 700; }}
      @font-face {{ font-family: "Montserrat"; src: url("assets/fonts/Montserrat-ExtraBold.ttf"); font-weight: 800; }}
      /* субтитры на белых стенах и светлом полу: тёмная обводка в 8 сторон и мягкая тень */
      .cap {{ text-shadow: 2px 2px 0 {INK}, -2px 2px 0 {INK}, 2px -2px 0 {INK}, -2px -2px 0 {INK}, 0 3px 0 {INK},
             0 -3px 0 {INK}, 3px 0 0 {INK}, -3px 0 0 {INK}, 0 8px 22px rgba(0,0,0,0.55); letter-spacing: 0.01em; }}
      .vk-gold {{ display: inline-block; font-family: "Unbounded"; font-weight: 800; text-transform: uppercase;
                 background: linear-gradient(180deg, #FFF0B8 0%, {GOLD} 46%, #E8961C 100%); -webkit-background-clip: text;
                 background-clip: text; color: transparent; filter: drop-shadow(0 4px 0 {INK}) drop-shadow(0 10px 22px rgba(0,0,0,0.5));
                 padding: 0 0.08em; line-height: 1.05; }}
      .vk-hand {{ font-family: "Caveat"; font-weight: 700; color: {CREAM}; line-height: 1.0;
                 text-shadow: 0 3px 0 {INK}, 0 0 8px rgba(43,26,12,0.9), 0 8px 24px rgba(0,0,0,0.5); }}
      .vk-chip {{ font-family: "Montserrat"; font-weight: 800; font-size: 40px; color: {INK}; background: {CREAM};
                 border-radius: 999px; padding: 14px 34px 16px; box-shadow: 0 10px 0 rgba(43,26,12,0.35), 0 18px 40px rgba(0,0,0,0.4);
                 white-space: nowrap; }}
      .vk-chip b {{ color: #C9711A; }}
      .vk-q {{ width: 700px; border-radius: 34px; overflow: hidden; background: #FFFFFF; box-shadow: 0 22px 50px rgba(0,0,0,0.45); }}
      .vk-q .top {{ padding: 18px 0 14px; text-align: center; font-family: "Montserrat"; font-weight: 800; font-size: 28px;
                   letter-spacing: 0.16em; color: #FFFFFF; background: linear-gradient(90deg, #F2A93B, #E2622F); }}
      .vk-q .body {{ padding: 24px 24px 30px; text-align: center; font-family: "Montserrat"; font-weight: 800; font-size: 46px; white-space: nowrap;
                    line-height: 1.12; color: {INK}; }}
      .cf {{ position: absolute; border-radius: 3px; }}
      .vk-ring {{ width: 220px; height: 220px; border-radius: 50%; border: 10px solid {GOLD}; box-shadow: 0 0 30px rgba(255,201,60,0.8); }}
''')


def confetti(cid: str, at: float, cx: int, cy: int, n: int = 30, seed: int = 7) -> None:
    """Залп конфетти из точки: разлёт за 0.45 с, падение и уход за 0.55 с — у каждой бумажки вход и выход."""
    rnd = random.Random(seed)
    colors = (GOLD, CREAM, RED, "#3FA45B", "#F2A93B", "#FFFFFF")
    html, js = [], [f"      // конфетти {cid}: залп на {at:.2f} с"]
    for i in range(n):
        w, h = rnd.choice(((14, 24), (18, 18), (10, 28), (16, 22)))
        angle, dist = rnd.uniform(-2.9, -0.25), rnd.uniform(220, 520)     # веером вверх и в стороны
        dx, dy = round(math.cos(angle) * dist), round(math.sin(angle) * dist)
        rot = rnd.randint(-540, 540)
        html.append(f'        <div id="{cid}{i}" class="g cf" style="left: {cx - w // 2}px; top: {cy - h // 2}px; width: {w}px; '
                    f'height: {h}px; background: {rnd.choice(colors)};"></div>')
        js.append(f'      tl.fromTo("#{cid}{i}", {{ opacity: 0, x: 0, y: 0, rotation: 0, scale: 0.4 }}, {{ opacity: 1, x: {dx}, '
                  f'y: {dy}, rotation: {rot}, scale: 1, duration: 0.45, ease: "power3.out" }}, {at:.3f});')
        js.append(f'      tl.to("#{cid}{i}", {{ opacity: 0, y: {dy + rnd.randint(180, 320)}, rotation: {rot * 2}, duration: 0.55, '
                  f'ease: "power1.in" }}, {at + 0.45:.3f});')
    m.front("\n".join(html))
    m.js("\n".join(js))


HEART = ('<svg viewBox="0 0 32 29" width="{w}" height="{h}"><path d="M16 29 L3.2 16.2 C-1.6 11.3 1.2 2 8.2 2 C11.9 2 14.3 4.2 16 '
         '7 C17.7 4.2 20.1 2 23.8 2 C30.8 2 33.6 11.3 28.8 16.2 Z" fill="' + RED + '" stroke="#FFF4D6" stroke-width="1.6"/></svg>')
CHECK = ('<svg viewBox="0 0 60 50" width="62" height="52" style="vertical-align: -6px; margin-right: 14px;"><path pathLength="1" '
         'stroke-dasharray="1" stroke-dashoffset="1" d="M6 26 L23 42 L54 6" fill="none" stroke="' + GOLD + '" stroke-width="9" '
         'stroke-linecap="round" stroke-linejoin="round"/></svg>')

# ---------------------------------------------------------------- хук: тост, «2026–2027! Ура!»
ura = word(2, "ура")
# заголовок — в нижней половине, над субтитрами: сверху в кадре тоста лицо сотрудницы (подбородок до y 378)
m.front('        <div id="t-title" class="g" style="left: 120px; top: 930px; width: 730px; text-align: center;">'
        '<span class="vk-gold" style="font-size: 80px;">новоселье</span></div>\n'
        '        <div id="t-sub" class="g vk-hand" style="left: 120px; top: 1040px; width: 730px; text-align: center; font-size: 84px;">'
        '«Вкудесника»</div>')
m.js(f'      enter("#t-title", 0.12, {{ fromScale: 0.6, dur: 0.36 }});\n'
     f'      enter("#t-sub", 0.42, {{ fromY: 30, fromScale: 0.8, dur: 0.3 }});\n'
     f'      leave(["#t-title", "#t-sub"], {tk.scenes[0] - 0.26:.2f}, {{ y: -50 }});')
confetti("cfa", ura + 0.05, 540, 980, seed=3)
m.sound("ura", "sparkle", ura, 0.8)

# ---------------------------------------------------------------- завязка: новоселье, фуршет — список рукой
m.punch(word(9, "новоселье"), round(word(10, "в") + 0.25, 2), 1.07)
ck = [(18, "фуршетик", "фуршетик"), (19, "тортик", "тортик"), (20, "закусочки", "закусочки")]
items = "\n".join(f'          <div id="ck{k}" class="g" style="position: relative; display: block; margin-bottom: 6px;">{CHECK}'
                  f'<span class="vk-hand" style="font-size: 96px;">{label}</span></div>' for k, (_, _, label) in enumerate(ck))
m.front(f'        <div id="ck" style="position: absolute; left: 560px; top: 300px; width: 470px;">\n{items}\n        </div>')
js = []
for k, (i, text, _) in enumerate(ck):
    t = word(i, text)
    js.append(f'      enter("#ck{k}", {t:.2f}, {{ fromX: 60, fromScale: 0.8, dur: 0.26 }});')
    js.append(f'      draw("#ck{k} path", {t + 0.12:.2f}, 0.24);')
end_list = round(word(21, "и") - 0.3, 2)                    # склейка-пауза на «И» — список уходит до неё
js.append(f'      leave(["#ck0", "#ck1", "#ck2"], {end_list:.2f}, {{ x: 60, y: 0 }});')
m.js("\n".join(js))
m.hide(round(word(18, "фуршетик") - 0.05, 2), end_list)    # список повторяет слова — субтитры не двоят
m.punch(word(27, "реакции"), round(word(31, "помещение") - 0.05, 2), 1.07)

# ---------------------------------------------------------------- идёт встречать, проходка ×3, встреча
s_go, s_walk, s_hello, s_hug = (clip("IMG_6709.MOV", 1.6), clip("IMG_6709.MOV", 6.7), clip("IMG_6709.MOV", 13.7),
                                clip("IMG_6709.MOV", 24.7))
# плашка — только на проходке (там нет речи): на «иду встречать» она повторяла бы субтитр
m.front('        <div id="ch-go" class="g vk-chip" style="left: 245px; top: 300px;">спускаюсь к команде <b>⏩</b></div>')
m.js(f'      enter("#ch-go", {s_walk + 0.08:.2f}, {{ fromX: -80, fromScale: 0.85, dur: 0.26 }});\n'
     f'      leave("#ch-go", {s_hello - 0.24:.2f}, {{ x: 120, y: 0 }});\n'
     f'      whip({s_walk:.2f});\n'
     f'      whip({s_hello:.2f});')
m.sound("walk", "whoosh", s_walk - 0.05, 0.9)
m.front('        <div id="ch-team" class="g vk-chip" style="left: 270px; top: 300px;">🔔 команда пришла!</div>')
m.js(f'      enter("#ch-team", {s_hello + 0.12:.2f}, {{ fromY: -40, fromScale: 0.8, dur: 0.3 }});\n'
     f'      leave("#ch-team", {s_hug - 0.25:.2f}, {{ y: -40 }});')
m.sound("team", "notification", s_hello + 0.12, 0.6)
m.hide(round(word(38, "здравствуйте") - 0.05, 2), round(tk.scenes[5] - 0.02, 2))
hearts = [(630, 560, 96), (770, 640, 72), (540, 690, 60)]     # над головами: обнимаются низко в кадре (подбородок до y 1269)
m.front("\n".join(f'        <div id="hz{k}" class="g" style="left: {x}px; top: {y}px;">{HEART.format(w=s, h=round(s * 0.9))}</div>'
                  for k, (x, y, s) in enumerate(hearts)))
m.js("\n".join(f'      enter("#hz{k}", {s_hug + 0.35 + 0.28 * k:.2f}, {{ fromScale: 0.3, fromY: 40, dur: 0.3 }});\n'
               f'      tl.to("#hz{k}", {{ y: -260, duration: 1.6, ease: "none" }}, {s_hug + 0.65 + 0.28 * k:.2f});\n'
               f'      leave("#hz{k}", {s_hug + 1.9 + 0.28 * k:.2f}, {{ y: -320 }});' for k in range(len(hearts))))

# ---------------------------------------------------------------- новый офис, к столу, дегустация
m.punch(word(45, "новый"), round(tk.scenes[7] - 0.1, 2), 1.07)
s_in, s_taste, s_face = clip("IMG_6710.MOV", 9.7), clip("IMG_6727.MOV", 15.1), clip("IMG_6727.MOV", 25.7)
m.front('        <div id="ch-table" class="g vk-chip" style="left: 230px; top: 300px;">и сразу — к столу 🍰</div>')
m.js(f'      enter("#ch-table", {s_in + 0.1:.2f}, {{ fromX: 80, fromScale: 0.85, dur: 0.28 }});\n'
     f'      leave("#ch-table", {s_taste - 0.3:.2f}, {{ x: -100, y: 0 }});')
m.sound("table", "click", s_in + 0.1, 0.8)
m.front('        <div id="ch-taste" class="g vk-chip" style="left: 330px; top: 1240px;">дегустация 🍬</div>')    # лица сверху
m.js(f'      enter("#ch-taste", {s_taste + 0.15:.2f}, {{ fromY: -40, fromScale: 0.85, dur: 0.28 }});\n'
     f'      leave("#ch-taste", {s_face - 0.3:.2f}, {{ y: -40 }});')
m.front('        <div id="liq" class="g vk-hand" style="left: 110px; top: 320px; width: 740px; text-align: center; font-size: 100px; '
        'transform: rotate(-3deg);">…а конфеты оказались<br>с ликёром 😂</div>')
liq_at = round(s_face + 0.9, 2)
m.js(f'      enter("#liq", {liq_at:.2f}, {{ fromScale: 0.5, rot: -3, dur: 0.34 }});\n'
     f'      leave("#liq", {tk.scenes[10] - 0.28:.2f}, {{ rot: -3 }});')
m.sound("liq", "error", liq_at, 0.6)

# ---------------------------------------------------------------- впечатления: вопрос-наклейка, «в восторге»
q_at = round(tk.scenes[10] + 0.12, 2)
m.front('        <div id="q" class="g vk-q" style="left: 190px; top: 236px;">\n'
        '          <div class="top">ВОПРОС КОМАНДЕ</div>\n'
        '          <div class="body">Как вам новый офис? 🏢</div>\n'
        '        </div>')
m.js(f'      enter("#q", {q_at:.2f}, {{ fromScale: 0.6, fromY: -40, dur: 0.34 }});\n'
     f'      leave("#q", {word(60, "ой") - 0.12:.2f}, {{ y: -60 }});')
m.sound("q", "ping", q_at, 0.7)
m.punch(word(64, "восторге"), round(word(65, "офис") + 0.2, 2), 1.07)
spark = ('<svg viewBox="0 0 40 40" width="{s}" height="{s}"><path d="M20 0 L24 16 L40 20 L24 24 L20 40 L16 24 L0 20 L16 16 Z" '
         'fill="' + GOLD + '"/></svg>')
stars = [(250, 1120, 54), (790, 1100, 44), (300, 1230, 34)]
m.front("\n".join(f'        <div id="st{k}" class="g" style="left: {x}px; top: {y}px;">{spark.format(s=s)}</div>'
                  for k, (x, y, s) in enumerate(stars)))
t_style = word(68, "стильный")
m.js("\n".join(f'      enter("#st{k}", {t_style + 0.08 * k:.2f}, {{ fromScale: 0, rot: 90, dur: 0.3 }});\n'
               f'      leave("#st{k}", {t_style + 1.3 + 0.08 * k:.2f}, {{ scale: 0, rot: -90, y: 0 }});' for k in range(len(stars))))
m.punch(word(76, "уровень"), round(word(79, "видно") + 0.25, 2), 1.07)

# ---------------------------------------------------------------- «в любимой команде» — сердце
t_love = word(88, "любимой")
m.front(f'        <div id="hz-love" class="g" style="left: 690px; top: 330px;">{HEART.format(w=120, h=108)}</div>')
m.js(f'      enter("#hz-love", {t_love:.2f}, {{ fromScale: 0.2, dur: 0.3, ease: "back.out(3)" }});\n'
     f'      tl.to("#hz-love", {{ scale: 1.12, duration: 0.25, yoyo: true, repeat: 1, ease: "sine.inOut" }}, {t_love + 0.35:.2f});\n'
     f'      leave("#hz-love", {tk.scenes[12] - 0.25:.2f}, {{ y: -60 }});')

# ---------------------------------------------------------------- пожелания на сезон
s_wish = tk.scenes[12]
m.front('        <div id="ch-wish" class="g vk-chip" style="left: 210px; top: 280px;">🎄 пожелания на сезон</div>')
m.js(f'      enter("#ch-wish", {s_wish + 0.08:.2f}, {{ fromY: -50, fromScale: 0.8, dur: 0.3 }});\n'
     f'      leave("#ch-wish", {s_wish + 2.4:.2f}, {{ y: -50 }});')
m.sound("wish", "whoosh", s_wish, 0.6)
m.punch(word(93, "качественной"), round(word(95, "выпустить"), 2), 1.07)
t_thumb = clip("IMG_6729.MOV", 20.95)            # большой палец: рука слева на груди, 66.2–66.6 с дубля
m.front('        <div id="ring" class="g vk-ring" style="left: 140px; top: 1052px; width: 180px; height: 180px;"></div>')
m.js(f'      enter("#ring", {t_thumb:.2f}, {{ fromScale: 0.3, blur: 0, dur: 0.25, ease: "power2.out" }});\n'
     f'      leave("#ring", {t_thumb + 0.55:.2f}, {{ scale: 1.6, y: 0, blur: 0 }});')
m.sound("thumb", "ping", t_thumb, 0.6)
m.punch(word(111, "процветания"), round(word(114, "успехов") - 0.1, 2), 1.07)

# ---------------------------------------------------------------- «Успехов, успехов, ещё раз успехов!»
hits = [(115, 66, 1048), (116, 80, 1128), (119, 96, 1222)]         # безопасная колонка: справа кнопки, снизу ник
m.front("\n".join(f'        <div id="us{k}" class="g" style="left: 120px; top: {top}px; width: 730px; text-align: center;">'
                  f'<span class="vk-gold" style="font-size: {size}px;">успехов!</span></div>'
                  for k, (_, size, top) in enumerate(hits)))
m.js("\n".join(f'      slam("#us{k}", {word(i, "успехов"):.2f}, {{ fromScale: 1.6, rot: {(-3, 2, -2)[k]} }});'
               for k, (i, _, _) in enumerate(hits))
     + f'\n      leave(["#us0", "#us1", "#us2"], {tk.scenes[15] - 0.22:.2f}, {{ y: -40 }});')
m.hide(round(word(115, "успехов") - 0.05, 2), round(tk.scenes[15], 2))
m.sound("us", "pop", word(115, "успехов"), 0.7)

# ---------------------------------------------------------------- финал: тост всей командой и подпись бренда
s_end = tk.scenes[15]
confetti("cfb", s_end + 0.1, 540, 900, seed=11)
m.sound("end", "sparkle", s_end + 0.1, 0.7)
m.front('        <div id="e-brand" class="g" data-hold="подпись бренда держится до конца ролика — так задумано" '
        'style="left: 120px; top: 300px; width: 730px; text-align: center;"><span class="vk-gold" style="font-size: 84px;">вкудесник</span></div>\n'
        '        <div id="e-sub" class="g vk-hand" data-hold="подпись бренда держится до конца ролика — так задумано" '
        'style="left: 120px; top: 410px; width: 730px; text-align: center; font-size: 74px;">подарки с атмосферой<br>настоящего праздника</div>')
m.js(f'      enter("#e-brand", {s_end + 0.2:.2f}, {{ fromScale: 0.6, dur: 0.36 }});\n'
     f'      enter("#e-sub", {s_end + 0.55:.2f}, {{ fromY: 30, fromScale: 0.85, dur: 0.32 }});')
m.sound("brand", "chime", s_end + 1.2, 0.5)

m.build("Новоселье «Вкудесника»", text_fixes={"0": "2026–2027", "1": "", "73": "всё", "105": "Всё", "117": "ещё"},
        accent_words=["новоселье", "реакции", "восторге", "уровень", "любимой", "процветания"],
        track="mx-christmas-gifts.mp3", framing=False, cutout=False,
        # селфи на ходу «Проходите, пожалуйста»: лицо низко (подбородок до y 1308) — субтитры над головой
        director_extra={"caption_lanes": [[round(tk.scenes[5], 2), round(tk.scenes[6], 2), 330]]})
