"""Доска IMG_1812: «нет шестёрки» — 5/6, за два броска 5/6 · 5/6 = 25/36.

Клип ставится на страницу с t(42.30) исходника: «5 шестых» — 42.5, «умножить» — 45.68,
«25 тридцать шестых» — 49.04. Длина ~7.6 с, дальше плашку сменяет сетка 6×6 (page.py).
"""
import manimgx as m

CREAM, RED, GOLD = "#F2EBDD", "#F0352C", "#F5B82E"


class Calc(m.Scene):
    def construct(self):
        self.camera.background_color = "#141210"
        one = m.Text("нет шестёрки за бросок", color=CREAM, weight="BOLD").scale(0.9).to_edge(m.UP, buff=0.9)
        two = m.Text("нет шестёрки за два броска", color=CREAM, weight="BOLD").scale(0.9).to_edge(m.UP, buff=0.9)
        f1 = m.MathTex(r"\frac{5}{6}", color=CREAM).scale(2.6).shift(m.DOWN * 0.5)
        f2 = m.MathTex(r"\frac{5}{6}", r"\cdot", r"\frac{5}{6}", color=CREAM).scale(2.6).shift(m.DOWN * 0.5)
        f2[1].set_color(GOLD)
        f3 = m.MathTex(r"\frac{5}{6}", r"\cdot", r"\frac{5}{6}", r"=", r"\frac{25}{36}", color=CREAM).scale(2.3).shift(m.DOWN * 0.5)
        f3[1].set_color(GOLD)
        f3[4].set_color(RED)

        self.wait(0.1)
        self.play(m.FadeIn(one, shift=m.DOWN * 0.3), m.Write(f1), run_time=0.5)      # 0.1–0.6: «5 шестых»
        self.wait(1.7)
        self.play(m.ReplacementTransform(one, two), run_time=0.4)                    # 2.3–2.7: «в двух подряд»
        self.wait(0.5)
        self.play(m.ReplacementTransform(f1, f2), run_time=0.5)                      # 3.2–3.7: «умножить на 5/6»
        self.wait(2.9)
        self.play(m.ReplacementTransform(f2, f3), run_time=0.45)                     # 6.6–7.05: «это 25/36»
        self.wait(0.6)
