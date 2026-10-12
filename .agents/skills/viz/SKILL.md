---
name: viz
description: Визуализации данных в роликах — счётчики сумм и процентов, столбики и линии роста, доли, «до/после», формулы LaTeX, графики функций (парабола, корни), карты, блок-схемы шагов решения. Используй, когда монтируешь ролик и в речи есть то, что лучше показать, чем сказать, или когда просят добавить график, формулу, счётчик, карту или схему.
---

# Визуализации данных

Визуализация — не украшение, а способ показать то, что на слух теряется. Решаешь сам, по
правилам ниже. Ставишь через `scripts/viz.py` в `work/<имя>/page.py`, рядом с остальной графикой
ролика (`kit.build_page`). Рендер — офлайн: библиотеки и каталог лежат в проекте.

## Когда к месту

| В речи | Что ставить | Куда (9:16) |
|---|---|---|
| Число, на котором держится мысль: сумма, балл, срок («кредит 182 000 рублей») | `count-up` | `upper` — над головой; или за спиной (behind + окно вырезки) |
| 2–6 величин: рост по годам, сравнение («было 40, стало 182») | `chart-story` bars/line | `chest` |
| Доля, процент («80% учеников теряют баллы») | `chart-story` donut/progress, `conic-progress-ring` | `chest` или `upper` |
| Падение, потеря («баллы тают») | `decline-chart` | `chest` |
| Было/стало, ошибка/правильно | `before-after-wipe` | `chest` |
| Гонка, рейтинг во времени | `bar-chart-race` | `center` |
| Формула, которую произносят или выводят | `viz.formula` (LaTeX) | `lower` |
| Функция, парабола, «нарисуем график», корни | `viz.plot` | `chest` |
| Шаги решения, алгоритм, «сначала… потом…» | шаблоны `hw-pipeline`, `flowchart-vertical` | `chest`/`center` |
| Страна, место, история («в Вавилоне…») | шаблон `world-map` | `chest` |
| Колебания, периодичность (синус, физика) | `oscilloscope-trace` | `chest` |

**Не ставь**, если:
- число проходное, мысль держится не на нём;
- визуализация повторяет субтитр слово в слово;
- в этот момент уже есть крупная типографика, карточка или документ;
- визуализация была меньше 10–15 с назад: не больше одной на мысль;
- стиль ролика просит без неё: `params.graphics.viz` = `never` (`styles.py --brief <имя>` это покажет);
- данных нет в речи или брифе. Цифры не выдумывай. Если считаешь сам (проценты, разницу),
  проверь арифметику и запиши проверку в docstring `page.py`. Ответ задачи, которого автор не
  озвучил, на экран не выноси (правило 7 скилла reels).

## Как ставить

```python
import viz                                    # scripts/ уже в sys.path у page.py
tk = Take(STEM)
fmt = tk.fmt
w = tk.words                                  # слова дубля: появление — с произнесённым числом

credit = viz.mount("count-up", "credit", at=tk.t(41.2) - 0.15, dur=3.5, fmt=fmt, where="upper",
                   values={"start": 0, "end": 182000, "suffix": " ₽"})
years = viz.mount("chart-story", "years", at=tk.t(44.0), dur=5, fmt=fmt, where="chest",
                  values={"type": "bars", "data": "40, 65, 77, 182", "labels": "2021, 2022, 2023, 2024",
                          "emphasize": 3, "unit": " тыс"})
disc = viz.formula("disc", r"D = b^2 - 4ac", at=tk.t(52.3), dur=3, fmt=fmt)        # where="lower"
parab = viz.plot("parab", lambda x: x * x - 4, x=(-3, 3), y=(-5, 6), at=tk.t(60.1), dur=4, fmt=fmt,
                 label=r"y = x^2 - 4", points=[(-2, 0), (2, 0)])
front += "\n".join(h for h, _ in (credit, years, disc, parab))
beats += "\n".join(j for _, j in (credit, years, disc, parab))
```

- Каждый вызов возвращает `(html, js)`. html кладётся в `front` (поверх) или `behind` (за спиной:
  тогда добавь окно в `fg_windows`, и человек из вырезки встанет поверх числа — фирменный приём).
- Вход И выход уже есть: обёртка влетает со смазом и улетает за 0.3 с до конца окна (правило 3).
  Свой выход у элементов каталога выключен, чтобы не уходили дважды.
- Окно — от 2.5 до 5 с: короче не успеет построиться, длиннее мешает лицу. Начало — с
  произнесённого числа (−0.15 с), а не раньше.
- На время `chest` и `center` спрячь субтитры: `director.json` → `hide_captions: [[начало, конец]]`.
- Переменные проверяются по объявлению элемента: опечатка в имени или не тот тип — сразу ошибка.

**Зоны** (`viz.ZONES`, по кадру IMG_3317). Вертикаль: голова y≈400–930, субтитры на груди y≈1150,
серые зоны площадок — верх до 260, низ от 1370, кнопки справа, бока по ~100 px (`formats.GREY_ZONES`,
замер по скринам 12.10). `chest` (y 945–1360), `lower` (1240–1360), `center` — шириной 590 по центру
экрана; заезд текста в серые зоны не пустит `verify_page` (скилл reels, правило 11).
- `upper` — узкая полоса над головой: одно число, короткая подпись. Без подложки.
- `chest` — на груди: графики, схемы. Тёмная подложка.
- `lower` — под субтитрами: формула, строка.
- `center` — поверх лица: только короткий главный момент (график, к которому вело объяснение).
- `side` — в 16:9 правая треть, лицо остаётся в центре. В 1:1 и 4:5 зоны свои, имена те же.

**Шаблоны без переменных** — карта мира, блок-схемы, линейный график, `data-chart`, `mk-*`.
Их копирует `viz.custom`, подставляя данные заменами. Каждый фрагмент должен найтись в шаблоне
ровно один раз, иначе будет ошибка. Сначала прочитай шаблон в `presets/viz/compositions/`.

```python
from pathlib import Path
project = ROOT / "studio" / tk.project
map_ = viz.custom("world-map", "babylon", project, "babylon-map", {
    '<h1 class="headline">Global GDP per Capita</h1>': '<h1 class="headline">Где был Вавилон</h1>',
    '<p class="subtitle">Nominal GDP per capita, 2024 IMF estimates</p>': '<p class="subtitle">Месопотамия, 1800 г. до н. э.</p>',
    # данные карты — объект gdpData: замени целиком своим (коды стран ISO 3166 числом)
}, at=tk.t(12.0), dur=4.5, fmt=fmt, where="chest")
```

Блоки 1920×1080 вписываются в зону масштабом. В вертикали карта мелкая, поэтому для главного
момента бери `center`.

## Каталог

Параметрами (`viz.mount`), из официального каталога HyperFrames, Apache-2.0:
- `count-up`: start, end, prefix, suffix, accent, glow;
- `chart-story`: type = bars | line | donut | progress, data «12, 28, 45», labels «А, Б, В», emphasize — номер
  акцентного с 0, unit;
- `decline-chart`: label, start_value, end_value;
- `conic-progress-ring`: progress, thickness, label;
- `before-after-wipe`: label_a, label_b, rest_split, wipe_at;
- `star-rating-fill`: rating, starCount, showValue;
- `bar-chart-race`: title, subtitle, periods «2021, 2022», series «Имя: 1, 2\nИмя: 3, 4», valuePrefix,
  valueSuffix, valueDecimals;
- `oscilloscope-trace`: waveform = sine | square | triangle | data, frequency, amplitude, dataSeries.

Свои, для математики: `viz.formula` (KaTeX, MIT) и `viz.plot` (путь функции считается в Python,
разрывы рвут линию).

Каталог целиком лежит в `presets/viz/catalog.json`. Обновить его из той же прибитой версии
HyperFrames — `scripts/viz_vendor.py`. Он заменит ссылки в интернет на копии в `studio/_vendor`,
числа переведёт на ru-RU, шрифты на наши с кириллицей и громко упадёт, если ссылка осталась.
Нового элемента прямо `npx hyperframes add` в проект не ставь: он потянет GSAP, D3 и шрифты из
сети при рендере. Сначала добавь его в `ITEMS` в `viz_vendor.py`.

## Проверка

1. `.venv/bin/python scripts/compose.py <имя>` подкладывает в проект элементы каталога, KaTeX, D3 и карту.
2. `.venv/bin/python scripts/verify_page.py <имя>` ловит залипания, пропавшие ассеты и ошибку в
   LaTeX: в ответе будет формула и причина.
3. `cd studio/<имя> && npx --yes hyperframes@0.8.141 snapshot --at <моменты визуализаций> --describe false`.
   Проверь глазами: лицо не закрыто, числа совпадают со сказанным, подписи читаются.
4. Дальше — как всегда, `render_reel.py`.

Справка по устройству каталога (блоки, компоненты, подключение) — `references/hyperframes-registry.md`,
это официальный скилл HyperFrames. Там `hyperframes add` ставит из сети, у нас — через `viz_vendor.py`.
