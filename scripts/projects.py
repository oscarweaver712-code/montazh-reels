#!/usr/bin/env python3
"""Проекты: у каждого свои исходники, выпуски, правила, референсы и стиль по умолчанию.

Правило Валеры (14.10.2026): «мои ролики» для Инсты, Ютуба и ТикТока — один проект; заказ со
своими требованиями, стилем, референсами и форматом — другой, и они не перемешиваются. Раньше
правила автора лежали в общем скилле, а тестовое для заказчицы держалось на ручных правках
брифа и заметке «без CTA и без нашей плашки» — на втором заказе чужое начало бы протекать.

  projects/<имя>/
    project.json    название, язык речи, умолчания брифа (стиль, форматы, цели), CTA, проверка лица
    rules.md        правила этого проекта — агент читает их до монтажа, они важнее стиля
    setup.json      анкета проекта (студия: «Проект → Настроить»): ответы ложатся блоком в rules.md
    references/     референсы: ссылки, ролики, скриншоты (analyze_reference.py их меряет)
    input/          исходники — ролик принадлежит тому проекту, в чьём input/ лежит
    input/<имя>/    сборка: папка с несколькими видео — сырьё ОДНОГО ролика <имя> (scripts/pack.py);
                    собранный дубль ложится рядом — input/<имя>.mp4, дальше обычный конвейер
    output/         готовые ролики проекта
    <раздел>/       раздел проекта (21.10.2026): section.json, свои input/, output/ и rules.md

Раздел — часть проекта со своими видео и своими правилами: «Антишкола → Рилс» и «Антишкола → YouTube»,
у заказчика «Склейки» и «Говорящая голова». Дизайн-система, музыка, анкета и референсы — общие, проекта
(home); конфиг — project.json, поверх него section.json; правил два файла, ИИ читает оба (сначала
проекта). Имя раздела — «проект/раздел» (antishkola/reels): так он и пишется в путях projects/<имя>/.
Тип (kind) — что делать с несколькими видео: talking — каждое свой ролик, pack — одним роликом (сборка).

work/<имя>/ и studio/<имя>/ остаются общими: имя ролика (IMG_1803) — одно на все проекты.
Одно имя в двух проектах — громкая ошибка, а не «какой-нибудь из двух».

  .venv/bin/python scripts/projects.py                      # проекты и их ролики
  .venv/bin/python scripts/projects.py new firuza --title "Фируза — тестовое"
  .venv/bin/python scripts/projects.py where IMG_6668       # чей ролик
  .venv/bin/python scripts/projects.py --check              # все project.json валидны, имена не повторяются
"""
import argparse
import copy
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT  # noqa: E402  (заодно UTF-8 в консоли — common это делает)

PROJECTS_DIR = ROOT / "projects"
DEFAULT = "antishkola"          # проект по умолчанию — ролики Валеры
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv"}
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*$")

# Что проект задаёт сам. Поля брифа — те же, что в work/<имя>/brief.json (styles.DEFAULT_BRIEF):
# бриф ролика берёт их отсюда и меняет только своё.
CONFIG = {
    "title": "",
    "language": "ru",                         # язык речи: распознавание и субтитры
    "brief": {},                              # умолчания брифа: style, formats, goals, boldness, overrides, notes
    "cta": True,                              # финальная плашка «смотри у меня в профиле»
    "face_max": 165,                          # лицо светлее — засвет (verify_render); null — не мерить
    "long_matte": False,                      # владелец согласен на долгую маску BiRefNet (matte.py без --yes)
    "fx_theme": "default",                    # тема приёмов fx.py (fx.THEMES): цвета и шрифты под стиль проекта
    "footage_style": "",                      # хвост стиля ИИ-перебивок (footage.py), один на проект
    "footage_clips": 0,                       # ИИ-клипов Flow на ролик по умолчанию (0 — только по просьбе)
    "footage_budget": 0,                      # бонусов Flow на ролик без отдельного «да» (0 — спросить владельца)
    "music": False,                           # фоновая музыка в каждом ролике: без неё verify_page не пускает в рендер
    "hook_flash": False,                      # вспышка с отъездом и звуком после хука (montage.py ставит сама)
    "soft_sounds": False,                     # тихие звуки монтажа в каждом ролике (не реже одного на 6 с)
    "face_min": 0.6,                          # доля ролика с человеком в кадре: перебивки во весь кадр — не больше остатка
    "insert_style": "",                       # мотив вставок: "blueprint" — «Чертёж» (рамка ИИ-клипов, scripts/blueprint.py)
    "cut_pauses": False,                      # резать длинные паузы внутри дубля (prep.py); edit.json ролика решает сам
    "pause_max": 0.5,                         # с: пауза длиннее режется …
    "pause_keep": 0.2,                        # с: … и от неё остаётся столько тишины
    "music_level": 0.55,                      # громкость фоновой музыки от нормы материалов (kit.background_music)
    "music_duck": False,                      # музыка поднимается в тишине дубля и уходит под голос (music.duck_lane)
    "keep_audio": False,                      # звук исходника как есть (трек подложил автор): prep не чистит и не режет
    "kind": "talking",                        # что такое несколько видео: talking — каждое свой ролик, pack — одним роликом
}
CONFIG_TYPES = {"title": (str, "строкой"), "language": (str, "строкой"), "brief": (dict, "объектом"),
                "kind": (str, "строкой: \"talking\" (говорящая голова) или \"pack\" (склейка)"),
                "cta": (bool, "true или false"), "face_max": ((int, float, type(None)), "числом или null"),
                "long_matte": (bool, "true или false"), "fx_theme": (str, "строкой — имя темы из fx.THEMES"),
                "footage_style": (str, "строкой — стиль генерации перебивок"),
                "footage_clips": (int, "целым числом — ИИ-клипов на ролик по умолчанию"),
                "footage_budget": (int, "целым числом — бонусов Flow на ролик без отдельного согласия"),
                "music": (bool, "true или false"), "hook_flash": (bool, "true или false"), "soft_sounds": (bool, "true или false"),
                "face_min": ((int, float), "числом от 0 до 1"), "insert_style": (str, "строкой: \"\" или \"blueprint\""),
                "insert_gap_max": ((int, float), "числом секунд — дольше без вставок verify_page не пускает"),
                "caption_accent_scale": ((int, float), "числом от 1 до 1.6 — во сколько ключевое слово субтитров крупнее"),
                "cut_pauses": (bool, "true или false"),
                "pause_max": ((int, float), "числом секунд — пауза длиннее режется"),
                "pause_keep": ((int, float), "числом секунд — сколько тишины остаётся от вырезанной паузы"),
                "music_level": ((int, float), "числом от 0 до 1 — громкость музыки от нормы материалов"),
                "music_duck": (bool, "true или false — музыка громче в тишине, тише под голосом"),
                "keep_audio": (bool, "true или false — звук исходника как есть, монтаж только картинки")}


class ProjectError(Exception):
    """Понятная ошибка о проекте — для вывода человеку."""


class Project:
    parent = None

    def __init__(self, name: str):
        self.name = name
        self.root = PROJECTS_DIR / name
        self.input = self.root / "input"
        self.output = self.root / "output"
        self.references = self.root / "references"
        self.rules = self.root / "rules.md"
        self.config = load_config(self.root / "project.json", name)

    @property
    def home(self) -> "Project":
        """Проект, которому принадлежат дизайн-система, музыка, анкета и референсы: у раздела — его проект."""
        return self

    def sections(self) -> list:
        """Разделы проекта: подпапки с section.json, по имени."""
        if not self.root.is_dir():
            return []
        return [Section(self, d.name) for d in sorted(self.root.iterdir())
                if d.is_dir() and d.name not in RESERVED and (d / SECTION_FILE).is_file()]

    def rule_files(self) -> list:
        """Файлы правил, которые ИИ читает перед монтажом, — по порядку: общие раньше частных."""
        return [self.rules]

    def all_rules_text(self) -> str:
        """Все правила ролика одним текстом (аналитику, автопилоту): проекта, затем раздела."""
        parts = []
        for path in self.rule_files():
            if path.exists() and path.read_text(encoding="utf-8").strip():
                parts.append(f"<!-- {rel(path)} -->\n" + path.read_text(encoding="utf-8").strip())
        return "\n\n".join(parts)

    def __repr__(self):
        return f"Project({self.name})"

    def __eq__(self, other):
        return isinstance(other, Project) and other.name == self.name

    def __hash__(self):
        return hash(self.name)

    @property
    def title(self) -> str:
        return self.config["title"] or self.name

    def sources(self) -> list:
        """Исходники проекта. Скрытые — недописанные загрузки и служебные «._имя» macOS."""
        if not self.input.is_dir():
            return []
        return sorted(p for p in self.input.iterdir()
                      if p.suffix.lower() in VIDEO_EXT and not p.name.startswith(".") and p.is_file())

    def packs(self) -> list:
        """Сборки проекта: папки в input/ хотя бы с одним видео (scripts/pack.py). Имя папки — имя ролика."""
        if not self.input.is_dir():
            return []
        return sorted(p for p in self.input.iterdir()
                      if p.is_dir() and not p.name.startswith((".", "_")) and pack_clips(p))

    def references_list(self) -> list:
        """Файлы-референсы проекта (без служебных): их видит ИИ перед каждым монтажом проекта."""
        if not self.references.is_dir():
            return []
        return sorted(p for p in self.references.iterdir()
                      if p.is_file() and not p.name.startswith(".") and p.name != "links.md")

    def rules_text(self) -> str:
        """Свой rules.md (у раздела — только раздела): его правит редактор правил в студии."""
        return self.rules.read_text(encoding="utf-8") if self.rules.exists() else ""


SECTION_FILE = "section.json"
RESERVED = {"input", "output", "references", "music"}      # папки проекта, которые разделом быть не могут
KINDS = {"talking": "говорящая голова — каждое видео свой ролик", "pack": "склейка — несколько видео одним роликом"}


class Section(Project):
    """Раздел проекта: свои исходники, выпуски и правила; дизайн, музыка, анкета и референсы — проекта."""

    def __init__(self, parent: Project, slug: str):
        self.parent = parent
        self.slug = slug
        self.name = f"{parent.name}/{slug}"
        self.root = parent.root / slug
        self.input = self.root / "input"
        self.output = self.root / "output"
        self.references = parent.references
        self.rules = self.root / "rules.md"
        self.config = load_config(self.root / SECTION_FILE, self.name, base=parent.config)

    @property
    def home(self) -> Project:
        return self.parent

    @property
    def own_title(self) -> str:
        return self.config["title"] or self.slug

    @property
    def title(self) -> str:
        return f"{self.parent.title} · {self.own_title}"

    def sections(self) -> list:
        return []                                         # разделы одного уровня: раздел в разделе — не нужно

    def rule_files(self) -> list:
        return [self.parent.rules, self.rules]


def load_config(path: Path, name: str, base: dict | None = None) -> dict:
    """project.json поверх умолчаний (section.json — поверх конфига своего проекта: бриф дополняется, остальное
    заменяется, название — своё). Битый файл — ошибка с именем файла и поля."""
    config = copy.deepcopy(base if base is not None else CONFIG)
    if base is not None:
        config["title"] = ""
    if not path.exists():
        return config
    where = f"projects/{name}/{path.name}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProjectError(f"{where}: битый JSON ({e})")
    if not isinstance(data, dict):
        raise ProjectError(f"{where}: должен быть объектом JSON {{…}}")
    for key, value in data.items():
        if key.startswith("_"):
            continue                                  # «_note» и т.п. — пояснения для людей
        if key not in CONFIG_TYPES:
            raise ProjectError(f"{where}: не знаю поля «{key}». Есть: {', '.join(CONFIG_TYPES)}")
        kind, what = CONFIG_TYPES[key]
        if not isinstance(value, kind) or (isinstance(value, bool) and kind is not bool):
            raise ProjectError(f"{where}: поле {key} должно быть {what}, а не {value!r}")
        if key == "kind" and value not in KINDS:
            raise ProjectError(f"{where}: kind — " + " или ".join(f"«{k}» ({v})" for k, v in KINDS.items()))
        config[key] = {**config["brief"], **value} if key == "brief" and base is not None else value
    return config


def pack_clips(folder: Path) -> list:
    """Видео сборки: файлы папки по имени (скрытые — недописанные загрузки и «._имя» macOS — нет)."""
    return sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.suffix.lower() in VIDEO_EXT and not p.name.startswith("."))


def names() -> list:
    if not PROJECTS_DIR.is_dir():
        return []
    return sorted(p.name for p in PROJECTS_DIR.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def all_projects() -> list:
    """Проекты и их разделы — всё, где могут лежать видео: раздел идёт сразу за своим проектом."""
    found = []
    for n in names():
        project = Project(n)
        found += [project] + project.sections()
    return found


def get(name: str) -> Project:
    """Проект по имени или раздел — «проект/раздел»."""
    head, _, slug = (name or "").partition("/")
    if not NAME_RE.match(head) or (slug and not NAME_RE.match(slug)):
        raise ProjectError(f"Плохое имя проекта «{name}»: латиница в нижнем регистре, цифры и дефис "
                           "(раздел — через косую: antishkola/reels)")
    if head not in names():
        raise ProjectError(f"Проекта «{head}» нет. Есть: {', '.join(names()) or 'ни одного'}. "
                           f"Новый — projects.py new {head}")
    project = Project(head)
    if not slug:
        return project
    section = next((s for s in project.sections() if s.slug == slug), None)
    if section is None:
        raise ProjectError(f"В проекте {head} нет раздела «{slug}». Есть: "
                           f"{', '.join(s.slug for s in project.sections()) or 'ни одного'}")
    return section


def owner(path: Path) -> Project:
    """Проект или раздел, в чьей папке лежит путь (input/X.MOV, input/<сборка>/клип.MOV, output/…)."""
    parts = Path(path).resolve().relative_to(PROJECTS_DIR.resolve()).parts
    if len(parts) > 1 and parts[1] not in RESERVED and (PROJECTS_DIR / parts[0] / parts[1] / SECTION_FILE).is_file():
        return get(f"{parts[0]}/{parts[1]}")
    return get(parts[0])


def default() -> Project:
    return get(DEFAULT)


def index() -> dict:
    """Имя ролика → (проект, исходник) по всем проектам. Одно имя в двух — громкая ошибка.

    У айфонов команды одинаковые имена IMG_XXXX, а work/<имя>/ у ролика общий: если бы
    одно имя лежало в двух проектах, транскрипт, решения и бриф одного достались бы другому.

    Сборка (папка input/<имя>/ с несколькими видео) до сборки — ролик с исходником-папкой; собрана
    (рядом input/<имя>.mp4) — обычный ролик с этим файлом, папка остаётся его сырьём (pack_of).
    """
    found, clash = {}, []
    for project in all_projects():
        for path in project.sources():
            if path.stem in found:
                clash.append(f"{path.stem}: projects/{found[path.stem][0].name}/input и projects/{project.name}/input")
                continue
            found[path.stem] = (project, path)
    for project in all_projects():
        for folder in project.packs():
            if folder.name in found:
                if found[folder.name][0] == project and found[folder.name][1].parent == folder.parent:
                    continue                          # собранная сборка: ролик — файл рядом с папкой
                clash.append(f"{folder.name}: сборка projects/{project.name}/input/{folder.name}/ и "
                             f"projects/{found[folder.name][0].name}/input")
                continue
            found[folder.name] = (project, folder)
    if clash:
        raise ProjectError("Одно имя ролика в двух проектах — у них общий work/<имя>/, решения "
                           "перемешаются. Переименуй один из файлов (IMG_1803 → IMG_1803_2):\n  " + "\n  ".join(clash))
    return found


def pack_of(stem: str) -> Path | None:
    """Папка сборки ролика (input/<имя>/ его проекта) — собран он уже или нет; не сборка — None."""
    entry = index().get(stem)
    if not entry:
        return None
    project, path = entry
    folder = project.input / stem
    return folder if folder.is_dir() and pack_clips(folder) else None


def sources() -> list:
    """Все исходники всех проектов: [(проект, путь)], новые сверху."""
    return sorted(index().values(), key=lambda pair: -pair[1].stat().st_mtime)


def source(stem: str) -> Path | None:
    entry = index().get(stem)
    return entry[1] if entry else None


def of(stem: str) -> Project:
    """Проект ролика: где лежит исходник; исходника нет — где лежат его выпуски."""
    entry = index().get(stem)
    if entry:
        return entry[0]
    owners = [p for p in all_projects() if p.output.is_dir() and any(
        belongs(f.name, stem) for f in p.output.glob(f"{stem}*"))]
    if len(owners) == 1:
        return owners[0]
    if owners:
        raise ProjectError(f"Выпуски {stem} лежат в нескольких проектах: {', '.join(p.name for p in owners)}")
    raise ProjectError(f"Ролика {stem} нет ни в одном проекте: положи исходник в projects/<проект>/input/")


def of_or_default(stem: str) -> Project:
    """Проект ролика, а для имени, которого нигде нет (проверки, черновики), — проект по умолчанию.

    Только для того, что ничего не пишет в чужой проект: умолчания брифа, язык. Куда класть
    выпуск, решает of() — там ошибка громкая.
    """
    try:
        return of(stem)
    except ProjectError as e:
        if "ни в одном проекте" in str(e) and DEFAULT in names():
            return default()
        raise


def belongs(name: str, stem: str) -> bool:
    """Файл — этого ролика? IMG_32790 не принадлежит IMG_3279."""
    base = Path(name).stem
    if base.endswith(".sheet"):
        base = base[:-6]
    rest = base[len(stem):] if base.startswith(stem) else None
    return rest is not None and (rest == "" or rest[0] in "_-")


def rel(path: Path) -> str:
    """Путь для шага очереди и для людей: от корня проекта, если он внутри, иначе целиком."""
    path = Path(path)
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def output_dir(stem: str) -> Path:
    out = of(stem).output
    out.mkdir(parents=True, exist_ok=True)
    return out


def locate(folder: str, name: str) -> Path:
    """Файл в input/ или output/ какого-то проекта по имени: имена роликов одни на все проекты."""
    if folder not in ("input", "output"):
        raise ProjectError(f"нет такой папки: {folder}")
    name = Path(name).name
    hits = [getattr(p, folder) / name for p in all_projects() if (getattr(p, folder) / name).exists()]
    if len(hits) > 1:
        raise ProjectError(f"{name} есть в нескольких проектах: {', '.join(h.parts[-3] for h in hits)}")
    if not hits:
        raise ProjectError(f"нет файла {name} в {folder}/ проектов")
    return hits[0]


RULES_TEMPLATE = """# Правила проекта «{title}»

Правила этого проекта важнее стиля и умолчаний скилла. Пиши сюда то, что заказчик или автор
сказал явно: что можно, чего нельзя, как должно выглядеть. С датой и словами человека — чтобы
следующий агент понял, откуда правило.

## Задача
- Для кого ролики и где их публикуют:
- Формат и длительность:
- Язык:

## Стиль
- Референсы — в references/ (ссылки — в references/links.md):
- Шрифт, цвета, субтитры:

## Нельзя
-
"""


# ---------------------------------------------------------------- анкета проекта

# Валера, 16.10.2026: «шаблон правил в новых проектах, и чтобы ИИ требовал ответы на вопросы
# предварительно». Новый проект без ответов на обязательные вопросы не монтируется — ни из студии,
# ни пачкой: ИИ без них монтирует «как-нибудь», а заметят это уже на готовом ролике.
SETUP_QUESTIONS = [
    {"id": "about", "q": "О чём ролики и кто в кадре", "required": True,
     "hint": "Тема, ниша, кто говорит. Например: «репетитор ЕГЭ по математике, объясняет с юмором»"},
    {"id": "audience", "q": "Для кого", "required": True,
     "hint": "Кто смотрит: возраст, чем живут, что им важно"},
    {"id": "platforms", "q": "Где публикуем", "required": True, "multi": True,
     "options": ["Instagram Reels", "TikTok", "YouTube Shorts", "YouTube 16:9", "VK Клипы", "Telegram"]},
    {"id": "language", "q": "Язык речи в роликах", "required": True, "options": ["ru", "en"]},
    {"id": "tone", "q": "Характер монтажа", "required": True, "multi": True, "free": True,
     "options": ["спокойный, экспертный", "динамичный, вирусный", "дерзкий, с юмором", "премиальный, минимализм"]},
    {"id": "never", "q": "Чего нельзя", "required": True,
     "hint": "Табу: мат в субтитрах, глитчи, чужие логотипы, цвета, приёмы. Нет табу — так и напиши"},
    {"id": "cta", "q": "Призыв в конце", "options": ["без призыва", "подписаться", "ссылка в профиле"], "free": True},
    {"id": "length", "q": "Длительность", "hint": "«до 60 секунд», «как в исходнике, без жёсткой нарезки»"},
    {"id": "brand", "q": "Шрифт, цвета, фирменный стиль", "hint": "Шрифты, цвета (#hex), логотип, что всегда одинаково"},
    {"id": "captions", "q": "Субтитры", "hint": "Крупные по слову или фразой, цвет ударного слова, где на экране"},
    {"id": "sound", "q": "Музыка и звуки", "hint": "Нужна ли музыка, какие звуки, насколько заметно"},
    {"id": "graphics", "q": "Графика и фоны", "hint": "Картинки за спиной, схемы, мемы, фото — сколько и каких"},
    {"id": "references", "q": "Референсы", "hint": "Ссылки на ролики, которые нравятся, и что именно в них взять. Файлы — ниже"},
    {"id": "extra", "q": "Что ещё важно", "hint": "Всё, что не влезло выше: нюансы, предпочтения, привычки автора"},
]
SETUP_BEGIN = "<!-- анкета проекта: этот блок пишет студия по ответам анкеты («Проект → Настроить проект») -->"
SETUP_END = "<!-- /анкета -->"
FORMAT_OF = {"YouTube 16:9": "16:9"}           # остальные площадки — вертикаль 9:16


def _answer(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(v).strip() for v in value if str(v).strip())
    return str(value or "").strip()


def load_setup(project: "Project") -> dict | None:
    project = project.home                            # анкета одна на проект: раздел живёт по ней же
    path = project.root / "setup.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise ProjectError(f"projects/{project.name}/setup.json: битый JSON ({e})")
    return data.get("answers") if isinstance(data, dict) and isinstance(data.get("answers"), dict) else {}


def missing_setup(project: "Project") -> list:
    """Обязательные вопросы анкеты без ответа. Пусто — проект настроен.

    Проекты, чьи правила написаны руками до анкеты (antishkola, firuza), считаются настроенными:
    их rules.md уже не шаблон. Новый проект с нетронутым шаблоном — не настроен.
    """
    project = project.home
    answers = load_setup(project)
    if answers is None:
        rules = project.rules_text().strip()
        if rules and rules != RULES_TEMPLATE.format(title=project.title).strip():
            return []
        answers = {}
    return [q for q in SETUP_QUESTIONS if q.get("required") and not _answer(answers.get(q["id"]))]


def setup_markdown(answers: dict) -> str:
    lines = [SETUP_BEGIN, "## Анкета проекта", ""]
    for q in SETUP_QUESTIONS:
        value = _answer(answers.get(q["id"]))
        if value:
            lines.append(f"- **{q['q']}:** {value}")
    return "\n".join(lines + ["", SETUP_END])


def save_setup(project: "Project", answers: dict) -> list:
    """Ответы анкеты → setup.json, блок «Анкета проекта» в rules.md и умолчания project.json.

    Блок между метками переписывается целиком, остальной rules.md — нет: правила, дописанные руками
    или ИИ, анкета не трогает. Возвращает обязательные вопросы, оставшиеся без ответа.
    """
    known = {q["id"] for q in SETUP_QUESTIONS}
    unknown = set(answers) - known
    if unknown:
        raise ProjectError(f"В анкете нет вопросов: {', '.join(sorted(unknown))}")
    clean = {k: v for k, v in answers.items() if _answer(v)}
    (project.root / "setup.json").write_text(json.dumps({"answers": clean}, ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8")
    rules = project.rules_text() or RULES_TEMPLATE.format(title=project.title)
    block = setup_markdown(clean)
    if SETUP_BEGIN in rules and SETUP_END in rules:
        head, rest = rules.split(SETUP_BEGIN, 1)
        rules = head + block + rest.split(SETUP_END, 1)[1]
    else:
        lines = rules.splitlines()
        at = next((i + 1 for i, line in enumerate(lines) if line.startswith("# ")), 0)
        rules = "\n".join(lines[:at] + ["", block, ""] + lines[at:]).rstrip() + "\n"
    project.rules.write_text(rules, encoding="utf-8")
    # умолчания роликов из ответов: язык, форматы площадок, нужен ли призыв
    path = project.root / "project.json"
    config = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    if _answer(clean.get("language")) in ("ru", "en"):
        config["language"] = _answer(clean["language"])
    platforms = clean.get("platforms") or []
    if isinstance(platforms, list) and platforms:
        config.setdefault("brief", {})["formats"] = sorted({FORMAT_OF.get(p, "9:16") for p in platforms},
                                                           key=lambda f: f != "9:16")
    if "cta" in clean:
        config["cta"] = "без" not in _answer(clean["cta"]).lower()
    path.write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    load_config(path, project.name)                   # проверка: записанное читается
    return missing_setup(Project(project.name))


def create(name: str, title: str = "") -> Project:
    """Каркас нового проекта. Существующий не трогается."""
    if not NAME_RE.match(name or ""):
        raise ProjectError(f"Плохое имя проекта «{name}»: латиница в нижнем регистре, цифры и дефис "
                           f"(например firuza или client-2)")
    root = PROJECTS_DIR / name
    if root.exists():
        raise ProjectError(f"Проект {name} уже есть: projects/{name}/ — его не трогаю")
    for sub in ("input", "output", "references"):
        (root / sub).mkdir(parents=True)
        (root / sub / ".gitkeep").write_text("", encoding="utf-8")
    config = {"title": title or name, "language": "ru", "cta": False, "face_max": None,
              "brief": {"style": "viral-behind", "formats": ["9:16"], "notes": ""},
              "_note": "Умолчания для всех роликов проекта; бриф ролика в студии меняет только своё. "
                       "cta — финальная плашка «смотри у меня в профиле» (она про профиль Валеры). "
                       "face_max — порог засвета лица по серии роликов; null — не мерить."}
    (root / "project.json").write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (root / "rules.md").write_text(RULES_TEMPLATE.format(title=title or name), encoding="utf-8")
    (root / "references" / "links.md").write_text("# Референсы\n\n<!-- ссылка — и что в ней взять -->\n",
                                                  encoding="utf-8")
    return Project(name)


SECTION_RULES = """# Правила раздела «{title}»

Только то, чем этот раздел отличается от проекта: правила проекта ИИ читает раньше и они действуют
и здесь. Например: формат 16:9 вместо вертикали, длина, свой тип монтажа, что тут нельзя.

-
"""


def slug_of(title: str) -> str:
    """Имя папки раздела из названия: «Рилс» → rils, «YouTube 16:9» → youtube-16-9."""
    table = str.maketrans({"а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh", "з": "z",
                           "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
                           "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "c", "ч": "ch", "ш": "sh", "щ": "sch",
                           "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya"})
    return re.sub(r"[^a-z0-9]+", "-", title.lower().translate(table)).strip("-")[:32] or "section"


def create_section(project: str, title: str, kind: str = "talking", slug: str = "", formats: list | None = None) -> "Section":
    """Новый раздел проекта: section.json, input/, output/, rules.md. Существующий не трогается."""
    parent = get(project)
    if parent.parent is not None:
        raise ProjectError("Раздел в разделе не делаю: разделы — один уровень внутри проекта")
    if kind not in KINDS:
        raise ProjectError(f"Тип раздела — {' или '.join(KINDS)}")
    slug = slug or slug_of(title)
    if not NAME_RE.match(slug) or slug in RESERVED:
        raise ProjectError(f"Плохое имя раздела «{slug}»: латиница, цифры, дефис; не {', '.join(sorted(RESERVED))}")
    root = parent.root / slug
    if root.exists():
        raise ProjectError(f"Раздел {parent.name}/{slug} уже есть — его не трогаю")
    for sub in ("input", "output"):
        (root / sub).mkdir(parents=True)
        (root / sub / ".gitkeep").write_text("", encoding="utf-8")
    config = {"title": title.strip() or slug, "kind": kind}
    if formats:
        config["brief"] = {"formats": formats}
    (root / SECTION_FILE).write_text(json.dumps(config, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (root / "rules.md").write_text(SECTION_RULES.format(title=config["title"]), encoding="utf-8")
    return get(f"{parent.name}/{slug}")


def move(stem: str, target: str) -> list:
    """Перенести видео в другой проект или раздел: исходник (или сборку) и его выпуски. work/<имя>/ общий —
    решения, транскрипт и маска остаются при ролике. Возвращает [(откуда, куда)]."""
    entry = index().get(stem)
    if not entry:
        raise ProjectError(f"Ролика {stem} нет ни в одном проекте")
    src_project, path = entry
    dest = get(target)
    if dest == src_project:
        return []
    moves = [path]
    pack = src_project.input / stem
    if pack.is_dir() and pack != path:
        moves.append(pack)                            # собранная сборка: файл и папка сырья едут вместе
    outs = [f for f in src_project.output.glob(f"{stem}*") if belongs(f.name, stem)] if src_project.output.is_dir() else []
    plan = [(m, dest.input / m.name) for m in moves] + [(f, dest.output / f.name) for f in outs]
    busy = [rel(b) for _, b in plan if b.exists()]
    if busy:
        raise ProjectError(f"В {dest.name} уже есть: {', '.join(busy)} — ничего не переношу")
    done = []
    for a, b in plan:
        b.parent.mkdir(parents=True, exist_ok=True)
        a.rename(b)
        done.append((rel(a), rel(b)))
    return done


def check() -> list:
    """Все проекты: конфиги читаются, стили брифа существуют, имена не повторяются. Список ошибок."""
    import styles
    problems = []
    if DEFAULT not in names():
        problems.append(f"нет проекта по умолчанию projects/{DEFAULT}/")
    for name in names():
        try:
            for project in [Project(name)] + Project(name).sections():
                styles.check_brief(project.config["brief"], f"projects/{project.name} → brief")
                if "style" in project.config["brief"]:
                    styles.load_style(project.config["brief"]["style"])
        except (ProjectError, styles.StyleError) as e:
            problems.append(str(e))
    try:
        index()
    except ProjectError as e:
        problems.append(str(e))
    return problems


def main():
    ap = argparse.ArgumentParser(description="Проекты монтажа")
    sub = ap.add_subparsers(dest="cmd")
    new = sub.add_parser("new", help="создать каркас проекта")
    new.add_argument("name")
    new.add_argument("--title", default="")
    where = sub.add_parser("where", help="чей ролик")
    where.add_argument("stem")
    ready = sub.add_parser("ready", help="настроен ли проект: обязательные вопросы анкеты без ответа")
    ready.add_argument("name")
    sec = sub.add_parser("section", help="создать раздел проекта")
    sec.add_argument("project")
    sec.add_argument("title")
    sec.add_argument("--kind", default="talking", choices=sorted(KINDS))
    sec.add_argument("--slug", default="")
    mv = sub.add_parser("move", help="перенести видео в другой проект или раздел (исходник и выпуски)")
    mv.add_argument("target", help="проект или «проект/раздел»")
    mv.add_argument("stems", nargs="+")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    try:
        if args.check:
            problems = check()
            for p in problems:
                print(f"  ✗ {p}")
            if problems:
                sys.exit(1)
            print(f"  ✓ проекты в порядке: {', '.join(names())}")
        elif args.cmd == "new":
            project = create(args.name, args.title)
            print(f"  ✓ проект {project.name}: projects/{project.name}/\n"
                  f"    исходники — в input/, референсы — в references/, правила — rules.md,\n"
                  f"    стиль и форматы по умолчанию — project.json\n"
                  f"    до первого монтажа ответь на анкету: студия → «Проект → Настроить проект»\n"
                  f"    ({', '.join(q['q'] for q in SETUP_QUESTIONS if q.get('required'))})")
        elif args.cmd == "ready":
            left = missing_setup(get(args.name))
            if left:
                sys.exit(f"✗ проект {args.name} не настроен — нет ответов: " + "; ".join(q["q"] for q in left)
                         + ". Спроси человека (студия: «Проект → Настроить проект») и не монтируй до ответа")
            print(f"  ✓ проект {args.name} настроен")
        elif args.cmd == "section":
            section = create_section(args.project, args.title, args.kind, args.slug)
            print(f"  ✓ раздел {section.name} — «{section.title}» ({KINDS[section.config['kind']]})")
        elif args.cmd == "move":
            for stem in args.stems:
                done = move(stem, args.target)
                print(f"  ✓ {stem} → {args.target}" + ("" if done else " (уже там)"))
        elif args.cmd == "where":
            project = of(args.stem)
            print(f"{args.stem} → {project.name} ({project.title})")
        else:
            found = index()
            for project in all_projects():
                stems = [s for s, (p, _) in found.items() if p == project]
                mark = " · по умолчанию" if project.name == DEFAULT else ""
                print(f"  {project.name} — {project.title}{mark}: {len(stems)} исх.")
                for stem in sorted(stems):
                    print(f"      {stem}")
    except ProjectError as e:
        sys.exit(f"✗ {e}")


if __name__ == "__main__":
    main()
