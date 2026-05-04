#!/usr/bin/env python3
"""Shared safe recovery/code-reading tools for Vlad's Telegram agents.

No secrets are printed. Destructive actions are not included.
"""
from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

HOME = Path.home()
BASE = HOME / "Папка тест/fixcraftvp"
LAUNCH_AGENTS = HOME / "Library/LaunchAgents"
LOGS = HOME / "logs"
UID = os.getuid()

SECRET_PATTERNS = [
    re.compile(r"([A-Z0-9_]*(?:TOKEN|KEY|SECRET|PASSWORD|PASS|AUTH|COOKIE|SESSION)[A-Z0-9_]*\s*=\s*)[^\n\r]+", re.I),
    re.compile(r"(bot)[0-9]{8,}:[A-Za-z0-9_-]{20,}", re.I),
    re.compile(r"([A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,})"),
    re.compile(r"(sk-[A-Za-z0-9_-]{20,})"),
]

@dataclass(frozen=True)
class AgentSpec:
    name: str
    aliases: tuple[str, ...]
    label: str | None = None
    plist: Path | None = None
    code: Path | None = None
    pid_file: Path | None = None
    log_file: Path | None = None
    notes: str = ""


def _plist(name: str) -> Path:
    return LAUNCH_AGENTS / name


AGENTS: dict[str, AgentSpec] = {
    "hermes": AgentSpec(
        name="hermes",
        aliases=("гермес", "ты", "тебя", "hermes", "gateway"),
        label="ai.hermes.gateway",
        plist=_plist("ai.hermes.gateway.plist"),
        log_file=LOGS / "hermes-gateway.log",
        notes="Главный Hermes/gateway. Если label отличается, проверь ai.hermes.gateway-vlad-claude.",
    ),
    "hermes-vlad": AgentSpec(
        name="hermes-vlad",
        aliases=("hermes-vlad", "gateway-vlad", "vlad-claude"),
        label="ai.hermes.gateway-vlad-claude",
        plist=_plist("ai.hermes.gateway-vlad-claude.plist"),
        log_file=LOGS / "hermes-gateway-vlad-claude.log",
        notes="Альтернативный Hermes gateway label.",
    ),
    "openai-oauth": AgentSpec(
        name="openai-oauth",
        aliases=("proxy", "прокси", "openai", "oauth", "gpt", "gpt-5.5"),
        label="com.openai-oauth",
        plist=_plist("com.openai-oauth.plist"),
        log_file=LOGS / "openai-oauth.log",
        notes="Локальный ChatGPT Plus/OpenAI OAuth proxy на 127.0.0.1:10531.",
    ),
    "dasha": AgentSpec(
        name="dasha",
        aliases=("даша", "dasha"),
        label="com.vladimir.dasha-bot",
        plist=_plist("com.vladimir.dasha-bot.plist"),
        code=BASE / "dasha-bot/bot.py",
        pid_file=LOGS / "dasha-bot.pid",
        log_file=LOGS / "dasha-bot.log",
    ),
    "bakha": AgentSpec(
        name="bakha",
        aliases=("баха", "бахтияр", "bakha", "bahaproger"),
        label="com.vladimir.bakha-bot",
        plist=_plist("com.vladimir.bakha-bot.plist"),
        code=BASE / "bakha-bot/bot.py",
        pid_file=LOGS / "bakha-bot.pid",
        log_file=LOGS / "bakha-bot.log",
    ),
    "kostya": AgentSpec(
        name="kostya",
        aliases=("костя", "kostya", "coder"),
        label="com.vladimir.kostya-bot",
        plist=_plist("com.vladimir.kostya-bot.plist"),
        code=BASE / "coder-bot/telegram_bot.py",
        log_file=LOGS / "kostya-bot.log",
    ),
    "philip": AgentSpec(
        name="philip",
        aliases=("филип", "филипп", "philip"),
        label="com.vladimir.philip-bot",
        plist=_plist("com.vladimir.philip-bot.plist"),
        code=BASE / "philip-bot/bot.py",
        log_file=LOGS / "philip-bot.log",
    ),
    "peter": AgentSpec(
        name="peter",
        aliases=("петр", "пётр", "доктор", "peter"),
        label="com.vladimir.peter-bot",
        plist=_plist("com.vladimir.peter-bot.plist"),
        code=BASE / "peter-bot/telegram_bot.py",
        log_file=LOGS / "peter-bot.log",
    ),
    "zina": AgentSpec(
        name="zina",
        aliases=("зина", "zina"),
        label="com.vladimir.zina-bot",
        plist=_plist("com.vladimir.zina-bot.plist"),
        code=BASE / "zina-bot/telegram_bot.py",
        log_file=LOGS / "zina-bot.log",
    ),
}


def sanitize(text: str) -> str:
    out = text or ""
    for pat in SECRET_PATTERNS:
        out = pat.sub(lambda m: (m.group(1) if m.lastindex else "") + "[REDACTED]", out)
    return out


def resolve_agent(name: str | None) -> AgentSpec | None:
    if not name:
        return None
    q = name.strip().lower().lstrip("/@")
    q = q.replace("ё", "е")
    if q in AGENTS:
        return AGENTS[q]
    for spec in AGENTS.values():
        for alias in spec.aliases:
            if q == alias.lower().replace("ё", "е"):
                return spec
    # loose contains for phrases like "восстанови Гермеса"
    for spec in AGENTS.values():
        aliases = (spec.name, *spec.aliases)
        if any(a.lower().replace("ё", "е") in q for a in aliases):
            return spec
    return None


def list_agents() -> str:
    lines = ["Агенты восстановления:"]
    for spec in AGENTS.values():
        plist = "plist ok" if spec.plist and spec.plist.exists() else "plist ?"
        code = "code ok" if spec.code and spec.code.exists() else ("no code" if not spec.code else "code ?")
        lines.append(f"- {spec.name}: {plist}, {code}, label={spec.label or '-'}")
    return "\n".join(lines)


def _run(cmd: list[str], timeout: int = 20) -> tuple[int, str, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, sanitize(p.stdout), sanitize(p.stderr)
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", sanitize(str(e))


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def agent_status(name: str | None = None) -> str:
    specs: Iterable[AgentSpec]
    spec = resolve_agent(name) if name else None
    specs = [spec] if spec else AGENTS.values()
    lines: list[str] = []
    for s in specs:
        lines.append(f"## {s.name}")
        if s.pid_file:
            if s.pid_file.exists():
                raw = s.pid_file.read_text(errors="ignore").strip()
                try:
                    pid = int(raw)
                    lines.append(f"pid_file: {pid} ({'alive' if _pid_alive(pid) else 'dead'})")
                except Exception:
                    lines.append(f"pid_file: unreadable ({sanitize(raw)})")
            else:
                lines.append("pid_file: missing")
        if s.plist:
            lines.append(f"plist: {s.plist} ({'exists' if s.plist.exists() else 'missing'})")
        if s.label:
            rc, out, err = _run(["/bin/launchctl", "print", f"gui/{UID}/{s.label}"], timeout=8)
            if rc == 0:
                state = "loaded"
                pid_match = re.search(r"pid = (\d+)", out)
                if pid_match:
                    state += f", pid={pid_match.group(1)}"
                lines.append(f"launchctl: {state}")
            else:
                lines.append(f"launchctl: not loaded ({(err or out).strip()[:180]})")
        if s.log_file and s.log_file.exists():
            try:
                tail = s.log_file.read_text(errors="ignore")[-1200:]
                lines.append("log_tail:\n" + sanitize(tail).strip())
            except Exception as e:
                lines.append(f"log_tail: error {e}")
        if s.notes:
            lines.append("notes: " + s.notes)
        lines.append("")
    return "\n".join(lines).strip()


def restart_agent(name: str) -> str:
    spec = resolve_agent(name)
    if not spec:
        return f"Не знаю агента: {name}\n\n{list_agents()}"
    if not spec.label:
        return f"У агента {spec.name} нет launchctl label."
    if spec.plist and not spec.plist.exists():
        return f"Plist не найден: {spec.plist}"

    before = agent_status(spec.name)
    # bootstrap is safe if not loaded; ignore already-loaded failures
    if spec.plist and spec.plist.exists():
        _run(["/bin/launchctl", "bootstrap", f"gui/{UID}", str(spec.plist)], timeout=15)
    rc, out, err = _run(["/bin/launchctl", "kickstart", "-k", f"gui/{UID}/{spec.label}"], timeout=20)
    after = agent_status(spec.name)
    status = "OK" if rc == 0 else f"WARN rc={rc}: {(err or out).strip()[:400]}"
    return f"Restart {spec.name}: {status}\n\nBEFORE:\n{before}\n\nAFTER:\n{after}"


def recover_agent(name: str | None = None) -> str:
    if not name:
        return "Укажи агента: /recover hermes | dasha | bakha | openai-oauth | all"
    q = name.strip().lower()
    if q in {"all", "все", "всех"}:
        targets = ["openai-oauth", "hermes", "hermes-vlad", "dasha", "bakha", "kostya", "philip", "peter", "zina"]
        chunks = []
        for t in targets:
            chunks.append(restart_agent(t)[:1800])
        return "\n\n---\n\n".join(chunks)
    return restart_agent(name)


def read_code(name: str | None = None, query: str | None = None, max_chars: int = 12000) -> str:
    spec = resolve_agent(name) if name else None
    if not spec:
        return "Укажи агента: /readcode dasha [слово] | bakha | hermes пока без code path"
    if not spec.code:
        return f"Для {spec.name} пока нет code path. Plist: {spec.plist or '-'}"
    path = spec.code
    if not path.exists():
        return f"Код не найден: {path}"
    if path.suffix in {".env", ".key", ".pem"}:
        return "Секретные файлы читать нельзя."
    text = sanitize(path.read_text(encoding="utf-8", errors="ignore"))
    if query:
        q = query.lower()
        lines = text.splitlines()
        hits: list[str] = []
        for i, line in enumerate(lines):
            if q in line.lower():
                start = max(0, i - 4)
                end = min(len(lines), i + 5)
                block = "\n".join(f"{n+1}: {lines[n]}" for n in range(start, end))
                hits.append(block)
                if len("\n\n".join(hits)) > max_chars:
                    break
        body = "\n\n---\n\n".join(hits) or f"В коде {spec.name} не найдено: {query}"
    else:
        body = "\n".join(f"{i+1}: {line}" for i, line in enumerate(text.splitlines()[:260]))
        if len(text.splitlines()) > 260:
            body += f"\n... truncated, total lines={len(text.splitlines())}"
    return f"CODE {spec.name}: {path}\n\n{body[:max_chars]}"


def detect_recovery_intent(text: str) -> tuple[str, str | None] | None:
    low = (text or "").lower().replace("ё", "е")
    recovery_words = ("восстанов", "перезапу", "подними", "оживи", "почини", "рестарт", "restart", "recover")
    code_words = ("прочитай код", "посмотри код", "readcode", "код бота", "исходник")
    if any(w in low for w in code_words):
        spec = resolve_agent(low)
        return ("readcode", spec.name if spec else None)
    if any(w in low for w in recovery_words):
        if "все" in low or "всех" in low or "all" in low:
            return ("recover", "all")
        spec = resolve_agent(low)
        if spec:
            return ("recover", spec.name)
    return None
