#!/usr/bin/env python3
"""Движок — в отдельный чистый репозиторий, без истории, где были клиенты (23.10.2026).

До 23.10.2026 проекты заказчиц и решения их роликов жили в git движка — в истории основного репозитория они остаются
навсегда. Раздавать движок (другу, команде) этой историей нельзя: «общий движок, клиентов отдельно, в этом и смысл».
Поэтому раздаётся репозиторий-снимок: каждый запуск кладёт туда один коммит — дерево текущего HEAD движка (в нём
клиентов уже нет: самопроверка краснеет, если файл клиента попал в индекс) поверх прошлого снимка. История снимков —
только движок; основной репозиторий и его история не меняются.

  .venv/bin/python scripts/engine_publish.py                    # опубликовать HEAD в remote «engine»
  .venv/bin/python scripts/engine_publish.py --remote engine --dry

Правки со стороны (кто-то закоммитил в репозиторий-снимок) сюда не возвращаются сами: забрать их — git fetch engine и
cherry-pick нужных коммитов в основной; публикация поверх них откажет, пока они не забраны.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args, check: bool = True) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"✗ git {' '.join(args[:2])}: {(r.stderr or r.stdout).strip()[-400:]}")
    return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser(description="Опубликовать движок снимком в чистый репозиторий")
    ap.add_argument("--remote", default="engine")
    ap.add_argument("--dry", action="store_true", help="только показать, что уйдёт")
    args = ap.parse_args()
    if not git("remote", "get-url", args.remote, check=False):
        sys.exit(f"✗ нет remote «{args.remote}»: git remote add {args.remote} <ссылка на репозиторий движка>")
    if git("status", "--porcelain", "--untracked-files=no"):
        sys.exit("✗ в движке незакоммиченные правки — сначала коммит (и самопроверка), потом публикация")
    leaked = [f for f in git("ls-files", "--", "projects", "work", "studio").splitlines()
              if f != "projects/README.md" and not f.startswith("studio/_vendor/")]
    if leaked:
        sys.exit(f"✗ в индексе движка файлы клиентов ({len(leaked)}: {', '.join(leaked[:3])}) — не публикую")
    git("fetch", "-q", args.remote)
    parent = git("rev-parse", "-q", "--verify", f"refs/remotes/{args.remote}/main", check=False)
    tree = git("rev-parse", "HEAD^{tree}")
    if parent and git("rev-parse", f"{parent}^{{tree}}") == tree:
        print("· движок уже опубликован — нового нет")
        return
    if parent:
        mine = git("log", "-1", "--format=%B", parent)
        if "engine_publish" not in mine:
            sys.exit(f"✗ в {args.remote}/main чужой коммит ({parent[:8]}): забери его в основной (cherry-pick), потом публикуй")
    head = git("log", "-1", "--format=%h %s")
    message = f"Движок: {head}\n\nСнимок основного репозитория без клиентов (scripts/engine_publish)."
    if args.dry:
        print(f"→ ушло бы в {args.remote}/main: {head} (дерево {tree[:8]}, поверх {parent[:8] if parent else 'пустого'})")
        return
    cmd = ["commit-tree", tree, "-m", message] + (["-p", parent] if parent else [])
    commit = git(*cmd)
    git("push", "-q", args.remote, f"{commit}:refs/heads/main")
    print(f"✓ опубликовано в {args.remote}/main: {head}")


if __name__ == "__main__":
    main()
