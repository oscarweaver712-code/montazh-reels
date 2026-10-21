"""Доска «Вкудесник» 21.10: четыре направления текста без обводки и без вырезки, по пять кадров."""
from pathlib import Path

HERE = Path(__file__).parent
Y = "#FFD60A"
SOFT = "text-shadow: 0 2px 6px rgba(0,0,0,.28), 0 8px 34px rgba(0,0,0,.38);"
FONTS = {"Jost": [("Jost-Medium", 500), ("Jost-SemiBold", 600), ("Jost-Bold", 700)],
         "Geologica": [("Geologica-Medium", 500), ("Geologica-Bold", 800)],
         "Unbounded": [("Unbounded-Medium", 500), ("Unbounded-SemiBold", 600)],
         "Onest": [("Onest-Medium", 500), ("Onest-SemiBold", 600), ("Onest-Bold", 700)],
         "Golos": [("GolosText-Medium", 500), ("GolosText-DemiBold", 600), ("GolosText-Bold", 700)],
         "Tenor": [("TenorSans-Regular", 400)]}


def box(css: str, body: str) -> str:
    return f'<div style="position:absolute;{css}">{body}</div>'


def t(font: str, w: int, size: int, body: str, extra: str = "") -> str:
    return (f'<div style="font-family:{font};font-weight:{w};font-size:{size}px;line-height:1.02;color:#fff;'
            f'white-space:nowrap;{SOFT}{extra}">{body}</div>')


def sub(font: str, w: int, words: str, hl: str, extra: str = "") -> str:
    body = words.replace(hl, f'<span style="color:{Y}">{hl}</span>')
    return box("left:245px;width:590px;top:1185px;text-align:center",
               f'<div style="font-family:{font};font-weight:{w};font-size:54px;line-height:1.12;color:#fff;{SOFT}{extra}">{body}</div>')


def tag(font: str, w: int, size: int, body: str, rot: float = 0, bg: str = "#fff", fg: str = "#111") -> str:
    return (f'<div style="display:inline-block;font-family:{font};font-weight:{w};font-size:{size}px;line-height:1.08;'
            f'color:{fg};background:{bg};padding:.1em .34em .14em;border-radius:.2em;transform:rotate({rot}deg);'
            f'box-shadow:0 10px 30px rgba(0,0,0,.28);white-space:nowrap">{body}</div>')


SCRIM = '<div style="position:absolute;left:0;top:0;width:1080px;height:900px;background:linear-gradient(rgba(0,0,0,.34),rgba(0,0,0,0))"></div>'
LOW = '<div style="position:absolute;left:0;top:1020px;width:1080px;height:900px;background:linear-gradient(rgba(0,0,0,0),rgba(0,0,0,.30))"></div>'
CAPS = "text-transform:uppercase;"

ROWS = {
    "1 · ФРАЗА — Geologica, фраза слева, акцент начертанием": [
        ("f_0.5", box("left:110px;top:840px",
                      t("Geologica", 500, 112, "устроила", "letter-spacing:-.035em;line-height:.98")
                      + t("Geologica", 500, 112, "команде", "letter-spacing:-.035em;line-height:.98")
                      + t("Geologica", 800, 112, "новоселье", f"letter-spacing:-.035em;line-height:.98;color:{Y}"))),
        ("f_9.2", box("left:110px;top:940px",
                      t("Geologica", 500, 104, "фуршетик,", "letter-spacing:-.035em;line-height:.98")
                      + t("Geologica", 500, 104, "тортик,", "letter-spacing:-.035em;line-height:.98")
                      + t("Geologica", 800, 104, "закусочки", f"letter-spacing:-.035em;line-height:.98;color:{Y}"))),
        ("f_34.3", SCRIM + box("left:110px;top:300px",
                               t("Geologica", 500, 104, "офис просто", "letter-spacing:-.035em;line-height:.98")
                               + t("Geologica", 500, 104, "очень", "letter-spacing:-.035em;line-height:.98")
                               + t("Geologica", 800, 104, "стильный", f"letter-spacing:-.035em;line-height:.98;color:{Y}"))),
        ("f_55.6", LOW + sub("Geologica", 500, "Желаю этому сезону", "сезону")),
        ("f_26.7", SCRIM + box("left:110px;top:300px",
                               t("Geologica", 500, 104, "конфеты", "letter-spacing:-.035em;line-height:.98")
                               + t("Geologica", 500, 104, "оказались", "letter-spacing:-.035em;line-height:.98")
                               + t("Geologica", 800, 104, "с ликёром?!", f"letter-spacing:-.035em;line-height:.98;color:{Y}"))),
    ],
    "2 · ШИРОКИЙ — Unbounded + Onest": [
        ("f_0.5", box("left:0;width:1080px;top:860px;text-align:center",
                      t("Onest", 500, 46, "устроила команде")
                      + t("Unbounded", 600, 134, "новоселье", "letter-spacing:-.05em;margin-top:8px"))),
        ("f_9.2", box("left:110px;top:950px",
                      t("Unbounded", 600, 104, "фуршетик,", "letter-spacing:-.05em")
                      + t("Unbounded", 600, 104, "тортик,", "letter-spacing:-.05em;margin-top:4px")
                      + t("Unbounded", 600, 104, "закусочки", f"letter-spacing:-.05em;margin-top:4px;color:{Y}"))),
        ("f_34.3", SCRIM + box("left:0;width:1080px;top:350px;text-align:center",
                               t("Onest", 500, 46, "офис просто очень")
                               + t("Unbounded", 600, 170, "стильно", "letter-spacing:-.05em;margin-top:6px"))),
        ("f_55.6", LOW + sub("Onest", 600, "Желаю этому сезону", "сезону")),
        ("f_26.7", SCRIM + box("left:0;width:1080px;top:330px;text-align:center",
                               t("Onest", 500, 50, "конфеты оказались")
                               + t("Unbounded", 600, 136, "с ликёром?!", f"color:{Y};letter-spacing:-.05em;margin-top:8px"))),
    ],
    "3 · ЯРЛЫКИ — Golos на плашках, как текст Instagram": [
        ("f_0.5", box("left:0;width:1080px;top:860px;text-align:center",
                      tag("Golos", 500, 46, "устроила команде", -2) + "<br>"
                      + f'<div style="margin-top:14px">{tag("Golos", 700, 150, "новоселье", 2)}</div>')),
        ("f_9.2", box("left:110px;top:960px",
                      tag("Golos", 600, 84, "фуршетик", -3) + "<br>"
                      + f'<div style="margin:14px 0 0 60px">{tag("Golos", 600, 84, "тортик", 2)}</div>'
                      + f'<div style="margin:14px 0 0 20px">{tag("Golos", 600, 84, "закусочки", -1.5)}</div>')),
        ("f_34.3", box("left:0;width:1080px;top:360px;text-align:center",
                       tag("Golos", 500, 44, "офис просто очень", -2) + "<br>"
                       + f'<div style="margin-top:14px">{tag("Golos", 700, 160, "стильно", 1.5)}</div>')),
        ("f_55.6", LOW + sub("Golos", 600, "Желаю этому сезону", "сезону")),
        ("f_26.7", box("left:0;width:1080px;top:330px;text-align:center",
                       tag("Golos", 600, 54, "конфеты оказались", -2) + "<br>"
                       + f'<div style="margin-top:14px">{tag("Golos", 700, 128, "с ликёром?!", 2, "#111", Y)}</div>')),
    ],
    "4 · БУТИК — Tenor Sans капсом + Jost": [
        ("f_0.5", box("left:0;width:1080px;top:850px;text-align:center",
                      t("Tenor", 400, 26, "вкудесник", CAPS + "letter-spacing:.6em")
                      + f'<div style="width:120px;height:2px;background:{Y};margin:22px auto 20px"></div>'
                      + t("Tenor", 400, 128, "новоселье", CAPS + "letter-spacing:.04em"))),
        ("f_9.2", LOW + box("left:0;width:1080px;top:1000px;text-align:center",
                      t("Tenor", 400, 64, "фуршетик", CAPS + "letter-spacing:.12em")
                      + t("Tenor", 400, 64, "тортик", CAPS + "letter-spacing:.12em;margin-top:10px")
                      + t("Tenor", 400, 64, "закусочки", CAPS + f"letter-spacing:.12em;margin-top:10px;color:{Y}"))),
        ("f_34.3", SCRIM + box("left:0;width:1080px;top:360px;text-align:center",
                               t("Jost", 500, 40, "офис просто очень")
                               + t("Tenor", 400, 170, "стильно", CAPS + "letter-spacing:.05em;margin-top:10px"))),
        ("f_55.6", LOW + sub("Jost", 500, "Желаю этому сезону", "сезону")),
        ("f_26.7", SCRIM + box("left:0;width:1080px;top:340px;text-align:center",
                               t("Tenor", 400, 44, "конфеты оказались", CAPS + "letter-spacing:.3em")
                               + t("Tenor", 400, 104, "с ликёром?!", CAPS + f"letter-spacing:.06em;margin-top:16px;color:{Y}"))),
    ],
}

faces = "".join(f'@font-face {{ font-family: "{fam}"; src: url("assets/fonts/{f}.ttf"); font-weight: {w}; }}\n'
                for fam, lst in FONTS.items() for f, w in lst)
scenes, sets = [], []
k = 0
for row in ROWS.values():
    for img, html in row:
        scenes.append(f'<div class="s" id="s{k}"><img class="L" src="assets/{img}.jpg">{html}</div>')
        sets.append(f'tl.set("#s{k}",{{opacity:1}},{k});tl.set("#s{k}",{{opacity:0}},{k}+0.99);')
        k += 1
page = f'''<!doctype html><html lang="ru"><head><meta charset="UTF-8"><script src="assets/gsap.min.js"></script><style>
{faces}html,body{{width:1080px;height:1920px;margin:0;background:#000;overflow:hidden}}
.s{{position:absolute;left:0;top:0;width:1080px;height:1920px;opacity:0}}
.L{{position:absolute;left:0;top:0;width:1080px;height:1920px;object-fit:cover}}
</style></head><body><div id="root" data-composition-id="main" data-start="0" data-duration="{k}" data-width="1080" data-height="1920">
{"".join(scenes)}
</div><script>window.__timelines=window.__timelines||{{}};const tl=gsap.timeline({{paused:true}});
{"".join(sets)}
window.__timelines["main"]=tl;</script></body></html>'''
(HERE / "index.html").write_text(page, encoding="utf-8")
(HERE / "rows.txt").write_text("\n".join(ROWS), encoding="utf-8")
print(k, "кадров:", ",".join(f"{i + 0.5}" for i in range(k)))
