# vendor — открытые материалы по сборке роликов через агентов

Скиллы, правила и справочники чужих открытых проектов, взятые 13.10.2026 по просьбе Валеры: «что
можем взять себе сейчас — сразу загружаем бесплатный опенсорс и материалы про сборку роликов через
Claude». Разбор, что из этого и зачем, — docs/АРСЕНАЛ.md.

Правила пользования:
- **Это материалы, а не правила проекта.** При расхождении действуют AGENTS.md и
  .agents/skills/reels. Чужие скиллы лежат не в .agents/skills и .claude/skills — агенты не
  подхватывают их как свои, а читают, когда план или задача к ним отсылает.
- **Код отсюда в конвейере не запускается**, инструкции по установке из чужих README не
  выполняются. Нужное переносится в scripts/ — с проверкой в самопроверке, как всё остальное.
- **AGPL-3.0** (openmontage, hyperframes-motion-director) — только справочник: их код в наш не
  переносится без решения владельца.
- **Облака не заводим:** ключи ElevenLabs, Gemini, fal и подобные не нужны — всё локально.
- Взяты только тексты (и в первой части — нужные скрипты): без медиа, без шрифтов с чужими
  лицензиями, без облачных частей. Что исключено — в SOURCE.md каждого проекта, лицензия рядом.
  Проекты без лицензии (все права у автора) не взяты вовсе.

## Главное — с этого начинать

| Проект | Лицензия | Зачем нам |
|---|---|---|
| [hyperframes-skills](hyperframes-skills/SOURCE.md) | Apache-2.0 | приёмы нашего же движка: стыки сцен, кривые движения, субтитры поверх — первое, что читать к графике |
| [motionmaxxing](motionmaxxing/SOURCE.md) | Apache-2.0 | правила движения уже в docs/АРСЕНАЛ.md; references/motion.md, transitions.md, type.md, slop.md — справочник к странице; precedent.py + library — «что делали профи в таком ударе» для плана; look.py и lint.mjs — образцы проверок к переносу в verify_render и verify_page |
| [video-use](video-use/SOURCE.md) | MIT | skills/manim-video — справочник к ManimGX (у него API как у Manim CE): математика движением для ЕГЭ |
| [taste-skill](taste-skill/SOURCE.md) | MIT | вкус в вёрстке плашек и карточек, правила против «шаблонного ИИ-дизайна» |
| [impeccable](impeccable/SOURCE.md) | Apache-2.0 | полировка и аудит дизайна плашек |
| [emil-skills](emil-skills/SOURCE.md) | MIT | тайминги, кривые, словарь движения, ревью анимаций |
| [opuscar](opuscar/SOURCE.md) | MIT | источник стилей и режиссёрских приёмов для presets/styles |
| [claude-animation-base](claude-animation-base/SOURCE.md) | MIT | на будущее: рукописные мазки, обводки, подчёркивания |
| [collage-broll](collage-broll/SOURCE.md) | MIT | приём коллажа (делать локально, CSS/SVG) и порядок одобрения «идея → кадр → анимация» |
| [open-edit](open-edit/SOURCE.md) | Apache-2.0 | правила реза и транскрипции другого конвейера — для сравнения; VEED.md — их облако, справочно |
| [video-edit-skill](video-edit-skill/SOURCE.md) | Apache-2.0 | «луки» и правило смены кадра каждые 3–5 с — сверка с нашими стилями |
| [claude-video-editing](claude-video-editing/SOURCE.md) | MIT | черновой рез говорящей головы, правило «оставить последний дубль фразы» |

## Ещё — из каталога claudevideo.org (только тексты)

| Проект | Лицензия | Зачем нам |
|---|---|---|
| [3brown1blue](3brown1blue/SOURCE.md) | MIT | к «доске» |
| [anidoodle](anidoodle/SOURCE.md) | Apache-2.0 | рукописные элементы без генерации |
| [automontage-agent](automontage-agent/SOURCE.md) | MIT | наш формат — сверка |
| [beat-synced-edit](beat-synced-edit/SOURCE.md) | MIT | на будущее: музыка в долю |
| [claude-youtube-editor](claude-youtube-editor/SOURCE.md) | MIT | ближайший к нам по задаче конвейер |
| [cut-video](cut-video/SOURCE.md) | MIT | сверка с нашим резом по тишине |
| [data-animation-skills](data-animation-skills/SOURCE.md) | MIT | числа и графики в viz |
| [favstash](favstash/SOURCE.md) | Apache-2.0 | наш формат — сверка |
| [ghost-editor](ghost-editor/SOURCE.md) | MIT | наш формат — сверка |
| [hyperdirector](hyperdirector/SOURCE.md) | Apache-2.0 | план до сборки на нашем движке |
| [hyperframes-motion-director](hyperframes-motion-director/SOURCE.md) | AGPL-3.0 | приёмы на нашем движке |
| [kinetic-typography-skills](kinetic-typography-skills/SOURCE.md) | MIT | крупное слово, маркер на слове |
| [ll-video-decomposer](ll-video-decomposer/SOURCE.md) | MIT | разбор референсов для плана |
| [manim-skill](manim-skill/SOURCE.md) | MIT | к «доске» (ManimGX — тот же API) |
| [map-animation-skills](map-animation-skills/SOURCE.md) | MIT | карты в viz |
| [motion-design-skills](motion-design-skills/SOURCE.md) | MIT | полировка графики |
| [openmontage](openmontage/SOURCE.md) | AGPL-3.0 | как устроен самый популярный открытый конвейер: этапы, роли агентов, проверки |
| [paper-cut](paper-cut/SOURCE.md) | MIT | коллаж локально |
| [recursive-math-animator](recursive-math-animator/SOURCE.md) | MIT | к «доске»: проверка математики в сцене |
| [reelbench](reelbench/SOURCE.md) | Apache-2.0 | покадровый разбор исходника для плана |
| [reelmimic](reelmimic/SOURCE.md) | MIT | разбор референса → стиль; рез говорящей головы; встроенные субтитры |
| [showtime](showtime/SOURCE.md) | MIT | локальный конвейер — сверка подходов |
| [tiktok-video-skills](tiktok-video-skills/SOURCE.md) | MIT | хук и плашки вертикали |
| [vertical-video-editing](vertical-video-editing/SOURCE.md) | MIT | наш формат — сверка |
| [video-script-builder](video-script-builder/SOURCE.md) | MIT | план до сборки |
| [viral-video-decomposer](viral-video-decomposer/SOURCE.md) | MIT | разбор референсов для плана |

Полный каталог скиллов для видео агентами (около 230, лицензии не проверены) — [claudevideo-catalog.md](claudevideo-catalog.md).

Обновить проект: заново выборочно скачать файлы из источника (коммит — в SOURCE.md) и сверить,
что лицензия не поменялась.
