"""Доска IMG_1805: логарифм превращает умножение в сложение — 100 · 1000 → 10² · 10³ → 10^(2+3) = 100 000.

Клип ставится на страницу с t(50.90) исходника: «Логарифм» — 51.06, «умножение» — 52.20,
«сложение» — 53.00, «сложить гораздо проще» — 54.04, «перемножить» — 55.32. Длина ~5.6 с.
Ответ (100 000) — не задача ЕГЭ, а пример для глаз: правило 7 проекта (кодовое слово) не касается.
"""
import manimgx as m

CREAM, RED, GOLD = "#F2EBDD", "#F0352C", "#F5B82E"


class Log(m.Scene):
    def construct(self):
        self.camera.background_color = "#141210"
        # крупно: на странице плашка ~560 px шириной — при 2.4 формула читалась мелко (снимок 15.10)
        mul = m.Text("умножение", color=GOLD, weight="BOLD").scale(1.3).to_edge(m.UP, buff=0.6)
        add = m.Text("сложение", color=RED, weight="BOLD").scale(1.3).to_edge(m.UP, buff=0.6)
        f1 = m.MathTex(r"100", r"\times", r"1000", color=CREAM).scale(3.3).shift(m.DOWN * 0.5)
        f1[1].set_color(GOLD)
        f2 = m.MathTex(r"10^{2}", r"\times", r"10^{3}", color=CREAM).scale(3.3).shift(m.DOWN * 0.5)
        f2[1].set_color(GOLD)
        f3 = m.MathTex(r"10^{\,2", r"+", r"3}", color=CREAM).scale(3.3).shift(m.DOWN * 0.5)
        f3[1].set_color(RED)
        f4 = m.MathTex(r"10^{\,2", r"+", r"3}", r"=", r"100\,000", color=CREAM).scale(2.7).shift(m.DOWN * 0.5)
        f4[1].set_color(RED)
        f4[4].set_color(RED)

        self.wait(0.1)
        self.play(m.FadeIn(mul, shift=m.DOWN * 0.3), m.Write(f1), run_time=0.5)     # 0.1–0.6: «логарифм»
        self.wait(0.7)
        self.play(m.ReplacementTransform(f1, f2), run_time=0.45)                    # 1.3–1.75: «умножение»
        self.wait(0.35)
        self.play(m.ReplacementTransform(mul, add), m.ReplacementTransform(f2, f3), run_time=0.5)   # 2.1–2.6: «в сложение»
        self.wait(0.6)
        self.play(m.ReplacementTransform(f3, f4), run_time=0.5)                     # 3.2–3.7: «сложить проще»
        self.wait(1.9)
