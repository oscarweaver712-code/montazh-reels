"""Страница графики IMG_1803: что такое миллион — от итальянского milione до британского биллиона.

Время ударов — по исходнику, на шкалу дубля переводит Take.
Проверено: milione = mille («тысяча») + увеличительный суффикс -one — «большая тысяча».
Старый русский (малый) счёт: тьма = 10 000, легион = 100 000, леодр = 1 000 000.
Короткая шкала (Россия, США): миллиард = биллион = 10⁹ = тысяча миллионов. Старая британская
длинная шкала: биллион = миллион миллионов = 10¹², в 1000 раз больше. Официально Британия
перешла на короткую шкалу в 1974 году (заявление премьера Г. Вильсона в парламенте).

v6 (13.10.2026): плашка про миллион — двумя показами: уходит на «как у нас -ище», возвращается на
«мили плюс ван, миллион» с итогом; субтитры между показами снова видны (Валера: «очень долго висела,
теряли в динамике»). Вырезка — комната без «припаркованной» банки и второй взгляд у кистей (микрофон).
v5 (12.10.2026): карточки на груди — ниже подбородка в каждом кадре (лицо опускается до y≈1236,
когда Валера наклоняется к камере), заезд под ник Instagram — осознанный (data-safe): лицо важнее.
Вырезка — по пустой комнате из дубля (matte.py): банка и рука целые, без серой дымки по краю. Фоны
под кадр 1188×2112 (gen_image --refit) и без постоянного размытия: размытие только в наплыве.
v4 (12.10.2026): всё внутри серых зон площадок (formats.GREY_ZONES, по скринам Валеры) — слова над
головой ниже вкладок TikTok, таблицы и карточки на груди в полосе 245–835 и выше ника Instagram.
Фоны за спиной СГЕНЕРИРОВАНЫ (Codex, imagegen; downloads/bg_*.md) — не фото, иллюстрация эпохи:
контора итальянского купца XIV века (2,9–12,5 с) и русская палата XV века (20,4–37 с). Смена —
наплыв из размытия с медленным наездом, уход в настоящую студию; «бардак» впечатывается уже в студию.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card, doc_img  # noqa: E402

STEM = "IMG_1803"
tk = Take(STEM)
t = tk.t
DUR = tk.duration

css = '''      .flag { display: inline-block; width: 66px; height: 44px; margin-right: 18px; vertical-align: -4px; border-radius: 4px;
              background: linear-gradient(90deg, #1F9D55 0 33.3%, #F4F1EA 33.3% 66.6%, #D7322B 66.6%); }
      .it-row { display: flex; justify-content: center; align-items: flex-end; gap: 34px; }
      .it-col { text-align: center; opacity: 0; display: inline-block; }
      .it-w { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 92px; line-height: 1; color: var(--ink);
              font-variant-numeric: lining-nums; }
      .it-l { margin-top: 8px; font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.12em;
              text-transform: uppercase; color: #6A5A44; }
      .lad-row { display: flex; justify-content: space-between; align-items: baseline; padding: 10px 6px; opacity: 0;
                 border-bottom: 2px solid rgba(242,235,221,0.14); }
      .lad-row:last-child { border-bottom: none; }
      .lad-n { font-family: "JBMono"; font-weight: 700; font-size: 46px; color: var(--cream); white-space: nowrap; }
      .lad-w { font-family: "Oswald"; font-weight: 700; font-size: 54px; text-transform: uppercase; color: #F5B82E; }
      .cmp-row { display: flex; justify-content: space-between; align-items: center; padding: 8px 6px; opacity: 0;
                 border-bottom: 2px solid rgba(242,235,221,0.14); }
      .cmp-row:last-child { border-bottom: none; }
      .cmp-who { max-width: 190px; line-height: 1.15; font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.06em; text-transform: uppercase; color: rgba(242,235,221,0.75); }
      .cmp-w { font-family: "Oswald"; font-weight: 700; font-size: 46px; text-transform: uppercase; color: var(--cream); }
      .cmp-v { font-family: "Cormorant"; font-weight: 700; font-size: 60px; color: var(--cream); font-variant-numeric: lining-nums; }
      .panel { border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .bil { width: 285px; height: 236px; padding: 22px 12px; text-align: center; }
      .bil-h { font-family: "Manrope"; font-weight: 800; font-size: 19px; letter-spacing: 0.12em; text-transform: uppercase; color: #F5B82E; }
      .bil-v { margin-top: 14px; font-family: "Cormorant"; font-weight: 700; font-size: 84px; line-height: 1; color: var(--cream);
               font-variant-numeric: lining-nums; }
      .bil-s { margin-top: 10px; font-family: "Manrope"; font-weight: 800; font-size: 18px; color: rgba(242,235,221,0.6); }
      /* карточка mille + -one = milione: две строки в полосе 590 */
      #d-it .it-row, #d-it2 .it-row { flex-wrap: wrap; gap: 6px 34px; }
      #d-it .it-w, #d-it2 .it-w { font-size: 74px; }
      #it-c2 { flex-basis: 100%; }
      /* портрет Маска — уже, чтобы не наезжал на голову и не уходил под обрезку Instagram */
      #c-musk { left: 722px; top: 270px; width: 250px; padding: 12px 12px 10px; }
      #c-musk .ph, #c-musk img { width: 226px; height: 250px; }
      #c-musk .card-name { font-size: 20px; }
      #c-musk .card-sub { font-size: 22px; }
      /* фоны за спиной (сгенерированы Codex): полный кадр под вырезкой; чуть темнее и мягче студии,
         чтобы человек оставался главным, края кадра притемнены как у объектива */
      .bg { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; opacity: 0; }
      .bg img { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover;
                filter: brightness(0.72) saturate(0.9) contrast(1.05); }
      .bg .vig { position: absolute; left: 0; top: 0; width: 1080px; height: 1920px;
                 background: radial-gradient(ellipse at 50% 42%, rgba(0,0,0,0) 38%, rgba(0,0,0,0.55) 100%),
                             linear-gradient(to bottom, rgba(0,0,0,0) 72%, rgba(0,0,0,0.5) 100%); }
'''

PANEL = "left: 245px; width: 590px; padding: 16px 28px;"
behind = "\n".join([
    '        <div id="bg-it" class="bg"><img src="assets/img/bg_italy.png" alt="" /><div class="vig"></div></div>',
    '        <div id="bg-rus" class="bg"><img src="assets/img/bg_rus.png" alt="" /><div class="vig"></div></div>',
    '        <div id="b-mil" class="g big" style="top: 285px; font-size: 192px;">миллион</div>',
    '        <div id="b-ishe-lead" class="g lead" style="top: 272px; font-size: 30px; letter-spacing: 0.12em;">'
    '<span id="ish1" style="display: inline-block; opacity: 0;">дом-ище</span> · '
    '<span id="ish2" style="display: inline-block; opacity: 0;">кот-ище</span> · '
    '<span id="ish3" style="display: inline-block; opacity: 0;">пепел-ище</span></div>',
    '        <div id="b-ishe" class="g big" style="top: 318px; font-size: 250px;">-ище</div>',
    '        <div id="b-tys" class="g big red" style="top: 285px; font-size: 175px;">тысячище</div>',
    '        <div id="b-tma-lead" class="g lead" style="top: 272px; font-size: 40px;">10 000 =</div>',
    '        <div id="b-tma" class="g big" style="top: 318px; font-size: 260px;">тьма</div>',
    '        <div id="b-leo-lead" class="g lead" style="top: 272px;">хочу зарабатывать</div>',
    '        <div id="b-leo" class="g big red" style="top: 318px; font-size: 250px;">леодр</div>',
    '        <div id="b-x" class="g big red" style="top: 285px; font-size: 260px;">×1000</div>',
    '        <div id="b-1974-lead" class="g lead" style="top: 272px;">Британия сдалась только в</div>',
    '        <div id="b-1974" class="g big" style="top: 318px; font-size: 260px;">1974</div>',
])

italy = ('        <div id="d-it" class="g doc" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)" style="left: 245px; top: 1260px; width: 590px; padding: 20px 16px 16px;">\n'
         '          <div class="it-row">\n'
         '            <div id="it-a" class="it-col"><div class="it-w">mille</div><div class="it-l">тысяча</div></div>\n'
         '            <div id="it-b" class="it-col"><div class="it-w">+ -one</div><div class="it-l">большой</div></div>\n'
         '          </div>\n        </div>')
# Вторая карточка — на «мили плюс ван, миллион»: обе части уже стоят, итог выходит на «миллион».
# Первая уходит на «как у нас -ище» (там над головой «-ИЩЕ»): одна плашка висела 13 с, из них 8 без
# изменений — Валера 13.10: «очень долго висела, теряли в динамике».
italy2 = ('        <div id="d-it2" class="g doc" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)" style="left: 245px; top: 1260px; width: 590px; padding: 20px 16px 16px;">\n'
          '          <div class="it-row">\n'
          '            <div class="it-col" style="opacity: 1;"><div class="it-w">mille</div><div class="it-l">тысяча</div></div>\n'
          '            <div class="it-col" style="opacity: 1;"><div class="it-w">+ -one</div><div class="it-l">большой</div></div>\n'
          '            <div id="it-c2" class="it-col"><div class="it-w" style="color: var(--red);">= milione</div>'
          '<div class="it-l">большая тысяча</div></div>\n'
          '          </div>\n        </div>')
ladder = ('        <div id="d-lad" class="g panel" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)" style="' + PANEL + ' top: 1225px;">\n'
          '          <div id="l1" class="lad-row"><span class="lad-n">10 000</span><span class="lad-w">тьма</span></div>\n'
          '          <div id="l2" class="lad-row"><span class="lad-n">100 000</span><span class="lad-w">легион</span></div>\n'
          '          <div id="l3" class="lad-row"><span class="lad-n">1 000 000</span><span class="lad-w" style="color: var(--red);">леодр</span></div>\n'
          '        </div>')
compare = ('        <div id="d-cmp" class="g panel" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)" style="' + PANEL + ' top: 1240px;">\n'
           '          <div id="c1" class="cmp-row"><span class="cmp-who">у нас</span><span class="cmp-w">миллиард</span><span class="cmp-v">10<sup>9</sup></span></div>\n'
           '          <div id="c2" class="cmp-row"><span class="cmp-who">США</span><span class="cmp-w">биллион</span><span class="cmp-v">10<sup>9</sup></span></div>\n'
           '          <div id="c3" class="cmp-row"><span class="cmp-who">Британия до 1974</span><span class="cmp-w">биллион</span>'
           '<span class="cmp-v" style="color: var(--red);">10<sup>12</sup></span></div>\n'
           '        </div>')
bil = ('        <div id="bil1" class="g panel bil" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)" style="left: 245px; top: 1215px;">'
       '<div class="bil-h">биллионер до 1974</div><div class="bil-v">10<sup>12</sup> £</div><div class="bil-s">миллион миллионов</div></div>\n'
       '        <div id="bil2" class="g panel bil" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)" style="left: 550px; top: 1215px;">'
       '<div class="bil-h">биллионер сейчас</div><div class="bil-v">10<sup>9</sup> £</div><div class="bil-s">тысяча миллионов</div></div>')

# Счётчик просмотров за спиной: крупно, как остальные слова, человек из вырезки встаёт поверх.
# Свой, а не count-up каталога: тот в полосе над головой упирается в высоту (34cqh ≈ 60 px).
# Цифры сменяются через set — покадровый рендер видит то же, что и снимок.
VIEWS = [0, 4000, 23000, 87000, 210000, 390000, 580000, 740000, 860000, 940000, 985000, 1000000]
V_AT, V_STEP = t(65.28) - 0.15, 0.06
views_html = ('        <div id="b-views" class="g big" style="top: 318px; font-size: 205px;">'
              + "".join(f'<span id="v{k}" style="position: absolute; left: 0; width: 1080px; opacity: 0;">'
                        + f"{v:,}".replace(",", " ") + "</span>" for k, v in enumerate(VIEWS))
              + '<span style="visibility: hidden;">1 000 000</span></div>\n'
              '        <div id="b-views-lab" class="g lead" style="top: 272px; font-size: 40px; letter-spacing: 0.14em;">просмотров</div>')
behind += "\n" + views_html
views_js = "\n".join(
    [f'      tl.set("#v{k}", {{ opacity: 1 }}, {V_AT + k * V_STEP:.2f});' for k in range(len(VIEWS))]
    + [f'      tl.set("#v{k}", {{ opacity: 0 }}, {V_AT + (k + 1) * V_STEP:.2f});' for k in range(len(VIEWS) - 1)])

front = "\n".join([
    '        <div id="st-it" class="g sticker" style="left: 330px; top: 290px; font-size: 56px; white-space: nowrap;">'
    '<span class="flag"></span>для итальянцев</div>',
    italy,
    italy2,
    '        <div id="st-rus" class="g sticker" style="left: 310px; top: 290px; font-size: 56px; white-space: nowrap;">а на Руси?</div>',
    doc_img("d-cyr", "cyr_numerals.jpg", "старинный счёт: цифры-буквы", left=245, top=1180, width=590,
            height=230, position="50% 100%").replace('class="g doc"', 'class="g doc" data-safe="лицо важнее серой зоны: карточка ниже подбородка (Валера, 12.10)"', 1),
    ladder,
    '        <div id="st-spell" class="g sticker" style="left: 330px; top: 300px; font-size: 56px; white-space: nowrap;">как заклинание</div>',
    '        <div id="st-mess" class="g stamp" style="left: 360px; top: 290px; font-size: 90px; white-space: nowrap;">бардак</div>',
    compare,
    bil,
    card("c-musk", "musk.jpg", "Илон Маск", "а это — не я", side="right"),
])

beats = f'''
      // ---------- фоны за спиной: наплыв из размытия, медленный наезд, уход обратно в студию ----------
      function bgIn(sel, tIn, tOut) {{
        tl.fromTo(sel, {{ opacity: 0, filter: "blur(14px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.8, ease: "power2.out" }}, tIn);
        tl.fromTo(`${{sel}} img`, {{ scale: 1.08 }}, {{ scale: 1.0, duration: tOut - tIn + 0.6, ease: "none" }}, tIn);
        tl.to(sel, {{ opacity: 0, filter: "blur(10px)", duration: 0.6, ease: "power2.in" }}, tOut);
      }}
      bgIn("#bg-it", {t(2.90)}, {t(11.90)});
      bgIn("#bg-rus", {t(20.40)}, {t(36.45)});

      // ---------- хук: что такое миллион ----------
      slam("#b-mil", {t(1.20)}, {{ fromScale: 1.5 }});
      leave("#b-mil", {t(2.45)}, {{ y: -60 }});

      // ---------- Италия: mille + -one = milione ----------
      enter("#st-it", {t(2.86)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-it", {t(4.50)}, {{ y: -30, rot: -10 }});
      doc("#d-it", {t(4.70)}, {t(12.25)}, {{ rot: -1 }});
      enter("#it-a", {t(4.80)}, {{ fromScale: 1.4, dur: 0.18, blur: 6 }});
      enter("#it-b", {t(8.78)}, {{ fromScale: 1.4, dur: 0.18, blur: 6 }});
      tl.to("#it-b", {{ scale: 1.15, duration: 0.25, ease: "back.out(2)" }}, {t(10.02)});
      tl.to("#it-b", {{ scale: 1, duration: 0.3, ease: "power2.out" }}, {t(10.60)});
      // «то есть милли, уана» — обе части загораются, следом плашка уходит на «как у нас -ище»
      tl.to("#it-a .it-w", {{ color: "#F0352C", duration: 0.15 }}, {t(11.60)});
      tl.to("#it-b .it-w", {{ color: "#F0352C", duration: 0.15 }}, {t(11.98)});
      doc("#d-it2", {t(16.10)}, {t(17.80)}, {{ rot: 1, fromRot: -5 }});
      enter("#it-c2", {t(17.02)}, {{ fromScale: 1.4, dur: 0.18, blur: 6 }});

      // ---------- как у нас: -ище ----------
      enter("#b-ishe-lead", {t(13.10)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-ishe", {t(13.16)}, {{ fromScale: 1.5 }});
      enter("#ish1", {t(14.00)}, {{ fromScale: 1.3, dur: 0.15, blur: 6 }});
      enter("#ish2", {t(14.62)}, {{ fromScale: 1.3, dur: 0.15, blur: 6 }});
      enter("#ish3", {t(15.08)}, {{ fromScale: 1.3, dur: 0.15, blur: 6 }});
      leave(["#b-ishe", "#b-ishe-lead"], {t(15.75)}, {{ y: -60 }});
      slam("#b-tys", {t(18.48)}, {{ fromScale: 1.5 }});
      leave("#b-tys", {t(20.45)}, {{ y: -60 }});

      // ---------- на Руси: тьма, легион, леодр ----------
      enter("#st-rus", {t(20.62)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-rus", {t(22.30)}, {{ y: -30, rot: 10 }});
      doc("#d-cyr", {t(22.44)}, {t(25.40)}, {{ rot: 2, fromRot: -6 }});
      enter("#b-tma-lead", {t(24.02)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-tma", {t(25.68)}, {{ fromScale: 1.5 }});
      leave(["#b-tma", "#b-tma-lead"], {t(29.75)}, {{ y: -60 }});
      enter("#d-lad", {t(29.90)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#l1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(29.96)});
      tl.fromTo("#l2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(30.92)});
      tl.fromTo("#l3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(32.52)});
      leave("#d-lad", {t(34.10)}, {{ y: 80 }});
      enter("#st-spell", {t(33.50)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-spell", {t(34.30)}, {{ y: -30, rot: -10 }});
      enter("#b-leo-lead", {t(34.40)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-leo", {t(35.00)}, {{ fromScale: 1.6 }});
      flash({t(35.00)});
      leave(["#b-leo", "#b-leo-lead"], {t(36.30)}, {{ y: -60 }});

      // ---------- бардак: миллиард, биллион, британский биллион ----------
      slam("#st-mess", {t(37.22)}, {{ fromScale: 1.6, rot: -6 }});
      leave("#st-mess", {t(38.30)}, {{ y: -30, rot: -14 }});
      enter("#d-cmp", {t(38.04)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#c1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(39.06)});
      tl.fromTo("#c2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(40.66)});
      // «это то же самое число» — оба 10⁹ загораются одним цветом: число одно, названия разные
      tl.to(["#c1 .cmp-v", "#c2 .cmp-v"], {{ color: "#F5B82E", duration: 0.2 }}, {t(42.20)});
      tl.fromTo("#c3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(45.76)});
      leave("#d-cmp", {t(49.70)}, {{ y: 80 }});
      slam("#b-x", {t(48.64)}, {{ fromScale: 1.6 }});
      flash({t(48.64)});
      leave("#b-x", {t(49.85)}, {{ y: -60 }});
      enter("#b-1974-lead", {t(49.94)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-1974", {t(52.30)}, {{ fromScale: 1.5 }});
      leave(["#b-1974", "#b-1974-lead"], {t(53.80)}, {{ y: -60 }});

      // ---------- два разных человека ----------
      enter("#bil1", {t(54.46)}, {{ fromX: -200, fromScale: 0.9, rot: -2, dur: 0.4, ease: "power3.out" }});
      enter("#bil2", {t(59.70)}, {{ fromX: 200, fromScale: 0.9, rot: 2, dur: 0.4, ease: "power3.out" }});
      leave("#bil1", {t(61.50)}, {{ x: -200, y: 40 }});
      leave("#bil2", {t(61.50)}, {{ x: 200, y: 40 }});
      card("#c-musk", {t(61.70)}, {t(63.20)}, "right");

      // ---------- хотя бы один леодр просмотров ----------
      enter("#b-views", {V_AT:.2f}, {{ fromScale: 1.3, dur: 0.2 }});
      enter("#b-views-lab", {V_AT + 0.30:.2f}, {{ fromScale: 0.9, dur: 0.25 }});
{views_js}
      leave(["#b-views", "#b-views-lab"], {t(67.05)}, {{ y: -60 }});
'''
# Звуки — по правилам 12.10.2026 (Валера: громко, одинаковые подряд, «бардак» — без звука):
# громкость — доля нормы (kit.audio), файл не больше двух раз, одно семейство не подряд, удары —
# только на главном: МИЛЛИОН, ТЫСЯЧИЩЕ, ЛЕОДР, ×1000. На «бардак» звука нет. Щелчок плашки — pop.
sounds = [
    audio("mil", "impact-bass-1", t(1.18), 1.0),
    audio("itdoc", "whoosh", t(4.68), 0.8),
    audio("ishe", "click", t(13.14), 0.9),
    audio("tys", "impact-bass-2", t(18.46), 0.9),
    audio("rus", "ping", t(20.60), 0.7),
    audio("cyr", "whoosh", t(22.42), 0.8),
    audio("tma", "click", t(25.66), 0.9),
    audio("spell", "sparkle", t(33.48), 0.7),
    audio("leo", "impact-bass-1", t(34.98), 1.0),
    audio("cmp", "notification", t(38.02), 0.6),
    audio("x", "impact-bass-2", t(48.62), 1.0),
    audio("y1974", "ping", t(52.28), 0.8),
    audio("bil", "chime", t(54.44), 0.7),
    audio("musk", "pop", t(61.68), 0.9),
    audio("views", "sparkle", V_AT, 0.8),
]
# человек поверх фонов на всё их время (с наплывами) и поверх слов за спиной
fg = [(t(1.10), t(12.60)), (t(13.00), t(16.10)), (t(18.40), t(37.15)), (t(48.55), t(54.15)),
      (V_AT - 0.1, t(67.40))]
page = build_page("Что такое миллион", DUR, behind, front, beats, sounds, fg, cta_at=t(67.30),
                  extra_css=css, cta_small="переходи ко мне в профиль", fmt=tk.fmt, captions=tk.captions)
page = page.replace('<div class="cta-big">Больше математики</div>', '<div class="cta-big">80+ на ЕГЭ</div>', 1)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# «1974» перед «года» ушло вместе со сбивкой «до 17…» (вырез 56.39–57.17): цифру несёт «года.»
# Итальянское — как произносит Валера («милли», «уана», «ван»); латиница только на карточке #d-it
fixes = tk.fixes({39: "-ище,", 45: "милли", 170: "леодр,", 180: "80+", 181: ""})
goda = next(k for k, w in enumerate(tk.words) if w["word"] == "года." and w["start"] > t(55.9) - 0.3)
fixes[str(goda)] = "1974 года."

director = {
    "_note": "Миллион, леодр, биллион. Время по дублю; раскладка — work/IMG_1803/page.py.",
    "punches": [[t(1.20), t(2.30), 1.22, 0.10], [t(18.48), t(19.60), 1.20, 0.10],
                [t(35.00), t(36.10), 1.22, 0.10], [t(48.64), t(49.60), 1.20, 0.10],
                [t(52.30), t(53.40), 1.18, 0.10], [t(57.17), t(58.20), 1.16, 0.0, 0.6],
                [t(65.56), t(66.70), 1.20, 0.10]],
    "text_fixes": fixes,
    "keep_case": ["Руси", "США", "Британия", "Илон", "Маск", "ЕГЭ"],
    "accent_words": ["тьма", "легион", "леодр", "миллиард", "биллион"],
    # таблички «тьма/легион/леодр» и «миллиард/биллион» повторяют речь — на их время субтитров нет,
    # иначе красное акцентное слово ложится на верх таблички (v2)
    # v4: карточки на груди стоят на уровне субтитров (1045–1370, выше ника Instagram) — на их время
    # субтитры спрятаны: «mille + -one», цифры-буквы, лестница, сравнение, биллионеры
    "hide_captions": [[t(1.15), t(2.40)], [t(4.65), t(12.25)], [t(16.05), t(19.60)], [t(22.40), t(26.40)],
                      [t(29.85), t(34.40)], [t(34.95), t(36.20)], [t(38.00), t(49.95)], [t(52.25), t(53.40)],
                      [t(54.40), t(61.60)], [t(65.20), t(66.10)], [t(67.25), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
