"""Страница графики IMG_6668 — тестовое для заказчицы: 11 с на английском в эстетике её референса.

Референс (instagram.com/reel/DZhDnJ6BIlT, разбор — downloads/ref/): капсы с засечками цвета
шампанского под изумрудно-золотым орнаментом, подписи смысловыми фразами, вставки — буквально по
фразе, тёплые и живые, музыка под голос, без звуковых эффектов. Нашей финальной плашки нет.

Фрагмент — 0:00–0:11.8 исходника: «I always thought that I have to do it alone and I have to be fierce
and I have to be strong. But really I can rely on my womb that is connected to the earth». Мысль: старая
установка «тащи всё одна, будь жёсткой и сильной» → опора в собственном теле и в земле.

v5 (13.10, Валера про v4: «звук звоночка не к месту, видео горизонтальные, а у нас вертикальное, крипово
и ИИшно»): никаких звуковых эффектов и свечений; вставки — полноэкранная вертикаль, склейки встык;
один тёплый плёночный цвет и зерно на весь кадр; музыка Mixkit «A New Life» раскрывается на «But really».
  alone  — одна идёт по пустой дороге (Coverr 6256);
  fierce — бежит по той же дороге (Coverr 8310): одна история, не набор стока;
  strong, But really, womb — героиня: её «strong» и руки на животе сильнее любой картинки;
  earth  — босые ноги на траве (Coverr 5234).
v6 (13.10, пожелание заказчицы: «необычные визуальные вставки вокруг человека, золотые и природные
элементы, симметрия, декоративные детали, атмосферность — и связь со смыслом»): за героиней —
симметричные фоны (вырезка поверх, низ кадра — родной: стул и юбка настоящие).
  установка «fierce, strong» (и хук) — две золотые львицы-стражи, шипы, изумруд: броня сильной женщины;
  «But really» — броня растворяется, героиня в живом саду;
  «my womb… connected to the earth» — золотые корни в живой земле.
Оба фона СГЕНЕРИРОВАНЫ (Codex, downloads/bg_lioness.md, bg_earth.md) — иллюстрация, не фото.
Бег и босые ноги из v5 убраны: их места заняли фоны вокруг героини.
Вставки, музыку и зерно готовит broll_prep.py; лицензии — broll/*.md, assets/music/bed.md.
Whisper слышит «wound»; по смыслу всей записи — «womb» («grow from their wombs, from their roots»).
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, build_page  # noqa: E402

STEM = "IMG_6668"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
END = round(DUR, 2)

GOLD, CHAMP, EMERALD = "#C9A45C", "#EBDDB8", "#2E8B57"
# один тёплый плёночный цвет на героиню и вставки: чуть теплее, тише насыщенность, мягче контраст
FILM = "sepia(0.16) saturate(0.84) contrast(0.95) brightness(1.03)"

css = f'''      /* подписи как в референсе: смысловая фраза капсами с засечками под орнаментом, без подсветки слов */
      .mc {{ left: 130px; width: 820px; top: 352px; text-align: center; font-family: "Cormorant"; font-weight: 600;
            font-size: 46px; letter-spacing: 0.07em; line-height: 1.2; text-transform: uppercase; color: {CHAMP};
            text-shadow: 0 2px 6px rgba(0,0,0,0.55), 0 0 26px rgba(0,0,0,0.35); }}
      #orn {{ left: 190px; top: 288px; width: 700px; height: 48px; }}
      #shade {{ left: 0; top: 0; width: 1080px; height: 1000px;
               background: linear-gradient(to bottom, rgba(10,12,8,0.55) 0%, rgba(10,12,8,0.32) 38%, rgba(10,12,8,0) 100%); }}
      #cam-fg {{ opacity: 1; }}   /* героиня поверх тени с первого кадра */
      .cam video, .ins video {{ filter: {FILM}; }}
      /* вставка — полноэкранная вертикаль, склейка встык */
      .ins {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden; }}
      .ins video {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1920px; object-fit: cover; }}
      /* фоны за героиней: верх кадра — иллюстрация, к низу переход в родной кадр (стул, юбка) */
      .bg {{ left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
            -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 60%, transparent 76%);
            mask-image: linear-gradient(to bottom, #000 0%, #000 60%, transparent 76%); }}
      .bg img {{ position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; filter: {FILM}; }}
      /* низ и края кадра в тень: стык иллюстрации с родным садом уходит, героиня (вырезка) — поверх */
      #vig {{ left: 0; top: 0; width: 1080px; height: 1920px;
             background: radial-gradient(ellipse 75% 60% at 50% 46%, rgba(6,8,5,0) 55%, rgba(6,8,5,0.55) 100%),
                         linear-gradient(to bottom, rgba(6,8,5,0) 52%, rgba(6,8,5,0.6) 74%, rgba(6,8,5,0.35) 100%); }}
      /* плёночное зерно поверх всего кадра; не графика (.g) — проверка лица его не считает */
      #grain {{ position: absolute; left: -256px; top: -256px; width: 1592px; height: 2432px; opacity: 0.075;
               background: url("assets/img/grain.png"); mix-blend-mode: overlay; pointer-events: none; }}
'''

# орнамент: две тонкие золотые линии от центра с полумесяцами на концах, изумрудная «змейка»
# поверх и камень посередине — как разделитель над подписью в референсе
WAVE = " ".join(f"{'M' if k == 0 else 'L'} {x} {24 + 5 * (1 if (x // 18) % 2 else -1) * (1 if x % 18 > 4 else 0.3):.1f}"
                for k, x in enumerate(range(0, 271, 6)))
orn = f'''        <svg id="orn" class="g" data-hold="орнамент-рамка подписей держится весь ролик — так в референсе" viewBox="0 0 700 48">
          <g id="orn-l"><path d="M 330 24 L 40 24" stroke="{GOLD}" stroke-width="2" fill="none" />
            <path d="M 52 24 A 9 9 0 1 1 34 18" stroke="{GOLD}" stroke-width="2" fill="none" />
            <path transform="translate(60 0)" d="{WAVE}" stroke="{EMERALD}" stroke-width="2.6" fill="none" /></g>
          <g id="orn-r"><g transform="translate(700 0) scale(-1 1)"><path d="M 330 24 L 40 24" stroke="{GOLD}" stroke-width="2" fill="none" />
            <path d="M 52 24 A 9 9 0 1 1 34 18" stroke="{GOLD}" stroke-width="2" fill="none" />
            <path transform="translate(60 0)" d="{WAVE}" stroke="{EMERALD}" stroke-width="2.6" fill="none" /></g></g>
          <g id="orn-gem"><path d="M 350 8 L 364 24 L 350 40 L 336 24 Z" fill="#1F6E46" stroke="{GOLD}" stroke-width="2.4" />
            <path d="M 350 14 L 357 24 L 350 34 L 343 24 Z" fill="#5FD08F" opacity="0.55" />
            <circle cx="318" cy="24" r="3" fill="{GOLD}" /><circle cx="382" cy="24" r="3" fill="{GOLD}" /></g>
        </svg>'''


# Подписи — смысловыми фразами, как в референсе («Я как будто всю жизнь / жила для кого-то»), а не
# по четыре слова подряд: автоматическая нарезка давала «HAVE TO DO IT» и «I HAVE TO BE».
# (номер первого слова фразы в исходнике, текст); фраза висит до начала следующей
PHRASES = [(0, "I always thought"), (3, "that I have to do it alone"), (10, "and I have to be fierce"),
           (16, "and I have to be strong"), (22, "But really"), (24, "I can rely on my womb"),
           (30, "that is connected"), (33, "to the earth")]
starts = [0.0] + [t(tk.src_words[i]["start"]) for i, _ in PHRASES[1:]]
CAPS = [(f"mc{k}", text, a, starts[k + 1] if k + 1 < len(starts) else END) for k, ((_, text), a) in enumerate(zip(PHRASES, starts))]
caps_html = "\n".join(f'        <div id="{cid}" class="g mc">{text}</div>' for cid, text, _, _ in CAPS)
caps_js = "\n".join(
    f'      tl.fromTo("#{cid}", {{ opacity: 0, y: 14, filter: BLUR(8) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.22, ease: "power2.out" }}, {a:.2f});'
    + f'\n      tl.to("#{cid}", {{ opacity: 0, y: -12, filter: BLUR(8), duration: 0.12, ease: "power1.in" }}, {(b if b < END else END - 0.18) - 0.12:.2f});'
    for cid, _, a, b in CAPS)



# Вставки: (имя, начало, конец) по словам исходника
W = tk.src_words
T_ALONE, T_FIERCE_IN, T_STRONG_IN, T_BUT = t(W[3]["start"]), t(W[10]["start"]), t(W[16]["start"]), t(W[22]["start"])
T_WOMB = t(W[29]["start"])             # «womb»
INSERTS = [("alone", T_ALONE, T_FIERCE_IN)]


def insert(name: str, a: float, b: float, track: int) -> str:
    return (f'        <div id="i-{name}" class="g ins"><video id="v-{name}" class="clip" src="assets/broll/{name}.mp4" '
            f'muted playsinline data-start="{a:.2f}" data-duration="{b - a:.2f}" data-track-index="{track}"></video></div>')


# Вставки — смена кадра, а не плашка поверх лица: они в слое за спиной (#behind), вырезка героини на их
# время выключена (fg-окна). Тень сверху — над вставками: подпись на светлом небе дороги читается.
behind = "\n".join([
    '        <div id="bg-armor" class="g bg"><img src="assets/img/bg_lioness.png" alt="" /></div>',
    '        <div id="bg-earth" class="g bg"><img src="assets/img/bg_earth.png" alt="" /></div>',
    '        <div id="vig" class="g" data-hold="виньетка под героиней держится весь ролик — стык фона с садом и кино-свет"></div>',
] + [insert(n, a, b, 2 + k) for k, (n, a, b) in enumerate(INSERTS)] + [
    '        <div id="shade" class="g" data-hold="тень сверху под подписями держится весь ролик — читаемость на светлом небе"></div>'])
front = "\n".join([orn, caps_html, '        <div id="grain"></div>'])

ins_js = []
for k, (n, a, b) in enumerate(INSERTS):
    # склейка встык; внутри кадра — медленный наезд, чтобы план жил
    ins_js.append(f'      tl.set("#i-{n}", {{ opacity: 1 }}, {a:.2f});')
    ins_js.append(f'      tl.fromTo("#v-{n}", {{ scale: 1.0 }}, {{ scale: 1.06, duration: {b - a:.2f}, ease: "none" }}, {a:.2f});')
    if b < END:
        ins_js.append(f'      tl.set("#i-{n}", {{ opacity: 0 }}, {b:.2f});')
ins_js = "\n".join(ins_js)

# зерно: тайл сдвигается 12 раз в секунду — как плёнка, а не грязь на экране
rnd = random.Random(6668)
grain_js = "\n".join(f'      tl.set("#grain", {{ x: {rnd.randint(0, 255)}, y: {rnd.randint(0, 255)} }}, {k / 12:.3f});'
                      for k in range(int(END * 12) + 1))

beats = f'''
      // ---------- рамка: тень сверху и орнамент раскрываются от камня к краям ----------
      tl.fromTo(["#shade", "#vig"], {{ opacity: 0 }}, {{ opacity: 1, duration: 0.5, ease: "power1.out" }}, 0);
      tl.set("#orn", {{ opacity: 1 }}, 0.05);
      tl.fromTo("#orn-gem", {{ opacity: 0, scale: 0.2, rotation: -90, transformOrigin: "350px 24px" }},
                {{ opacity: 1, scale: 1, rotation: 0, duration: 0.45, ease: "back.out(2)" }}, 0.05);
      tl.fromTo(["#orn-l", "#orn-r"], {{ opacity: 0, scaleX: 0, transformOrigin: "350px 24px" }},
                {{ opacity: 1, scaleX: 1, duration: 0.7, ease: "power3.out" }}, 0.2);

      // ---------- подписи фразами ----------
{caps_js}

      // ---------- броня «сильной женщины»: львицы-стражи с первого кадра до «But really» ----------
      tl.fromTo("#bg-armor", {{ opacity: 0, filter: "blur(18px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.5, ease: "power2.out" }}, 0);
      tl.fromTo("#bg-armor img", {{ scale: 1.0 }}, {{ scale: 1.08, duration: {T_BUT + 0.7:.2f}, ease: "none" }}, 0);
      // «But really» — броня растворяется, остаётся живой сад
      tl.to("#bg-armor", {{ opacity: 0, filter: "blur(16px)", duration: 0.7, ease: "power2.in" }}, {T_BUT:.2f});

      // ---------- «my womb… connected to the earth»: за ней прорастают золотые корни ----------
      tl.fromTo("#bg-earth", {{ opacity: 0, filter: "blur(16px)" }}, {{ opacity: 1, filter: "blur(0px)", duration: 0.9, ease: "power2.out" }}, {T_WOMB:.2f});
      tl.fromTo("#bg-earth img", {{ scale: 1.0 }}, {{ scale: 1.07, duration: {END - T_WOMB:.2f}, ease: "none" }}, {T_WOMB:.2f});

      // ---------- перебивка: alone ----------
{ins_js}

      // ---------- финал: орнамент сходится в камень ----------
      tl.to(["#orn-l", "#orn-r"], {{ scaleX: 0, opacity: 0, duration: 0.24, ease: "power2.in" }}, {END - 0.3:.2f});
      tl.to("#orn-gem", {{ scale: 0, rotation: 90, opacity: 0, duration: 0.18, ease: "power2.in" }}, {END - 0.2:.2f});

      // ---------- зерно ----------
{grain_js}
'''

# Звуковых эффектов нет (v4: «звук звоночка не к месту»). Только музыка под голос: уровень заложен
# в сам файл (broll_prep.py, −31 LUFS при голосе −14), вход и уход плавные.
music = f'      <audio id="music" src="assets/music/bed.m4a" data-start="0" data-duration="{END:.2f}" data-volume="1"></audio>'
fg = [(0.0, T_ALONE), (T_FIERCE_IN, END)]
page = build_page("Rooted", DUR, behind, front, beats, [music], fg, cta_at=END,
                  extra_css=css, fmt=tk.fmt, captions=tk.captions, cta=False)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

director = {
    "_note": "Тестовое для заказчицы, эстетика её референса. Раскладка — work/IMG_6668/page.py.",
    # камера спокойная, как в референсе: медленный наезд от «But really», пока героиня в кадре
    "punches": [[T_BUT, END, 1.2, 2.6, 0.0]],
    "text_fixes": {},          # подписи — свои, фразами (PHRASES), «wound» там уже «womb»
    "keep_case": [],
    "accent_words": [],
    "hide_captions": [],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", END)
