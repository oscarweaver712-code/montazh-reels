// Хук «после каждого действия» у агентов студии: человек дописал просьбу, пока ИИ монтирует.
//
// Студия кладёт дописанное в work/_studio/inbox/<разговор>/<время>.json, а агент получает его
// сразу после ближайшего действия — посреди монтажа, а не когда ход закончится через 20 минут.
// Доставленное переименовывается в .done (переименование атомарно: студия и хук не затрут друг
// друга). Чего хук не доставил (Codex без хуков, ход кончился раньше), студия отправит следующим
// ходом сама.
//
// Разговор хук узнаёт из REELS_THREAD — его ставит студия только своим агентам; в обычной сессии
// Claude или Codex переменной нет, и хук выходит сразу. Хук никогда не роняет агента: выход 0.
import { existsSync, readdirSync, readFileSync, renameSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const thread = process.env.REELS_THREAD || "";
try {
  if (/^[\w-]+$/.test(thread)) {
    const root = join(dirname(fileURLToPath(import.meta.url)), "..");
    const box = join(root, "work", "_studio", "inbox", thread);
    if (existsSync(box)) {
      const texts = [];
      for (const name of readdirSync(box).filter((n) => n.endsWith(".json")).sort()) {
        const path = join(box, name);
        try {
          const msg = JSON.parse(readFileSync(path, "utf8"));
          renameSync(path, path.replace(/\.json$/, ".done"));
          if (msg.text) texts.push(msg.text);
        } catch {
          // недописанный файл подхватим следующим действием
        }
      }
      if (texts.length) {
        const context = "Человек дописал, пока ты работаешь (из студии монтажа):\n"
          + texts.map((t) => `— ${t}`).join("\n")
          + "\nУчти это с текущего шага. Если уже сделанное этому противоречит — переделай и скажи об этом в отчёте.";
        process.stdout.write(JSON.stringify({
          hookSpecificOutput: { hookEventName: process.env.REELS_HOOK_EVENT || "PostToolUse", additionalContext: context },
        }));
      }
    }
  }
} catch {
  // не доставили сейчас — доставит студия следующим ходом
}
process.exit(0);
