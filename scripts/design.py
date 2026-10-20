#!/usr/bin/env python3
"""Дизайн-система проекта: projects/<проект>/DESIGN.md — токены и правила одним файлом (20.10.2026).

Валера 20.10.2026: «один раз собрать идеальную — шрифты и т. п. — как будто делает профессиональный
постановщик-дизайнер». Формат — design.md (google-labs-code, Apache-2.0): токены в шапке YAML (цвета, градиент,
шрифты по ролям, компоненты, движение), ниже правила словами — их читают и люди, и аналитик. Код берёт значения
отсюда, а не из своих констант:

  сборка (montage.py)   → CSS системы поверх kit: шрифты ролей, цвета вместо --cream/--red/--ink, субтитры с
                          маркером, подписи «Чертежа» рукой; JS вылетов (буквы дымом и рукой, маркер, квадраты, ручка);
  партитура (score.py)  → приёмы системы hand, number, promise, strike; крупное слово — буквами из дыма;
  verify_page           → цвет или шрифт мимо DESIGN.md на странице — провал (страница помечена reels-design).

Проекта без DESIGN.md всё это не касается: страница собирается как раньше.

  .venv/bin/python scripts/design.py antishkola          # проверить DESIGN.md и показать токены
"""
import argparse
import html
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT  # noqa: E402

FONT_DIR = ROOT / "presets" / "fonts"
PROJECTS_DIR = ROOT / "projects"
FILE = "DESIGN.md"
MARK = "reels-design"
COLORS = ("text", "plate", "pen", "accent", "on-accent", "flash", "shade")
ROLES = ("caption", "whisper", "headline", "number", "hand", "variable")
W = 1080
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_STOP = re.compile(r"(#[0-9A-Fa-f]{6})\s+(-?[\d.]+)%")
_ANGLE = re.compile(r"^linear-gradient\(\s*(-?[\d.]+)deg\s*,")
_REF = re.compile(r"^\{(colors|gradients)\.([\w-]+)\}$")
# запас по бокам у буквы, которая движется своим слоем: у Caveat штрих шире ячейки буквы, и Chrome срезает слой по ней
# (Валера 20.10.2026 на доске: «буквы откусаны слева справа»); поля и минус-поля строку не двигают
LETTER_PAD = 0.14


class DesignError(ValueError):
    """DESIGN.md с ошибкой — по-русски, с местом: человек или ИИ правит по этому тексту."""


def _rgb(hex_: str) -> tuple:
    return tuple(int(hex_[i:i + 2], 16) for i in (1, 3, 5))


def _rgba(hex_: str, alpha: float) -> str:
    r, g, b = _rgb(hex_)
    return f"rgba({r},{g},{b},{alpha:g})"


def _front_matter(text: str, where: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise DesignError(f"{where}: нет шапки с токенами — файл начинается со строки «---», токены YAML, снова «---»")
    for k, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return "\n".join(lines[1:k])
    raise DesignError(f"{where}: шапка токенов не закрыта второй строкой «---»")


class Design:
    """Токены DESIGN.md проекта, проверенные целиком: ошибки — одним списком, а не по одной за запуск."""

    def __init__(self, path: Path, project: str):
        import yaml
        self.path, self.project = Path(path), project
        where = f"projects/{project}/{FILE}"
        text = self.path.read_text(encoding="utf-8")
        try:
            tokens = yaml.safe_load(_front_matter(text, where))
        except yaml.YAMLError as e:
            raise DesignError(f"{where}: шапка не читается как YAML — {e}") from None
        if not isinstance(tokens, dict):
            raise DesignError(f"{where}: в шапке нет токенов (colors, gradients, typography, components)")
        self.tokens, self.body = tokens, text.split("---", 2)[2].strip() if text.count("---") >= 2 else ""
        errs = []

        colors = tokens.get("colors") or {}
        self.colors = {}
        for name in COLORS:
            value = colors.get(name)
            if not isinstance(value, str) or not _HEX.match(value):
                errs.append(f"colors.{name}: нужен цвет вида \"#RRGGBB\", а не {value!r}")
            else:
                self.colors[name] = value.upper()

        grad = (tokens.get("gradients") or {}).get("accent")
        self.gradient, self.stops, self.angle = "", [], 90.0
        if not isinstance(grad, str) or not _ANGLE.match(grad.strip()):
            errs.append(f"gradients.accent: нужен \"linear-gradient(165deg, #RRGGBB 0%, …, #RRGGBB 100%)\", а не {grad!r}")
        else:
            self.gradient = grad.strip()
            self.angle = float(_ANGLE.match(self.gradient).group(1))
            self.stops = [(h.upper(), float(p) / 100) for h, p in _STOP.findall(self.gradient)]
            if len(self.stops) < 2 or any(b[1] < a[1] for a, b in zip(self.stops, self.stops[1:])):
                errs.append(f"gradients.accent: точки «#RRGGBB N%» — от двух, по возрастанию процентов: {self.gradient}")

        typo = tokens.get("typography") or {}
        self.fonts = {}
        for role in ROLES:
            spec = typo.get(role)
            if not isinstance(spec, dict):
                errs.append(f"typography.{role}: роли нет — нужны {', '.join(ROLES)} (fontFamily, fontWeight, src)")
                continue
            family, weight, src = spec.get("fontFamily"), spec.get("fontWeight"), spec.get("src")
            style = spec.get("fontStyle", "normal")
            if not isinstance(family, str) or not family.strip():
                errs.append(f"typography.{role}.fontFamily: нужно имя шрифта")
            if not isinstance(weight, int) or not 100 <= weight <= 900:
                errs.append(f"typography.{role}.fontWeight: число 100–900, а не {weight!r}")
            if style not in ("normal", "italic"):
                errs.append(f"typography.{role}.fontStyle: normal или italic, а не {style!r}")
            if not isinstance(src, str) or not (FONT_DIR / src).is_file():
                errs.append(f"typography.{role}.src: файла {src!r} нет в presets/fonts — положи туда шрифт (OFL)")
            elif not _cyrillic(FONT_DIR / src):
                errs.append(f"typography.{role}.src: в {src} нет кириллицы — русские буквы выйдут квадратами")
            if not errs or all(not e.startswith(f"typography.{role}") for e in errs):
                self.fonts[role] = {"family": family.strip(), "weight": weight, "style": style, "src": src}

        comp = tokens.get("components") or {}
        cap = comp.get("caption") or {}
        self.accent_scale = cap.get("accentScale", 1.15)
        if not isinstance(self.accent_scale, (int, float)) or not 1.0 <= self.accent_scale <= 1.6:
            errs.append(f"components.caption.accentScale: 1.0–1.6, а не {self.accent_scale!r}")
        self.sweep = (comp.get("marker") or {}).get("sweep", 0.22)
        if not isinstance(self.sweep, (int, float)) or not 0.08 <= self.sweep <= 0.6:
            errs.append(f"components.marker.sweep: секунды 0.08–0.6, а не {self.sweep!r}")
        for cname, fields in comp.items():                        # ссылки {colors.x} и {gradients.x} ведут в токены
            for field, value in (fields or {}).items() if isinstance(fields, dict) else ():
                if isinstance(value, str) and value.startswith("{"):
                    found = _REF.match(value)
                    group = (tokens.get(found.group(1)) or {}) if found else {}
                    if not found or found.group(2) not in group:
                        errs.append(f"components.{cname}.{field}: ссылка {value} никуда не ведёт")

        motion = tokens.get("motion") or {}
        self.enter = str(motion.get("enter", "expo.out"))
        self.letter_stagger = motion.get("letterStagger", 0.04)
        self.hand_stagger = motion.get("handStagger", 0.028)
        for key, value in (("letterStagger", self.letter_stagger), ("handStagger", self.hand_stagger)):
            if not isinstance(value, (int, float)) or not 0.005 <= value <= 0.12:
                errs.append(f"motion.{key}: секунды 0.005–0.12, а не {value!r}")
        if motion.get("bounce") or "back" in self.enter or "elastic" in self.enter or "bounce" in self.enter:
            errs.append(f"motion: отскоки и «желе» системе запрещены (enter {self.enter}) — expo.out или power")

        # ИИ-клипы: один стиль на все генерации проекта (footage.py дописывает замок к промптам, рамка листа — saturate)
        foot = tokens.get("footage") or {}
        self.footage = {}
        if foot:
            for key in ("style", "motion"):
                if not isinstance(foot.get(key), str) or len(foot[key].strip()) < 40:
                    errs.append(f"footage.{key}: замок стиля ИИ-клипов — строкой по-английски, от 40 знаков")
            sat = foot.get("saturate", 0.55)
            if not isinstance(sat, (int, float)) or not 0.2 <= sat <= 1.2:
                errs.append(f"footage.saturate: 0.2–1.2 (насыщенность клипа в рамке листа), а не {sat!r}")
            if not errs or all(not e.startswith("footage") for e in errs):
                self.footage = {"name": str(foot.get("name") or ""), "style": " ".join(foot["style"].split()),
                                "motion": " ".join(foot["motion"].split()), "saturate": float(sat)}
        if errs:
            raise DesignError(f"{where}:\n  " + "\n  ".join(errs))

    # ---------------------------------------------------------------- для страницы

    def family(self, role: str) -> str:
        return self.fonts[role]["family"]

    def allowed(self) -> dict:
        """Что можно на странице: цвета (любой прозрачности) и семейства шрифтов — для проверки verify_page."""
        hexes = list(self.colors.values()) + [h for h, _ in self.stops]
        return {"colors": [list(_rgb(h)) for h in dict.fromkeys(hexes)],
                "fonts": sorted({f["family"] for f in self.fonts.values()}),
                "project": self.project}

    def brief(self) -> str:
        """Что аналитик и критик знают о системе: приёмы системы в форме партитуры и правила словами из DESIGN.md."""
        return "\n".join([
            f"ДИЗАЙН-СИСТЕМА ПРОЕКТА (projects/{self.project}/{FILE} — главнее общих слов про цвет и шрифты выше):",
            "Сборка сама ставит шрифты, цвета, маркер ключевых слов субтитров и вылеты; ты выбираешь приёмы и слова.",
            "Акцент системы — градиент из DESIGN.md (маркер, числа, квадраты, штамп); \"red\" у приёмов «Чертежа» (write, "
            "hexes, маршрут) — этот же акцент на главном. Одно акцентное пятно за раз. У word \"red\" не ставь.",
            "Приёмы системы (кроме общих):",
            '- {"kind": "hand", "w": [от, до], "text": "тут все ошибаются", "line": true} — пометка рукой над головой, '
            'по буквам; "line" — подчерк акцентом. До 26 знаков. В середине ролика к месту; хук рукой не пиши '
            '(Валера 20.10: «выглядит сомнительно»).',
            '- {"kind": "number", "w": [от, до], "at": номер, "text": "2/3", "sub": "шанс, что другая быстрее"} — число '
            'акцентом над головой, бьёт на «at»; "sub" — шёпотом над ним (над головой тесно — без "sub"). До 7 знаков. '
            'Субтитры этих слов спрятаны сами — окно не длиннее 2,5 с.',
            '- {"kind": "promise", "w": [от, до], "title": "3 причины", "rows": [{"text": "вероятность", "w": номер}, …]} '
            '— список-обещание на груди, 2–4 строки до 24 знаков; квадрат строки заливается акцентом на её слове (по порядку '
            'речи, внутри окна). Держит зрителя до конца: ставь в хуке, если дальше в ролике есть 2–4 пункта.',
            '- {"kind": "strike", "w": [от, до], "at": номер, "text": "проклят"} — миф на груди, красная ручка '
            'зачёркивает его на «at»: «не проклят», «не поможет», неверный шаг.',
            "Хук по системе: первые 3 с — не меньше четырёх событий (word, number, promise, strike, ключевое слово "
            "субтитров, смена плана); рукописью хук не пиши; одно крупное слово word за ролик остаётся правилом.",
            "",
            self.body,
        ])

    def meta(self) -> str:
        return f'<meta name="{MARK}" content="{html.escape(self.project)}" />'

    def captions(self, caps: dict) -> dict:
        """Субтитры стиля в системе: шрифт роли caption, крем, ключевое слово — маркером акцента, а не цветом."""
        caps = dict(caps)
        caps.update(css_font=self.family("caption"), font_weight=self.fonts["caption"]["weight"],
                    color=self.colors["text"], highlight=self.colors["text"], marker=True,
                    marker_sweep=float(self.sweep), accent_scale=float(self.accent_scale))
        return caps

    def defs(self) -> str:
        """Градиент акцента для линий SVG (url(#ds-grad)): направление — как у CSS-градиента, в рамке линии."""
        import math
        a = math.radians(self.angle)
        dx, dy = math.sin(a) / 2, -math.cos(a) / 2
        stops = "".join(f'<stop offset="{p:g}" stop-color="{h}" />' for h, p in self.stops)
        return (f'        <svg width="0" height="0" style="position: absolute;" aria-hidden="true"><defs>'
                f'<linearGradient id="ds-grad" x1="{0.5 - dx:.3f}" y1="{0.5 - dy:.3f}" x2="{0.5 + dx:.3f}" y2="{0.5 + dy:.3f}">'
                f'{stops}</linearGradient></defs></svg>')

    def css(self) -> str:
        c, f = self.colors, self.fonts
        fam = lambda role: f'"{f[role]["family"]}"'                       # noqa: E731
        wt = lambda role: f[role]["weight"]                                # noqa: E731
        faces, seen = [], set()
        for role in ROLES:
            key = (f[role]["family"], f[role]["weight"], f[role]["style"])
            if key not in seen:
                seen.add(key)
                faces.append(f'      @font-face {{ font-family: "{key[0]}"; src: url("assets/fonts/{f[role]["src"]}"); '
                             f'font-weight: {key[1]}; font-style: {key[2]}; }}')
        dim, shade = _rgba(c["text"], 0.45), _rgba(c["shade"], 0.55)
        # ореол текста на груди: под ним белый принт худи и рука с микрофоном (IMG_3647 v1, 20.10.2026: вторая строка
        # списка тонкой гарнитурой на гербе не читалась) — плотная тень вплотную к буквам, без плашки
        halo = f"0 0 6px {_rgba(c['shade'], 0.9)}, 0 0 18px {_rgba(c['shade'], 0.75)}, 0 3px 10px {shade}"
        grad_text = ("background-image: var(--ds-grad); -webkit-background-clip: text; background-clip: text; "
                     "-webkit-text-fill-color: transparent; color: transparent;")
        rules = [
            f"      /* дизайн-система проекта ({self.project}/{FILE}, scripts/design.py): поверх kit — цвета, шрифты ролей, приёмы */",
            f"      :root {{ --cream: {c['text']}; --red: {c['pen']}; --ink: {c['plate']}; --ds-text: {c['text']}; "
            f"--ds-plate: {c['plate']}; --ds-pen: {c['pen']}; --ds-acc: {c['accent']}; --ds-on-acc: {c['on-accent']}; "
            f"--ds-grad: {self.gradient}; --ds-label-font: {fam('hand')}; --ds-label-weight: {wt('hand')}; "
            f"--ds-label-size: 64px; --ds-label-track: 0; --ds-label-case: none; }}",
            f"      #root {{ font-family: {fam('caption')}, sans-serif; }}",
            f"      .lead, .pill, .label, .cta-small {{ font-family: {fam('caption')}; font-weight: {wt('caption')}; }}",
            f"      .cta {{ background: {_rgba(c['plate'], 0.86)}; border-color: {_rgba(c['text'], 0.16)}; }}",
            "      .stamp { color: var(--ds-acc); border-color: var(--ds-acc); }",
            # «Чертёж»: подписи рукой, числа — Oswald, как было; акцент «Чертежа» (класс red) — градиент системы.
            # Подписи и линии крупнее (Валера 20.10 на v2: «мелковаты подписи и визуализация»): 76/56 px рукописью
            # вместо 40 px Manrope капсом, линии 8 px (64/50 на кадрах IMG_3647 читались мелко — у Caveat низкие строчные)
            f"      .bp-lbl {{ font-family: {fam('hand')}; font-weight: {wt('hand')}; font-size: 76px; letter-spacing: 0; "
            f"text-transform: none; }}",
            f"      .bp-lbl.big {{ font-family: {fam('headline')}; font-weight: {wt('headline')}; text-transform: uppercase; }}",
            f"      .bp-lbl .sub {{ font-family: {fam('hand')}; font-style: normal; font-weight: {wt('hand')}; font-size: 56px; }}",
            "      .bp-ln { stroke-width: 8; }",
            "      .bp-ln.thin { stroke-width: 4; }",
            "      .bp-lbl.red { color: var(--ds-acc); }",
            "      .bp-ln.red { stroke: url(#ds-grad); stroke-width: 10; }",
            "      .bp-dot.red, .bp-fill, .bp-mark { fill: url(#ds-grad); }",
            # приёмы системы (score.py: word дымом, hand, number, promise, strike; маркер субтитров — kit.caption_js)
            f"      .ds-ch {{ display: inline-block; padding: 0 {LETTER_PAD}em; margin: 0 -{LETTER_PAD}em; }}",
            f"      .ds-hand {{ left: 0; width: {W}px; text-align: center; white-space: nowrap; font-family: {fam('hand')}; "
            f"font-weight: {wt('hand')}; line-height: 1.1; color: var(--ds-text); text-shadow: 0 4px 18px {shade}; }}",
            "      .ds-uline { position: absolute; overflow: visible; }",
            "      .ds-uline path { fill: none; stroke: url(#ds-grad); stroke-width: 10; stroke-linecap: round; "
            "stroke-dasharray: 1; stroke-dashoffset: 1; }",
            f"      .ds-num-wrap {{ left: 0; width: {W}px; text-align: center; white-space: nowrap; }}",
            f"      .ds-numcap {{ display: block; font-family: {fam('whisper')}; font-weight: {wt('whisper')}; font-size: 60px; "
            f"line-height: 1.15; color: var(--ds-text); text-shadow: 0 3px 12px {shade}; }}",
            f"      .ds-num {{ display: inline-block; padding: 0 0.04em; font-family: {fam('number')}; font-weight: {wt('number')}; "
            f"line-height: 1; {grad_text} }}",
            f"      .ds-list {{ left: 160px; width: 760px; display: grid; gap: 14px; text-shadow: {halo}; }}",
            f"      .ds-list-h {{ font-family: {fam('caption')}; font-weight: {wt('caption')}; font-size: 70px; line-height: 1.1; "
            f"color: var(--ds-text); }}",
            f"      .ds-list-h .ds-n {{ font-family: {fam('number')}; font-weight: {wt('number')}; {grad_text} }}",
            f"      .ds-row {{ display: flex; align-items: center; gap: 24px; font-family: {fam('whisper')}; font-weight: {wt('whisper')}; "
            f"font-size: 58px; line-height: 1.15; color: {dim}; white-space: nowrap; }}",
            f"      .ds-box {{ position: relative; flex: none; display: block; width: 52px; height: 52px; "
            f"border: 4px solid {_rgba(c['text'], 0.55)}; border-radius: 11px; }}",
            "      .ds-box::after { content: \"\"; position: absolute; inset: 5px; border-radius: 6px; background: var(--ds-grad); "
            "transform: scale(var(--k, 0)); }",
            f"      .ds-strike-w {{ left: 0; width: {W}px; text-align: center; white-space: nowrap; font-family: {fam('caption')}; "
            f"font-weight: {wt('caption')}; line-height: 1.1; color: var(--ds-text); text-shadow: {halo}; }}",
            "      .ds-in { position: relative; display: inline-block; }",
            "      .ds-strike { position: absolute; left: -6%; top: 0; width: 112%; height: 100%; overflow: visible; }",
            "      .ds-strike path { fill: none; stroke: var(--ds-pen); stroke-width: 12; stroke-linecap: round; "
            "stroke-dasharray: 1; stroke-dashoffset: 1; }",
            "      .ds-mk { position: relative; display: inline-block; }",
            "      .ds-mk-fill { position: absolute; left: -0.18em; right: -0.18em; top: -0.03em; bottom: -0.09em; "
            "padding: 0.03em 0.18em 0.09em; color: var(--ds-on-acc); white-space: nowrap; text-shadow: none; isolation: isolate; "
            "clip-path: inset(-12% 100% -12% -6%); }",
            "      .ds-mk-fill::before { content: \"\"; position: absolute; inset: 0; z-index: -1; background: var(--ds-grad); "
            f"border-radius: {(self.tokens.get('rounded') or {}).get('marker', '0.14em')}; transform: rotate(-1.4deg); }}",
        ]
        return "\n" + "\n".join(faces + rules) + "\n"

    def js(self) -> str:
        """Движения системы: функции страницы, как enter/slam у kit (время — секунды дубля)."""
        return f'''      // ---------- дизайн-система проекта ({FILE}): буквы дымом и рукой, маркер, квадраты, ручка ----------
      // без отскоков: вход kit (enter) и точки «Чертежа» берут ход системы вместо back.out
      window.DS_ENTER = "{self.enter}";
      function dsSmoke(sel, t, o = {{}}) {{
        tl.set(sel, {{ opacity: 1 }}, t);
        tl.fromTo(`${{sel}} .ds-ch`, {{ opacity: 0, y: o.y ?? 34, filter: BLUR(o.blur ?? 16) }},
                  {{ opacity: 1, y: 0, filter: BLUR(0), duration: o.dur ?? 0.5, ease: "{self.enter}", stagger: o.stagger ?? {self.letter_stagger:g} }}, t);
      }}
      function dsHand(sel, t, o = {{}}) {{
        tl.set(sel, {{ opacity: 1 }}, t);
        tl.fromTo(`${{sel}} .ds-ch`, {{ opacity: 0, y: 14, rotation: -6, filter: BLUR(3) }},
                  {{ opacity: 1, y: 0, rotation: 0, filter: BLUR(0), duration: 0.22, ease: "power2.out", stagger: o.stagger ?? {self.hand_stagger:g} }}, t);
      }}
      function dsMark(sel, t, dur = {self.sweep:g}) {{
        tl.fromTo(sel, {{ clipPath: "inset(-12% 100% -12% -6%)" }}, {{ clipPath: "inset(-12% -6% -12% -6%)", duration: dur,
                  ease: "power3.out", immediateRender: false }}, t);
      }}
      function dsBox(sel, t) {{
        tl.fromTo(sel, {{ "--k": 0 }}, {{ "--k": 1, duration: 0.18, ease: "power4.out", immediateRender: false }}, t);
      }}
      function dsPen(sel, t, dur = 0.3) {{
        tl.fromTo(sel, {{ strokeDashoffset: 1 }}, {{ strokeDashoffset: 0, duration: dur, ease: "power2.out", immediateRender: false }}, t);
      }}
'''


def letters(text: str) -> str:
    """Строка буквами по одной (class ds-ch) — для вылета дымом и рукой; пробел — неразрывный, ширина та же."""
    return "".join(f'<span class="ds-ch">{"&nbsp;" if ch == " " else html.escape(ch)}</span>' for ch in text)


def _cyrillic(path: Path) -> bool:
    from fontTools.ttLib import TTFont
    cmap = TTFont(path, lazy=True).getBestCmap()
    return all(ord(ch) in cmap for ch in "АаЖжЁёЯя")


_CACHE: dict = {}


def by_name(project: str) -> Design | None:
    """DESIGN.md проекта или None, если у проекта своей системы нет. Перечитывается, когда файл поменяли."""
    path = PROJECTS_DIR / project / FILE
    if not path.is_file():
        return None
    key = (str(path), path.stat().st_mtime_ns)
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = Design(path, project)
    return _CACHE[key]


def of(project) -> Design | None:
    """Система проекта (projects.Project) или None."""
    return by_name(project.name)


def main():
    ap = argparse.ArgumentParser(description="Проверить DESIGN.md проекта и показать токены")
    ap.add_argument("project")
    args = ap.parse_args()
    try:
        d = by_name(args.project)
    except DesignError as e:
        sys.exit(f"✗ {e}")
    if d is None:
        sys.exit(f"✗ у проекта {args.project} нет {FILE} (projects/{args.project}/{FILE})")
    print(f"✓ projects/{args.project}/{FILE}: {d.tokens.get('name', '')}")
    if d.footage:
        print(f"  ИИ-клипы  «{d.footage['name']}», насыщенность в рамке {d.footage['saturate']:g}")
    for name, value in d.colors.items():
        print(f"  {name:<10} {value}")
    print(f"  градиент   {d.gradient}")
    for role, spec in d.fonts.items():
        print(f"  {role:<10} {spec['family']} {spec['weight']}{' italic' if spec['style'] == 'italic' else ''} · {spec['src']}")


if __name__ == "__main__":
    main()
