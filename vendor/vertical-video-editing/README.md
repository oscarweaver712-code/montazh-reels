# Vertical Video Editing Skill

> **Turn a script + talking-head footage into a polished, creator-grade vertical (9:16) short — automatically.** A [Claude Code](https://claude.com/claude-code) / Claude Agent **skill** that edits short-form video the way a senior editor would: engineered hooks, A‑roll/B‑roll cutting, eased camera moves, an editorial design system, layered SFX, and a render verification gate — rendered with [HyperFrames](https://www.npmjs.com/package/hyperframes).

<p align="center">
  <code>npx vertical-video-editing-skill</code>
</p>

<p align="center">
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-features">Features</a> ·
  <a href="#-how-it-works">How it works</a> ·
  <a href="#-styles">Styles</a> ·
  <a href="#-requirements">Requirements</a> ·
  <a href="#-faq">FAQ</a>
</p>

---

## What is this?

This is a **packaged AI skill** for editing **short-form vertical video** (TikTok, Reels, YouTube Shorts — 1080×1920, 9:16). You give your AI agent an approved script, your voiceover/talking-head media, and some gathered B‑roll/assets. The skill encodes the *editing standard* — the taste, the rules, and the workflow — so the agent produces a finished MP4 that looks like a real creator made it, not like generic AI slideshow output.

It does **not** reinvent rendering. It rides on top of **HyperFrames** (an HTML + GSAP video composition engine) and adds the layer that actually makes shorts good: the hook grammar, the cutting rhythm, the camera-motion physics, the design system, the sound design, and a hard verification gate.

**Who it's for:** creators, agencies, and developers building automated video pipelines who want creator-grade output instead of the uniform-1s-cuts, default-font, stock-template look that most AI video tools produce.

---

## ✨ Features

- 🎬 **Engineered hooks (first 1–3s)** — pattern interrupts and split-panels that grow into the full 9:16 frame. Never opens on a static talking head.
- ✂️ **A‑roll / B‑roll cutting** — your talking head is the spine; B‑roll covers and punctuates it. Non-metronomic cuts down to **0.2s**, paced to the script's energy — never robotic 1‑second cuts.
- 🎥 **Eased camera-motion system** — zoom pushes and pans with an explicit **anti-jitter contract** (GPU-promoted layers, `force3D`, animate-the-wrapper) so motion is smooth in the *render*, not just the preview.
- 🗞️ **Editorial "designed page" look** — ten reusable layout patterns: mixed serif/sans headlines, paper & dark-grid grounds, stacked splits with seam captions, highlight-bar supers, name pills, **headline cards, UI-card stacks**, and more. Frames are designed pages, not video with text on top.
- 🧑‍🦱 **Face-safe framing** — automatically biases crops so faces stay centered (eyes in the upper third) instead of getting chopped by panel seams.
- 🔢 **Themed motion graphics** — number/stat counters, spec/JSON cards, callouts, poster splits, chart builds — all designed on *your* style theme, not a generic template.
- 🔊 **Rights-free SFX + clean audio** — synthesizes whooshes/clicks/risers/impacts with ffmpeg and mixes everything into **one pre-mixed master track** (no multi-`<audio>` echo/desync).
- 🎨 **Pluggable visual styles** — a `FRAME.md` design-token system. Ship your brand's colors, fonts, and components once; the editor themes every video from it. **Add your own styles** in seconds.
- ✅ **Render verification gate** — a bundled `verify-render.mjs` script asserts 9:16 dimensions, duration, h264/yuv420p, and audio presence with `ffprobe`. "Looks fine in preview" becomes a hard, scriptable pass/fail.
- 📋 **Auto handoff report** — every edit produces an `edit-report.md`: beat-by-beat decisions, assets used, SFX, and verification evidence.
- 📦 **One-command install** — `npx vertical-video-editing-skill` drops it into your Claude skills folder.

---

## 🚀 Quick start

### 1. Install the skill

```sh
# Global / user-level (installs to ~/.claude/skills/video-editing)
npx vertical-video-editing-skill

# …or into the current project only (./.claude/skills/video-editing)
npx vertical-video-editing-skill --project

# …or a custom skills directory
npx vertical-video-editing-skill --dir /path/to/skills
```

Re-run with `--force` to overwrite an existing install. Restart / reload Claude Code afterward so it picks up the skill.

### 2. Make sure the engines are present

```sh
npx hyperframes --version   # the rendering engine
ffmpeg -version             # for SFX, audio mixing, and verification
```

### 3. Hand the agent your inputs and ask for a short

Point it at a folder like this:

```
your-project/
├── script.md          # approved script with beats/timestamps + on-screen supers
├── voiceover/         # your VO / talking-head clips (the A-roll)
├── assets/
│   ├── manifest.json  # gathered B-roll + a per-beat asset map
│   └── ...            # the media
└── edit/              # the agent writes the finished video here
```

Then prompt: **"Edit this into a 9:16 short using the `vibe-life` style."** The agent runs the non-negotiable `init → preview → lint → render → verify` workflow and hands back a verified MP4 plus an `edit-report.md`.

---

## 🛠 How it works

The skill enforces one workflow (it never hand-authors HTML from scratch — that breaks live-reload and structure):

1. **`npx hyperframes init edit`** — scaffold the project.
2. **Build the edit beat-by-beat** in `index.html` (+ sub-compositions) applying the editing grammar.
3. **Theme from a style** — turn `styles/<style>/FRAME.md` into a concrete design spec (palette tokens, local `@font-face`, motion personality).
4. **Author SFX + one master audio track** with ffmpeg.
5. **`npx hyperframes preview`** — screenshot key beats, confirm pacing/layout/motion.
6. **`npx hyperframes lint`** — fix every error.
7. **`npx hyperframes render`** — final MP4.
8. **Verify** — `node scripts/verify-render.mjs <file>.mp4` + ffmpeg contact-sheet frame checks.

The full standard lives in [`skills/video-editing/SKILL.md`](skills/video-editing/SKILL.md), including inlined references for the editorial look, the camera-move anti-jitter contract, SFX synthesis, style theming, and the report template.

---

## 🎨 Styles

A **style** is a design-token pack (`FRAME.md`) that decides how every video *looks* — colors, type, spacing, components, and motion — without touching the editing logic. **Different style → different look, same craft.**

This repo ships:

| Style       | What it is                                                                 |
|-------------|---------------------------------------------------------------------------|
| `vibe-life` | A worked example: warm editorial — cream paper, ink outline, one italic-serif accent word, peach/butter accents. Includes an HTML showcase. |
| `_template` | A blank starting point — copy it to build your own brand style.           |

### Add your own style

```sh
cd ~/.claude/skills/video-editing/styles   # (or this repo's skills/video-editing/styles)
cp -r _template my-brand
# edit my-brand/FRAME.md — colors, fonts, components, motion personality
```

Then tell the agent to **"theme from `styles/my-brand/FRAME.md`."** See [`styles/README.md`](skills/video-editing/styles/README.md) for the full guide on what makes a good `FRAME.md` (grounds vs. rationed accents, reading vs. display type ramps, local fonts, component tokens, motion personality).

---

## 📦 Requirements

| Tool        | Why                                                | Check                       |
|-------------|----------------------------------------------------|-----------------------------|
| **Claude Code** or a Claude Agent | runs the skill                        | —                           |
| **HyperFrames** | the HTML + GSAP rendering engine               | `npx hyperframes --version` |
| **Node.js 16+** | `npx`, the installer, the verify script        | `node --version`            |
| **ffmpeg / ffprobe** | SFX synthesis, audio mixing, render verification | `ffmpeg -version`     |

---

## 📁 Repo structure

```
vertical-video-editing-skill/
├── README.md                       ← you are here
├── package.json                    ← npx installer + metadata
├── bin/install.mjs                 ← copies the skill into your Claude skills dir
└── skills/
    └── video-editing/
        ├── SKILL.md                ← the editing standard (the skill itself)
        ├── scripts/
        │   └── verify-render.mjs   ← the render verification gate
        └── styles/
            ├── README.md           ← how to add your own style
            ├── _template/FRAME.md  ← copy this to start a style
            └── vibe-life/          ← worked-example style + HTML showcase
```

---

## ❓ FAQ

**Does this generate the video by itself?**
No — it's the *editing brain*. It drives HyperFrames (rendering) and ffmpeg (audio), and it needs you to provide a script and media. It supplies the taste, the rules, and the verification.

**Is it only for 9:16?**
The pacing and hook grammar are written for vertical short-form first (the default and the strongest use case). The style packs also define 16:9 and 1:1 behavior, so the same look can be retargeted.

**Can I use it without Claude Code?**
The skill is a structured `SKILL.md` standard. It's designed for Claude Code / Claude Agents, but the reference material (editorial patterns, camera-move physics, SFX recipes, the verification script) is useful to any editor or pipeline.

**How do I update it?**
Re-run `npx vertical-video-editing-skill --force`.

**How do I uninstall?**
Delete the installed folder, e.g. `rm -rf ~/.claude/skills/video-editing`.

---

## 🙏 Credits

Built on **[HyperFrames](https://www.npmjs.com/package/hyperframes)**. Adopts conventions from [`hyperframes-helper`](https://github.com/robonuggets/hyperframes-helper) (GSAP power-eases, glow captions, the lint gotcha list) and extends them with a 9:16 short-form grammar, an eased camera-motion system, a style-theming pipeline, rights-free SFX synthesis, and a render verification gate. See the provenance section in [`SKILL.md`](skills/video-editing/SKILL.md) for the full adopted-vs-added breakdown.

## 📄 License

[MIT](LICENSE) © adriiita
