// Хук старта Claude Code и Codex: поднять студию монтажа (scripts/studio_up.py).
//
// Почему Node, а не строка оболочки: хук должен одинаково работать на Mac (bash/zsh) и на
// Windows (Git Bash у Claude, PowerShell или cmd у Codex). Синтаксис «[ -x … ] && … || true»
// понимает только bash, а `node scripts/studio_hook.mjs` понимают все. Node есть везде, где
// стоит проект: на нём работает HyperFrames.
//
// Хук никогда не роняет сессию агента: что бы ни случилось — выход 0.
import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

try {
  const root = join(dirname(fileURLToPath(import.meta.url)), "..");
  const python = [join(root, ".venv", "bin", "python"), join(root, ".venv", "Scripts", "python.exe")]
    .find((path) => existsSync(path));
  if (python) {
    spawnSync(python, [join(root, "scripts", "studio_up.py")], {
      cwd: root,
      stdio: ["ignore", "inherit", "inherit"],
      timeout: 18000,
      env: { ...process.env, PYTHONUTF8: "1", PYTHONIOENCODING: "utf-8" },
    });
  }
} catch {
  // студия — удобство, а не условие работы агента
}
process.exit(0);
