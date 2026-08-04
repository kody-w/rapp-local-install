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
derived by reading it rather than invented here.

MIT © RAPP ecosystem — see the [map](https://github.com/kody-w/rapp-map).
