// Ручные правки монтажной поверх страницы ролика (work/<имя>/timeline.json → edits.js → window.EDITS).
//
// Слой графики (блок .g в #behind/#front) можно:
//   сдвинуть во времени целиком — все твины, чьи цели внутри блока (shift, секунды);
//   выключить (mute);
//   подвинуть и масштабировать на кадре (dx, dy — пиксели сцены; scale) — свойствами CSS translate и
//   scale: они складываются с transform, который анимирует GSAP, и анимацию не ломают;
//   перекрасить (color) и сменить шрифт (font — .ttf без расширения или .otf с ним: движка или проекта, scripts/fonts.py);
//   переписать текст (texts — тексты блока по порядку, как они стоят в разметке).
// Субтитры (EDITS.captions): шрифт, цвет, цвет акцента, масштаб и сдвиг по высоте.
//
// Звук и видео внутри блока сдвигает сборка в самой разметке (timeline.patch_page): их время
// HyperFrames читает из атрибутов, а не из таймлайна. Вызов — строкой страницы перед
// window.__timelines["main"] = tl; ошибка здесь перебрасывается ею с текстом (иначе браузер покажет
// обезличенное «Script error.»).
(function () {
  "use strict";
  const family = (font) => `Студия ${font}`;

  function fontFaces(fonts) {
    if (!fonts.size) return;
    const css = [...fonts].map((f) => `@font-face { font-family: "${family(f)}"; src: url("assets/fonts/${/\.(ttf|otf)$/i.test(f) ? f : f + ".ttf"}"); }`).join("\n");
    const st = document.createElement("style");
    st.id = "studio-fonts";
    st.textContent = css;
    document.head.appendChild(st);
  }

  // текстовые узлы блока по порядку — те же, что студия показывает в свойствах слоя
  function textNodes(el) {
    const out = [], walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    for (let n = walk.nextNode(); n; n = walk.nextNode()) if (n.nodeValue.trim()) out.push(n);
    return out;
  }

  function applyEdits(tl) {
    const E = window.EDITS || {};
    const fonts = new Set();
    for (const [id, e] of Object.entries(E.items || {})) {
      const el = document.getElementById(id);
      if (!el) throw new Error(`на странице нет #${id} — блок переименовали? Сними правку на дорожке`);
      if (el.tagName === "AUDIO") continue;
      if (e.mute) el.style.display = "none";
      if (e.shift) {
        for (const tw of tl.getChildren(true, true, false)) {
          const ts = tw.targets ? tw.targets() : [];
          if (ts.some((x) => x instanceof Element && (x === el || el.contains(x)))) tw.startTime(tw.startTime() + e.shift);
        }
      }
      if (e.dx || e.dy) el.style.translate = `${e.dx || 0}px ${e.dy || 0}px`;
      if (e.scale && e.scale !== 1) el.style.scale = String(e.scale);
      if (e.color) el.style.color = e.color;
      if (e.font) { fonts.add(e.font); el.style.fontFamily = `"${family(e.font)}", sans-serif`; }
      if (Array.isArray(e.texts)) {
        const nodes = textNodes(el);
        if (e.texts.length !== nodes.length) {
          throw new Error(`#${id}: текстов в правке ${e.texts.length}, а на странице ${nodes.length} — блок изменился, перепиши текст в студии`);
        }
        nodes.forEach((n, i) => { n.nodeValue = e.texts[i]; });
      }
    }
    // свой текст на кадре (кнопка «Текст» в монтажной): блок .g в #front, влетает и уходит движением,
    // как графика ИИ, — правила страницы (не висит дольше 5 с, не в серых зонах) действуют и на него
    const root = document.getElementById("root"), front = document.getElementById("front") || root;
    const W = Number(root.dataset.width) || 1080;
    for (const t of E.texts || []) {
      const box = document.createElement("div");
      box.id = `ut-${t.id}`;
      box.className = "g ut";
      fonts.add(t.font);
      box.style.cssText = `position:absolute;left:${t.x}px;top:${t.y}px;translate:-50% -50%;width:max-content;`
        + `max-width:${W - 240}px;text-align:center;white-space:pre-wrap;font-size:${t.size}px;line-height:1.05;`
        + `color:${t.color};font-family:"${family(t.font)}",sans-serif;text-shadow:0 4px 18px rgba(0,0,0,.45);opacity:0;`
        + (t.box ? `background:${t.box};padding:.12em .38em .18em;border-radius:.18em;text-shadow:none;` : "");
      box.textContent = t.text;
      const flash = document.getElementById("flash");
      if (flash && flash.parentElement === front) front.insertBefore(box, flash); else front.appendChild(box);
      const out = Math.max(t.t0 + 0.25, t.t1 - 0.18);
      if (t.anim === "fade") tl.fromTo(box, { opacity: 0 }, { opacity: 1, duration: 0.25, ease: "power1.out" }, t.t0);
      else if (t.anim === "slide") tl.fromTo(box, { opacity: 0, y: 60 }, { opacity: 1, y: 0, duration: 0.3, ease: "power3.out" }, t.t0);
      else if (t.anim === "none") tl.set(box, { opacity: 1 }, t.t0);
      else tl.fromTo(box, { opacity: 0, scale: 1.35, filter: "blur(10px)" }, { opacity: 1, scale: 1, filter: "blur(0px)", duration: 0.22, ease: "power3.out" }, t.t0);
      tl.to(box, { opacity: 0, scale: 0.94, filter: "blur(8px)", duration: 0.18, ease: "power2.in" }, out);
    }
    const c = E.captions || {};
    if (Object.keys(c).length) {
      if (c.font) fonts.add(c.font);
      const rules = [];
      const cap = [];
      if (c.font) cap.push(`font-family: "${family(c.font)}", sans-serif !important`);
      if (c.color) cap.push(`color: ${c.color} !important`);
      if (cap.length) rules.push(`#caps .cap { ${cap.join("; ")}; }`);
      if (c.accent) rules.push(`#caps .cap.accent { color: ${c.accent} !important; }`);
      if (c.dy || (c.scale && c.scale !== 1)) {
        rules.push(`#caps { translate: 0 ${c.dy || 0}px; scale: ${c.scale || 1}; transform-origin: 50% ${c.origin || 70}%; }`);
      }
      const st = document.createElement("style");
      st.id = "studio-captions";
      st.textContent = rules.join("\n");
      document.head.appendChild(st);
    }
    fontFaces(fonts);
  }

  window.REELS_EDITS = applyEdits;
})();
