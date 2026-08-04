# rapp-local-install/1.0

**A convention for installing software onto a device from source, verifiably, with
nothing installed globally and no trust placed in anything that was not checked.**

Read [`SPEC.md`](SPEC.md). Score an installer against it:

```bash
python3 check.py path/to/install.sh
```

## Why

An install is a supply chain, and a broken install looks exactly like a compromised one
after the fact. The checks meant to tell them apart routinely fail open.

Two real installers were read line by line to write this. One pins an exact commit,
verifies every artifact against the publisher's own checksum manifest, dies on any
mismatch, and re-hashes the extracted binaries on every later run. The other verified the
same Node.js archive and **failed open three ways** — no manifest, no matching entry, or
no hashing tool on the machine — each path proceeding to install, one of them printing a
warning nobody reads.

The verification existed. It just did not bind.

## The dependency you did not install

§5 covers the other half of a local install: the binary your product cannot run without.
The instinct is to find it on the user's machine — and a GUI process does not inherit
your shell. A launchd-started app on macOS sees `/usr/bin:/bin:/usr/sbin:/sbin`: no
Homebrew, no `nvm`, no `~/.local/bin`. The workaround is always the same list of guessed
directories, and it is always maintained twice.

Bundle it instead. Redistribution is often permitted even for proprietary binaries —
GitHub's Copilot CLI licence grants it explicitly, on the condition that the copy is
unmodified and ships its licence. §5.5 requires reading that grant rather than assuming
it, in either direction.

## Conformance is checked, not claimed

`check.py` reports per-rule evidence with file line numbers, so a verdict can be argued
with rather than believed.

It is static analysis and says so: a PASS means the shape is present, not that the logic
is sound. A FAIL is a finding. Both halves of that sentence are load-bearing — the first
version of this checker cited a joke tagline as evidence of a global install, and a
checker that quotes a punchline as a security finding deserves to be ignored.

## Prior art

[`microsoft/skill-recorder`](https://github.com/microsoft/skill-recorder) is the closest
thing to a reference implementation that existed before this document. §3.5
(re-verification), §3.8 (runtime identity), and §3.10 (prove the refusal in CI) were all
derived by reading it rather than invented here, as was §5 — it vendors the Copilot CLI
unmodified, declares it in `THIRD-PARTY-NOTICES.md`, and re-checks after packing.

It scores 14/15 against this spec. So does openrappter's `install-pinned.sh`, on a
different 14: skill-recorder writes no provenance record, and openrappter bundles no
runtime. Neither gap is visible from the other's.

MIT © RAPP ecosystem — see the [map](https://github.com/kody-w/rapp-map).
