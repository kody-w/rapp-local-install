#!/usr/bin/env python3
"""Score an installer against rapp-local-install/1.0 §3.

Conformance is checkable, not claimable. This reads an installer script and
reports, per rule, what it found and where — so a verdict can be argued with.

    python3 check.py path/to/install.sh
    python3 check.py path/to/install.sh --json

Deliberate limitation, stated rather than hidden: this is static analysis of
shell/PowerShell text. It can prove a pattern is ABSENT far more reliably than
it can prove one is correct. A PASS means "the shape is there"; it does not
mean the logic is sound. Treat a PASS as an invitation to read the code, and a
FAIL as a finding.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SPEC = "rapp-local-install/1.0"


class Rule:
    def __init__(self, key, title, why):
        self.key, self.title, self.why = key, title, why


RULES = [
    Rule("pin", "Requires an exact immutable pin",
         "Two users running the same command a day apart must get identical bytes."),
    Rule("https_only", "Refuses non-HTTPS transport explicitly",
         "Assuming HTTPS is not the same as refusing anything else."),
    Rule("verify", "Verifies artifacts against a publisher manifest",
         "A download nobody hashed is a download nobody checked."),
    Rule("fail_closed", "Every verification path fails closed",
         "A check that degrades to a no-op and reports success is worse than no check."),
    Rule("name_check", "Validates artifact filenames against a pattern",
         "A hash proves bytes are unmodified, not that they are the bytes you asked for."),
    Rule("reverify", "Re-verifies installed binaries on later runs",
         "Presence is not integrity; a directory proves something wrote to it once."),
    Rule("no_global", "Writes nothing outside its root; no elevation",
         "Uninstall should be rm -rf of one directory."),
    Rule("content_addressed", "Versions live at versions/<pin>/",
         "Upgrade must not mutate a working install."),
    Rule("identity", "Queries the runtime's identity after extraction",
         "An archive named darwin-arm64 that reports linux-x64 is worth learning early."),
    Rule("manifest", "Checks an explicit completeness manifest",
         "Including licenses, which are the files most often silently dropped."),
    Rule("provenance", "Writes a provenance record",
         "Otherwise 'which version is this' is answerable only by guessing."),
    Rule("no_remote_exec", "Never executes an unverified remote script",
         "The most common violation and the hardest to notice once habitual."),
    Rule("platform_allowlist", "Supported platform/arch pairs are an allowlist",
         "A platform you do not name is a platform you do not support."),
    Rule("ci_installs", "CI runs the real installer, including the refusal test",
         "A platform without a CI leg is unsupported no matter what the README says."),
    Rule("bundled_runtime", "Required binaries are bundled, not found on PATH",
         "A GUI process does not inherit your shell; PATH-guessing is the bug, not the fix."),
]

# (rule, regex, human description). Multiple patterns may satisfy one rule.
SIGNALS = [
    ("pin", r"\b[0-9a-f]{40}\b|COMMIT\b|\bpin(ned)?\b", "an explicit commit/pin variable"),
    ("https_only", r"Refusing non-HTTPS|refuse.*non-https|https://\*\)", "an explicit non-HTTPS refusal"),
    ("verify", r"SHASUMS|sha256sum|shasum -a 256|Get-FileHash", "hash verification"),
    ("name_check", r"Unexpected .*archive name|archive_name\)|expected pattern", "a filename pattern check"),
    ("reverify", r"\.archive-sha256|\.node-sha256|-sha256\"|validate_existing_install|Re-?verif",
     "recorded hashes re-checked on reuse"),
    ("content_addressed", r"versions/\$|versions/\{|VERSIONS_ROOT|versions[\\/]<", "a versions/<pin> layout"),
    ("identity", r"process\.versions|process\.platform|process\.arch|--version.*!=|Expected .* got ",
     "a post-extraction identity assertion"),
    ("manifest", r"required_install_files|required.*files|LICENSE\b.*\n.*LICENSE|THIRD-PARTY",
     "a required-files list"),
    ("provenance", r"rapp-local-install|\.rapp-install\.json|provenance", "a provenance record"),
    ("platform_allowlist", r"Unsupported .*architecture|supports .* only|\*\)\s*die|throw \".*supports",
     "an explicit platform/arch refusal"),
]

# Anti-signals: presence is a FAIL regardless of anything else.
ANTI = [
    ("no_remote_exec", r"curl[^\n|]*\|\s*(ba)?sh|iwr[^\n|]*\|\s*iex|bash\s+<\(\s*curl",
     "a remote script piped straight to a shell"),
    ("no_remote_exec", r"run_remote_bash|/bin/bash \"\$tmp\"", "a downloaded script executed unverified"),
    ("no_global", r"\bsudo\b(?!.*#)|npm i(nstall)? -g\b|brew install\b", "elevation or a global install"),
    ("fail_closed", r"skipping verification|could not.*verif.*continu|warn.*skip.*verif",
     "verification skipped with a warning instead of an error"),
]


def analyse(text: str) -> dict:
    lines = text.split("\n")

    def find(pattern):
        rx = re.compile(pattern, re.I)
        return [(i + 1, lines[i].strip()[:100]) for i in range(len(lines)) if rx.search(lines[i])]

    results = {r.key: {"ok": None, "evidence": [], "rule": r.title, "why": r.why} for r in RULES}

    for key, pat, desc in SIGNALS:
        hits = find(pat)
        if hits:
            results[key]["ok"] = True
            results[key]["evidence"].append({"found": desc, "line": hits[0][0], "text": hits[0][1]})

    def is_prose(line: str) -> bool:
        """A match inside a comment or a quoted literal is weak evidence.

        The first version cited a joke tagline — `TAGLINES+=("npm install -g
        openrappter - because you deserve nice things.")` - as proof of a
        global install. The finding happened to be true for other reasons, but
        a checker that quotes a punchline as a security finding gets dismissed,
        and rightly so. Prefer executable evidence; fall back to prose only
        when nothing better exists, and label it.
        """
        st = line.strip()
        return st.startswith("#") or st.startswith("//") or bool(re.match(r'^[A-Z_]+\+?=\("', st))

    for key, pat, desc in ANTI:
        hits = find(pat)
        if not hits:
            continue
        real = [h for h in hits if not is_prose(h[1])]
        if not real:
            # Prose-only match: a comment saying "no sudo" is not a sudo call.
            # Record it as context, do not fail the rule on it.
            results[key]["evidence"].append(
                {"note": "pattern appears only in a comment or string",
                 "line": hits[0][0], "text": hits[0][1]})
            continue
        results[key]["ok"] = False
        results[key]["evidence"].append(
            {"violation": desc, "line": real[0][0], "text": real[0][1]})

    # fail_closed: a die/throw adjacent to verification is the positive signal,
    # but an anti-signal already recorded above always wins.
    if results["fail_closed"]["ok"] is None:
        # Shell projects terminate in more ways than `die`. Accept any error
        # report that is immediately followed by a non-zero exit, which is what
        # fail-closed actually means. The first version only matched `die` and
        # scored a correctly-hardened installer as failing.
        strict = find(r"(die|ui_error|throw|Write-Error)[^\n]*"
                      r"(mismatch|checksum|SHA-256|hash|refusing|unverified)")
        if strict:
            has_exit = find(r"(^\s*|\|\|\s*|&&\s*)(return 1|exit 1|die\b|throw\b)")
            if not has_exit:
                strict = []
        if strict:
            results["fail_closed"]["ok"] = True
            results["fail_closed"]["evidence"].append(
                {"found": "verification failure terminates the install",
                 "line": strict[0][0], "text": strict[0][1]})

    # Rules expressed purely as anti-signals are PROHIBITIONS: absence of the
    # bad pattern is compliance. Defaulting them to FAIL penalised the correct
    # behaviour — caught by running this against a well-built installer, which
    # scored 10/12 for never doing two things it is supposed to never do.
    PROHIBITIONS = {
        "no_global": "no elevation or global install detected",
        "no_remote_exec": "no unverified remote script execution detected",
    }
    for key, msg in PROHIBITIONS.items():
        if results[key]["ok"] is None:
            results[key]["ok"] = True
            results[key]["evidence"].append({"found": msg})

    for k, v in results.items():
        if v["ok"] is None:
            v["ok"] = False
            v["evidence"].append({"missing": "no signal found"})
    return results


def judge_bundled_runtime(root: Path, results: dict) -> None:
    """§5 is a property of packaging, not of installer text — bundling leaves no
    trace in the script at all. Judged from package.json, like ci_installs is
    judged from workflows.

    `ok=None` here means NOT APPLICABLE (no package.json), which is deliberately
    distinct from False. Scoring a non-Node installer as failing a Node rule
    would be the same mistake as defaulting prohibitions to FAIL.
    """
    r = results["bundled_runtime"]
    r["evidence"].clear()

    # An installer often sits above the package it installs (openrappter keeps
    # its manifest in typescript/). Looking only beside the script reported
    # "not applicable" for a project that genuinely does not bundle — hiding a
    # real finding behind a clean score.
    manifests = [p for p in [root / "package.json"] if p.is_file()]
    if not manifests:
        manifests = sorted(p for p in root.glob("*/package.json")
                           if "node_modules" not in p.parts)[:8]
    if not manifests:
        r["ok"] = None
        r["evidence"].append({"note": "no package.json found; rule not applicable"})
        return

    plat = re.compile(r"-(darwin|win32|linuxmusl|linux)-(x64|arm64)\b")
    found: list[str] = []
    for pj in manifests:
        try:
            pkg = json.loads(pj.read_text(encoding="utf-8", errors="ignore"))
        except json.JSONDecodeError as exc:
            r["ok"] = False
            r["evidence"].append({"missing": f"{pj.name} does not parse: {exc}"})
            return

        deps = {}
        for field in ("dependencies", "optionalDependencies", "devDependencies"):
            deps.update(pkg.get(field) or {})
        direct = sorted(n for n in deps if plat.search(n))

        # Platform packages are usually transitive (a wrapper declares them as
        # optionalDependencies), so for an app the honest signal is the
        # packaging rule that unpacks them. Missing this scored skill-recorder
        # — the reference implementation — as failing.
        packaging = json.dumps(pkg.get("build") or {})
        unpacked = sorted(set(re.findall(
            r"node_modules/(@[\w.-]+/[\w.-]*\*?[\w.-]*|[\w.-]*\*[\w.-]*)/\*\*", packaging)))

        where = pj.parent.name or "."
        if direct:
            found.append(f"{where}: declares {', '.join(direct[:4])}")
        elif unpacked:
            found.append(f"{where}: unpacks {', '.join(unpacked[:4])}")

    if found:
        r["ok"] = True
        for f in found:
            r["evidence"].append({"found": f})
    else:
        r["ok"] = False
        r["evidence"].append(
            {"missing": "no per-platform binary package declared or unpacked in "
                        + ", ".join(str(p.relative_to(root)) for p in manifests)
                        + "; the runtime is expected to already exist on the machine"})
    return


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 1
    path = Path(args[0])
    if not path.is_file():
        print(f"not a file: {path}", file=sys.stderr)
        return 1

    results = analyse(path.read_text(encoding="utf-8", errors="ignore"))

    # CI evidence lives beside the installer, not inside it.
    wf = path.parent / ".github" / "workflows"
    results["ci_installs"]["evidence"].clear()   # judged here, not in analyse()
    if wf.is_dir():
        blob = "\n".join(f.read_text(encoding="utf-8", errors="ignore")
                          for f in wf.glob("*.yml"))
        runs = path.name in blob
        refuses = bool(re.search(r"accepted a mutable source reference|COMMIT\s*=\s*[\"\']?(master|main)", blob))
        results["ci_installs"]["ok"] = runs and refuses
        results["ci_installs"]["evidence"].append(
            {"found": f"workflows invoke {path.name}={runs}, refusal test={refuses}"}
            if runs else {"missing": f"no workflow invokes {path.name}"})
    else:
        results["ci_installs"]["ok"] = False
        results["ci_installs"]["evidence"].append({"missing": "no .github/workflows beside the installer"})
    judge_bundled_runtime(path.parent, results)

    # ok is True (pass), False (fail), or None (not applicable). Counting None
    # as a failure would penalise a non-Node installer for a Node rule.
    score = sum(1 for v in results.values() if v["ok"] is True)
    applicable = sum(1 for v in results.values() if v["ok"] is not None)
    skipped = len(RULES) - applicable

    if "--json" in sys.argv:
        print(json.dumps({"schema": SPEC, "target": str(path),
                          "score": score, "of": applicable, "not_applicable": skipped,
                          "rules": results}, indent=2))
        return 0 if score == applicable else 1

    print(f"{SPEC} — {path}")
    print("=" * 72)
    for r in RULES:
        v = results[r.key]
        mark = "N/A " if v["ok"] is None else ("PASS" if v["ok"] else "FAIL")
        print(f"  [{mark}] {r.title}")
        for e in v["evidence"]:
            if "violation" in e:
                tag = "  [weak: comment/string only]" if e.get("weak") else ""
                print(f"         ! {e['violation']}  (line {e['line']}){tag}")
                print(f"           {e['text']}")
            elif "note" in e:
                where = f"  (line {e['line']})" if "line" in e else ""
                print(f"         ~ {e['note']}{where}")
            elif "missing" in e:
                print(f"         - {e['missing']} — {r.why}")
            elif "line" in e:
                print(f"         + {e['found']}  (line {e['line']})")
            else:
                print(f"         + {e['found']}")
    print("=" * 72)
    tail = f"  ({skipped} not applicable)" if skipped else ""
    print(f"  {score}/{applicable} conformant{tail}")
    print("\n  Static analysis: a PASS means the shape is present, not that the logic")
    print("  is sound. Read the code. A FAIL is a finding.")
    return 0 if score == applicable else 1


if __name__ == "__main__":
    sys.exit(main())
