#!/usr/bin/env python3
"""Данные клиентов — отдельно от движка (23.10.2026).

Валера 23.10.2026: «общий движок, клиентов отдельно, в этом и смысл». До этого в одном репозитории лежали и код, и
проекты заказчиц (анкеты, правила с цитатами, тексты речи их роликов) — раздать движок другу значило раздать клиентов.

Теперь две истории в одной папке:
  движок   — git этой папки (origin): scripts/, presets/, web/, docs/, правила. projects/ и work/ он не видит (.gitignore).
  клиенты  — свой git в .clients/ с той же рабочей папкой: projects/ (анкеты, правила, DESIGN.md, шрифты бренда) и из
             work/ — решения режиссёра и транскрипты (что именно — scripts/clients.gitignore, как раньше было в .gitignore
             движка). Видео, дубли, маски и рендеры — нигде, они пересобираются из исходника.

Пути не меняются: work/<имя>/page.py, projects/<проект>/rules.md — там же, где были. У каждого человека свой репозиторий
клиентов (приватный) — или никакого: монтаж работает и без него.

  .venv/bin/python scripts/clients.py                 # состояние: подключён ли, что изменилось
  .venv/bin/python scripts/clients.py ensure          # проект по умолчанию есть (установка, старт студии)
  .venv/bin/python scripts/clients.py init <url>      # завести: свой приватный репозиторий клиентов
  .venv/bin/python scripts/clients.py clone <url>     # на другой машине: забрать клиентов в эту папку
  .venv/bin/python scripts/clients.py save "что сделал"   # сохранить решения и правила: коммит и push
  .venv/bin/python scripts/clients.py pull            # забрать чужие правки
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from common import ROOT  # noqa: E402

GIT_DIR = ROOT / ".clients"
SPEC = Path(__file__).resolve().parent / "clients.gitignore"
TRACKED = ("projects", "work")


class ClientsError(RuntimeError):
    """По-русски, с тем, что сделать."""


def git(*args, check: bool = True, capture: bool = True) -> str:
    cmd = ["git", f"--git-dir={GIT_DIR}", f"--work-tree={ROOT}", *args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=capture, text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        raise ClientsError(f"git {' '.join(args[:2])}: {(r.stderr or r.stdout or '').strip()[-400:]}")
    return (r.stdout or "").strip()


def connected() -> bool:
    return (GIT_DIR / "HEAD").is_file()


def candidates() -> list:
    """Файлы клиентов, которые храним: по scripts/clients.gitignore (тот же отбор, что был в .gitignore движка до 23.10).
    .gitignore движка здесь не действует: ls-files без --exclude-standard читает только данный список."""
    out = git("ls-files", "-o", "-c", f"--exclude-from={SPEC}", "--", *TRACKED)
    return sorted({line for line in out.splitlines() if line})


def _setup_repo() -> None:
    git("config", "core.quotepath", "false")
    git("config", "core.autocrlf", "false")
    git("config", "status.showUntrackedFiles", "no")         # в status — только то, что уже храним


def init(url: str | None = None) -> str:
    if connected():
        raise ClientsError(f"данные клиентов уже подключены ({GIT_DIR.name}/) — save / pull")
    subprocess.run(["git", f"--git-dir={GIT_DIR}", "init", "-q", "-b", "main"], cwd=ROOT, check=True, capture_output=True)
    _setup_repo()
    if url:
        git("remote", "add", "origin", url)
    return save("Данные клиентов: проекты и решения роликов отдельно от движка", push=bool(url))


def clone(url: str) -> str:
    if connected():
        raise ClientsError("данные клиентов уже подключены — clients.py pull")
    subprocess.run(["git", "clone", "-q", "--bare", url, str(GIT_DIR)], check=True, capture_output=True)
    git("config", "--unset", "core.bare", check=False)
    git("config", "remote.origin.fetch", "+refs/heads/*:refs/remotes/origin/*")
    _setup_repo()
    git("fetch", "-q", "origin")
    # файлы клиентов кладутся в папку; то, что уже лежит под тем же именем, не затирается молча
    clash = [p for p in git("ls-tree", "-r", "--name-only", "origin/main").splitlines() if (ROOT / p).exists()]
    if clash:
        raise ClientsError(f"в папке уже есть файлы клиентов ({len(clash)}: {', '.join(clash[:3])}…) — перенеси их или "
                           f"удали .clients/ и сделай clone в чистую папку")
    git("checkout", "-q", "-B", "main", "origin/main")
    return f"✓ клиенты на месте: {len(candidates())} файлов"


def save(message: str, push: bool = True) -> str:
    if not connected():
        raise ClientsError("данные клиентов не подключены: clients.py init <url своего приватного репозитория> "
                           "(или init без url — только на этой машине)")
    files = candidates()
    for i in range(0, len(files), 200):
        git("add", "-f", "--", *files[i:i + 200])
    git("add", "-u", "--", *TRACKED)                          # удалённые и изменённые из хранимого
    note = "· изменений нет"
    if git("diff", "--cached", "--name-only"):
        # на чистой Windows у git нет имени автора — коммит клиентов не должен падать из-за этого
        who = [] if git("config", "user.email", check=False) else ["-c", "user.name=Монтаж Reels", "-c", "user.email=reels@localhost"]
        git(*who, "commit", "-q", "-m", message)
        note = f"✓ сохранено: {message}"
    if push and git("remote", check=False):
        git("push", "-q", "-u", "origin", "main")             # и то, что не ушло в прошлый раз (не было сети)
        note += " → отправлено"
    return note


def pull() -> str:
    if not connected():
        raise ClientsError("данные клиентов не подключены — clients.py clone <url>")
    git("pull", "-q", "--ff-only", "origin", "main")
    return "✓ забрал"


def status() -> str:
    import projects
    lines = [f"проект по умолчанию: {projects.DEFAULT}" + ("" if projects.DEFAULT in projects.names() else " (ещё нет — ensure)"),
             f"проекты: {', '.join(projects.names()) or 'нет'}"]
    if not connected():
        lines.append("данные клиентов: не подключены (монтаж работает и так; хранить — clients.py init <url>)")
    else:
        remote = git("remote", "get-url", "origin", check=False) or "только на этой машине"
        changed = git("status", "--porcelain", "--", *TRACKED).splitlines()
        new = [f for f in candidates() if f not in set(git("ls-files", "--", *TRACKED).splitlines())]
        lines.append(f"данные клиентов: .clients/ → {remote}; изменено {len(changed)}, новых {len(new)}"
                     + (" — clients.py save «что сделал»" if changed or new else ""))
    return "\n".join(lines)


def main():
    import host
    import projects
    host.utf8_console()
    ap = argparse.ArgumentParser(description="Данные клиентов отдельно от движка")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("ensure")
    i = sub.add_parser("init")
    i.add_argument("url", nargs="?")
    c = sub.add_parser("clone")
    c.add_argument("url")
    s = sub.add_parser("save")
    s.add_argument("message", nargs="?", default="Решения и правила роликов")
    s.add_argument("--no-push", action="store_true")
    sub.add_parser("pull")
    args = ap.parse_args()
    try:
        if args.cmd == "ensure":
            p = projects.ensure_default()
            print(f"✓ проект по умолчанию: {p.name} ({p.title})")
        elif args.cmd == "init":
            print(init(args.url))
        elif args.cmd == "clone":
            print(clone(args.url))
        elif args.cmd == "save":
            print(save(args.message, push=not args.no_push))
        elif args.cmd == "pull":
            print(pull())
        else:
            print(status())
    except (ClientsError, projects.ProjectError) as e:
        sys.exit(f"✗ {e}")
    except subprocess.CalledProcessError as e:
        sys.exit(f"✗ git: {(e.stderr or b'').decode('utf-8', 'replace').strip()[-300:]}")


if __name__ == "__main__":
    main()
