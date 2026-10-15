"""Страница графики IMG_1810: Леонард Эйлер — половина значков ЕГЭ, 800 работ, считал почти вслепую.

Время ударов — по исходнику, на шкалу дубля переводит Take.
Проверено (по биографии Эйлера): родился 1707 в Базеле, в Петербургскую академию — 1727 (20 лет),
в Берлин — 1741 (через 14 лет), обратно в Петербург — 1766, умер там же 18.09.1783. Похоронен на
Смоленском лютеранском кладбище, в 1957 перенесён в Лазаревскую усыпальницу Александро-Невской
лавры. Правый глаз потерял около 1738 (31 год), к старости ослеп почти полностью. Работ — больше
800 (около 850 при жизни и посмертно). В последний день считал подъём монгольфьера (первые полёты —
июнь 1783), обедал, играл с внуком. «Il cessa de calculer et de vivre» — Кондорсе, похвальное слово.
Значки: f(x), e, i, Σ — Эйлер ввёл их в широкий оборот. Автор говорит «придумал не он» — для f(x), e
и Σ это спорно (их обычно приписывают ему); на экран не выносим ни то, ни другое — подпись
«сделал популярными» повторяет только сказанное.
Шутку «рядом с Декартом, который с портретом Путина» не режем — авторская (заметка 14.10).
Картинки (v3, 14.10): портрет Эйлера — Я. Э. Хандманн, 1753, PD; первый полёт монгольфьера (Анноне,
4 июня 1783) — открытка XIX века, PD; оба скачивает work/IMG_1810/fetch.py. Декарт — Франс Хальс, PD.
v3 по просьбе «улучши ролик»: хук — значки крупно за головой (в v2 — мелкая плашка на груди),
настоящий портрет вместо таблички и ещё раз на «Это был Леонард Эйлер», плашки крупнее (на телефоне
подписи не читались), гравюра шара вместо мелкого рисунка.
v4 (15.10, п.13 rules.md, заметка автора): всё из v3 на месте; камера с базой 1.2 и медленным наездом
через мысль (наезды подняты над базой — 1.26–1.30); визуализации: карта-маршрут Базель → Петербург →
Берлин → Петербург с годами 1727/1741/1766/1783 вместо таблички биографии, схема «знак → смысл»
(f(x) → y = f(x); e ≈ 2,718 — верно, e = 2,71828…; i² = −1; Σ — сумма a₁ + a₂ + …), счётчик 800,
линия жизни по зрению (1707–1783: правый глаз ~1738 — 31 год, почти полная слепота ~1771 — отметка без
года, «к старости»), линия времени последнего дня. Подменённый фон трижды: Академия наук (гравюра
Качалова по рисунку Махаева, 1753, PD), Унтер-ден-Линден в Берлине (Й. Г. Розенберг, 1780, PD — там
же стояло здание Прусской академии), Троицкий собор Александро-Невской лавры (фото Pavlikhin, 2014,
CC BY-SA 3.0 — указать при публикации). Ничего не сгенерировано. Контуры карты — world-atlas 110m (ISC),
studio/_vendor/countries-110m.json, считаются здесь же в статичный SVG. Откат на v3 — page_v3.py.bak.
"""
import json
import math
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from kit import Take, audio, build_page, card  # noqa: E402

STEM = "IMG_1810"
tk = Take(STEM)
t = tk.t
DUR = tk.duration
IMG = ROOT / f"studio/{STEM}/assets/img"
IMG.mkdir(parents=True, exist_ok=True)

# портрет Декарта (Франс Хальс, PD) — тот же файл, что в прошлых роликах серии
desc_src = ROOT / "work/IMG_3297/downloads/descartes.jpg"
shutil.copyfile(desc_src, IMG / "descartes.jpg")
for name in ("euler.jpg", "balloon.jpg", "bg_spb.jpg", "bg_berlin.jpg", "bg_lavra.jpg"):
    src = ROOT / f"work/{STEM}/downloads/{name}"
    if not src.exists():
        sys.exit(f"✗ нет {src.name} — запусти work/{STEM}/fetch.py (портрет и гравюра с Wikimedia, PD)")
    dst = IMG / name
    if not (dst.exists() and dst.samefile(src)):      # студия может держать ту же картинку жёсткой ссылкой
        shutil.copyfile(src, dst)
# рамка-табличка v2 больше не используется — оставлена на случай отката
(IMG / "euler_frame.svg").write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 268 300" width="268" height="300">'
    '<rect width="268" height="300" fill="#2A2219"/>'
    '<ellipse cx="134" cy="150" rx="112" ry="134" fill="#3B3024" stroke="#C9A55A" stroke-width="8"/>'
    '<ellipse cx="134" cy="150" rx="98" ry="120" fill="none" stroke="#C9A55A" stroke-width="2"/>'
    '<text x="134" y="132" text-anchor="middle" font-family="Georgia, serif" font-style="italic" '
    'font-size="44" fill="#F2EBDD">L. Euler</text>'
    '<text x="134" y="180" text-anchor="middle" font-family="Georgia, serif" font-size="28" '
    'fill="#C9A55A">1707 – 1783</text></svg>', encoding="utf-8")

css = '''      .flag-ch { display: inline-block; position: relative; width: 48px; height: 48px; margin-right: 16px; vertical-align: -6px;
                 border-radius: 6px; background: #D52B1E; }
      .flag-ch::before { content: ""; position: absolute; left: 20px; top: 9px; width: 9px; height: 30px; background: #fff; }
      .flag-ch::after { content: ""; position: absolute; left: 9px; top: 20px; width: 30px; height: 9px; background: #fff; }
      .panel { border-radius: 28px; background: rgba(12,12,14,0.88); border: 2px solid rgba(242,235,221,0.16);
               box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .row { display: flex; justify-content: space-between; align-items: baseline; padding: 8px 6px; opacity: 0;
             border-bottom: 2px solid rgba(242,235,221,0.14); }
      .row:last-child { border-bottom: none; }
      .row-n { font-family: "Cormorant"; font-weight: 700; font-size: 78px; color: var(--cream); font-variant-numeric: lining-nums; }
      .row-w { font-family: "Manrope"; font-weight: 800; font-size: 32px; letter-spacing: 0.08em; text-transform: uppercase;
               color: rgba(242,235,221,0.8); text-align: right; }
      .sym { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 100px; color: #F5B82E;
             font-variant-numeric: lining-nums; line-height: 1; }
      .cell { text-align: center; padding: 8px 4px; opacity: 0; }
      .cell-w { margin-top: 6px; font-family: "Manrope"; font-weight: 800; font-size: 25px; letter-spacing: 0.08em;
                text-transform: uppercase; color: rgba(242,235,221,0.8); }
      .hook-big { display: inline-block; opacity: 0; margin: 0 34px; font-family: "Cormorant"; font-style: italic;
                  font-weight: 700; color: #F5B82E; font-variant-numeric: lining-nums;
                  text-transform: none; }
      .quote { padding: 30px 38px 26px; border-radius: 8px; background: #F3EAD6; box-shadow: 0 30px 80px rgba(0,0,0,0.6); }
      .quote-t { font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 50px; line-height: 1.15; color: #2A2219; }
      .quote-t span { display: inline-block; }
      .quote-s { margin-top: 12px; text-align: right; font-family: "Manrope"; font-weight: 800; font-size: 22px;
                 letter-spacing: 0.1em; text-transform: uppercase; color: #6A5A44; }
      /* портреты — на груди парой, ниже подбородка: лицо в этом дубле крупное и в верхних углах
         карточки его закрывали (verify_page: подбородок до y 1219) */
      #c-euler, #c-desc { top: 1245px; width: 270px; padding: 12px 12px 10px; }
      #c-euler { left: 560px; } #c-desc { left: 250px; }
      #c-euler .ph, #c-euler img, #c-desc .ph, #c-desc img { width: 246px; height: 200px; }
      #c-euler img, #c-eul0 img { object-position: 45% 30%; }
      #c-eul0, #c-ball { top: 1240px; left: 370px; width: 340px; padding: 14px 14px 12px; }
      #c-eul0 .ph, #c-eul0 img { width: 312px; height: 290px; }
      #c-ball .ph, #c-ball img { width: 312px; height: 300px; }
      #c-ball img { object-position: 50% 4%; }
      #c-eul0 .card-name, #c-ball .card-name { font-size: 22px; margin-top: 8px; }
      #c-eul0 .card-sub, #c-ball .card-sub { font-size: 22px; }
      #c-euler .card-name, #c-desc .card-name { font-size: 20px; margin-top: 8px; }
      #c-euler .card-sub, #c-desc .card-sub { font-size: 22px; }
      /* v4: подменённый фон за спиной — сверху, низ переходит в родной кадр (там банка и руки) */
      .bg { left: 0; top: 0; width: 1080px; height: 1920px; overflow: hidden;
            -webkit-mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%);
            mask-image: linear-gradient(to bottom, #000 0%, #000 52%, transparent 70%); }
      .bg img { position: absolute; left: -54px; top: -96px; width: 1188px; height: 2112px; object-fit: cover;
                filter: brightness(0.82) contrast(1.05); }
      .bg .vig { position: absolute; inset: 0; background: radial-gradient(ellipse at 50% 38%, rgba(0,0,0,0) 40%, rgba(0,0,0,0.6) 100%); }
      /* v4: карта-маршрут */
      .map { position: absolute; left: 15px; top: 14px; width: 560px; height: 330px; }
      .map svg { position: absolute; left: 0; top: 0; width: 560px; height: 330px; overflow: hidden; }
      .city { position: absolute; opacity: 0; }
      .city .dot { position: absolute; left: -11px; top: -11px; width: 22px; height: 22px; border-radius: 11px;
                   background: var(--cream); box-shadow: 0 0 0 5px rgba(242,235,221,0.18); }
      .city .nm { position: absolute; top: -16px; font-family: "Manrope"; font-weight: 800; font-size: 24px; letter-spacing: 0.08em;
                  text-transform: uppercase; color: var(--cream); white-space: nowrap; text-shadow: 0 2px 8px rgba(0,0,0,0.8); }
      #ct-spb .dot { background: #F5B82E; }
      .yr { position: absolute; left: 18px; top: 8px; opacity: 0; }
      .yr-n { font-family: "Cormorant"; font-weight: 700; font-size: 84px; line-height: 0.95; color: var(--cream);
              font-variant-numeric: lining-nums; }
      .yr-w { font-family: "Manrope"; font-weight: 800; font-size: 22px; letter-spacing: 0.08em; text-transform: uppercase;
              color: rgba(242,235,221,0.85); white-space: nowrap; }
      /* v4: схема «знак → смысл» в ряд */
      #d-sym .sym { font-size: 76px; }
      #d-sym .cell { padding: 6px 2px; }
      .frm { margin-top: 4px; font-family: "Cormorant"; font-style: italic; font-weight: 700; font-size: 30px; color: var(--cream);
             font-variant-numeric: lining-nums; white-space: nowrap; opacity: 0; }
      #d-sym .cell-w { font-size: 18px; margin-top: 6px; }
      /* v4: линия жизни по зрению */
      .lt { position: absolute; left: 30px; top: 92px; width: 530px; height: 24px; border-radius: 12px; background: rgba(242,235,221,0.12); }
      .seg { position: absolute; top: 92px; height: 24px; transform-origin: 0 50%; opacity: 0; }
      .el { position: absolute; top: 46px; text-align: center; font-family: "Manrope"; font-weight: 800; font-size: 22px;
            letter-spacing: 0.08em; text-transform: uppercase; color: rgba(242,235,221,0.85); white-space: nowrap; opacity: 0; }
      .et { position: absolute; top: 130px; font-family: "Cormorant"; font-weight: 700; font-size: 38px; color: var(--cream);
            font-variant-numeric: lining-nums; white-space: nowrap; }
      /* v4: линия времени последнего дня */
      #d-last { padding-left: 76px; }
      #d-last .row { position: relative; justify-content: flex-start; }
      .tl-line { position: absolute; left: 44px; top: 40px; bottom: 40px; width: 4px; border-radius: 2px;
                 background: rgba(242,235,221,0.4); transform-origin: 50% 0; transform: scaleY(0); }
      .tl-dot { position: absolute; left: -42px; top: 50%; width: 20px; height: 20px; margin-top: -10px; border-radius: 10px;
                background: var(--cream); }
'''

PANEL = "left: 245px; width: 590px; padding: 14px 28px;"
SAFE = 'data-safe="лицо важнее серой зоны: плашка ниже подбородка (Валера, 12.10)"'


def bg(bid: str, img: str, place: str = "") -> str:
    """place — своя рамка картинки (left/top/width/height): у гравюр здания в нижней трети листа,
    и кадр «по высоте» уводил их в переход к родному кадру — на экране было одно небо (v4, снимки)."""
    return (f'        <div id="{bid}" class="g bg"><img src="assets/img/{img}" alt="" style="{place}" />'
            '<div class="vig"></div></div>')


# Рамки посчитаны по пропорциям листа: Петербург 3067×1928 → высота 2000, полоса зданий (52–72 % листа)
# встаёт на y 450–850, башня Кунсткамеры (51 %) — у x≈230, левее головы; Берлин 3000×2000 → высота 1700,
# мостовая (70 %) на y≈1150, арсенал (с 68 % листа) — правее головы, x≈700.
SPB_PLACE = "left: -1392px; top: -590px; width: 3181px; height: 2000px;"
BER_PLACE = "left: -1034px; top: -40px; width: 2550px; height: 1700px;"


# v4: камера 1.2 крупнее v3 и наезды до 1.30 — крупные слова выше и чуть мельче, чтобы остаться над макушкой
behind = "\n".join([
    bg("bg-spb", "bg_spb.jpg", SPB_PLACE),
    bg("bg-ber", "bg_berlin.jpg", BER_PLACE),
    bg("bg-lav", "bg_lavra.jpg"),
    '        <div id="b-hook" class="g big" style="top: 300px; font-size: 180px;">'
    + "".join(f'<span id="hs{k}" class="hook-big">{s}</span>' for k, s in enumerate(["f(x)", "e", "i", "Σ"])) + '</div>',
    '        <div id="b-x2-lead" class="g lead" style="top: 264px;">пока все уезжают</div>',
    '        <div id="b-x2" class="g big red" style="top: 304px; font-size: 230px;">×2</div>',
    # кратка «Й» закрывала «Л» подписи (снимок 9.3 с): подпись выше, слово ниже и чуть мельче
    '        <div id="b-eul-lead" class="g lead" style="top: 260px;">Леонард</div>',
    '        <div id="b-eul" class="g big" style="top: 318px; font-size: 200px;">Эйлер</div>',
    '        <div id="b-what" class="g big" style="top: 300px; font-size: 120px;">что оставил?</div>',
    '        <div id="b-31-lead" class="g lead" style="top: 264px;">минус глаз в</div>',
    '        <div id="b-31" class="g big red" style="top: 304px; font-size: 220px;">31 год</div>',
    '        <div id="b-blind" class="g big red" style="top: 296px; font-size: 170px;">вслепую</div>',
])


# ---------- v4: карта-маршрут вместо таблички биографии (годы те же, что в v3) ----------
# Контуры стран — world-atlas 110m (topojson, ISC) из studio/_vendor: считаются здесь в статичный SVG,
# в рендере ничего не грузится и не считается. Равнопромежуточная проекция с поправкой на широту 54°.
MAP_W, MAP_H, LON0, LON1, LAT1 = 560, 330, -2.0, 40.0, 61.2
COS = math.cos(math.radians(54))
K = MAP_W / ((LON1 - LON0) * COS)


def proj(lon: float, lat: float) -> tuple:
    return (lon - LON0) * COS * K, (LAT1 - lat) * K


def europe_svg() -> str:
    topo = json.loads((ROOT / "studio/_vendor/countries-110m.json").read_text(encoding="utf-8"))
    tr = topo.get("transform")
    arcs = []
    for arc in topo["arcs"]:
        pts, x, y = [], 0, 0
        for p in arc:
            if tr:                                   # квантованные дуги: дельты от прошлой точки
                x, y = x + p[0], y + p[1]
                pts.append((x * tr["scale"][0] + tr["translate"][0], y * tr["scale"][1] + tr["translate"][1]))
            else:
                pts.append((p[0], p[1]))
        arcs.append(pts)

    def ring(ids):
        out = []
        for a in ids:
            pts = arcs[a] if a >= 0 else arcs[~a][::-1]
            out += pts if not out else pts[1:]
        return out

    paths = []
    for g in topo["objects"]["countries"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        for poly in polys:
            for ids in poly:
                xy = [proj(lon, lat) for lon, lat in ring(ids)]
                if not any(-80 < x < MAP_W + 80 and -80 < y < MAP_H + 80 for x, y in xy):
                    continue
                d, last = [], None
                for x, y in xy:
                    if last and abs(x - last[0]) + abs(y - last[1]) < 1.5:
                        continue
                    d.append(f"{x:.1f} {y:.1f}")
                    last = (x, y)
                if len(d) > 2:
                    paths.append("M" + " L".join(d) + "Z")
    if not paths:
        raise ValueError("карта Европы пустая: в countries-110m.json не нашлось контуров в рамке")
    return (f'<path d="{" ".join(paths)}" fill="rgba(242,235,221,0.10)" stroke="rgba(242,235,221,0.32)" '
            'stroke-width="1.2" stroke-linejoin="round" />')


CITY = {"bas": (7.59, 47.56), "ber": (13.40, 52.52), "spb": (30.32, 59.94)}
P = {k: proj(*v) for k, v in CITY.items()}


def arc(aid: str, a: str, b: str, ctrl: tuple, color: str) -> str:
    (x0, y0), (x1, y1) = P[a], P[b]
    return (f'<path id="{aid}" d="M {x0:.1f} {y0:.1f} Q {ctrl[0]} {ctrl[1]} {x1:.1f} {y1:.1f}" fill="none" stroke="{color}" '
            'stroke-width="6" stroke-linecap="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1" />')


def city(cid: str, key: str, name: str, dx: int, dy: int) -> str:
    x, y = P[key]
    return (f'<div id="ct-{cid}" class="city" style="left: {x:.0f}px; top: {y:.0f}px;"><div class="dot"></div>'
            f'<div class="nm" style="left: {dx}px; top: {dy}px;">{name}</div></div>')


# подписи короткие: длинные «… — Петербург» налезали на подпись города (снимки 12.9 и 16.9 с)
YEARS = [("1727", "в 20 лет", ""), ("1741", "через 14 лет", ""),
         ("1766", "снова Петербург", "color: var(--red);"), ("1783", "до смерти", "")]
bio = ('        <div id="d-map" class="g panel" ' + SAFE + ' style="' + PANEL.replace("padding: 14px 28px;", "")
       + ' top: 1240px; height: 358px;">\n          <div class="map">\n'
       f'            <svg viewBox="0 0 {MAP_W} {MAP_H}">{europe_svg()}\n'
       f'              {arc("arc1", "bas", "spb", (360, 250), "#F5B82E")}\n'
       f'              {arc("arc2", "spb", "ber", (300, 40), "#F2EBDD")}\n'
       f'              {arc("arc3", "ber", "spb", (330, 160), "#F0352C")}\n            </svg>\n'
       f'            {city("bas", "bas", "Базель", 20, -16)}\n'
       f'            {city("ber", "ber", "Берлин", -126, -16)}\n'
       f'            {city("spb", "spb", "Петербург", -170, -14)}\n'
       + "".join(f'            <div id="yr{k}" class="yr"><div class="yr-n">{n}</div><div class="yr-w" style="{c}">{w}</div></div>\n'
                 for k, (n, w, c) in enumerate(YEARS))
       + '          </div>\n        </div>')

# ---------- v4: значки — схема в ряд «знак → смысл» (сетка 2×2 из v3 уходила под ник) ----------
SIGNS = [("f(x)", "y = f(x)", "функция"), ("e", "e ≈ 2,718", "основание ln"),
         ("i", "i² = −1", "мнимая единица"), ("Σ", "a₁ + a₂ + …", "знак суммы")]
marks = ('        <div id="d-sym" class="g panel" ' + SAFE + ' style="' + PANEL.replace("padding: 14px 28px;", "")
         # verify_page: на «знак суммы» подбородок доходит до y 1302 — верх схемы ≥ 1322
         + ' top: 1325px; padding: 14px 8px 16px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 0 4px;">\n'
         + "\n".join(f'          <div id="m{k + 1}" class="cell"><div class="sym">{s}</div><div id="mf{k + 1}" class="frm">{f}</div>'
                     f'<div class="cell-w">{w}</div></div>' for k, (s, f, w) in enumerate(SIGNS))
         + '\n        </div>')

# ---------- v4: линия жизни по зрению: 1707 — 31 год (~1738) — к старости (~1771) — 1783 ----------
def yx(year: float) -> float:
    return 30 + (year - 1707) / (1783 - 1707) * 530


X38, X71 = yx(1738), yx(1771)
eye = ('        <div id="d-eye" class="g panel" ' + SAFE + ' style="left: 245px; width: 590px; top: 1250px; height: 196px;">\n'
       '          <div class="lt"></div>\n'
       f'          <div id="e1" class="seg" style="left: 30px; width: {X38 - 30:.0f}px; background: var(--cream); border-radius: 12px 0 0 12px;"></div>\n'
       f'          <div id="e2" class="seg" style="left: {X38:.0f}px; width: {X71 - X38:.0f}px; background: #F5B82E;"></div>\n'
       f'          <div id="e3" class="seg" style="left: {X71:.0f}px; width: {560 - X71:.0f}px; background: var(--red); border-radius: 0 12px 12px 0;"></div>\n'
       f'          <div id="el1" class="el" style="left: 30px; width: {X38 - 30:.0f}px;">два глаза</div>\n'
       f'          <div id="el2" class="el" style="left: {X38:.0f}px; width: {X71 - X38:.0f}px; color: #F5B82E;">один глаз</div>\n'
       f'          <div id="el3" class="el" style="left: {X71 - 30:.0f}px; width: {590 - X71:.0f}px; color: var(--red);">ослеп</div>\n'
       f'          <div id="emk" class="g" style="left: {X38 - 2:.0f}px; top: 80px; width: 4px; height: 52px; background: var(--cream);"></div>\n'
       '          <div class="et" style="left: 30px;">1707</div>\n'
       f'          <div id="et2" class="g et" style="left: {X38 - 60:.0f}px; width: 120px; text-align: center; color: #F5B82E;">31 год</div>\n'
       '          <div id="et3" class="g et" style="left: 470px; width: 90px; text-align: right;">1783</div>\n'
       '        </div>')

work = ('        <div id="d-work" class="g panel" ' + SAFE + ' style="' + PANEL + ' top: 1240px;">\n'
        '          <div id="w1" class="row"><span class="row-w" style="font-size: 38px; color: var(--cream);">диктовал помощникам</span></div>\n'
        '          <div id="w2" class="row"><span class="row-w" style="font-size: 38px; color: #F5B82E;">считал в уме</span></div>\n'
        '        </div>')

# воздушный шар 1783: рисованный, поднимается на «как высоко поднимается»
balloon = ('        <svg id="balloon" class="g" viewBox="0 0 220 300" style="left: 770px; top: 360px; width: 210px; height: 286px;">\n'
           '          <path d="M110 10 C 40 10 10 70 20 130 C 30 180 80 210 92 232 L 128 232 C 140 210 190 180 200 130 '
           'C 210 70 180 10 110 10 Z" fill="#D9A441" stroke="#7A2E1E" stroke-width="5" />\n'
           '          <path d="M110 10 C 85 60 85 180 96 232 M110 10 C 135 60 135 180 124 232 M24 110 H 196" '
           'fill="none" stroke="#7A2E1E" stroke-width="4" />\n'
           '          <path d="M96 232 L 92 262 M124 232 L 128 262" stroke="#4A3F30" stroke-width="3" />\n'
           '          <rect x="86" y="262" width="48" height="30" rx="4" fill="#6A4A2C" />\n'
           '        </svg>')

# v4: последний день — линия времени: линия тянется вниз, точки встают по словам, последняя красная
last = ('        <div id="d-last" class="g panel" ' + SAFE + ' style="' + PANEL + ' top: 1230px;">\n'
        '          <div id="l-line" class="tl-line"></div>\n'
        '          <div id="l1" class="row"><span class="tl-dot"></span><span class="row-w" style="font-size: 38px; color: var(--cream);">пообедал</span></div>\n'
        '          <div id="l2" class="row"><span class="tl-dot"></span><span class="row-w" style="font-size: 38px; color: var(--cream);">поиграл с внуком</span></div>\n'
        '          <div id="l3" class="row"><span class="tl-dot" style="background: var(--red);"></span><span class="row-w" style="font-size: 38px; color: var(--red);">«я умираю»</span></div>\n'
        '        </div>')

quote = ('        <div id="d-quote" class="g quote" ' + SAFE + ' style="left: 245px; top: 1230px; width: 590px;">\n'
         '          <div class="quote-t">«Он перестал <span id="q1">вычислять</span> и <span id="q2">жить</span>»</div>\n'
         '          <div class="quote-s">Кондорсе, 1783</div>\n'
         '        </div>')

front = "\n".join([
    '        <div id="st-one" class="g sticker" style="left: 330px; top: 290px; font-size: 56px; white-space: nowrap;">один человек</div>',
    '        <div id="st-ch" class="g sticker" style="left: 300px; top: 290px; font-size: 56px; white-space: nowrap;">'
    '<span class="flag-ch"></span>швейцарец</div>',
    bio,
    '        <div id="st-na" class="g stamp" style="left: 330px; top: 290px; font-size: 76px; white-space: nowrap;">на, а не в</div>',
    '        <div id="st-lavra" class="g sticker" style="left: 160px; top: 290px; font-size: 50px; white-space: nowrap;">Александро-Невская лавра</div>',
    card("c-eul0", "euler.jpg", "Леонард Эйлер", "1707–1783", side="right").replace('class="g card', SAFE + ' class="g card', 1),
    card("c-euler", "euler.jpg", "Леонард Эйлер", "висит в кабинете", side="right").replace('class="g card', SAFE + ' class="g card', 1),
    card("c-desc", "descartes.jpg", "Рене Декарт", "сосед по стене", side="left").replace('class="g card', SAFE + ' class="g card', 1),
    marks,
    '        <div id="st-pop" class="g sticker" style="left: 250px; top: 290px; font-size: 54px; white-space: nowrap;">сделал популярными</div>',
    eye,
    '        <div id="st-blind" class="g stamp" style="left: 380px; top: 290px; font-size: 76px; white-space: nowrap;">ослеп</div>',
    work,
    card("c-ball", "balloon.jpg", "первый полёт", "Анноне, июнь 1783", side="right").replace('class="g card', SAFE + ' class="g card', 1),
    '        <div id="st-1783" class="g sticker" style="left: 180px; top: 290px; font-size: 50px; white-space: nowrap;">1783 — только изобрели</div>',
    last,
    quote,
    '        <div id="st-hard" class="g sticker" style="left: 380px; top: 290px; font-size: 60px; white-space: nowrap;">тяжело?</div>',
])

# 800 работ: число набегает за спиной крупно, человек из вырезки поверх. Свой счётчик, а не
# count-up каталога: тот в полосе над головой вышел крошечным (v1 — по сетке кадров), как в IMG_1803.
# Цифры сменяются через set — покадровый рендер видит то же, что и снимок.
WORKS = ["0", "40", "130", "270", "420", "560", "670", "750", "790", "800+"]
W_AT, W_STEP = t(40.88) - 0.15, 0.06
works_html = ('        <div id="b-works" class="g big" style="top: 304px; font-size: 210px;">'
              + "".join(f'<span id="wk{k}" style="position: absolute; left: 0; width: 1080px; opacity: 0;">{v}</span>'
                        for k, v in enumerate(WORKS))
              + '<span style="visibility: hidden;">800+</span></div>\n'
              '        <div id="b-works-lab" class="g lead" style="top: 264px;">написал больше</div>')
works_js = "\n".join(
    [f'      tl.set("#wk{k}", {{ opacity: 1 }}, {W_AT + k * W_STEP:.2f});' for k in range(len(WORKS))]
    + [f'      tl.set("#wk{k}", {{ opacity: 0 }}, {W_AT + (k + 1) * W_STEP:.2f});' for k in range(len(WORKS) - 1)]
    + [f'      enter("#b-works", {W_AT:.2f}, {{ fromScale: 1.3, dur: 0.2 }});',
       f'      enter("#b-works-lab", {W_AT + 0.30:.2f}, {{ fromScale: 0.9, dur: 0.25 }});',
       f'      leave(["#b-works", "#b-works-lab"], {t(43.55)}, {{ y: -60 }});'])

def bg_in(sel: str, a: float, b: float) -> str:
    """Фон наплывом со смазом, медленный наезд внутри, уход со смазом; на показе резкий (как IMG_1821)."""
    return (f'      tl.fromTo("{sel}", {{ opacity: 0, scale: 1.08, filter: BLUR(14) }}, '
            f'{{ opacity: 1, scale: 1, filter: BLUR(0), duration: 0.45, ease: "power2.out" }}, {a});\n'
            f'      tl.fromTo("{sel} img", {{ scale: 1 }}, {{ scale: 1.06, duration: {b - a + 0.35:.2f}, ease: "none" }}, {a});\n'
            f'      tl.to("{sel}", {{ opacity: 0, scale: 1.04, filter: BLUR(12), duration: 0.35, ease: "power2.in" }}, {b});')


def swap(a: str, b: str, at: float) -> str:
    """Год на карте сменяется следующим: старый уходит вверх со смазом, новый встаёт."""
    return (f'      tl.to("{a}", {{ opacity: 0, y: -30, filter: BLUR(10), duration: 0.18, ease: "power2.in" }}, {at});\n'
            f'      tl.fromTo("{b}", {{ opacity: 0, y: 30, filter: BLUR(10) }}, '
            f'{{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.24, ease: "power3.out" }}, {round(at + 0.12, 2)});')


def pop(sel: str, at: float) -> str:
    return f'      enter("{sel}", {at}, {{ fromScale: 0.3, dur: 0.28 }});'


PANEL_IN = '{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }'
FRM_IN = '{ opacity: 0, y: -18, filter: BLUR(8) }, { opacity: 1, y: 0, filter: BLUR(0), duration: 0.25, ease: "power3.out" }'
SEG_IN = '{ opacity: 0, scaleX: 0 }, { opacity: 1, scaleX: 1, ease: "power2.out"'

beats = f'''
      // ---------- хук: половина значков в твоём ЕГЭ — один человек ----------
      tl.set("#b-hook", {{ opacity: 1 }}, {t(0.55)});
      slam("#hs0", {t(0.62)}, {{ fromScale: 1.6 }});
      slam("#hs1", {t(1.00)}, {{ fromScale: 1.6 }});
      slam("#hs2", {t(1.42)}, {{ fromScale: 1.6 }});
      slam("#hs3", {t(1.84)}, {{ fromScale: 1.6 }});
      leave("#b-hook", {t(2.42)}, {{ y: -60 }});
      enter("#st-one", {t(2.56)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-one", {t(3.40)}, {{ y: -30, rot: -10 }});
      enter("#st-ch", {t(3.55)}, {{ fromScale: 0.6, rot: 4 }});
      leave("#st-ch", {t(5.40)}, {{ y: -30, rot: 10 }});

      // ---------- приехал два раза — Леонард Эйлер ----------
      enter("#b-x2-lead", {t(5.90)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-x2", {t(7.30)}, {{ fromScale: 1.5 }});
      leave(["#b-x2", "#b-x2-lead"], {t(8.20)}, {{ y: -60 }});
      enter("#b-eul-lead", {t(8.62)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-eul", {t(9.18)}, {{ fromScale: 1.5 }});
      leave(["#b-eul", "#b-eul-lead"], {t(9.95)}, {{ y: -60 }});
      card("#c-eul0", {t(8.70)}, {t(9.85)}, "right");

      // ---------- биография картой: Базель → Петербург (1727) → Берлин (1741) → Петербург (1766) ----------
      enter("#d-map", {t(9.95)}, {PANEL_IN});
      tl.fromTo("#yr0", {{ opacity: 0, y: 30, filter: BLUR(10) }}, {{ opacity: 1, y: 0, filter: BLUR(0), duration: 0.25, ease: "power3.out" }}, {t(10.05)});
{pop("#ct-bas", t(10.15))}
      draw("#arc1", {t(11.70)}, 0.6);
{pop("#ct-spb", t(12.24))}
{bg_in("#bg-spb", t(11.55), t(14.55))}
      slam("#st-na", {t(13.40)}, {{ fromScale: 1.6, rot: -5 }});
      leave("#st-na", {t(14.30)}, {{ y: -30, rot: -12 }});
{swap("#yr0", "#yr1", t(15.20))}
{bg_in("#bg-ber", t(15.95), t(17.45))}
      draw("#arc2", {t(16.15)}, 0.45);
{pop("#ct-ber", t(16.54))}
{swap("#yr1", "#yr2", t(17.20))}
      draw("#arc3", {t(17.30)}, 0.5);
      tl.fromTo("#ct-spb .dot", {{ scale: 1 }}, {{ scale: 1.7, duration: 0.18, yoyo: true, repeat: 1, ease: "sine.inOut", immediateRender: false }}, {t(17.85)});
{swap("#yr2", "#yr3", t(18.40))}
      leave("#d-map", {t(19.30)}, {{ y: 80 }});
{bg_in("#bg-lav", t(18.95), t(21.45))}
      enter("#st-lavra", {t(20.26)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-lavra", {t(21.40)}, {{ y: -30, rot: -10 }});

      // ---------- висит в кабинете математички, рядом с Декартом ----------
      card("#c-euler", {t(21.58)}, {t(26.40)}, "right");
      card("#c-desc", {t(24.82)}, {t(26.40)}, "left");

      // ---------- что он нам оставил: f(x), e, i, Σ ----------
      slam("#b-what", {t(27.16)}, {{ fromScale: 1.5 }});
      leave("#b-what", {t(27.80)}, {{ y: -60 }});
      enter("#d-sym", {t(27.70)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#m1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(27.76)});
      tl.fromTo("#mf1", {FRM_IN}, {t(28.90)});
      tl.fromTo("#m2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(30.04)});
      tl.fromTo("#mf2", {FRM_IN}, {t(31.00)});
      tl.fromTo("#m3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(32.32)});
      tl.fromTo("#mf3", {FRM_IN}, {t(32.80)});
      tl.fromTo("#m4", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(34.00)});
      tl.fromTo("#mf4", {FRM_IN}, {t(34.94)});
      leave("#d-sym", {t(35.60)}, {{ y: 80 }});
      enter("#st-pop", {t(37.08)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-pop", {t(39.50)}, {{ y: -30, rot: -10 }});

      // ---------- 800 работ, глаз в 31, ослеп ----------
      enter("#b-31-lead", {t(43.86)}, {{ fromScale: 0.9, dur: 0.25 }});
      slam("#b-31", {t(44.40)}, {{ fromScale: 1.5 }});
      leave(["#b-31", "#b-31-lead"], {t(45.70)}, {{ y: -60 }});
      // линия жизни по зрению: два глаза → с 31 года один → к старости ослеп
      enter("#d-eye", {t(44.30)}, {PANEL_IN});
      tl.fromTo("#e1", {SEG_IN}, duration: 0.4 }}, {t(44.40)});
      enter("#el1", {t(44.45)}, {{ fromScale: 0.8, dur: 0.22 }});
      slam("#emk", {t(44.50)}, {{ fromScale: 1.8 }});
      slam("#et2", {t(44.50)}, {{ fromScale: 1.6 }});
      tl.fromTo("#e2", {SEG_IN}, duration: 1.2 }}, {t(45.10)});
      enter("#el2", {t(45.30)}, {{ fromScale: 0.8, dur: 0.22 }});
      tl.fromTo("#e3", {SEG_IN}, duration: 0.5 }}, {t(46.40)});
      enter("#et3", {t(46.50)}, {{ fromScale: 0.8, dur: 0.22 }});
      slam("#el3", {t(47.02)}, {{ fromScale: 1.6 }});
      slam("#st-blind", {t(47.02)}, {{ fromScale: 1.6, rot: 4 }});
      leave("#st-blind", {t(48.00)}, {{ y: -30, rot: 12 }});
      leave("#d-eye", {t(48.85)}, {{ y: 80 }});
      enter("#d-work", {t(49.06)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#w1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(49.10)});
      tl.fromTo("#w2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(50.32)});
      leave("#d-work", {t(51.40)}, {{ y: 80 }});

      // ---------- последний день: воздушный шар ----------
      card("#c-ball", {t(53.46)}, {t(56.62)}, "right");
      enter("#st-1783", {t(55.44)}, {{ fromScale: 0.6, rot: -3 }});
      leave("#st-1783", {t(56.80)}, {{ y: -30, rot: -10 }});
      enter("#d-last", {t(56.95)}, {{ fromY: 140, fromScale: 0.92, dur: 0.4, ease: "power3.out" }});
      tl.fromTo("#l-line", {{ scaleY: 0 }}, {{ scaleY: 1, duration: 2.5, ease: "none", immediateRender: false }}, {t(57.00)});
      tl.fromTo("#l1", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(57.00)});
      tl.fromTo("#l2", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(57.98)});
      tl.fromTo("#l3", {{ opacity: 0, x: -30 }}, {{ opacity: 1, x: 0, duration: 0.2, ease: "power2.out" }}, {t(59.28)});
      leave("#d-last", {t(60.70)}, {{ y: 80 }});

      // ---------- «он перестал вычислять и жить» — именно в таком порядке ----------
      doc("#d-quote", {t(61.86)}, {t(65.40)}, {{ rot: -1 }});
      tl.to("#q1", {{ color: "#F0352C", scale: 1.08, duration: 0.2, ease: "back.out(2)" }}, {t(64.50)});
      tl.to("#q2", {{ color: "#F0352C", scale: 1.08, duration: 0.2, ease: "back.out(2)" }}, {t(64.84)});

      // ---------- финал: тяжело? — человек решал почти вслепую ----------
      enter("#st-hard", {t(68.38)}, {{ fromScale: 0.6, rot: -4 }});
      leave("#st-hard", {t(69.90)}, {{ y: -30, rot: -10 }});
      slam("#b-blind", {t(71.86)}, {{ fromScale: 1.6 }});
      flash({t(71.86)});
      leave("#b-blind", {t(72.70)}, {{ y: -60 }});
'''
behind += "\n" + works_html
beats += works_js + "\n"

# Звуки — мало (бриф: few), по правилам 12.10: удары только на главном (ЭЙЛЕР, 800, ВСЛЕПУЮ),
# семейства не подряд, каждый файл ≤ 2 раз, между звуками ≥ 1 с.
sounds = [
    audio("hook", "whoosh", t(0.58), 0.8),
    audio("eul", "impact-bass-1", t(9.16), 0.9),
    audio("na", "click", t(13.38), 0.8),
    audio("desc", "pop", t(24.80), 0.8),
    audio("sym", "whoosh", t(27.68), 0.7),
    audio("works", "impact-bass-2", t(40.71), 0.8),
    audio("balloon", "sparkle", t(53.44), 0.6),
    audio("blind", "impact-bass-1", t(71.84), 0.9),
]
# человек поверх слов за спиной: ×2 и ЭЙЛЕР, «что оставил?», 800 + «31 год», ВСЛЕПУЮ
fg = [(t(0.50), t(2.80)), (t(5.85), t(10.25)), (t(11.50), t(14.95)), (t(15.90), t(17.85)), (t(18.90), t(21.85)),
      (t(27.10), t(28.10)), (t(40.60), t(46.00)), (t(71.80), t(73.00))]

# не раньше чем через секунду после удара «вслепую» (71.84): звуки ближе 1 с слипаются
CTA_AT = t(72.95)
page = build_page("Леонард Эйлер", DUR, behind, front, beats, sounds, fg, cta_at=CTA_AT,
                  extra_css=css, cta_small="больше интересной математики — у меня в профиле",
                  fmt=tk.fmt, captions=tk.captions)
out = ROOT / f"studio/{STEM}/index.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(page, encoding="utf-8")

# «F от X» — как функция; «Е» — e и Σ (на это время субтитры и так спрятаны плашкой)
fixes = tk.fixes({79: "f", 81: "x", 85: "e", 86: "", 96: "Σ", 97: ""})

director = {
    "_note": "Эйлер. Время по дублю; раскладка — work/IMG_1810/page.py.",
    # v4: база камеры 1.2 (проект, п.13) — удары выше базы, иначе пропали бы; медленный наезд через мысль:
    # биография, слепота, финал (длинный въезд, max() с ударами — финальный удар поверх наезда)
    "punches": [[t(2.56), t(3.40), 1.27, 0.10], [t(9.18), t(9.95), 1.30, 0.10],
                [t(27.16), t(27.90), 1.27, 0.10], [t(41.30), t(42.20), 1.28, 0.10],
                [t(44.40), t(45.50), 1.28, 0.10], [t(60.66), t(61.20), 1.26, 0.10],
                [t(71.86), t(72.70), 1.30, 0.10],
                [t(9.95), t(19.20), 1.26, 8.0, 0.6], [t(45.50), t(51.30), 1.25, 5.0, 0.5],
                [t(65.50), t(72.70), 1.25, 6.0, 0.6]],
    "text_fixes": fixes,
    "keep_case": ["ЕГЭ", "Россию", "Леонард", "Эйлер", "Эйлер.", "Петербургскую", "Берлин", "Петербурге",
                  "Александро", "-Невской", "Декартом", "Путина"],
    "accent_words": ["Эйлер.", "800", "ослеп.", "вслепую."],
    # плашки на груди стоят на уровне субтитров — на их время субтитров нет
    "hide_captions": [[t(8.62), t(19.60)], [t(21.50), t(26.75)], [t(27.65), t(35.90)], [t(44.25), t(51.70)],
                      [t(53.40), t(61.00)], [t(61.80), t(65.70)], [t(72.70), DUR]],
}
(ROOT / f"work/{STEM}/director.json").write_text(json.dumps(director, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(page.splitlines()), "строк, длина", round(DUR, 2))
