# Bundled type assets

Retrieved 6 October 2026 from Vercel's official `geist-font` repository, pinned to [release v1.7.2](https://github.com/vercel/geist-font/releases/tag/v1.7.2). No font package or system font was installed. These are the upright variable webfonts, renamed locally for predictable asset URLs without modifying their contents.

| Local file | Exact download source | Bytes | SHA-256 |
| --- | --- | ---: | --- |
| `Geist-Variable.woff2` | [Geist upright variable WOFF2](https://raw.githubusercontent.com/vercel/geist-font/v1.7.2/fonts/Geist/webfonts/Geist%5Bwght%5D.woff2) | 69760 | `2ffebe993e969069a9789d15164b7715d42491b5835516c5e3b935d5f81b05f1` |
| `GeistMono-Variable.woff2` | [Geist Mono upright variable WOFF2](https://raw.githubusercontent.com/vercel/geist-font/v1.7.2/fonts/GeistMono/webfonts/GeistMono%5Bwght%5D.woff2) | 71596 | `afaacc4c5fbba89d2ebf7a02dc4070208540874592a5504d57175782fe893101` |
| `OFL.txt` | [Pinned original license](https://raw.githubusercontent.com/vercel/geist-font/v1.7.2/OFL.txt) | 4383 | `c683bfbcc7e087f5d37a54ef628f10387c451a83ddc459b151403a164ac46c90` |

Keep `OFL.txt` with redistributed font files. The official font license is SIL Open Font License 1.1. Copyright remains with The Geist Project Authors. The font choice does not imply an affiliation with Vercel.

Use Geist Sans for display, prose, navigation, and controls. Reserve Geist Mono for source/version identifiers and literal code. Self-host these files in the eventual implementation with `font-display: swap`; use upright text because italic assets are not part of this handoff. Asset integrity was checked by nonzero file size, `wOF2` binary signatures, and the hashes above. Rendering fidelity still needs the actual frontend's viewport checks.
