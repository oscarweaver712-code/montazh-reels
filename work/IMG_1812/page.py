"""Страница графики IMG_1812: Серега, два броска кубика и «хотя бы одна шестёрка».

Время ударов — по исходнику, на шкалу дубля (0.97–83.27, хвост «Ну это хорошо. Но, ну так.»
убран) переводит Take. План — work/IMG_1812/plan.md (15.10, по п.13 rules.md).
Проверено: P(хотя бы одна 6 за 2 броска) = 1 − (5/6)² = 1 − 25/36 = 11/36 ≈ 0,306 ≈ 0,31 — верно.
Сетка 6×6: исходов 36, без шестёрки 5·5 = 25, с шестёркой 36 − 25 = 11 (шестая строка и шестой
столбец: 6 + 6 − 1 общая клетка 6:6) — сходится с дробью.
Ошибка Сереги 1/6 + 1/6 = 1/3 ≈ 0,333: разница 1/36, «гораздо меньше» — оценка автора; на экран
выносим только «а Серега думал ⅓», без «гораздо». История: 1654 — переписка Паскаля и Ферма,
поводом были вопросы игрока Антуана Гомбо, шевалье де Мере, про ставки в кости — верно.
Распознавание: «ладоманам» → «лудоманам», «Шевалье Демере» → «шевалье де Мере», «ферма» → «Ферма».
Хук «Помните Серегу…» отсылает к IMG_3320, где героя звали Тимофей, — не исправляем (заметка 14.10).
Призыв — кодовое слово «вероятность» (как он говорит), финальной плашки «в профиле» нет.
Картинки — Wikimedia Commons, качает work/IMG_1812/fetch.py; лицензии и авторы — в
downloads/candidates.json: портреты Паскаля и Ферма (PD), фоны за спиной — см. BG ниже.
Портрета де Мере достоверного нет — не показываем.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import viz  # noqa: E402
from kit import Take, audio, build_page, card, keyword_beats, keyword_card  # noqa: E402

STEM = "IMG_1812"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)
# фон за спиной (п.13 rules.md): выбран глазами из кандидатов fetch.py
#   казино — «Norwegian Dawn casino 1.JPG», CC BY-SA 3.0 (автор — в candidates.json): настоящий стол рулетки;
#   игроки в кости — Жорж де Латур, «Игроки в кости», ок. 1650 («Georges de La Tour 035.jpg»), PD: та же эпоха
#   вахта — СГЕНЕРИРОВАНА (gen_image.py, Codex), не фото: свободной буровой в Commons не нашлось (downloads/vahta.md)
BG = {"bg_casino.jpg": "casino_4.jpg", "bg_vahta.png": "vahta.png", "bg_dice.jpg": "dice_2.jpg"}
for dst_name, src_name in {"pascal.jpg": "pascal.jpg", "fermat.jpg": "fermat.jpg", **BG}.items():
    src = ROOT / f"work/{STEM}/downloads/{src_name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (картинки с Wikimedia Commons)")
    dst = IMG / dst_name
    if not (dst.exists() and dst.samefile(src)):
        shutil.copyfile(src, dst)

CHEST = 1290        # верх плашек на груди: подбородок при базе 1.2 доходит до y 1263 (verify_page)
css = f'''      .panel {{ border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }}
      .row {{ position: relative; display: flex; justify-content: space-between; align-items: center; min-height: 92px;
             padding: 4px 6px; opacity: 0; border-bottom: 2px solid rgba(242,235,221,0.14); }}
      .row:last-child {{ border-bottom: none; }}
      .row-w {{ font-family: "Manrope"; font-weight: 800; font-size: 28px; letter-spacing: 0.06em; text-transform: uppercase;
               color: rgba(242,235,221,0.8); }}
      .row-m {{ display: inline-flex; align-items: center; color: var(--cream); font-size: 50px; white-space: nowrap; }}
      .row-m .katex-src, .fx .katex-src {{ display: inline-block; }}
      .row-m .katex-display, .fx .katex-display {{ margin: 0; }}
      .eq {{ display: inline-block; opacity: 0; margin-left: 10px; }}
      .gold {{ color: #F5B82E; }}
      .strike {{ position: absolute; right: 0; top: 46%; width: 150px; height: 8px; border-radius: 4px; background: var(--red);
                transform-origin: 0 50%; transform: scaleX(0); }}
      .task-row {{ margin-top: 6px; font-family: "Manrope"; font-weight: 800; font-size: 34px; color: #1A1A1A; opacity: 0; white-space: nowrap; }}
      .task-head {{ display: flex; justify-content: space-between; align-items: center; font-family: "Manrope"; font-weight: 800;
                   font-size: 26px; letter-spacing: 0.12em; text-transform: uppercase; color: #2B3A67; }}
      /* портреты в верхних углах — меньше обычных: макушка поднимается высоко */
      #c-pas, #c-fer {{ top: 268px; width: 236px; padding: 12px 12px 10px; }}
      #c-pas {{ left: 716px; }} #c-fer {{ left: 128px; }}
      #c-pas .ph, #c-pas img, #c-fer .ph, #c-fer img {{ width: 212px; height: 220px; }}
      #c-pas .card-name, #c-fer .card-name {{ font-size: 20px; margin-top: 8px; }}
      #c-pas .card-sub, #c-fer .card-sub {{ font-size: 22px; }}
      /* подменённый фон за спиной: сверху, низ переходит в родной кадр (там банка и руки) */
      .bg {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
             -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
             mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }}
      .bg img {{ position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover; }}
      .bg .vig {{ position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }}
      /* схема правила: три шага в ряд со стрелками */
      .step {{ position: absolute; top: 22px; width: 160px; height: 112px; border-radius: 18px; display: flex; align-items: center;
              justify-content: center; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 27px; line-height: 1.1;
              color: var(--cream); border: 3px solid rgba(242,235,221,0.35); opacity: 0; }}
      .step.hot {{ border-color: #F5B82E; color: #F5B82E; }}
      /* сетка 36 исходов двух бросков */
      .cell {{ position: absolute; width: 38px; height: 38px; border-radius: 8px; background: rgba(242,235,221,0.32); opacity: 0; }}
      .cell.six {{ background: rgba(242,235,221,0.32); }}
      .ax {{ position: absolute; width: 38px; height: 30px; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 24px;
            color: rgba(242,235,221,0.7); }}
      .ax.r {{ color: #F0352C; }}
      .fx {{ position: absolute; left: 372px; width: 200px; text-align: center; color: var(--cream); font-size: 46px; opacity: 0; }}
      .fx-note {{ position: absolute; left: 372px; width: 200px; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 22px;
                 letter-spacing: 0.06em; text-transform: uppercase; color: rgba(242,235,221,0.75); opacity: 0; }}
'''

PANEL = "left: 245px; width: 590px; padding: 10px 26px;"
SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'


def tex(s: str, cls: str = "") -> str:
    return f'<span class="katex-src{(" " + cls) if cls else ""}" data-tex="{s}"></span>'


def die(x: int, pips: list) -> str:
    """Грань кубика 90×90 с точками (координаты в долях)."""
    dots = "".join(f'<circle cx="{x + 18 + 54 * a:.0f}" cy="{18 + 54 * b:.0f}" r="8" fill="#1A1A1A" />' for a, b in pips)
    return f'<rect x="{x}" y="0" width="90" height="90" rx="16" fill="#FFFFFF" stroke="#1A1A1A" stroke-width="4" />{dots}'


def bg(bid: str, img: str) -> str:
    return (f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" /><div class="vig"></div></div>')


SIX = [(0, 0), (0, 0.5), (0, 1), (1, 0), (1, 0.5), (1, 1)]
THREE = [(0, 0), (0.5, 0.5), (1, 1)]
dice = (f'<svg id="dice" viewBox="0 0 200 94" style="width: 150px; height: 70px;">'
        f'<g id="die1">{die(2, THREE)}</g><g id="die2">{die(106, SIX)}</g></svg>')

task = (f'        <div id="task" class="g paper" {SAFE} style="left: 160px; top: {CHEST}px; width: 760px; padding: 22px 36px 24px; background: #FBFBF8;">\n'
        f'          <div class="task-head"><span>задача из ЕГЭ · условие</span>{dice}</div>\n'
        '          <div id="tr1" class="task-row">кубик бросают 2 раза</div>\n'
        '          <div id="tr2" class="task-row">ставка: хотя бы одна <span style="color: #C7271F;">6</span></div>\n'
        '          <div id="tr3" class="task-row">P(выигрыш) — ?</div>\n'
        '        </div>')

# логика Сереги: 1/6 + 1/6 = 1/3, на «Нет» итог перечёркивается
F16, F16x2, F13 = tex(r"\tfrac16"), tex(r"\tfrac16+\tfrac16"), tex(r"=\tfrac13")
ser = (f'        <div id="p-ser" class="g panel" {SAFE} style="{PANEL} top: {CHEST}px;">\n'
       f'          <div id="s1" class="row"><span class="row-w">1 бросок</span><span class="row-m">{F16}</span></div>\n'
       f'          <div id="s2" class="row"><span class="row-w">2 броска</span><span class="row-m">{F16x2}'
       f'<span id="s2-eq" class="eq">{F13}</span></span><div id="s2-x" class="strike"></div></div>\n'
       '        </div>')

# схема правила «хотя бы один»: три шага в ряд, стрелки дорисовываются под речь
ARROW = 'fill="none" stroke="#F2EBDD" stroke-width="6" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"'
rule = (f'        <div id="p-rule" class="g panel" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 156px;">\n'
        '          <div id="u1" class="step hot" style="left: 22px;">хотя бы<br />одна 6</div>\n'
        '          <div id="u2" class="step" style="left: 215px;">ни одной 6</div>\n'
        '          <div id="u3" class="step" style="left: 408px;">1 − это</div>\n'
        '          <svg viewBox="0 0 590 156" style="position: absolute; left: 0; top: 0; width: 590px; height: 156px;">'
        f'<path id="ua1" d="M 186 78 L 211 78 M 201 68 L 211 78 L 201 88" {ARROW} />'
        f'<path id="ua2" d="M 379 78 L 404 78 M 394 68 L 404 78 L 394 88" {ARROW} /></svg>\n'
        '        </div>')

# сетка 36 исходов: строки — первый бросок, столбцы — второй; шестая строка и столбец — 11 клеток
G0X, G0Y, STEP = 70, 50, 44
cells, axes = [], []
for j in range(6):
    axes.append(f'<div class="ax{" r" if j == 5 else ""}" style="left: {G0X + j * STEP}px; top: 20px;">{j + 1}</div>')
    axes.append(f'<div class="ax{" r" if j == 5 else ""}" style="left: 22px; top: {G0Y + j * STEP + 7}px;">{j + 1}</div>')
for i in range(6):
    for j in range(6):
        six = i == 5 or j == 5
        cells.append(f'<div class="cell{" six" if six else ""}" style="left: {G0X + j * STEP}px; top: {G0Y + i * STEP}px;"></div>')
grid = (f'        <div id="p-grid" class="g panel" {SAFE} style="left: 245px; top: {CHEST}px; width: 590px; height: 330px;">\n'
        f'          {"".join(axes)}\n          {"".join(cells)}\n'
        '          <div id="gn1" class="fx-note" style="top: 24px;">исходов 36</div>\n'
        f'          <div id="gf1" class="fx" style="top: 66px;">{tex(r"1-\tfrac{25}{36}")}</div>\n'
        f'          <div id="gf2" class="fx" style="top: 166px; color: #F0352C;">{tex(r"=\tfrac{11}{36}")}</div>\n'
        '          <div id="gn2" class="fx-note" style="top: 276px; color: #F0352C;">с шестёркой</div>\n'
        '        </div>')

house = ('        <svg id="house" class="g" viewBox="0 0 200 180" style="left: 440px; top: 300px; width: 200px; height: 180px;">'
         '<path d="M 20 170 V 80 L 100 16 L 180 80 V 170 Z" fill="rgba(245,184,46,0.85)" stroke="#F2EBDD" stroke-width="8" stroke-linejoin="round" />'
         '<rect x="80" y="104" width="40" height="66" fill="#2A2219" /></svg>')

letter = ('        <svg id="letter" class="g" viewBox="0 0 120 84" style="left: 770px; top: 470px; width: 120px; height: 84px;">'
          '<rect x="4" y="4" width="112" height="76" rx="6" fill="#F1E9D8" stroke="#6A5A44" stroke-width="4" />'
          '<path d="M 6 8 L 60 48 L 114 8" fill="none" stroke="#6A5A44" stroke-width="4" />'
          '<circle cx="60" cy="50" r="10" fill="#C7271F" /></svg>')

# доска ManimGX: 5/6 → 5/6 · 5/6 = 25/36 (work/IMG_1812/manim/calc.py)
bd_html, bd_js = viz.board("bd", STEM, "Calc.mp4", at=t(42.30), fmt=tk.fmt, place=(245, CHEST, 590, 330))
bd_html = bd_html.replace('class="g viz"', f'class="g viz" {SAFE}', 1)
BD_END = round(t(42.30) + 7.70, 2)        # длина клипа Calc.mp4

STK = 'top: 300px; font-size: 56px; white-space: nowrap;'
behind = "\n".join([
    bg("bg-casino", "bg_casino.jpg"),
    bg("bg-vahta", "bg_vahta.png"),
    '        <div id="b-zp-lead" class="g lead" style="top: 272px;">ставит на ставки</div>',
    '        <div id="b-zp" class="g big red" style="top: 318px; font-size: 200px;">зарплату</div>',
    '        <div id="b-one" class="g big" style="top: 330px; font-size: 128px; white-space: nowrap;">хотя бы один</div>',
    '        <div id="b-031-lead" class="g lead" style="top: 272px;">примерно</div>',
    '        <div id="b-031" class="g big" style="top: 318px; font-size: 250px; color: #F5B82E;">0,31</div>',
    bg("bg-dice", "bg_dice.jpg"),
    '        <div id="b-1654-lead" class="g lead" style="top: 272px;">теория вероятностей родилась в</div>',
    '        <div id="b-1654" class="g big" style="top: 318px; font-size: 250px;"><span id="b-1654-n">1654</span></div>',
])

front = "\n".join([
    f'        <div id="st-ser" class="g sticker" style="left: 290px; {STK}">тот самый Серега</div>',
    house,
    '        <div id="st-lost" class="g stamp" style="left: 300px; top: 300px; font-size: 96px; background: rgba(12,12,14,0.55);">проиграл</div>',
    f'        <div id="st-ns" class="g sticker" style="left: 370px; {STK}">не сдался</div>',
    f'        <div id="st-vahta" class="g sticker" style="left: 380px; {STK}">вахтовик</div>',
    f'        <div id="st-ege" class="g sticker" style="left: 270px; {STK}">снова задача из ЕГЭ</div>',
    task,
    f'        <div id="st-logic" class="g sticker" style="left: 320px; {STK}">логика Сереги</div>',
    ser,
    f'        <div id="st-ok" class="g sticker" style="left: 400px; {STK}">логично?</div>',
    '        <div id="st-no" class="g stamp" style="left: 420px; top: 290px; font-size: 120px; background: rgba(12,12,14,0.55);">нет</div>',
    f'        <div id="st-lost2" class="g sticker" style="left: 230px; {STK}">так и потерял квартиру</div>',
    '        <div id="p-beacon" class="g pill" style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 40px;">'
    '<span id="beacon-dot" style="color: #F0352C;">●</span> главный маячок</div>',
    rule,
    bd_html,
    '        <div id="st-plus" class="g stamp" style="left: 330px; top: 290px; font-size: 96px; background: rgba(12,12,14,0.55); white-space: nowrap;">×, а не +</div>',
    grid,
    f'        <div id="st-thought" class="g sticker" style="left: 260px; {STK}">а Серега думал ⅓</div>',
    f'        <div id="st-mere" class="g sticker" style="left: 170px; {STK}">шевалье де Мере, игрок</div>',
    card("c-pas", "pascal.jpg", "Блез Паскаль", "получил жалобу", side="right"),
    card("c-fer", "fermat.jpg", "Пьер Ферма", "ответил письмом", side="left"),
    letter,
    '        <div id="st-sci" class="g stamp" style="left: 360px; top: 290px; font-size: 110px; background: rgba(12,12,14,0.55);">наука</div>',
    f'        <div id="st-lud" class="g sticker" style="left: 240px; {STK}">спасибо лудоманам</div>',
    f'        <div id="st-razbor" class="g sticker" style="left: 170px; {STK}">разбор всех типов задач</div>',
    # подпись над полем закрывала подбородок (база 1.2), приписка снизу уходила под ник — подпись
    # над головой, приписки нет: «разбор всех типов задач» было стикером перед этим
    "\n".join(s for s in keyword_card("вероятность", "", "", top=1250).splitlines() if 'id="kw-label"' not in s),
    '        <div id="kw-top" class="g pill" data-hold="призыв держится до конца ролика — так задумано" '
    'style="left: 0; width: 1080px; text-align: center; top: 300px; background: none; border: none; font-size: 44px;">пиши в комментариях</div>',
    '        <div id="st-stop" class="g stamp" style="left: 260px; top: 290px; font-size: 110px; background: rgba(12,12,14,0.55);">завязывай</div>',
])

ROW = '{ opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }'


def row(sel: str, at: float) -> str:
    return f'      tl.fromTo("{sel}", {ROW}, {at});'


def eq(sel: str, at: float) -> str:
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.5, filter: BLUR(10) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.18, ease: "power4.out" }}, {at});')


def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'
SIXES = "#p-grid .cell.six"
beats = f'''
      // ---------- хук: игорный стол за спиной, тот самый Серега проиграл квартиру ----------
{bg_in("#bg-casino", t(1.00), t(4.40))}
      enter("#st-ser", {t(1.06)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-ser", {t(2.80)}, {{ y: -30, rot: -10 }});
      tl.fromTo("#house", {{ opacity: 0, scale: 0.3 }}, {{ opacity: 1, scale: 1, duration: 0.25, ease: "back.out(2)" }}, {t(2.94)});
      tl.to("#house", {{ x: 420, y: -260, rotation: 50, opacity: 0, duration: 0.42, ease: "power2.in" }}, {t(3.30)});
      slam("#st-lost", {t(3.30)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#st-lost", {t(4.30)}, {{ scale: 0.6, y: 0, rot: -18 }});
      enter("#st-ns", {t(4.52)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-ns", {t(5.40)}, {{ y: -30, rot: 10 }});

      // ---------- вахта за спиной: ставит на ставки ЗАРПЛАТУ ----------
{bg_in("#bg-vahta", t(5.70), t(9.25))}
      enter("#st-vahta", {t(5.74)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-vahta", {t(7.00)}, {{ y: -30, rot: -10 }});
      enter("#b-zp-lead", {t(7.26)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-zp", {t(8.04)}, {{ fromScale: 1.5 }});
      leave(["#b-zp", "#b-zp-lead"], {t(9.20)}, {{ y: -60 }});
      enter("#st-ege", {t(9.40)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-ege", {t(10.90)}, {{ y: -30, rot: 10 }});

      // ---------- условие ----------
      doc("#task", {t(11.14)}, {t(18.90)}, {{ fromRot: -5, rot: 1 }});
      tl.fromTo("#die1", {{ rotation: -200, svgOrigin: "47 45" }}, {{ rotation: 0, duration: 0.6, ease: "power3.out" }}, {t(12.56)});
      tl.fromTo("#die2", {{ rotation: 220, svgOrigin: "151 45" }}, {{ rotation: 0, duration: 0.6, ease: "power3.out" }}, {t(12.70)});
{row("#tr1", t(12.14))}
{row("#tr2", t(14.74))}
{row("#tr3", t(16.64))}

      // ---------- логика Сереги: 1/6 + 1/6 = 1/3 — нет ----------
      enter("#st-logic", {t(19.08)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-logic", {t(20.40)}, {{ y: -30, rot: -10 }});
      enter("#p-ser", {t(20.30)}, {PANEL_IN});
{row("#s1", t(21.30))}
{row("#s2", t(23.18))}
{eq("#s2-eq", t(25.00))}
      enter("#st-ok", {t(25.56)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-ok", {t(26.40)}, {{ y: -30, rot: 10 }});
      tl.to("#s2-x", {{ scaleX: 1, duration: 0.18, ease: "power2.out" }}, {t(26.60)});
      slam("#st-no", {t(26.60)}, {{ fromScale: 2.2, rot: -6, blur: 10 }});
      leave("#st-no", {t(27.40)}, {{ scale: 0.6, y: 0, rot: -18 }});
      leave("#p-ser", {t(27.50)}, {{ y: 80 }});
      enter("#st-lost2", {t(27.60)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-lost2", {t(28.90)}, {{ y: -30, rot: -10 }});

      // ---------- маячок: «хотя бы один» и схема правила ----------
      enter("#p-beacon", {t(29.06)}, {{ fromScale: 0.85, dur: 0.25 }});
      tl.fromTo("#beacon-dot", {{ opacity: 1 }}, {{ opacity: 0.2, duration: 0.25, yoyo: true, repeat: 5, ease: "none" }}, {t(29.35)});
      leave("#p-beacon", {t(31.70)}, {{ y: -30 }});
      slam("#b-one", {t(31.98)}, {{ fromScale: 1.5 }});
      flash({t(31.98)});
      leave("#b-one", {t(33.30)}, {{ y: -60 }});
      enter("#p-rule", {t(33.40)}, {PANEL_IN});
      enter("#u1", {t(33.64)}, {{ fromScale: 0.6, dur: 0.25 }});
      draw("#ua1", {t(35.08)}, 0.25);
      enter("#u2", {t(35.30)}, {{ fromScale: 0.6, dur: 0.25 }});
      draw("#ua2", {t(38.74)}, 0.2);
      enter("#u3", {t(38.90)}, {{ fromScale: 0.6, dur: 0.25 }});
      leave("#p-rule", {t(39.80)}, {{ y: 80 }});

      // ---------- доска: 5/6 · 5/6 = 25/36 ----------
{bd_js}
      slam("#st-plus", {t(47.24)}, {{ fromScale: 2.0, rot: -5, blur: 10 }});
      leave("#st-plus", {t(48.50)}, {{ scale: 0.6, y: 0, rot: -14 }});

      // ---------- сетка 36 исходов: 25 без шестёрки, 11 — хотя бы одна ----------
      enter("#p-grid", {round(BD_END + 0.05, 2)}, {PANEL_IN});
      tl.fromTo("#p-grid .cell", {{ opacity: 0, scale: 0.3 }}, {{ opacity: 1, scale: 1, duration: 0.18, ease: "back.out(2)",
                stagger: 0.012 }}, {round(BD_END + 0.2, 2)});
      enter("#gn1", {round(BD_END + 0.4, 2)}, {{ fromScale: 0.8, dur: 0.25 }});
      tl.to("{SIXES}", {{ backgroundColor: "#F0352C", scale: 1.15, duration: 0.16, ease: "power2.out", stagger: 0.05 }}, {t(51.60)});
      tl.to("{SIXES}", {{ scale: 1, duration: 0.2, ease: "power2.out" }}, {t(52.40)});
      enter("#gn2", {t(52.20)}, {{ fromScale: 0.8, dur: 0.25 }});
{eq("#gf1", t(53.60))}
{eq("#gf2", t(55.86))}
      tl.fromTo("{SIXES}", {{ scale: 1 }}, {{ scale: 1.12, duration: 0.2, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(55.90)});
      leave("#p-grid", {t(57.30)}, {{ y: 80 }});

      // ---------- ≈ 0,31 ----------
      enter("#b-031-lead", {t(57.26)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-031", {t(57.90)}, {{ fromScale: 1.5 }});
      leave(["#b-031", "#b-031-lead"], {t(59.50)}, {{ y: -60 }});
      enter("#st-thought", {t(59.70)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-thought", {t(61.00)}, {{ y: -30, rot: -10 }});

      // ---------- история: игроки в кости за спиной, 1654, де Мере, Паскаль и Ферма ----------
{bg_in("#bg-dice", t(62.00), t(69.50))}
      enter("#b-1654-lead", {t(62.04)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-1654", {t(64.25)}, {{ fromScale: 1.3 }});
      tl.fromTo("#b-1654-n", {{ textContent: 1500 }}, {{ textContent: 1654, snap: {{ textContent: 1 }}, duration: 0.8, ease: "power2.out",
                immediateRender: false }}, {t(64.25)});
      leave(["#b-1654", "#b-1654-lead"], {t(66.50)}, {{ y: -60 }});
      enter("#st-mere", {t(67.20)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-mere", {t(70.30)}, {{ y: -30, rot: 10 }});
      card("#c-pas", {t(70.90)}, {t(73.40)}, "right");
      card("#c-fer", {t(72.30)}, {t(73.40)}, "left");
      enter("#letter", {t(72.50)}, {{ fromScale: 0.4, dur: 0.2 }});
      tl.to("#letter", {{ keyframes: [{{ x: -280, y: -90, rotation: -12, duration: 0.3, ease: "none" }},
                                     {{ x: -560, y: 0, rotation: -20, duration: 0.3, ease: "power2.out" }}] }}, {t(72.72)});
      leave("#letter", {t(73.36)}, {{ scale: 0.4, y: 0 }});
      slam("#st-sci", {t(73.75)}, {{ fromScale: 2.0, rot: 4, blur: 10 }});
      leave("#st-sci", {t(74.35)}, {{ scale: 0.6, y: 0, rot: 12 }});
      enter("#st-lud", {t(74.50)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-lud", {t(75.60)}, {{ y: -30, rot: -10 }});

      // ---------- кодовое слово «вероятность» и «завязывай» ----------
      enter("#st-razbor", {t(76.32)}, {{ fromScale: 0.6, rot: 3 }});
      leave("#st-razbor", {t(78.90)}, {{ y: -30, rot: 10 }});
{chr(10).join(s for s in keyword_beats(t(79.04), t(80.56), t(81.20), len("вероятность")).splitlines() if "#kw-label" not in s)}
      enter("#kw-top", {t(79.04)}, {{ fromScale: 0.85, dur: 0.25 }});
      leave("#kw-top", {t(82.20)}, {{ y: -30 }});
      slam("#st-stop", {t(82.38)}, {{ fromScale: 2.0, rot: -5, blur: 10 }});
      leave("#st-stop", {round(DUR - 0.3, 2)}, {{ scale: 0.6, y: 0, rot: -14 }});
'''

# Звуки — мало (бриф: few), по правилам 12.10: удары только на главном (НЕТ, 0,31, «завязывай»),
# семейства не подряд, каждый файл ≤ 2 раз, между звуками ≥ 1 с. Фоны и визуализации — без звука.
sounds = [
    audio("lost", "whoosh", t(3.28), 0.8),
    audio("no", "impact-bass-1", t(26.58), 0.9),
    audio("one", "whoosh-cinematic", t(31.96), 0.7),
    audio("plus", "click", t(47.22), 0.8),
    audio("p031", "impact-bass-2", t(57.88), 0.8),
    audio("y1654", "whoosh", t(64.23), 0.7),
    audio("pascal", "pop", t(70.88), 0.7),
    audio("type", "typing", t(80.54), 0.6, duration=0.6, fade_out=0.2),
    audio("stop", "impact-bass-1", t(82.36), 0.9),
]
# человек поверх фонов и слов за спиной: казино, вахта + ЗАРПЛАТУ, ХОТЯ БЫ ОДИН, 0,31, игроки + 1654
fg = [(t(1.00), t(4.85)), (t(5.60), t(9.70)), (t(31.90), t(33.60)), (t(57.20), t(59.80)), (t(61.90), t(70.00))]

page = build_page("Серега и хотя бы одна шестёрка", DUR, behind, front, beats, sounds, fg, cta_at=DUR,
                  extra_css=css, fmt=tk.fmt, captions=tk.captions, cta=False)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

fixes = tk.fixes({154: "0,31.", 155: "", 175: "шевалье", 176: "де Мере", 189: "Ферма,", 195: "лудоманам."})

director = {
    "_note": "Серега и вероятность. Время по дублю; раскладка — work/IMG_1812/page.py, план — plan.md.",
    "punches": [[t(3.30), t(4.20), 1.16, 0.10], [t(8.04), t(9.10), 1.20, 0.10], [t(26.60), t(27.40), 1.22, 0.10],
                [t(31.98), t(33.20), 1.22, 0.10], [t(57.90), t(59.30), 1.20, 0.10], [t(65.06), t(66.30), 1.16, 0.10],
                [t(82.38), round(DUR - 0.1, 2), 1.20, 0.05]],
    "text_fixes": fixes,
    # compose сравнивает слово без знаков препинания по краям
    "keep_case": ["ЕГЭ", "Серегу", "Серега", "Сереги", "Сергей", "Паскалю", "Паскаль", "Ферма", "Мере", "де Мере"],
    "accent_words": ["Нет", "противоположное", "0,31", "1654"],
    # плашки на груди стоят на уровне субтитров — на их время субтитров нет
    "hide_captions": [[t(11.10), t(19.20)], [t(20.25), t(27.80)], [t(33.35), t(40.10)], [t(42.25), t(57.60)],
                      [t(79.00), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
