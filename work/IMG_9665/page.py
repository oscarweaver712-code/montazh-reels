"""IMG_9665 — отзыв клиентки Ольги Статировой (тестовое, ТЗ Ольги 22.10.2026), страница через montage.Montage.

ТЗ: «отзыв классный, но скучный — оставить самое лучшее, ускорить, доставить спецэффектов и мемов… до минуты».
Мысль: за полгода с Ольгой её «внутренняя погода» сменилась — в апреле гроза (агрессия, нервы, мама), в октябре ясно и
спокойно; жалеет только, что ждала 48 лет. Визуальная идея — «Внутренняя погода»: виджет погоды её состояния слева,
апрель — холодный кадр, дождь, молния и гром на «агрессивное»; на «октябрь» виджет переворачивается в солнце, кадр
теплеет, свет, птицы, музыка поднимается. Хук — забегание вперёд: её «что я 48 лет ждала?» из конца, стоп-кадр под
тормоз пластинки, «как она до этого дошла?», перемотка. Мемы — на надежде и на «чуде», не на боли: «магия?»,
«(спойлер: возможно)», загрузка нового состояния, поиск «агрессия — ничего не найдено», ценник «бесценно».

Дубль — сборка из 16 кусков одного видео (pack.json, ×1.1, тишина внутри слов whisper вырезана), шкала дубля 51,77 с.
Склейки внутри плана: 3.73, 15.27, 20.37, 22.70, 27.30, 29.43, 30.00, 35.53, 36.60, 37.63, 39.13, 40.43, 40.93, 43.93, 44.50;
стык сцены — 1.83 (после стоп-кадра хука).
Кадр: лицо почти во всю ширину (x 210–850, y 370–1330), субтитры compose поставил над головой (y 277) — графика — на груди (y ≥ 1350:
голова на наездах почти у верхнего края, слово за спиной закрывал ободок — «ЧУДО» и «ОКТЯБРЬ» тоже на груди, маска не
нужна) и виджет погоды в левом верхнем углу.
Звуки из материалов — Mixkit Sound Effects Free License (коммерческое использование, без указания автора): 704 тормоз
пластинки, 871 искры, 2393 дождь, 1283 гром, 17 птицы, 2674 мягкий подъём. Музыка — Mixkit «Tears of Joy» (839, Stock
Music Free License) из запаса проекта.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import kit  # noqa: E402
from montage import Montage  # noqa: E402

STEM = "IMG_9665"
TRACK = "mx-tears-of-joy.mp3"
m = Montage(STEM)
DUR = m.duration
SH = "0 3px 8px rgba(0,0,0,0.55), 0 10px 34px rgba(0,0,0,0.45)"
CHEST = 'data-safe="на груди под лицом: над головой — субтитры"'
SPLICE = 'data-splice="склейка внутри плана — вырезана тишина, кадр тот же: надпись досказывает мысль через неё"'

# цвета ролика: гроза апреля — чернильный и сигнальный красный, октябрь — солнце и крем, любовь — розовый
m.css(f"""
      @font-face {{ font-family: "Golos"; src: url("assets/fonts/GolosText-Black.ttf"); font-weight: 900; }}
      @font-face {{ font-family: "Caveat"; src: url("assets/fonts/Caveat-Bold.ttf"); font-weight: 700; }}
      @font-face {{ font-family: "InterD"; src: url("assets/fonts/InterDisplay-ExtraBold.ttf"); font-weight: 800; }}
      @font-face {{ font-family: "InterD"; src: url("assets/fonts/InterDisplay-Light.ttf"); font-weight: 300; }}
      :root {{ --ink: #161B26; --storm: #2A3346; --alert: #FF3B30; --sun: #FFC83D; --sun2: #FF9F1C; --cream: #FFF6E6;
               --love: #FF5C8A; }}
      .big {{ left: 0; width: 1080px; text-align: center; font-family: "Golos"; font-weight: 900; text-transform: uppercase;
              line-height: 0.9; color: var(--cream); text-shadow: {SH}; white-space: nowrap; }}
      .gold {{ background: linear-gradient(180deg, #FFE38A 0%, var(--sun) 45%, var(--sun2) 100%); -webkit-background-clip: text;
               background-clip: text; -webkit-text-fill-color: transparent; color: transparent; text-shadow: none;
               filter: drop-shadow(0 6px 22px rgba(0,0,0,0.45)); }}
      .hand {{ font-family: "Caveat"; font-weight: 700; color: var(--cream); text-shadow: {SH}; white-space: nowrap; line-height: 1; }}
      .hand.red {{ color: #FF4D45; }}
      .sticker {{ font-family: "Caveat"; font-weight: 700; color: var(--ink); background: var(--cream); border-radius: 22px;
                  padding: 4px 26px 10px; box-shadow: 0 14px 40px rgba(0,0,0,0.45); white-space: nowrap; }}
      .mid {{ left: 0; width: 1080px; display: flex; justify-content: center; align-items: center; }}

      /* виджет внутренней погоды */
      #wx {{ left: 18px; top: 226px; width: 246px; height: 90px; transform-origin: 50% 50%; }}
      .wx-face {{ position: absolute; left: 0; top: 0; width: 246px; height: 90px; border-radius: 24px; padding: 10px 12px 0 84px;
                  background: linear-gradient(160deg, rgba(42,51,70,0.82), rgba(18,22,32,0.86));
                  border: 2px solid rgba(255,255,255,0.16); box-shadow: 0 20px 60px rgba(0,0,0,0.5); color: #fff; }}
      #wx-oct {{ background: linear-gradient(160deg, rgba(78,148,214,0.86), rgba(36,98,170,0.88)); opacity: 0; }}
      .wx-m {{ font-family: "Golos"; font-weight: 900; font-size: 22px; letter-spacing: 0.04em; }}
      .wx-t {{ display: none; }}
      .wx-ic {{ position: absolute; left: 10px; top: 8px; width: 72px; height: 72px; }}
      .wx-d {{ position: relative; margin-top: 4px; font-family: "InterD"; font-weight: 800; font-size: 26px; white-space: nowrap; }}
      .wx-d small {{ display: none; }}
      #wx-calm {{ opacity: 0; }}

      /* погода на кадре */
      #rain {{ left: 0; top: 0; width: 1080px; height: 1920px; pointer-events: none;
               background-image: repeating-linear-gradient(104deg, rgba(210,225,255,0) 0px, rgba(210,225,255,0) 22px,
                                 rgba(210,225,255,0.34) 22px, rgba(210,225,255,0.34) 24px),
                                 repeating-linear-gradient(98deg, rgba(210,225,255,0) 0px, rgba(210,225,255,0) 41px,
                                 rgba(210,225,255,0.22) 41px, rgba(210,225,255,0.22) 43px);
               background-size: 70px 210px, 110px 330px; }}
      #storm {{ left: 0; top: 0; width: 1080px; height: 1920px;
                background: radial-gradient(ellipse at 50% 40%, rgba(10,16,30,0) 40%, rgba(10,16,30,0.55) 100%); }}
      #sun {{ left: 0; top: 0; width: 1080px; height: 1920px; mix-blend-mode: screen;
              background: radial-gradient(circle at 92% 6%, rgba(255,214,120,0.75) 0%, rgba(255,170,60,0.32) 22%,
                          rgba(255,150,40,0) 48%); }}
      #bolt {{ left: 610px; top: 0; width: 470px; height: 980px; filter: drop-shadow(0 0 18px #CFE3FF) drop-shadow(0 0 40px #8FB8FF); }}
      #vhs {{ left: 0; top: 0; width: 1080px; height: 1920px;
              background: repeating-linear-gradient(0deg, rgba(255,255,255,0.07) 0px, rgba(255,255,255,0.07) 3px,
                          rgba(0,0,0,0) 3px, rgba(0,0,0,0) 7px); }}
      .vhs-bar {{ left: 0; width: 1080px; height: 46px; background: rgba(255,255,255,0.22); filter: blur(3px); }}
      #rew {{ left: 56px; top: 470px; font-family: "InterD"; font-weight: 800; font-size: 46px; color: #fff; letter-spacing: 0.06em;
              text-shadow: 2px 0 0 rgba(255,0,80,0.7), -2px 0 0 rgba(0,200,255,0.7), 0 4px 20px rgba(0,0,0,0.5); }}

      /* шторм: предупреждение и чипы */
      .warn {{ display: inline-flex; align-items: center; gap: 14px; padding: 12px 30px 12px 22px; border-radius: 18px;
               background: var(--alert); color: #fff; font-family: "Golos"; font-weight: 900; font-size: 38px; letter-spacing: 0.03em;
               box-shadow: 0 16px 44px rgba(120,0,0,0.5); text-transform: uppercase; }}
      .chips {{ gap: 18px; }}
      .chip {{ padding: 12px 28px 14px; border-radius: 40px; background: rgba(22,27,38,0.86); border: 3px solid var(--alert);
               color: #fff; font-family: "InterD"; font-weight: 800; font-size: 40px; white-space: nowrap; }}

      /* загрузка нового состояния → заряд любви */
      .load {{ width: 720px; padding: 20px 28px 26px; border-radius: 26px; background: rgba(22,27,38,0.84);
               border: 2px solid rgba(255,255,255,0.16); box-shadow: 0 20px 60px rgba(0,0,0,0.5); }}
      .load-l {{ font-family: "InterD"; font-weight: 800; font-size: 36px; color: #fff; display: flex; justify-content: space-between; }}
      .load-b {{ margin-top: 16px; height: 34px; border-radius: 17px; background: rgba(255,255,255,0.14); overflow: hidden; }}
      .load-f {{ width: 100%; height: 100%; border-radius: 17px; transform-origin: 0 50%; transform: scaleX(0);
                 background: linear-gradient(90deg, #7FB8FF, #B79CFF); }}
      #lv .load-f {{ background: linear-gradient(90deg, #FF8FB0, var(--love)); }}
      .heart {{ width: 86px; height: 80px; }}

      /* поиск */
      .search {{ width: 760px; padding: 22px 30px; border-radius: 30px; background: #FFFFFF; box-shadow: 0 20px 60px rgba(0,0,0,0.5); }}
      .s-row {{ display: flex; align-items: center; gap: 18px; font-family: "InterD"; font-weight: 800; font-size: 46px; color: #1B1F2A; height: 56px; }}
      .s-row svg {{ width: 44px; height: 44px; flex: none; }}
      .s-q {{ position: relative; }}
      .s-q span {{ display: inline-block; opacity: 0; }}
      .s-res {{ margin-top: 14px; font-family: "InterD"; font-weight: 300; font-size: 36px; color: #E0312B; height: 42px; position: relative; }}
      .s-res div {{ position: absolute; left: 0; top: 0; opacity: 0; white-space: nowrap; }}

      /* звёзды, до/после, ценник */
      .stars {{ gap: 14px; }}
      .star {{ width: 118px; height: 118px; filter: drop-shadow(0 8px 20px rgba(0,0,0,0.45)); }}
      .ba {{ gap: 22px; }}
      .mini {{ width: 300px; height: 190px; border-radius: 28px; padding: 18px 22px; position: relative; color: #fff;
               box-shadow: 0 18px 50px rgba(0,0,0,0.5); }}
      .mini.apr {{ background: linear-gradient(160deg, #3A4560, #171C28); }}
      .mini.oct {{ background: linear-gradient(160deg, #5BA4E6, #2563AA); }}
      .mini .wx-m {{ font-size: 28px; }}
      .mini .wx-d {{ left: 22px; bottom: 18px; font-size: 34px; }}
      .mini svg {{ position: absolute; right: 14px; top: 30px; width: 104px; height: 104px; }}
      .arrow {{ font-family: "Golos"; font-weight: 900; font-size: 70px; color: var(--cream); text-shadow: {SH}; }}
      #tag {{ left: 300px; top: 1330px; width: 480px; transform-origin: 50% 0%; }}
      .tag-b {{ position: relative; margin-top: 70px; padding: 26px 30px 30px 74px; border-radius: 18px 60px 60px 18px; background: var(--cream);
                box-shadow: 0 20px 50px rgba(0,0,0,0.5); font-family: "Golos"; font-weight: 900; font-size: 64px; color: #E0312B; text-align: center; }}
      .tag-b small {{ display: block; font-family: "InterD"; font-weight: 300; font-size: 30px; color: #4B4B55; margin-bottom: 2px; }}
      .tag-b i {{ position: absolute; left: 26px; top: 50%; width: 26px; height: 26px; margin-top: -13px; border-radius: 13px;
                  background: #3B3B44; }}
      .tag-s {{ position: absolute; left: 39px; top: 0; width: 4px; height: 118px; background: #D9D2C3; transform-origin: 50% 0; transform: rotate(-24deg); }}
      .sign {{ font-family: "InterD"; font-weight: 300; font-size: 34px; color: #fff; letter-spacing: 0.04em; text-shadow: {SH}; }}
      .sign b {{ font-weight: 800; }}
""")

STORM = ('<path d="M30 66 Q14 66 14 50 Q14 34 32 34 Q38 14 60 14 Q82 14 88 34 Q106 34 106 52 Q106 66 90 66 Z" fill="#C9D3E6"/>'
         '<path d="M58 62 L44 88 L58 88 L48 108 L74 78 L60 78 L70 62 Z" fill="#FFC83D"/>'
         '<path d="M26 76 L20 90 M40 80 L34 94 M88 76 L82 90" stroke="#9FC1FF" stroke-width="4" stroke-linecap="round"/>')
SUN = ('<circle cx="60" cy="60" r="26" fill="#FFC83D"/>'
       '<g stroke="#FFC83D" stroke-width="7" stroke-linecap="round">'
       '<path d="M60 10 L60 22"/><path d="M60 98 L60 110"/><path d="M10 60 L22 60"/><path d="M98 60 L110 60"/>'
       '<path d="M25 25 L33 33"/><path d="M87 87 L95 95"/><path d="M25 95 L33 87"/><path d="M87 33 L95 25"/></g>')
HEART = '<path d="M43 76 C10 52 2 34 10 20 C18 6 36 6 43 22 C50 6 68 6 76 20 C84 34 76 52 43 76 Z" fill="{c}"/>'
STAR = ('<svg class="star" viewBox="0 0 100 100"><path d="M50 6 L62 37 L95 38 L69 58 L78 91 L50 72 L22 91 L31 58 L5 38 L38 37 Z" '
        'fill="#FFC83D" stroke="#FF9F1C" stroke-width="3" stroke-linejoin="round"/></svg>')
LENS = ('<svg viewBox="0 0 48 48"><circle cx="20" cy="20" r="13" fill="none" stroke="#8A8F9C" stroke-width="5"/>'
        '<path d="M30 30 L42 42" stroke="#8A8F9C" stroke-width="6" stroke-linecap="round"/></svg>')


def letters(word: str) -> str:
    return "".join(f"<span>{ch}</span>" for ch in word)


# ---------------------------------------------------------------- 1. хук: «что я 48 лет ждала?» → стоп-кадр, перемотка
m.front(f'        <div id="h48" class="g big" {CHEST} style="top: 1318px; font-size: 230px;">48 лет</div>\n'
        f'        <div id="h48w" class="g hand red" {CHEST} style="left: 600px; top: 1500px; font-size: 104px;">ждала?!</div>\n'
        f'        <div id="vhs" class="g" data-safe="полосы перемотки поверх стоп-кадра, 0,8 с"></div>\n'
        f'        <div id="vb1" class="g vhs-bar" data-safe="полоса перемотки бежит по кадру" style="top: 300px;"></div>\n'
        f'        <div id="vb2" class="g vhs-bar" data-safe="полоса перемотки бежит по кадру" style="top: 1100px; height: 26px;"></div>\n'
        f'        <div id="rew" class="g" data-safe="метка перемотки на стене слева">◀◀ ОТМОТАЕМ</div>\n'
        f'        <div id="hq" class="g mid" {CHEST} style="top: 1380px;"><div class="sticker" style="font-size: 70px; '
        f'transform: rotate(-3deg);">как она до этого дошла?</div></div>')
m.js('      slam("#h48", 0.14, { fromScale: 1.6, dur: 0.18 });\n'
     '      enter("#h48w", 0.66, { fromScale: 0.5, rot: -7, blur: 10, dur: 0.24 });\n'
     '      leave(["#h48", "#h48w"], 1.04, { y: 30, dur: 0.14 });\n'
     # стоп-кадр (pack.json hold 0.7): кадр серый, тормоз пластинки, перемотка назад
     '      tl.set("#aroll", { filter: "grayscale(1) contrast(1.12) brightness(0.92)" }, 1.03);\n'
     '      tl.set("#aroll", { filter: "none" }, 1.83);\n'
     '      enter("#hq", 1.1, { fromScale: 0.6, rot: -3, blur: 10, dur: 0.22 });\n'
     '      leave("#hq", 1.66, { y: 20, dur: 0.14 });\n'
     '      tl.fromTo("#vhs", { opacity: 0 }, { opacity: 1, duration: 0.06, ease: "none", immediateRender: false }, 1.36);\n'
     '      tl.to("#vhs", { opacity: 0, duration: 0.08, ease: "none" }, 1.74);\n'
     '      tl.fromTo("#vb1", { opacity: 1, y: 0 }, { opacity: 1, y: -340, duration: 0.42, ease: "none", immediateRender: false }, 1.36);\n'
     '      tl.fromTo("#vb2", { opacity: 1, y: 0 }, { opacity: 1, y: -640, duration: 0.42, ease: "none", immediateRender: false }, 1.36);\n'
     '      tl.set(["#vb1", "#vb2"], { opacity: 0 }, 1.78);\n'
     '      enter("#rew", 1.36, { fromX: 60, fromScale: 1, blur: 6, dur: 0.12 });\n'
     '      leave("#rew", 1.72, { x: -40, scale: 1, dur: 0.1 });')
SND = []                                  # звуки из материалов (Mixkit) — kit.material_audio, в m.sounds перед сборкой
SND.append(kit.material_audio("scratch", STEM, "sfx-mixkit-scratch-stop.mp3", 0.98, 0.9, duration=0.75, fade_out=0.2))
m.punch(0.14, 1.0)
m.hide(0.0, 1.83)
m.hook(1.83, "перемотка из стоп-кадра в начало истории")

# ---------------------------------------------------------------- 2. «Я не знаю, как ты это делаешь» → «магия?»
m.front('        <div id="magic" class="g" data-safe="стикер в левом верхнем углу над головой" style="left: 24px; top: 236px;">'
        '<div class="sticker" style="font-size: 60px; transform: rotate(-7deg);">магия?</div></div>')
m.js('      enter("#magic", 2.92, { fromScale: 0.4, rot: -9, blur: 10, dur: 0.24 });\n'
     '      leave("#magic", 3.6, { y: -20, dur: 0.12 });')

# ---------------------------------------------------------------- 3. «я называю это чудо» → ЧУДО за головой, искры
SPARK = '<svg viewBox="0 0 40 40"><path d="M20 0 L24 16 L40 20 L24 24 L20 40 L16 24 L0 20 L16 16 Z" fill="#FFE38A"/></svg>'
SPARKS = [(150, 1380, 64), (860, 1360, 76), (40, 1520, 46), (990, 1500, 50), (230, 1640, 40), (930, 1650, 38), (70, 1420, 42)]
m.front(f'        <div id="chudo" class="g big gold" {CHEST} style="top: 1362px; font-size: 236px;">чудо</div>')
m.front("\n".join(f'        <div id="sp{k}" class="g" data-safe="искра у слова «чудо», мельком" style="left: {x}px; top: {y}px; '
                  f'width: {s}px; height: {s}px;">{SPARK}</div>' for k, (x, y, s) in enumerate(SPARKS)))
m.js('      slam("#chudo", 6.79, { fromScale: 1.3, dur: 0.2 });\n'
     + "".join(f'      tl.fromTo("#sp{k}", {{ opacity: 0, scale: 0, rotation: -40 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: 0.22, '
               f'ease: "back.out(3)", immediateRender: false }}, {6.84 + k * 0.05:.2f});\n'
               f'      tl.to("#sp{k}", {{ opacity: 0, scale: 0.3, rotation: 60, duration: 0.3, ease: "power2.in" }}, {7.6 + k * 0.04:.2f});\n'
               for k in range(len(SPARKS)))
     + '      leave("#chudo", 8.3, { y: -30, dur: 0.22 });')
m.hide(6.7, 8.55)
m.punch(6.79, 7.55)
SND.append(kit.material_audio("sparkle", STEM, "sfx-mixkit-sparkle-fairy.mp3", 6.76, 0.8))

# ---------------------------------------------------------------- 4. апрель: виджет «гроза», холодный кадр, дождь
WXH = ('data-hold="виджет внутренней погоды — сквозной мотив: апрель, молния, переворот в октябрь, штиль" '
       'data-splice="виджет погоды стоит через склейки — мотив ролика, кадр тот же" data-safe="виджет в левом верхнем углу над лицом"')
m.front(f'        <div id="wx" class="g" {WXH}>\n'
        f'          <div id="wx-apr" class="wx-face"><div class="wx-m">АПРЕЛЬ</div><div class="wx-t">+4°</div>'
        f'<svg class="wx-ic" viewBox="0 0 120 120">{STORM}</svg><div class="wx-d">+4° гроза</div></div>\n'
        f'          <div id="wx-oct" class="wx-face"><div class="wx-m">ОКТЯБРЬ</div><div class="wx-t">+24°</div>'
        f'<svg class="wx-ic" viewBox="0 0 120 120">{SUN}</svg><div class="wx-d"><span id="wx-clear">+24° ясно</span>'
        f'<span id="wx-calm" style="position: absolute; left: 0; top: 0; white-space: nowrap;">+24° штиль</span></div></div>\n'
        f'        </div>')
m.behind('        <div id="storm" class="g" data-hold="тень грозы апреля по краям кадра" data-splice="погода апреля через склейки" '
         'data-safe="тёмная виньетка по краям, лицо открыто"></div>\n'
         '        <div id="rain" class="g" data-hold="дождь апреля — фон истории до «октября»" data-splice="дождь идёт через склейки" '
         'data-safe="прозрачные штрихи дождя поверх кадра, лицо видно"></div>\n'
         '        <div id="sun" class="g" data-hold="тёплый свет октября до конца ролика" data-splice="свет октября через склейки" '
         'data-safe="тёплый свет из угла, лицо открыто"></div>')
GRADE0 = "saturate(1) brightness(1) contrast(1) hue-rotate(0deg) sepia(0)"
APRIL = "saturate(0.55) brightness(0.86) contrast(1.08) hue-rotate(-8deg) sepia(0)"
OCT = "saturate(1.12) brightness(1.03) contrast(1.02) hue-rotate(0deg) sepia(0.1)"
m.js('      enter("#wx", 10.17, { fromX: -240, fromScale: 1, blur: 12, dur: 0.4, ease: "power3.out" });\n'
     f'      tl.fromTo("#aroll", {{ filter: "{GRADE0}" }}, {{ filter: "{APRIL}", duration: 0.7, ease: "power1.inOut", '
     f'immediateRender: false }}, 10.17);\n'
     '      tl.fromTo("#storm", { opacity: 0 }, { opacity: 1, duration: 0.7, ease: "power1.inOut", immediateRender: false }, 10.17);\n'
     '      tl.fromTo("#rain", { opacity: 0 }, { opacity: 0.75, duration: 0.6, ease: "power1.out", immediateRender: false }, 10.3);\n'
     '      tl.fromTo("#rain", { backgroundPosition: "0px 0px, 0px 0px" }, { backgroundPosition: "-420px 2520px, -300px 1980px", '
     'duration: 10.6, ease: "none", immediateRender: false }, 10.3);')
m.hide(10.0, 10.75)                       # «в апреле» — виджет «АПРЕЛЬ» говорит то же
SND.append(kit.material_audio("rain", STEM, "sfx-mixkit-rain.mp3", 10.2, 0.5, duration=10.6, fade_out=1.2))

# «я не думала, что вообще возможно изменить» → рукой «(спойлер: возможно)»
m.front(f'        <div id="spoil" class="g mid hand" {CHEST} style="top: 1400px; font-size: 84px;">'
        '<span style="display: inline-block; transform: rotate(-4deg);">(спойлер: возможно)</span></div>')
m.js('      enter("#spoil", 13.7, { fromY: 30, fromScale: 0.8, blur: 10, dur: 0.3 });\n'
     '      leave("#spoil", 15.0, { y: 30, dur: 0.18 });')

# ---------------------------------------------------------------- 5. «мои сложные отношения с мамой и моё агрессивное…»
WARN = ('<svg viewBox="0 0 40 36" style="width: 40px; height: 36px;"><path d="M20 2 L38 34 L2 34 Z" fill="#fff"/>'
        '<path d="M20 13 L20 23" stroke="#FF3B30" stroke-width="4" stroke-linecap="round"/><circle cx="20" cy="28.5" r="2.4" fill="#FF3B30"/></svg>')
m.front(f'        <div id="warn" class="g mid" {CHEST} style="top: 1400px;"><div class="warn">{WARN}штормовое предупреждение</div></div>\n'
        f'        <div id="chips" class="g mid chips" {CHEST} style="top: 1494px;">'
        f'<div class="chip" id="c-mom">отношения с мамой</div><div class="chip" id="c-agr">агрессия</div></div>\n'
        '        <svg id="bolt" class="g" viewBox="0 0 470 980" data-safe="молния по стене справа, 0,3 с">'
        '<path d="M300 0 L180 360 L290 360 L120 700 L230 700 L60 980" fill="none" stroke="#FFFFFF" stroke-width="16" '
        'stroke-linejoin="round" stroke-linecap="round"/></svg>')
m.js('      enter("#warn", 15.45, { fromScale: 1.25, blur: 14, dur: 0.22, ease: "power4.out" });\n'
     '      tl.to("#warn .warn", { scale: 1.05, duration: 0.3, yoyo: true, repeat: 3, ease: "sine.inOut" }, 15.8);\n'
     '      tl.set("#chips", { opacity: 1 }, 16.55);\n'
     '      tl.fromTo("#c-mom", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.24, ease: "back.out(2.4)", immediateRender: false }, 16.59);\n'
     '      tl.set("#c-agr", { opacity: 0 }, 16.55);\n'
     '      tl.fromTo("#c-agr", { opacity: 0, scale: 0.4 }, { opacity: 1, scale: 1, duration: 0.2, ease: "back.out(2.4)", immediateRender: false }, 18.25);\n'
     # молния: вспышка, разряд по стене, виджет вздрагивает
     '      flash(18.2);\n'
     '      tl.fromTo("#bolt", { opacity: 0 }, { opacity: 1, duration: 0.03, ease: "none", immediateRender: false }, 18.2);\n'
     '      tl.to("#bolt", { opacity: 0.2, duration: 0.05, ease: "none" }, 18.28);\n'
     '      tl.to("#bolt", { opacity: 1, duration: 0.03, ease: "none" }, 18.34);\n'
     '      tl.to("#bolt", { opacity: 0, duration: 0.18, ease: "power1.in" }, 18.42);\n'
     '      tl.fromTo("#wx", { x: 0 }, { x: 9, duration: 0.04, yoyo: true, repeat: 7, ease: "none", immediateRender: false }, 18.22);\n'
     '      leave(["#warn", "#chips"], 20.12, { y: 30, dur: 0.2 });')
m.js('      whip(15.26);')     # склейка 15.267: смаз до неё, а не через 3 мс после (framing округлил вверх)
m.hide(16.55, 19.2)
m.punch(18.23, 19.05)
SND.append(kit.material_audio("thunder", STEM, "sfx-mixkit-thunder.mp3", 18.12, 0.85, duration=2.6, fade_out=1.2))

# ---------------------------------------------------------------- 6. «Но вот сейчас октябрь» — погода меняется
m.front(f'        <div id="okt" class="g big gold" {CHEST} style="top: 1384px; font-size: 158px;">октябрь</div>')
m.js('      tl.to("#rain", { opacity: 0, duration: 0.6, ease: "power1.in" }, 20.4);\n'
     '      tl.to("#storm", { opacity: 0, duration: 0.9, ease: "power1.inOut" }, 20.9);\n'
     '      slam("#okt", 21.44, { fromScale: 1.3, dur: 0.2 });\n'
     '      leave("#okt", 22.45, { y: -30, dur: 0.2 });\n'
     # виджет уходит ребром перед словом «октябрь» и встаёт обратно уже солнечным
     '      tl.to("#wx", { scaleX: 0, duration: 0.14, ease: "power2.in" }, 21.2);\n'
     '      tl.set("#wx-apr", { opacity: 0 }, 21.36);\n'
     '      tl.set("#wx-oct", { opacity: 1 }, 21.36);\n'
     '      tl.to("#wx", { scaleX: 1, duration: 0.24, ease: "back.out(2)" }, 22.5);\n'
     f'      tl.to("#aroll", {{ filter: "{OCT}", duration: 0.8, ease: "power1.inOut" }}, 21.44);\n'
     '      tl.fromTo("#sun", { opacity: 0, x: 60, y: -60 }, { opacity: 1, x: 0, y: 0, duration: 1.2, ease: "power2.out", immediateRender: false }, 21.44);\n'
     '      tl.to("#sun", { x: -30, y: 40, duration: 28, ease: "sine.inOut" }, 22.7);')
m.js('      whip(20.36);')
m.punch(20.36, 21.4, level=1.36, ease_in=0.0, ease_out=0.2)   # поворот «Но вот сейчас» — план крупнее на резе
m.hide(21.4, 22.6)
m.punch(21.44, 22.4)
SND.append(kit.material_audio("birds", STEM, "sfx-mixkit-birds.mp3", 21.36, 0.6, duration=4.0, fade_out=1.8))

# ---------------------------------------------------------------- 7. «очень странное состояние, непривычное» → загрузка
m.front(f'        <div id="ld" class="g mid" {CHEST} style="top: 1360px;"><div class="load"><div class="load-l">'
        f'<span>устанавливаю обновление…</span><span id="ld-p">63%</span></div><div class="load-b"><div class="load-f"></div></div></div></div>')
m.js('      enter("#ld", 24.86, { fromY: 40, fromScale: 0.9, blur: 12, dur: 0.3 });\n'
     '      tl.fromTo("#ld .load-f", { scaleX: 0 }, { scaleX: 0.63, duration: 1.4, ease: "power2.out", immediateRender: false }, 25.0);\n'
     '      tl.to("#ld .load-f", { opacity: 0.5, duration: 0.25, yoyo: true, repeat: 2, ease: "sine.inOut" }, 26.4);\n'
     '      leave("#ld", 27.12, { y: 30, dur: 0.16 });')

# «Но сейчас я наполнена какой-то любовью ко всем» → заряд любви до 100 %, сердца от её рук
# сердца поднимаются по бокам кадра — мимо лица (x 210–850)
HEARTS = [(40, 1500, "#FF5C8A", 1.0), (930, 1520, "#FF8FB0", 0.8), (110, 1580, "#FF3B6B", 0.85), (960, 1600, "#FF5C8A", 1.0),
          (20, 1660, "#FF8FB0", 0.75), (900, 1680, "#FF3B6B", 0.9), (90, 1740, "#FF5C8A", 0.8), (950, 1760, "#FF8FB0", 0.85)]
m.front(f'        <div id="lv" class="g mid" {CHEST} {SPLICE} style="top: 1360px;"><div class="load"><div class="load-l">'
        f'<span>заряд любви</span><span id="lv-p">100%</span></div><div class="load-b"><div class="load-f"></div></div></div></div>\n'
        + "\n".join(f'        <svg id="hr{k}" class="g heart" viewBox="0 0 86 80" data-safe="сердце пролетает мимо, 1,5 с" '
                    f'style="left: {x}px; top: {y}px; width: {round(86 * s)}px; height: {round(80 * s)}px;">{HEART.format(c=c)}</svg>'
                    for k, (x, y, c, s) in enumerate(HEARTS)))
m.js('      enter("#lv", 28.55, { fromY: 40, fromScale: 0.9, blur: 12, dur: 0.3 });\n'
     '      tl.fromTo("#lv .load-f", { scaleX: 0.2 }, { scaleX: 1, duration: 1.7, ease: "power1.inOut", immediateRender: false }, 28.65);\n'
     '      tl.to("#lv .load", { scale: 1.06, duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut" }, 30.31);\n'
     + "".join(f'      tl.fromTo("#hr{k}", {{ opacity: 0, y: 0, x: 0, rotation: {(-1) ** k * 12} }}, {{ opacity: 1, y: -{620 + 60 * (k % 4)}, '
               f'x: {(-1) ** k * 16}, rotation: {(-1) ** (k + 1) * 10}, duration: 1.0, ease: "power1.out", immediateRender: false }}, {30.25 + k * 0.07:.2f});\n'
               f'      tl.to("#hr{k}", {{ opacity: 0, scale: 0.4, duration: 0.25, ease: "power1.in" }}, {31.27 + k * 0.07:.2f});\n'
               for k in range(len(HEARTS)))
     + '      leave("#lv", 31.95, { y: 30, dur: 0.2 });')
m.punch(30.31, 31.3)
m.sound("hearts", "sparkle", 30.3, 0.8)

# ---------------------------------------------------------------- 8. «У меня нет агрессии, нет обиды» → поиск ничего не находит
m.front(f'        <div id="srch" class="g mid" {CHEST} {SPLICE} style="top: 1350px;"><div class="search">'
        f'<div class="s-row">{LENS}<div class="s-q"><span id="q1">{letters("агрессия")}</span>'
        f'<span id="q2" style="position: absolute; left: 0; top: 0;">{letters("обида")}</span></div></div>'
        '<div class="s-res"><div id="r1">ничего не найдено</div><div id="r2">0 результатов</div></div></div></div>')
m.js('      enter("#srch", 32.9, { fromY: 40, fromScale: 0.9, blur: 12, dur: 0.26 });\n'
     '      tl.set("#q1", { opacity: 1 }, 32.9);\n'
     '      tl.fromTo("#q1 span", { opacity: 0 }, { opacity: 1, duration: 0.01, stagger: 0.055, ease: "none", immediateRender: false }, 33.0);\n'
     '      tl.fromTo("#r1", { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.16, ease: "power2.out", immediateRender: false }, 33.6);\n'
     '      tl.to(["#q1", "#r1"], { opacity: 0, duration: 0.12, ease: "none" }, 34.45);\n'
     '      tl.set("#q2", { opacity: 1 }, 34.55);\n'
     '      tl.fromTo("#q2 span", { opacity: 0 }, { opacity: 1, duration: 0.01, stagger: 0.055, ease: "none", immediateRender: false }, 34.58);\n'
     '      tl.fromTo("#r2", { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.16, ease: "power2.out", immediateRender: false }, 35.0);\n'
     '      leave("#srch", 35.36, { y: 30, dur: 0.15 });')
m.hide(32.9, 35.47)
m.sound("type1", "typing", 32.98, 0.7, duration=0.5)
m.sound("type2", "key-press", 34.56, 0.7)

# ---------------------------------------------------------------- 9. «Мне хорошо. И мне спокойно» — штиль
m.js('      tl.to("#wx-clear", { opacity: 0, duration: 0.15, ease: "none" }, 37.27);\n'
     '      tl.fromTo("#wx-calm", { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "none", immediateRender: false }, 37.3);\n'
     '      tl.to("#wx", { scale: 1.08, duration: 0.25, yoyo: true, repeat: 1, ease: "sine.inOut" }, 37.27);\n'
     '      tl.to("#sun", { opacity: 1.0, scale: 1.08, duration: 2.0, ease: "sine.inOut" }, 35.55);')
m.punch(35.6, 36.45, ease_in=0.6, ease_out=0.3)
SND.append(kit.material_audio("calm", STEM, "sfx-mixkit-heavenly.mp3", 35.45, 0.6, duration=3.4, fade_out=1.6))

# ---------------------------------------------------------------- 10. «всем рекомендую, всем тебя советую» → пять звёзд
m.front(f'        <div id="stars" class="g mid stars" {CHEST} {SPLICE} style="top: 1370px;">'
        + "".join(f'<div id="st{k}" style="opacity: 0;">{STAR}</div>' for k in range(5)) + '</div>')
m.js('      tl.set("#stars", { opacity: 1 }, 37.7);\n'
     + "".join(f'      tl.fromTo("#st{k}", {{ opacity: 0, scale: 0.2, rotation: -60 }}, {{ opacity: 1, scale: 1, rotation: 0, duration: 0.22, '
               f'ease: "back.out(3)", immediateRender: false }}, {37.72 + k * 0.13:.2f});\n' for k in range(5))
     + '      tl.to("#stars", { scale: 1.08, duration: 0.2, yoyo: true, repeat: 1, ease: "sine.inOut" }, 39.6);\n'
     '      leave("#stars", 40.8, { y: 30, dur: 0.12 });\n'
     '      leave("#wx", 40.8, { x: -60, scale: 0.9, dur: 0.12 });')
m.sound("stars", "chime", 37.72, 0.8)

# ---------------------------------------------------------------- 11. «те трансформации и изменения…» → до/после, «бесценно»
m.front(f'        <div id="ba" class="g mid ba" {CHEST} {SPLICE} style="top: 1352px;">'
        f'<div class="mini apr" id="ba1"><div class="wx-m">АПРЕЛЬ</div><svg viewBox="0 0 120 120">{STORM}</svg>'
        f'<div class="wx-d">гроза</div></div><div class="arrow" id="ba-a">→</div>'
        f'<div class="mini oct" id="ba2"><div class="wx-m">ОКТЯБРЬ</div><svg viewBox="0 0 120 120">{SUN}</svg>'
        f'<div class="wx-d">ясно</div></div></div>')
m.js('      tl.set("#ba", { opacity: 1 }, 41.37);\n'
     '      tl.fromTo("#ba1", { opacity: 0, x: -200, rotation: -8 }, { opacity: 1, x: 0, rotation: -3, duration: 0.35, ease: "power3.out", immediateRender: false }, 41.4);\n'
     '      tl.fromTo("#ba-a", { opacity: 0, x: -30 }, { opacity: 1, x: 0, duration: 0.25, ease: "power2.out", immediateRender: false }, 42.1);\n'
     '      tl.fromTo("#ba2", { opacity: 0, x: 200, rotation: 8 }, { opacity: 1, x: 0, rotation: 3, duration: 0.35, ease: "power3.out", immediateRender: false }, 42.2);\n'
     '      tl.to("#ba2", { scale: 1.06, duration: 0.2, yoyo: true, repeat: 1, ease: "sine.inOut" }, 43.6);\n'
     '      leave("#ba", 45.2, { y: 30, dur: 0.16 });')
m.sound("ba", "pop", 42.2, 0.7)

m.front(f'        <div id="tag" class="g" {CHEST}><div class="tag-s"></div><div class="tag-b"><i></i><small>трансформация</small>БЕСЦЕННО</div></div>')
m.js('      tl.fromTo("#tag", { opacity: 0, y: -500, rotation: 14 }, { opacity: 1, y: 0, rotation: -4, duration: 0.42, ease: "back.out(1.6)", immediateRender: false }, 45.38);\n'
     '      tl.to("#tag", { rotation: 3, duration: 0.5, yoyo: true, repeat: 1, ease: "sine.inOut" }, 45.82);\n'
     '      leave("#tag", 46.85, { y: 40, dur: 0.18 });')
m.hide(45.35, 46.9)
m.punch(45.41, 46.0)
m.sound("tag", "ping", 45.42, 0.8)

# ---------------------------------------------------------------- 12. «что я 48 лет ждала? Почему не раньше?» — возврат к хуку
GLASS = ('<svg viewBox="0 0 60 90" style="width: 120px; height: 180px; vertical-align: -18px; margin-right: 18px;">'
         '<path d="M8 4 H52 M8 86 H52" stroke="#FFF6E6" stroke-width="6" stroke-linecap="round"/>'
         '<path d="M12 8 C12 30 26 38 30 45 C34 52 48 60 48 82 H12 C12 60 26 52 30 45 C34 38 48 30 48 8 Z" fill="none" stroke="#FFF6E6" stroke-width="5"/>'
         '<path id="sand" d="M20 80 Q30 62 40 80 Z" fill="#FFC83D"/></svg>')
m.front(f'        <div id="r48" class="g big" {CHEST} style="top: 1330px; font-size: 200px;">{GLASS}48 лет</div>\n'
        f'        <div id="late" class="g mid hand" {CHEST} style="top: 1400px; font-size: 92px;">'
        '<span style="display: inline-block; transform: rotate(-3deg);">лучше поздно, чем никогда '
        f'<svg viewBox="0 0 86 80" style="width: 70px; height: 66px; vertical-align: -6px;">{HEART.format(c="#FF5C8A")}</svg></span></div>')
m.js('      slam("#r48", 47.15, { fromScale: 1.5, dur: 0.18 });\n'
     '      tl.fromTo("#r48 svg", { rotation: 0 }, { rotation: 180, duration: 0.5, ease: "power2.inOut", immediateRender: false }, 47.5);\n'
     '      leave("#r48", 48.1, { y: 30, dur: 0.14 });\n'
     '      enter("#late", 48.75, { fromY: 30, fromScale: 0.8, blur: 10, dur: 0.3 });\n'
     '      leave("#late", 50.25, { y: 30, dur: 0.18 });')
m.hide(47.0, 48.1)
m.punch(47.15, 47.95)
m.sound("r48", "impact-bass-1", 47.14, 0.8)

# ---------------------------------------------------------------- 13. «Спасибо тебе огромное» — сердца и подпись
FIN = [(50, 1560, "#FF5C8A", 0.9), (930, 1540, "#FF3B6B", 1.0), (110, 1660, "#FF8FB0", 0.8), (960, 1650, "#FF5C8A", 0.85),
       (30, 1740, "#FF3B6B", 0.75)]
m.front(f'        <div id="sig" class="g mid sign" {CHEST} style="top: 1420px;">отзыв клиентки · <b>&nbsp;Ольга Статирова</b></div>\n'
        + "\n".join(f'        <svg id="fh{k}" class="g heart" viewBox="0 0 86 80" data-safe="сердце пролетает мимо в финале" '
                    f'style="left: {x}px; top: {y}px; width: {round(86 * s)}px; height: {round(80 * s)}px;">{HEART.format(c=c)}</svg>'
                    for k, (x, y, c, s) in enumerate(FIN)))
m.js('      enter("#sig", 50.45, { fromY: 24, fromScale: 1, blur: 10, dur: 0.3 });\n'
     + "".join(f'      tl.fromTo("#fh{k}", {{ opacity: 0, y: 0 }}, {{ opacity: 1, y: -{560 + 50 * k}, duration: 0.8, ease: "power1.out", '
               f'immediateRender: false }}, {50.45 + k * 0.08:.2f});\n'
               f'      tl.to("#fh{k}", {{ opacity: 0, duration: 0.14, ease: "none" }}, {50.45 + k * 0.08 + 0.82:.2f});\n' for k in range(len(FIN)))
     + '      leave("#sig", 51.5, { y: 20, dur: 0.16 });')

for s in SND:
    m.sounds.append(s)

page = m.build("IMG_9665 — отзыв: внутренняя погода", cta_at=None, track=TRACK, music_fade=1.2,
               director_extra={"caption_lanes": [[0, round(DUR, 2), 270]]},
               text_fixes={59: "какой-то", 60: "", 61: ""},
               accent_words=["думала,", "изменить", "странное", "апреле,", "непривычное.", "любовью", "спокойно.", "рекомендую", "раньше?", "огромное."])

# музыка: тихо под грозой апреля (×0.35), на «октябрь» поднимается до уровня проекта — поворот истории и в звуке
index = ROOT / "studio" / STEM / "index.html"
html = index.read_text(encoding="utf-8")
bgm = kit.background_music(STEM, TRACK, DUR, lane=[[0, 0.35], [21.2, 0.35], [22.2, 1.0]], fade_out=1.2)
html, n = re.subn(r'      <audio id="sfx-bgm"[^\n]*</audio>', lambda _: bgm, html)
if n != 1:
    sys.exit(f"музыка: тег sfx-bgm в странице найден {n} раз — лента громкости не встала")
index.write_text(html, encoding="utf-8")
print("  → музыка: лента громкости ×0.35 в апреле → ×1 с «октября» (22,2 с)")
