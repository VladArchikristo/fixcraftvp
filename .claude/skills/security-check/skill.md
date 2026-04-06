---
name: security-check
description: Full security audit of the system — open ports, VPN, updates, passwords, firewall, and vulnerabilities.
argument-hint: "[quick/full]"
allowed-tools: Bash, Read, Grep, Glob, WebSearch
---

# System Security Audit

Comprehensive security check of the macOS system.

## Mode

If `$ARGUMENTS` is `quick` — run only critical checks (1-3 minutes).
If `$ARGUMENTS` is `full` or empty — run all checks.

## Checks

### 1. Network Security
- Open ports: `lsof -i -P -n | grep LISTEN`
- Active connections: `netstat -an | grep ESTABLISHED` — flag connections to unusual IPs
- VPN status: check for active `utun` interfaces
- Firewall status: `socketfilterfw --getglobalstate`
- DNS settings: check for DNS leaks

### 2. System Updates
- macOS updates available: `softwareupdate -l`
- Homebrew outdated (if installed): `brew outdated`
- npm global packages outdated: `npm outdated -g`
- Python packages with known vulnerabilities: `pip3 list --outdated`

### 3. File Security
- World-writable files in home: `find ~ -maxdepth 3 -perm -002 -type f`
- Files with setuid/setgid: `find ~ -maxdepth 3 -perm -4000 -o -perm -2000`
- Exposed credentials: search for `.env` files with real tokens, unencrypted private keys
- SSH keys permissions: check `~/.ssh/` permissions

### 4. Application Security
- Unsigned apps in /Applications: check codesign for all .app bundles
- Browser extensions: list installed extensions
- LaunchAgents/LaunchDaemons: check for suspicious entries

### 5. Account Security
- Screen lock enabled: check settings
- FileVault (disk encryption): `fdesetup status`
- Gatekeeper status: `spctl --status`
- SIP (System Integrity Protection): `csrutil status`

### 6. Process Check
- Running processes: flag any suspicious or unknown processes
- High CPU/memory processes: `top -l 1 -n 10`
- Processes with network access

## Output

```
=== SECURITY AUDIT ===

[PASS/WARN/FAIL] Category: Detail

Network:
  [PASS] Firewall: Enabled
  [PASS] VPN: Active
  [WARN] Open ports: 3 found (details...)

System:
  [PASS] SIP: Enabled
  [PASS] FileVault: Enabled
  [WARN] Updates: 2 available

Files:
  [PASS] No exposed credentials found
  [PASS] SSH keys properly secured

Score: 85/100 — Good
Recommendations: (list any fixes needed)
```
