# rapp-local-install/1.0

**A convention for installing software onto a device from source, verifiably, with nothing
installed globally and no trust placed in anything that was not checked.**

An install is a supply chain. Every byte that lands on the machine either came from a
pinned, hash-verified source or it did not, and the difference is invisible after the
fact — a broken install and a compromised one both look like a working directory.

This spec exists because that difference is checkable, and because the checks that
guard it fail open more often than anyone intends.

---

## 1. Why this is written down

Two real installers were compared byte by byte to produce it.

`microsoft/skill-recorder` pins an exact 40-character commit, verifies the Node.js
archive against the official `SHASUMS256.txt`, **dies** on any mismatch, and — the part
most implementations miss — records `.archive-sha256` and `.node-sha256` so that on every
later run it re-hashes the *extracted binary* rather than trusting that a directory which
exists is a directory which is intact.

A sibling installer in this ecosystem verified the same Node.js archive and **failed open
three separate ways**: if the checksum manifest could not be downloaded, if the tarball
name was not found inside it, or if neither `sha256sum` nor `shasum` was present on the
machine. Each path proceeded to install, and one printed a warning nobody reads.

The verification existed. It just did not bind.

That is the failure this spec is shaped against: **a check that degrades to a no-op and
reports success is worse than no check, because it also removes the suspicion that would
have caused someone to look.**

## 2. Anatomy

| # | Role | Requirement |
|---|------|-------------|
| 1 | **Pin** | An exact immutable revision — a 40-hex commit or a content digest. Never a branch, tag, or `HEAD`. |
| 2 | **Transport** | HTTPS only, refused explicitly rather than assumed. |
| 3 | **Integrity** | Every downloaded artifact hash-verified against a manifest fetched from the artifact's own publisher. |
| 4 | **Fail-closed** | Every verification path terminates the install on failure, including the paths where verification *could not be performed*. |
| 5 | **Re-verification** | Recorded hashes re-checked on every subsequent run, against the extracted artifact, not the archive. |
| 6 | **Containment** | Everything under one root the user owns. No global installs, no `sudo`, no `PATH` mutation outside the root. |
| 7 | **Content-addressed versions** | Installs live at `versions/<pin>/`, so two versions coexist and a rollback is a path change. |
| 8 | **Identity check** | After extraction, the runtime is asked what it is, and disagreement is fatal. |
| 9 | **Completeness manifest** | An explicit list of files that must exist post-install, licenses included. |
| 10 | **Provenance record** | A machine-readable record of what was installed, from where, and with which digests. |

## 3. Rules

**3.1 Pin or refuse.** An installer MUST NOT resolve a branch name at install time. Two
users running the same command a day apart MUST get identical bytes or an error. `HEAD`,
`main`, and `latest` are not pins.

**3.2 Never execute an unverified remote script.** `curl … | bash` is prohibited, as is
downloading a script and running it without first checking it against a pin or digest.
This is stated flatly because it is the single most common violation and the hardest to
notice once it is habitual.

**3.3 Fail closed, including on absence.** Every branch where verification is skipped
MUST terminate the install. Specifically, an installer MUST fail — not warn — when:

- the checksum manifest cannot be fetched;
- the artifact is absent from the manifest;
- no hashing tool is available on the machine.

The third is the one that is always missed. An empty computed hash compared against an
expected hash must never be treated as a match, and must never be treated as "skip".

**3.4 Verify the name, not only the hash.** The artifact filename MUST be matched against
an expected pattern before use. A hash confirms bytes are unmodified; it does not confirm
they are the bytes you meant to ask for.

**3.5 Re-verify what is on disk.** On a subsequent run, an installer MUST re-hash the
installed executables and compare against recorded values before reusing them. Presence
is not integrity. A directory that exists proves only that something wrote to it once.

**3.6 Nothing global.** No `sudo`, no writes outside the install root, no global package
installs, no modification of the user's shell profile. Uninstall MUST be `rm -rf` of one
directory.

**3.7 Content-address the version directory.** Installs live at `versions/<pin>/`.
Immutable by construction: if the pin differs the path differs, so upgrade never mutates
a working install and rollback is not a download.

**3.8 Ask the runtime what it is.** After extraction, query the interpreter for its
version, platform, and architecture, and fail on disagreement. An archive named for
`darwin-arm64` that reports `linux-x64` is a fact worth learning before the first run
rather than during it.

**3.9 Record provenance.** Write a machine-readable record — schema `rapp-local-install/1.0` —
naming the pin, every source URL, and every verified digest. Without it, "which version is
this and where did it come from" is answerable only by guessing.

**3.10 Prove the refusal in CI.** An installer MUST have a test that invokes it with a
mutable reference and **fails if the install is accepted**. Asserting that a guard exists
is not the same as observing it fire.

`skill-recorder` does exactly this on every platform:

```bash
output="$(SKILL_RECORDER_COMMIT=master bash install.sh 2>&1)" \
  && echo "install.sh accepted a mutable source reference" >&2 && exit 1
```

Then it runs the installer for real, with the commit under test. Both halves matter: the
first proves the refusal works, the second proves the acceptance still does.

**3.11 Reproducible dependency resolution.** Dependency installation MUST use a lockfile
and a command that fails on drift (`npm ci`, not `npm install`). The lockfile's own hash
belongs in the provenance record.

## 4. Multi-platform

A platform an installer does not name is a platform it does not support, and saying so is
kinder than a half-install.

**4.1 Enumerate, then refuse.** Supported `(platform, architecture)` pairs MUST be an
explicit allowlist, and anything outside it MUST terminate with a message naming what was
found. Best-effort installation onto an unrecognised platform produces a broken tree that
looks installed.

```bash
case "$MACHINE" in
  x86_64|amd64)  ARCHITECTURE="x64"   ;;
  arm64|aarch64) ARCHITECTURE="arm64" ;;
  *) die "Unsupported processor architecture: $MACHINE." ;;
esac
```

**4.2 Normalise architecture names once.** `x86_64`/`amd64` and `arm64`/`aarch64` are the
same targets under different names. Normalise at the boundary so no later comparison has
to know both spellings.

**4.3 Identify the distribution, not just the kernel.** `uname -s` returning `Linux` says
nothing about whether the package assumptions hold. Read `/etc/os-release` and refuse a
distribution that has not been tested.

**4.4 Use platform-native roots.** `~/Library/Application Support/<Name>` on macOS,
`${XDG_DATA_HOME:-$HOME/.local/share}/<Name>` on Linux, `%LOCALAPPDATA%\<Name>` on
Windows. One override variable, honoured on every platform.

**4.5 One installer per platform family.** A POSIX shell script and a PowerShell script,
each readable on its own, beat one script threaded with branches. They MUST enforce the
same rules — §3 applies to each independently.

**4.6 Verify per-platform binaries per platform.** A native artifact has a different hash
on every target. Each supported pair's hash MUST be verified separately; a single hash
covering "the release" verifies nothing about the bytes that actually landed.

**4.7 Require two-source agreement for native artifacts.** Where a dependency publishes
its own checksum manifest, the installer SHOULD also carry a **reviewed** copy of the
expected hash in-repo, and fail when the two disagree:

```
manifest hash (node_modules/electron/checksums.json)
    vs
reviewed hash (third_party/compliance-policy.json)
    -> mismatch is fatal
```

This is the only rule here that defends against the *publisher* rather than the network.
An upstream that silently changes a hash is caught because the reviewed value is committed
and diffable.

**4.8 CI runs the real installer on every supported platform.** Not a lint, not a dry run
— the actual installer, on a runner for each pair, on every pull request. Including the
§3.10 refusal test. A platform without a CI leg is unsupported no matter what the README
says.

## 5. Bundled runtimes

The hardest problem in a local install is usually not fetching a dependency. It is
*finding* one that somebody else installed, somewhere else, under a `PATH` this process
never sees. The most reliable way to resolve a required binary is to not resolve it.

**5.1 Bundle what the product cannot run without.** A required third-party binary MUST
ship inside the install tree. Resolving it from the user's environment makes correctness a
property of their shell configuration — which the installer does not control, cannot test,
and is never told about when it changes.

**5.2 `PATH` is not a contract.** A process started by a GUI or a service manager does not
inherit an interactive shell's environment. A launchd-started process on macOS gets
`/usr/bin:/bin:/usr/sbin:/sbin` — no Homebrew, no `nvm`, no `~/.local/bin`. Code that
compensates by *guessing* at those directories is the symptom, not the fix:

```ts
// the shape to delete, not to maintain
const candidates = ["/opt/homebrew/bin", "~/.local/bin", "~/.volta/bin", "~/.asdf/shims"];
```

Every entry is a bet about one machine's layout. Bundling makes the whole list
unnecessary — and deletes its inevitable second copy in whatever other language the
project also ships.

**5.3 Select the platform binary by declaration, not by branching.** Publish or consume one
package per `(platform, arch)` pair, constrained by `os`/`cpu`, and let the package manager
choose. Resolution then fails at install time on the machine that cannot be satisfied,
rather than at first use.

**5.4 A missing bundled binary is an install failure, not a runtime failure.** If it is
absent, the install is broken and MUST say exactly that. Deferring the discovery to first
use reports a packaging fault as an authentication or network error, which is where the
debugging time goes.

**5.5 Redistribution requires a grant you have actually read.** Bundling a third-party
binary is redistribution. The licence MUST be read and its conditions recorded in-repo
before shipping — never inferred from the ecosystem it is published to. A `license` field
of the form `SEE LICENSE IN LICENSE.md` means the answer is not in the metadata, and a
proprietary licence may still grant redistribution: the only way to know is to read it.

**5.6 Ship the licence with the bytes.** Redistribution grants are near-universally
conditioned on carrying the licence and attribution notices, and on the copy being
unmodified. Vendoring the dependency **whole** satisfies this by construction; lifting just
the binary out of its package is what breaks it. The completeness manifest (§2, row 9) MUST
list the licence file.

**5.7 Verify compliance against the packaged artifact.** A check that runs on the source
tree proves nothing about what the packer emitted. It MUST run after packaging and inspect
the artifact itself.

## 6. The provenance record

`<install_root>/versions/<pin>/.rapp-install.json`:

```json
{
  "schema": "rapp-local-install/1.0",
  "pin": "d2cd5abed48d3f52b86bbb975ac3558286d1db41",
  "pin_kind": "git-commit",
  "installed_utc": "2026-08-04T22:30:00Z",
  "sources": [
    { "url": "https://codeload.github.com/owner/repo/tar.gz/<pin>", "sha256": "…" }
  ],
  "runtime": {
    "name": "node", "version": "24.4.1",
    "archive_sha256": "…", "binary_sha256": "…"
  },
  "artifacts": [ { "path": "node_modules/.bin/thing", "sha256": "…" } ],
  "lockfile_sha256": "…"
}
```

Every digest here is re-checked on the next run. That is what makes the record load-bearing
rather than decorative.

## 7. Conformance

An installer is **rapp-local-install/1.0 conformant** if:

- [ ] It requires an exact immutable pin and refuses branch names.
- [ ] It refuses non-HTTPS transport explicitly.
- [ ] It verifies every downloaded artifact against a publisher-provided manifest.
- [ ] **Every** verification failure path — including "could not verify" — terminates the install.
- [ ] It validates artifact filenames against an expected pattern.
- [ ] It re-verifies installed binaries by hash on subsequent runs.
- [ ] It writes nothing outside its install root and requires no elevation.
- [ ] Versions are content-addressed at `versions/<pin>/`.
- [ ] It queries the installed runtime's identity and fails on disagreement.
- [ ] It checks an explicit completeness manifest, licenses included.
- [ ] It writes a `rapp-local-install/1.0` provenance record.
- [ ] It never pipes or executes an unverified remote script.
- [ ] CI proves the mutable-reference refusal by observing it fire.
- [ ] Supported platform/architecture pairs are an explicit allowlist; others are refused.
- [ ] Native artifacts are verified per platform, not once per release.
- [ ] CI runs the real installer on every supported pair.
- [ ] Required third-party binaries are bundled, not resolved from `PATH`.
- [ ] Every redistributed binary ships its licence, and the grant is recorded in-repo.

Conformance is **checkable, not claimable**: `check.py` scores an installer against these
rules and prints the evidence for each verdict.

## 8. What this deliberately does not require

- **Signatures.** Publisher-provided checksum manifests over HTTPS are the realistic floor
  today. Signing is strictly better and out of scope; nothing here forbids it.
- **A specific language or packaging tool.** These are properties of an install, not of an
  implementation.
- **Offline installs.** Reproducibility is required; network independence is not.

## 9. Prior art

`microsoft/skill-recorder` — `install.sh` is the closest thing to a reference
implementation that existed before this document. It satisfies most of §3 on its own
merits and was the source of §3.5 and §3.8, both of which were derived by reading it
rather than invented here. §5 was derived the same way, from its handling of the bundled
GitHub Copilot CLI — a proprietary binary whose licence grants redistribution, which it
vendors unmodified, declares in `THIRD-PARTY-NOTICES.md`, and re-checks after packing.

MIT © RAPP ecosystem — see the [map](https://github.com/kody-w/rapp-map).
