# Reference: may `@github/copilot` be bundled?

**Yes, explicitly — subject to five conditions, all of which vendoring unmodified
satisfies by construction.**

This file exists because §5.5 requires the grant to be *read and recorded*, not assumed.
It is the worked example. Verified 2026-08-04 against `@github/copilot@1.0.76-1`.

## What the metadata does and does not tell you

```
$ npm view @github/copilot license
SEE LICENSE IN LICENSE.md
```

Not an SPDX identifier. No tooling that reads the `license` field can answer the question,
and "it is on npm" answers nothing — the package is proprietary. The answer is only in the
file, which ships inside the tarball.

## The grant

`LICENSE.md` §1, verbatim:

> Subject to Section 2 below, GitHub also grants you the right to reproduce and
> redistribute unmodified copies of the Software as part of an application or service.

§2 conditions it on all of:

| Condition | How vendoring satisfies it |
|---|---|
| Distributed only in unmodified form | Copy `node_modules/@github/copilot*` whole; never repack the binary alone |
| Only as part of an application with material functionality beyond the Software | A judgement call — see below |
| Not standalone or as a primary product | Same judgement call |
| Include this Licence, retain attribution notices | `LICENSE.md` is *inside* the platform package, so an unmodified copy carries it automatically |
| Your application licensed independently | §2 states plainly that it "does not restrict your choice of license … including distribution under an open source license" |

§3 additionally forbids modifying or creating derivative works of the Software, and using
GitHub branding beyond identifying it.

## The one condition that is a judgement call

"Material functionality beyond the Software itself" and "not a primary product" cannot be
checked mechanically. An agent platform that happens to use the CLI as one transport
clearly qualifies. **A thin tray wrapper whose whole purpose is to run Copilot plausibly
does not** — that is closer to redistributing the Software as the product.

Do not let a conformance checker imply this was decided. It was not; it is the reason
§5.5 says *read the grant* rather than *check a field*.

## Verified facts

- `LICENSE.md` in `@github/copilot-darwin-arm64` is byte-identical to the one in the
  wrapper package, and sits beside the `copilot` binary.
- Eight platform packages exist, all carrying the same licence and constrained by
  `os`/`cpu`: `{darwin,win32,linux,linuxmusl}-{x64,arm64}`.
- Unpacked size is **319 MB per platform** — the real cost of bundling, and larger than
  any licensing concern. Build one artifact per platform; never all eight at once.

## Prior art in practice

`microsoft/skill-recorder` is **MIT** and bundles the CLI. Its compliance machinery is the
pattern worth copying, because it is enforced rather than described:

- `asarUnpack: ["node_modules/@github/copilot-*/**"]` — vendored whole
- `THIRD-PARTY-NOTICES.md` — records the grant and its conditions in prose
- `third_party/compliance-policy.json` — pins the reviewed version and hashes
- `afterPack: scripts/verify-packaged-compliance.mjs` — checks the **packed artifact**,
  which is what §5.7 requires and what a source-tree check cannot do
