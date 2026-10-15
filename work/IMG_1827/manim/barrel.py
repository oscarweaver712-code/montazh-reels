"""Доска IMG_1827: бочка с недоливом — на ней черта «−», долили — вторая черта, вышел «+».

Клип ставится на страницу с t(32.30) исходника («И часто бывало…»). Метки по речи (исходник):
«не хватало» 34.06 → 1.8 с клипа, «черточку» 36.16 → 3.9, «доливали» 38.26 → 6.0,
«ещё одну черту» 40.36 → 8.1, «плюс» 41.54 → 9.2. Длина ~9.8 с. Размер — wide (1080×720).
"""
import manimgx as m

CREAM, RED, GOLD, WOOD = "#F2EBDD", "#F0352C", "#F5B82E", "#8A5A2B"
W, H, BULGE = 3.0, 4.4, 0.42
CX = -2.4


def side(y: float) -> float:
    """Полуширина бочки на высоте y: бока выгнуты параболой."""
    return W / 2 + BULGE * (1 - (2 * y / H) ** 2)


def outline() -> m.Polygon:
    ys = [-H / 2 + H * k / 24 for k in range(25)]
    pts = [[CX + side(y), y, 0] for y in ys] + [[CX - side(y), y, 0] for y in reversed(ys)]
    return m.Polygon(*pts)


class Barrel(m.Scene):
    def construct(self):
        self.camera.background_color = "#141210"
        shell = outline().set_stroke(CREAM, 6).set_fill(opacity=0)
        hoops = m.VGroup(*[m.Line([CX - side(y), y, 0], [CX + side(y), y, 0]) for y in (-1.45, 1.45)])
        hoops.set_stroke(WOOD, 8)

        def liquid(level: float) -> m.VMobject:
            h = max(0.05, H * level)
            box = m.Rectangle(width=W + 2 * BULGE + 0.4, height=h).move_to([CX, -H / 2 + h / 2, 0])
            return m.Intersection(box, outline(), stroke_width=0, fill_color=GOLD, fill_opacity=0.55)

        fill = liquid(0.04)
        low, full = liquid(0.55), liquid(1.0)

        # метки мелом — прямо на боку бочки
        dash = m.Line([CX - 1.0, 0.3, 0], [CX + 1.0, 0.3, 0], stroke_width=24, color=CREAM)
        bar = m.Line([CX, 1.3, 0], [CX, -0.7, 0], stroke_width=24, color=CREAM)

        note = m.Text("недолив", color=CREAM, weight="BOLD").scale(1.0).move_to([2.9, 0.9, 0])
        # знаки — линиями: шрифтовой «−» у Text выходит волосяной чертой
        sign_at = note.get_center() + m.DOWN * 1.9
        note_sign = m.Line(sign_at + m.LEFT * 0.85, sign_at + m.RIGHT * 0.85, stroke_width=22, color=CREAM)
        note2 = m.Text("долили", color=CREAM, weight="BOLD").scale(1.0).move_to(note)
        plus_sign = m.VGroup(m.Line(sign_at + m.LEFT * 0.85, sign_at + m.RIGHT * 0.85),
                             m.Line(sign_at + m.UP * 0.85, sign_at + m.DOWN * 0.85)).set_stroke(RED, 22)

        self.play(m.Create(shell), m.Create(hoops), run_time=0.6)                       # 0.0–0.6
        self.add(fill)
        self.bring_to_front(shell, hoops)
        self.play(m.Transform(fill, low), run_time=0.8)                                  # 0.6–1.4
        self.play(m.FadeIn(note, shift=m.DOWN * 0.3), run_time=0.35)                     # 1.4–1.75 «не хватало»
        self.wait(2.05)
        self.play(m.Create(dash), m.FadeIn(note_sign, shift=m.LEFT * 0.4), run_time=0.4)  # 3.8–4.2 «черточку»
        self.wait(1.7)
        # слово сменяется уходом и входом: морфинг букв в середине давал кашу из глифов
        self.play(m.Transform(fill, full), m.FadeOut(note, shift=m.UP * 0.4), m.FadeIn(note2, shift=m.UP * 0.4),
                  run_time=1.0)                                                          # 5.9–6.9 «доливали»
        self.bring_to_front(dash)
        self.wait(1.15)
        self.play(m.Create(bar), run_time=0.4)                                           # 8.05–8.45 «ещё одну черту»
        self.wait(0.65)
        self.play(m.VGroup(dash, bar).animate.set_color(RED).scale(1.15),
                  m.ReplacementTransform(note_sign, plus_sign), run_time=0.3)            # 9.1–9.4 «плюс»
        self.wait(0.4)
