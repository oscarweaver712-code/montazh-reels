"""IMG_0930 — рилс Виктории @target_vikatopol (тестовое от Славы, 22.10.2026), страница через montage.Montage.

Мысль: «Салону нужен не просто клиент, а тот, кто вернётся. Поэтому я не настраиваю просто таргет — я как маркетолог
строю путь клиента до повторных продаж. Доказательство — кейс из поста: 604 заявки → 304 клиента → $14 за клиента».
Визуальная идея — «Клиент, который вернётся»: путь заявка → покупка → повтор замыкается петлёй, и ролик сам
возвращается к хуку цифрами кейса. Шрифты и цвета — DESIGN.md проекта («Подпись и шапка»): пара «рукопись Nicoletta
крем-жёлтым + строка SF Pro капсом белым», кирпич из её поста — на цифрах и квадратах пути, шапка весь ролик.

Время — шкала дубля (aroll.words.json, 61,33 с): затупы и повторы вырезаны в edit.json, склейки на 10.53, 18.27,
33.37, 53.97 — надписи уходят до них.
Факты сверены: 304 / 604 = 50,3 % — то же число на слайде её поста (IMG_0960.PNG); LTV — lifetime value, сколько
клиент приносит за всё время; «5-летний опыт», «рынок США» — из шапки, которую дала заказчица.
Кадр: волосы у верхнего края, подбородок до y 1190, субтитры на y 1240 — графика на груди, шапка сверху на тени.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import design  # noqa: E402
from montage import Montage  # noqa: E402

STEM = "IMG_0930"
m = Montage(STEM)
L = design.letters
SHADOW = "0 2px 6px rgba(0,0,0,0.55), 0 6px 26px rgba(0,0,0,0.45)"
LOW = 'data-safe="на груди под субтитрами: над головой места нет (волосы у края кадра)" data-safe-zones="низ"'

m.css(f"""
      .pair-h {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; font-family: "Nicoletta script";
                 font-weight: 400; line-height: 1; color: var(--ds-hand); text-shadow: {SHADOW}; }}
      .pair-c {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; font-family: "SF Pro Display";
                 font-weight: 700; text-transform: uppercase; letter-spacing: 0.02em; line-height: 1; color: #FFFFFF;
                 text-shadow: {SHADOW}; }}
      .pair-c .brick {{ color: var(--ds-acc); text-shadow: none; filter: drop-shadow(0 3px 10px rgba(0,0,0,0.5));
                        background-image: var(--ds-grad); -webkit-background-clip: text; background-clip: text;
                        -webkit-text-fill-color: transparent; }}
      .hdr {{ font-family: "SF Pro Display"; color: #FFFFFF; text-shadow: 0 1px 4px rgba(0,0,0,0.6), 0 4px 18px rgba(0,0,0,0.45); }}
      #hdr-shade {{ left: 0; top: 0; width: 1080px; height: 520px;
                    background: linear-gradient(180deg, rgba(0,0,0,0.42) 0%, rgba(0,0,0,0.22) 45%, rgba(0,0,0,0) 100%); }}
      #low-shade {{ left: 0; top: 1060px; width: 1080px; height: 860px;
                    background: linear-gradient(0deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.38) 45%, rgba(0,0,0,0) 100%); }}
      .chain {{ left: 0; width: 1080px; display: flex; justify-content: center; align-items: center; gap: 18px; }}
      .chip {{ position: relative; padding: 14px 30px 16px; border-radius: 44px; font-family: "SF Pro Display"; font-weight: 600;
               font-size: 46px; color: #FFFFFF; background: rgba(26,21,18,0.6); border: 2px solid rgba(255,255,255,0.35);
               overflow: hidden; isolation: isolate; text-shadow: 0 2px 8px rgba(0,0,0,0.4); }}
      .chip i {{ position: absolute; inset: 0; z-index: -1; background: var(--ds-grad); opacity: 0; }}
      .arr {{ font-family: "SF Pro Display"; font-weight: 300; font-size: 52px; color: #FFFFFF; text-shadow: {SHADOW}; }}
      #st-tg path {{ vector-effect: non-scaling-stroke; stroke-width: 9; }}
      #loop path {{ fill: none; stroke: #FFFFFF; stroke-width: 7; stroke-linecap: round; }}
      #post {{ left: 210px; top: 262px; width: 660px; height: 910px; overflow: hidden; border-radius: 30px; background: #FFFFFF;
               box-shadow: 0 30px 90px rgba(0,0,0,0.6); }}
      #post img {{ display: block; width: 660px; }}
      #post-dim {{ left: 0; top: 0; width: 1080px; height: 1920px; background: rgba(26,21,18,0.9); }}
      .num-w {{ left: 0; width: 1080px; text-align: center; white-space: nowrap; filter: drop-shadow(0 4px 14px rgba(0,0,0,0.55)); }}
      .num-w::before {{ content: ""; position: absolute; left: 50%; top: 52%; width: 820px; height: 330px; transform: translate(-50%, -50%); z-index: -1;
                        background: radial-gradient(closest-side, rgba(0,0,0,0.5), rgba(0,0,0,0)); }}
      .num-w {{ isolation: isolate; }}
      .num-cap {{ display: block; font-family: "SF Pro Display"; font-weight: 300; font-size: 44px; line-height: 1.15;
                  color: #FFFFFF; text-shadow: {SHADOW}; }}
      .num {{ display: inline-block; font-family: "SF Pro Display"; font-weight: 700; font-size: 150px; line-height: 1;
              background-image: var(--ds-grad); -webkit-background-clip: text; background-clip: text;
              -webkit-text-fill-color: transparent; color: transparent; }}
""")

# шапка весь ролик (ТЗ: «можно ещё в риллсы добавить вот такую шапку»), тень сверху и снизу — белая стена и рубашка
HOLD = 'data-hold="шапка заказчицы — весь ролик по ТЗ" data-splice="шапка заказчицы стоит через склейки — по ТЗ весь ролик" data-header="шапка"'
m.behind(f'        <div id="low-shade" class="g" {HOLD} data-safe="тень под субтитрами и графикой на светлой рубашке"></div>')
m.behind(f'        <div id="hdr-shade" class="g" {HOLD} data-safe="тень под шапкой на волосах и белой стене"></div>\n'
        f'        <div id="hdr-nick" class="g hdr" {HOLD} data-safe="шапка над волосами" '
        f'style="left: 56px; top: 238px; font-weight: 500; font-size: 40px;">@target_vikatopol</div>\n'
        f'        <div id="hdr-role" class="g hdr" {HOLD} data-safe="шапка над волосами" '
        f'style="left: 520px; width: 504px; top: 232px; text-align: right; font-weight: 300; font-size: 36px; '
        f'line-height: 1.18;">Маркетолог на рынке США<br>с 5-летним опытом</div>')
m.js('      tl.fromTo(["#hdr-shade", "#low-shade"], { opacity: 0 }, { opacity: 1, duration: 0.4, ease: "power1.out" }, 0.05);\n'
     '      enter(["#hdr-nick", "#hdr-role"], 0.25, { fromY: -24, fromScale: 1, blur: 8, dur: 0.45 });\n'
     '      leave(["#hdr-nick", "#hdr-role", "#hdr-shade", "#low-shade"], 61.1, { y: -10, scale: 1, dur: 0.2 });')


def pair(pid: str, hand: str, caps: str, top: int, t_hand: float, t_caps: float, t_out: float, size: int = 186,
         caps_size: int = 74):
    """Пара «рукопись + строка»: слово Nicoletta по буквам, под ним внахлёст строка SF Pro капсом из размытия."""
    m.front(f'        <div id="{pid}-h" class="g pair-h" {LOW} style="top: {top}px; font-size: {size}px;">{L(hand)}</div>\n'
            f'        <div id="{pid}-c" class="g pair-c" {LOW} style="top: {top + int(size * 0.74)}px; '
            f'font-size: {caps_size}px;">{caps}</div>')
    m.js(f'      dsHand("#{pid}-h", {t_hand:.2f}, {{ stagger: 0.035 }});\n'
         f'      enter("#{pid}-c", {t_caps:.2f}, {{ fromY: 36, fromScale: 1, blur: 14, dur: 0.4 }});\n'
         f'      leave(["#{pid}-h", "#{pid}-c"], {t_out:.2f}, {{ y: 30, dur: 0.22 }});')


# 1. хук 0–3 с — картинкой, до слов: салону нужен не просто клиент, а тот, кто вернётся (её мысль 5,8–9,9 с)
pair("hk", "Клиент,", "который вернётся", 1322, 0.15, 0.85, 3.55, size=176, caps_size=68)
m.punch(0.85, 2.4)

# 2. «просто на настройку таргетированной рекламы» → на «бесполезная» ручка зачёркивает «просто таргет»
m.front(f'        <div id="st-tg" class="g ds-strike-w" {LOW} style="top: 1392px; font-size: 66px; font-family: \'SF Pro Display\'; '
        f'font-weight: 700; text-transform: uppercase;"><span class="ds-in">просто таргет'
        f'<svg class="ds-strike" viewBox="0 0 100 20" preserveAspectRatio="none">'
        f'<path pathLength="1" d="M 1 13 L 99 8" /></svg></span></div>')
m.js('      enter("#st-tg", 14.43, { fromY: 30, fromScale: 1, blur: 14, dur: 0.35 });\n'
     '      dsPen("#st-tg path", 16.91, 0.3);\n'
     '      leave("#st-tg", 17.95, { y: 30, dur: 0.2 });')
m.hide(14.4, 15.9)
m.punch(16.91, 17.7)

# 3. «Я беру бьюти-проекты уже как маркетолог» — ответ на хук той же парой
pair("mk", "Беру", "как маркетолог", 1236, 20.71, 21.01, 22.05)
m.hide(20.6, 22.05)

# 4. путь клиента: заявка → покупка → повтор, квадраты-чипы загораются по речи, на «цикл жизни» — петля назад
m.front(f'        <div id="chain" class="g chain" {LOW} style="top: 1338px;">'
        '<div class="chip" id="ch1"><i></i>заявка</div><div class="arr">→</div>'
        '<div class="chip" id="ch2"><i></i>покупка</div><div class="arr">→</div>'
        '<div class="chip" id="ch3"><i></i>повтор</div></div>\n'
        f'        <svg id="loop" class="g" {LOW} viewBox="0 0 800 130" style="left: 140px; top: 1428px; width: 800px; height: 130px;">'
        '<path id="loop-p" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" '
        'd="M 690 6 C 690 118, 110 118, 110 10" />'
        '<path id="loop-h" d="M 110 8 L 88 40 M 110 8 L 134 38" style="opacity: 0;" /></svg>')
m.js('      enter("#chain", 22.13, { fromY: 30, fromScale: 1, blur: 12, dur: 0.4 });\n'
     '      tl.fromTo("#ch1 i", { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power2.out", immediateRender: false }, 25.37);\n'
     '      tl.fromTo("#ch2 i", { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power2.out", immediateRender: false }, 25.95);\n'
     '      tl.fromTo("#ch3 i", { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "power2.out", immediateRender: false }, 26.63);\n'
     '      tl.set("#loop", { opacity: 1 }, 28.4);\n'
     '      draw("#loop-p", 28.47, 0.6);\n'
     '      tl.to("#loop-h", { opacity: 1, duration: 0.1 }, 29.05);\n'
     '      tl.to("#ch1, #ch2, #ch3", { scale: 1.07, duration: 0.25, yoyo: true, repeat: 1, ease: "sine.inOut" }, 29.1);\n'
     '      leave(["#chain", "#loop"], 31.05, { y: 30, dur: 0.22 });')
m.hide(25.0, 27.0)

# 5. «с высоким LTV» — кирпичное LTV с расшифровкой для владельца салона
m.front(f'        <div id="ltv" class="g num-w" {LOW} style="top: 1236px;">'
        '<span class="num-cap">доход с клиента за всё время</span><span class="num">LTV</span></div>')
m.js('      slam("#ltv", 31.33, { fromScale: 1.35, dur: 0.2 });\n'
     '      leave("#ltv", 33.12, { y: 30, dur: 0.2 });')
m.hide(31.3, 33.3)
m.punch(32.83, 33.2)

# 6. «Вот в этом посте рассказала» — её пост карточкой (скрин заказчицы, materials/post-keis.png), фон гаснет
m.behind('        <div id="post-dim" class="g footage" data-safe="подложка перебивки с постом"></div>')
m.front('        <div id="post" class="g" data-safe="её пост поверх лица на 3,6 с — доказательство, о котором она говорит">'
        '<img src="assets/img/post-keis.png" alt="" /></div>')
m.js('      tl.fromTo("#post-dim", { opacity: 0 }, { opacity: 1, duration: 0.3, ease: "power1.out", immediateRender: false }, 33.40);\n'
     '      tl.fromTo("#post", { opacity: 0, y: 380, rotation: 5, scale: 0.9, filter: BLUR(14) }, '
     '{ opacity: 1, y: 0, rotation: -1.5, scale: 1, filter: BLUR(0), duration: 0.45, ease: "expo.out", immediateRender: false }, 33.40);\n'
     '      tl.fromTo("#post img", { y: 0 }, { y: -40, duration: 3.4, ease: "none", immediateRender: false }, 33.65);\n'
     '      tl.to("#post", { opacity: 0, y: -260, scale: 0.86, rotation: -5, filter: BLUR(12), duration: 0.32, ease: "power2.in" }, 37.15);\n'
     '      tl.to("#post-dim", { opacity: 0, duration: 0.3, ease: "power1.in" }, 37.15);')

# 7. цифры кейса: 604 заявки → 304 стали клиентами → 50,3 % (число со слайда её поста)
NUMS = [("n604", "604", "заявки за лето", 37.63, 39.52), ("n304", "304", "новых покупателей", 39.59, 42.52),
        ("n503", "50,3 %", "конверсия заявки в покупку", 42.61, 46.75)]
for nid, num, cap, a, b in NUMS:
    m.front(f'        <div id="{nid}" class="g num-w" {LOW} style="top: 1384px;">'
            f'<span class="num-cap">{cap}</span><span class="num">{num}</span></div>')
    m.js(f'      slam("#{nid}", {a:.2f}, {{ fromScale: 1.35, dur: 0.2 }});\n'
         f'      leave("#{nid}", {b:.2f}, {{ y: -30, dur: 0.18 }});')
m.hide(37.60, 39.10)
m.hide(39.52, 40.35)
m.punch(37.63, 38.50)
m.punch(39.59, 40.40)

# 8. «И, внимание, стоимость этого клиента всего 14 долларов. Для Калифорнии это классный результат» — кульминация
m.punch(47.75, 48.60)
m.wide(48.60, 50.20)
pair("usd", "Всего", '<span class="brick">$14</span> за клиента', 1350, 50.11, 50.55, 53.65, caps_size=84)
m.hide(50.10, 51.75)
m.wide(52.30, 53.97)
# камера к концу кейса уже на 1.227 (медленный наезд стиля) — склейке к призыву нужен удар крупнее обычного
m.punch(53.97, 54.87, level=1.34, ease_in=0.0, ease_out=0.6)
m.punch(50.55, 51.60)

# 9. призыв её голосом: «…чтобы ваш маркетинговый бюджет окупался, жду вас в Директ»
pair("dm", "Жду вас", "в Директ", 1236, 59.80, 60.48, 61.10)
m.hide(59.75, 61.33)

m.build("IMG_0930 — Виктория: клиент, который вернётся", cta_at=None, cutout=False,
        text_fixes={47: "Я беру", 74: "Вот в", 94: "которые"},
        keep_case=["Калифорнии", "Директ.", "LTV."],
        accent_words=["повторную", "внимание,", "окупался,", "маркетолог,"])
