---
name: antivirus
description: Scan files for viruses, malware, and suspicious content. Use to check downloaded files, specific paths, or the entire Downloads folder.
argument-hint: "[file/folder path or leave empty for ~/Downloads]"
allowed-tools: Read, Grep, Glob, Bash, WebSearch, Agent
---

# Antivirus File Scanner

You are acting as a local antivirus scanner. Your job is to thoroughly inspect files for malicious content, suspicious patterns, and potential threats.

## Target

If `$ARGUMENTS` is provided, scan that specific file or folder.
If `$ARGUMENTS` is empty, scan `~/Downloads/` — focus on files modified in the last 24 hours.

## Scan Procedure

Perform ALL of the following checks for each file. Use parallel tool calls where possible.

### 1. File Type Verification
- Run `file <path>` to determine the true file type
- Compare the actual type with the file extension
- FLAG: extension mismatch (e.g., `.pdf` that is actually an executable, `.jpg` that is a script)
- FLAG: double extensions (e.g., `document.pdf.exe`, `image.jpg.scr`)
- FLAG: dangerous extensions: `.exe`, `.scr`, `.bat`, `.cmd`, `.vbs`, `.vbe`, `.js`, `.jse`, `.wsf`, `.wsh`, `.ps1`, `.msi`, `.com`, `.pif`, `.hta`, `.cpl`, `.reg`, `.inf`, `.dll`, `.sys`, `.drv`, `.app`, `.command`, `.action`, `.workflow`

### 2. Content Analysis
For text-based files (scripts, HTML, office macros, configs):
- Search for obfuscated code (excessive base64, hex encoding, char code arrays)
- Search for shell command execution patterns (`eval`, `exec`, `system`, `subprocess`, `os.system`, `Runtime.getRuntime`, `child_process`)
- Search for network calls to suspicious destinations (raw IPs, unusual ports, known malware C2 patterns)
- Search for credential harvesting patterns (keylogger signatures, clipboard monitoring, password regex)
- Search for persistence mechanisms (crontab, launchd, login items, startup scripts)
- Search for privilege escalation attempts (`sudo`, `dscl`, `chmod 777`, `setuid`)
- Search for data exfiltration patterns (encoding + network send, archive + upload)

### 3. Archive Inspection
For `.zip`, `.tar`, `.gz`, `.rar`, `.7z`, `.dmg`, `.iso`:
- List contents WITHOUT extracting: `zipinfo`, `tar -tf`, `7z l`, `hdiutil info`
- FLAG: archives containing executables or scripts
- FLAG: zip bombs (suspiciously high compression ratio)
- FLAG: password-protected archives (common malware delivery method)

### 4. macOS-Specific Checks
- Check if `.app` bundles are properly signed: `codesign -dv --verbose=4 <path>`
- Check quarantine attribute: `xattr -l <path>` — look for `com.apple.quarantine`
- For `.dmg` files: check if they contain unsigned apps
- For `.pkg` files: inspect with `pkgutil --payload-files <path>` without installing
- Check Gatekeeper status: `spctl --assess --verbose <path>`

### 5. Hash Verification
- Calculate SHA-256 hash: `shasum -a 256 <path>`
- Search the web for the hash to check against known malware databases (VirusTotal, MalwareBazaar)
- FLAG: if hash matches known malware

### 6. Metadata & Permissions
- Check file permissions: `ls -la@` — FLAG unusual permissions (setuid, world-writable)
- Check creation/modification dates — FLAG if metadata dates don't match download time
- Check extended attributes: `xattr -l`

## Output Format

For each scanned file, report:

```
[SAFE/WARNING/DANGER] filename.ext
  Type: actual file type
  Size: file size
  Hash: SHA-256
  Findings: list of any issues found, or "No threats detected"
```

At the end, provide a summary:
```
=== SCAN COMPLETE ===
Files scanned: N
Safe: N | Warnings: N | Threats: N
```

If ANY threats or warnings are found, provide clear recommendations:
- What the threat is
- What the user should do (delete, quarantine, investigate further)
- How to remove the threat if applicable

## Important Rules

- NEVER execute or open suspicious files — only inspect them
- NEVER extract archives — only list contents
- If a file is too large to read, use `head -c` or `xxd` to inspect only headers
- Be thorough but avoid false positives — only flag genuinely suspicious patterns
- When in doubt, flag as WARNING rather than DANGER
- Always explain WHY something is flagged so the user can make an informed decision
