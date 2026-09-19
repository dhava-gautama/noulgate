// noulgate OMP/Pi hook: gate mutating bash commands with Jev before they run.
//
// Two layers, matching scripts/jev-gate-hook.py exactly:
//   1. A denylist of destructive/irreversible commands blocks outright.
//   2. Other mutating commands get a live Jev tool_gate read logged as advisory.
// Reads, non-mutating commands, and any error fail open (the call runs).
//
// Discovered at ~/.omp/agent/hooks/pre/jev-gate.ts (OMP) or the Pi equivalent.
// The extension runner loads factories from hooks/pre/ only.

import type { HookAPI } from "@oh-my-pi/pi-coding-agent/extensibility/hooks";

import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

// The repo the hook runs `python -m jev` from. Set JEV_HELPER_ROOT, or the
// marker the installer writes next to the installed SKILL.md. Default: the
// parent of this script's directory (scripts/ -> repo root).
const HELPER_ROOT =
  process.env.JEV_HELPER_ROOT ??
  dirname(dirname(fileURLToPath(import.meta.url)));

// The only commands a hook may block: irreversible, high-blast-radius.
const DESTRUCTIVE =
  /(rm\s+-[a-z]*r[fd]?\s+[^-]|\bdd\b\s+.*\bof=\/dev\/|\bmkfs\b|\bshred\b|\b(?:drop|truncate)\s+(?:database|table)\b|\bgit\s+push\b[^|]*--force\b|\bgit\s+push\s+-f\b|\bkill\s+-9\b.*\b1\b|\bsudo\s+(?:rm|dd|mkfs)\b)/i;

// Mutating commands that get an advisory Jev read (logged, not blocked).
const MUTATING =
  /\b(rm|mv|cp|chmod|chown|tee|dd|git\s+(push|commit|reset|rebase|merge|clean|rm)|curl\s+[^|]*-X\s*(POST|PUT|DELETE|PATCH)|curl\s+[^|]*--data|pip\s+install|npm\s+(install|publish|run\s+deploy)|apt|apt-get|brew|deploy|kubectl|docker\s+(run|push|rm)|systemctl|kill|pkill|sudo)\b/i;

export default function hook(pi: HookAPI): void {
  pi.on("tool_call", async (event) => {
    if (event.toolName !== "bash") return;
    const cmd = String(event.input?.command ?? "");
    if (!cmd) return;

    // Layer 1: the denylist blocks with no model call.
    if (DESTRUCTIVE.test(cmd)) {
      return {
        block: true,
        reason:
          "jev gate: blocked a destructive/irreversible command (denylist). " +
          "Run it by hand if you mean it.",
      };
    }

    // Layer 2: advisory Jev read on other mutating commands, live only. The
    // result is logged through the hook logger; the command still runs.
    if (process.env.JEV_ALLOW_LIVE !== "1" || !MUTATING.test(cmd)) return;
    try {
      const result = await pi.exec(
        "python3",
        [
          "-m",
          "jev",
          "decide",
          "--pack",
          "tool_gate",
          "--goal",
          `run this shell command: ${cmd.slice(0, 400)}`,
          "--tool",
          "shell",
          "--live",
          "--compact",
        ],
        { cwd: HELPER_ROOT, timeout: 20_000 },
      );
      if (result.code === 0) {
        const out = JSON.parse(result.stdout);
        pi.logger?.info?.(
          `jev advisory: ${out.advice} (side_effect ${out.signals?.side_effect ?? 0})`,
        );
      }
    } catch {
      // fail open: an advisory failure never blocks the command
    }
    return;
  });
}
