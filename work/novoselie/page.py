"""novoselie v2 — новоселье «Вкудесника» лайф-влогом (20.10.2026): стильно, на удержание, динамично, петлёй.

Решения заказчика — projects/vkudesnik/rules.md, «Стиль монтажа». Без ИИ-генераций и без «душевности»: ни сердечек,
ни рукописи. Типографика: открытие — «НОВО / СЕЛЬЕ» Alumni Sans Black в долю «House 02» (123 BPM, трек с 0.41 с — доля
на 0 ролика, сборка резала вспышки и рывки в долю: pack.json → beat); субтитры — Golos Black строчными, активное слово на
жёлтой плашке (стиль проекта); плашки — Onest Black; мем — нативная белая подложка. Музыка уходит под живой звук дубля и
поднимается в тишине (project.json → music_duck). Петля: команда поднимает стаканы → первый тост.
Факты: «конфеты с ликёром» — подпись самого бренда к прошлому ролику с этого новоселья (@vkudesnik_).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from montage import Montage  # noqa: E402

STEM = "novoselie"
BEAT = 60 / 123.0
m = Montage(STEM)
tk = m.tk
W, S = tk.words, tk.scenes


def word(i: int, text: str) -> float:
    """Начало слова i на шкале дубля; слово не то — громкая ошибка (пересобрали сборку — номера сдвинулись)."""
    got = W[i]["word"].strip(" .,!?").lower()
    if got != text:
        raise ValueError(f"слово [{i}] — «{W[i]['word']}», а ждал «{text}»: сверь номера после пересборки")
    return round(W[i]["start"], 2)


def whip_at(t: float) -> str:
    """Смаз на стыке — на 4 мс раньше: время стыка округлено до мс, кадр стыка — чуть раньше (см. montage.cover_cuts)."""
    return f"      whip({t - 0.004:.3f});"


def scene(t: float) -> float:
    """Стык сцен у момента t (сборка: aroll.json → scenes); нет такого — громкая ошибка."""
    hit = min(S, key=lambda x: abs(x - t))
    if abs(hit - t) > 0.1:
        raise ValueError(f"стыка сцен около {t:.2f} с нет (есть {S})")
    return hit


YEL, INK, WHITE = "#FFD60A", "#111111", "#FFFFFF"
m.css(f'''
      @font-face {{ font-family: "Alumni"; src: url("assets/fonts/AlumniSans-Black.ttf"); font-weight: 900; }}
      @font-face {{ font-family: "Onest"; src: url("assets/fonts/Onest-Black.ttf"); font-weight: 900; }}
      @font-face {{ font-family: "Golos"; src: url("assets/fonts/GolosText-Black.ttf"); font-weight: 900; }}
      .cap {{ text-shadow: 0 2px 2px rgba(0,0,0,0.55), 0 6px 22px rgba(0,0,0,0.45); letter-spacing: -0.01em; }}
      .x-huge {{ font-family: "Alumni"; font-weight: 900; text-transform: uppercase; line-height: 0.84; letter-spacing: 0.005em;
                color: {WHITE}; text-shadow: 0 10px 34px rgba(0,0,0,0.45); }}
      .x-huge .y {{ color: {YEL}; }}
      .x-tag {{ font-family: "Onest"; font-weight: 900; font-size: 36px; letter-spacing: 0.02em; color: {INK}; background: {YEL};
               border-radius: 12px; padding: 10px 22px 12px; white-space: nowrap; }}
      .x-tag.dark {{ color: {WHITE}; background: rgba(17,17,17,0.86); }}
      .x-tag.big {{ font-size: 48px; padding: 12px 26px 14px; }}
      .x-meme {{ font-family: "Golos"; font-weight: 900; font-size: 64px; line-height: 1.08; color: {INK}; background: {WHITE};
                border-radius: 18px; padding: 16px 30px 20px; text-align: center; box-shadow: 0 16px 40px rgba(0,0,0,0.35); }}
      .x-meme small {{ display: block; font-size: 38px; color: #6B6B6B; margin-bottom: 4px; }}
''')

# ---------------------------------------------------------------- открытие: три вспышки в долю, «НОВО / СЕЛЬЕ»
open_end = scene(4 * BEAT)
# лица во вспышках на трёх высотах (тост — вверху, объятие — внизу, смех — посередине): заголовок сначала посередине,
# на третьей доле прыгает вниз — кинетика в ритм, лица свободны. Прыжок — два комплекта: верхний уходит, нижний бьёт
m.front('''        <div id="o-1" class="g x-huge" style="left: 120px; top: 430px; width: 730px; font-size: 250px;">ново</div>
        <div id="o-2" class="g x-huge" style="left: 120px; top: 640px; width: 730px; font-size: 250px;"><span class="y">селье</span></div>
        <div id="o-tag" class="g x-tag dark" style="left: 120px; top: 862px;">вкудесник · мы переехали</div>
        <div id="o-3" class="g x-huge" style="left: 120px; top: 948px; width: 730px; font-size: 250px;">ново</div>
        <div id="o-4" class="g x-huge" style="left: 120px; top: 1158px; width: 730px; font-size: 250px;"><span class="y">селье</span></div>''')
jump = round(3 * BEAT, 3)
m.js(f'''      slam("#o-1", 0.02, {{ fromScale: 1.35, blur: 10 }});
      slam("#o-2", {BEAT:.3f}, {{ fromScale: 1.35, blur: 10 }});
      enter("#o-tag", {2 * BEAT:.3f}, {{ fromX: -60, fromScale: 0.9, dur: 0.2 }});
      leave(["#o-1", "#o-2"], {jump - 0.1:.3f}, {{ y: 120, dur: 0.09 }});
      slam("#o-3", {jump:.3f}, {{ fromScale: 1.25, blur: 8, dur: 0.12 }});
      slam("#o-4", {jump + 0.05:.3f}, {{ fromScale: 1.25, blur: 8, dur: 0.12 }});
      leave(["#o-3", "#o-4"], {open_end - 0.2:.3f}, {{ y: 60, dur: 0.18 }});
      leave("#o-tag", {open_end - 0.2:.3f}, {{ y: -40, dur: 0.18 }});
      flash({open_end:.3f});
{whip_at(scene(2 * BEAT))}
{whip_at(scene(3 * BEAT))}''')
m.hide(0.0, round(open_end, 2))          # «ура!» и так орёт кадр; под словом — не субтитр, а заголовок
m.sound("open", "impact-bass-1", 0.0, 0.7)

# ---------------------------------------------------------------- завязка: новоселье, фуршет — список плашками
m.punch(word(7, "новоселье"), round(word(8, "в") + 0.3, 2), 1.08)
items = [(16, "фуршетик"), (17, "тортик"), (18, "закусочки")]
m.front("\n".join(f'        <div id="ck{k}" class="g x-tag big" style="left: {120 + 24 * k}px; top: {320 + 92 * k}px;">'
                  f'✓ {label}</div>' for k, (_, label) in enumerate(items)))
m.js("\n".join(f'      slam("#ck{k}", {word(i, label):.2f}, {{ fromScale: 1.4, rot: {(-3, 2, -2)[k]} }});'
               for k, (i, label) in enumerate(items))
     + f'\n      leave(["#ck0", "#ck1", "#ck2"], {scene(S[3]) - 0.22:.2f}, {{ x: 80, y: 0 }});')
m.hide(round(word(16, "фуршетик") - 0.05, 2), round(S[3] - 0.02, 2))
m.punch(word(25, "добро"), round(word(26, "пожаловать") + 0.4, 2), 1.08)

# ---------------------------------------------------------------- проходка рывком, встреча, вход
walk, walk_end = scene(S[4]), scene(S[5])
m.front('        <div id="t-walk" class="g x-tag" style="left: 120px; top: 300px;">встречаю команду →</div>')
m.js(f'''{whip_at(walk)}
      enter("#t-walk", {walk + 0.12:.2f}, {{ fromX: -80, dur: 0.22 }});
      leave("#t-walk", {walk_end - 0.22:.2f}, {{ x: 120, y: 0 }});
{whip_at(walk_end)}''')
m.sound("walk", "whoosh", walk - 0.08, 0.9)
m.sound("hello", "notification", walk_end + 0.3, 0.5)          # пришли — колокольчик (между двумя свистами)
hug = scene(S[6])
m.js(whip_at(hug))
enter_in, enter_out = scene(S[8]), scene(S[9])
m.front('        <div id="t-table" class="g x-tag" style="left: 120px; top: 300px;">первым делом — к столу</div>')
m.js(f'''{whip_at(enter_in)}
      enter("#t-table", {enter_in + 0.1:.2f}, {{ fromX: -80, dur: 0.22 }});
      leave("#t-table", {enter_out - 0.22:.2f}, {{ x: 120, y: 0 }});''')
m.sound("enter", "whoosh-cinematic", enter_in - 0.1, 0.5)

# ---------------------------------------------------------------- мем: стоп-кадр на конфете с ликёром
taste = scene(S[10])
freeze = round(taste + (26.42 - 25.6), 2)            # дальше кадр стоит (pack.json: hold)
meme_end = scene(S[11])
m.front('''        <div id="meme" class="g x-meme" style="left: 150px; top: 300px; width: 670px; transform: rotate(-2deg);">
          <small>стоп…</small>конфеты<br>С ЛИКЁРОМ?! 🥃</div>''')
m.js(f'''      flash({freeze:.2f});
      slam("#meme", {freeze + 0.06:.2f}, {{ fromScale: 1.5, rot: -2, blur: 8 }});
      leave("#meme", {meme_end - 0.2:.2f}, {{ rot: -2, y: -40 }});''')
m.punch(freeze, round(meme_end - 0.05, 2), 1.18, ease_in=0.06, ease_out=0.1)
m.sound("scratch", "error", freeze, 0.7)

# ---------------------------------------------------------------- отзывы нарезкой: вопрос плашкой, ключевые наезды
q_at = meme_end
m.front('        <div id="q" class="g x-tag dark" style="left: 120px; top: 290px;">что говорит команда 👇</div>')
m.js(f'''      enter("#q", {q_at + 0.08:.2f}, {{ fromY: -40, fromScale: 0.9, dur: 0.24 }});
      leave("#q", {q_at + 4.3:.2f}, {{ y: -40 }});''')
m.sound("q", "pop", q_at + 0.08, 0.7)
m.punch(word(35, "восторге"), round(S[12] - 0.05, 2), 1.08)
m.punch(word(47, "уровень"), round(word(50, "видно") + 0.3, 2), 1.08)
m.punch(word(59, "любимой"), round(S[15] - 0.05, 2), 1.08)
wish = scene(S[15])
m.front('        <div id="w" class="g x-tag dark" style="left: 120px; top: 290px;">а пожелания на сезон?</div>')
m.js(f'''      enter("#w", {wish + 0.08:.2f}, {{ fromY: -40, fromScale: 0.9, dur: 0.24 }});
      leave("#w", {wish + 4.2:.2f}, {{ y: -40 }});''')
m.sound("w", "click", wish + 0.08, 0.8)
m.punch(word(77, "вовремя"), round(S[17] - 0.05, 2), 1.08)        # большой палец
m.punch(word(81, "процветания"), round(word(84, "успехов") - 0.1, 2), 1.08)

# ---------------------------------------------------------------- «Успехов, успехов, ещё раз успехов!»
hits = [(85, 100, 1046), (86, 116, 1134), (89, 136, 1236)]     # под лицом (подбородок до y 1025), над ником
m.front("\n".join(f'        <div id="us{k}" class="g x-huge" style="left: 120px; top: {top}px; width: 730px; font-size: {size}px;">'
                  f'{"<span class=y>успехов!</span>" if k == 2 else "успехов!"}</div>' for k, (_, size, top) in enumerate(hits)))
m.js("\n".join(f'      slam("#us{k}", {word(i, "успехов"):.2f}, {{ fromScale: 1.6, blur: 10 }});' for k, (i, _, _) in enumerate(hits))
     + f'\n      leave(["#us0", "#us1", "#us2"], {S[-1] - 0.2:.2f}, {{ y: -50, dur: 0.18 }});')
m.hide(round(word(85, "успехов") - 0.05, 2), round(S[-1], 2))
m.sound("us", "impact-bass-2", word(89, "успехов"), 0.6)

# ---------------------------------------------------------------- петля: команда поднимает стаканы → первый тост
m.js(whip_at(S[-1]))

m.build("Новоселье «Вкудесника»", text_fixes={"67": "в этом", "75": "всё", "87": "ещё"},
        accent_words=[], track="mx-house-02.mp3", music_start=0.41, music_fade=0.3,
        framing=False, cutout=False, jump_whip=True)
