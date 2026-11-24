# Ceramic vase · Ember and linen

One local exploratory campaign implementing the accepted AGO-107 direction (`direction=ceramic`). This is a standalone static demo, not the orchestration application's UI. Open `site/index.html` in a modern browser, or serve only this directory on loopback:

```sh
python3 -m http.server 19404 --bind 127.0.0.1 --directory studies/ceramic-campaign/site
```

Then visit `http://127.0.0.1:19404`. There are no runtime packages, remote fonts, analytics, checkout or publication steps. The photograph is local; only the explicitly activated photographer-credit link leaves the page.

## Accepted scope and supplied inputs

The captain chose **Ceramic vase · Ember and linen**, as proposed, using Approve and build. Implementation approval is not merge consent.

- Header: an original locally authored Hollow Form wordmark and linear H mark, with an “Objects for quiet spaces” signature.
- Campaign: “A quiet room. A warm presence.”, a short proposition and Cindy Bartillon's real vase photograph integrated into the page.
- Offer: Ember vase, explicitly fictional sample **S$90**, and a visually distinct **View details** button.
- Dialog: the same product, sample price, visual description, demo disclosure and Close control; keyboard, pointer, Escape and focus return.
- Footer: visible fictional-demo/no-sales disclosure and linked photographer credit.
- Narrow layout: headline → photograph → offer/action → disclosure/credit, rather than compressed desktop positioning.
- Palette: background `#040404`, text/offer `#C9BC9C`, decorative accent `#C7722C`, action `#DCB278`, action label `#040404`. No colour substitutions were needed. Hover uses linen; pressed uses copper; both retain dark labels and borders.

Exact active inputs, captured before authoring, live in `inputs/`:

1. `base-S02.md` and `base-SHARED-NOTES.md`: complete byte-for-byte base files; their source-relative links are historical context, not rewritten links.
2. `R03-source.json`: complete original source-index record. The actual original R03 PNG was extracted directly from the preserved archive, hash-verified and visually inspected alongside the selected photo before building. It stays outside the project because reference access does not imply redistribution permission; the outcome card retains a view of it.
3. `candidate-addendum.md`: the current candidate's exact photography section (including builder-only clarification), S02 pointer text and corrected R03 observation. The corrected sentence supersedes only the base R03 observation; every other base paragraph remains intact.
4. `product-prompt.md`: the separate exact accepted product-change prompt and selected setting. Fonts, alignment and geometry remain open.
5. `candidate-S02-snapshot.md` and `candidate-SHARED-NOTES-snapshot.md`: unchanged full candidate snapshots for audit, not a replacement for the base-plus-separate-addendum arrangement.
6. `pack-hashes.json`: SHA-256 hashes of all 37 files across both source packs. All 37 were checked unchanged after the run.

Original R03 SHA-256: `0ba4a1159ce950fcde7ac94cdd8ad4434a9452a65e47586fba09badd14ac4027`.

Selected photograph SHA-256: `2c4727fc7aabdc07a5bcb2469147358a5d00d7bf9128d2bb5153671aa5c54104`.

The selected full 2400 × 3600 JPEG is preserved unchanged as `site/ceramic.jpg`. Cropping and edge transitions happen only in CSS. There is no second angle, synthetic reflection, colour filter or generated product imagery.

## Provenance and rights

Photograph: Cindy Bartillon, [an orange vase sitting on a white table](https://unsplash.com/photos/an-orange-vase-sitting-on-a-white-table-THtfRdrK0nI), identifier `THtfRdrK0nI`. The planner retrieved this rendition under the [Unsplash License](https://unsplash.com/license), without sign-in or payment; this run preserved those exact bytes before planner evidence expiry. The license is not clearance of depicted object design or a product endorsement. This run performs no commercial publication or clearance investigation. S$90 is a fictional demonstration setting, not the photographed object's actual price.

R03 is composition guidance only: the roasting scene, visible directional light/material highlights, large headline and separate pale offer. Its branding, reviews, commercial claims, olive colour and pixels are not used in the campaign. No earlier trial result or code was used as a baseline or implementation source.

## Verification

`verify.py` launches an ephemeral loopback server and a new isolated, disposable browser profile. It uses already available Python `websockets` and Pillow plus an existing Chrome-for-Testing executable. It installs nothing and does not use real accounts or personal browser profiles.

```sh
python3 studies/ceramic-campaign/verify.py \
  --evidence /absolute/path/outside/the/working-copy \
  --phase corrected --record
```

Override `--chrome /path/to/an/already-installed/browser` when necessary. The default points to the pre-existing cached Chromium 153 used here. The desktop Chrome 155 preflight answered, but local navigation returned `ERR_ABORTED`; the existing test browser resolved this tool limitation. No browser package was downloaded.

The verifier captures 1440 × 1080 and 390 × 844 viewports and full pages, plus 320px reflow and 200% zoom-equivalent layout (720 × 540 CSS pixels, device scale 2, corresponding to a 1440 × 1080 physical window). This is explicit emulation, not a claim that the browser's zoom menu was operated. It checks image decoding/dimensions, overflow, actual rendered copy, keyboard skip/Tab/Enter, six forward/reverse modal Tab steps, Escape, Close, focus return, pointer activation and accessible names/roles. It measures every visible text run against the actual composited background with text temporarily hidden, including the open dialog. It records a real-time keyboard journey as a once-playing GIF: the existing bundled encoder lacks H.264, so no encoder was installed.

All screenshots, recordings, runtime transcripts, accessibility-tree extracts and measured results stay in the task's external evidence folder, not this project. The outcome card carries the selected visual evidence. See `ASSESSMENT.md` for findings, correction history, exact checks and clause recommendations. First-pass implementation is retained in commit `4db69b0`; subsequent corrections are separate commits, not presented as first-pass success.

## Boundaries

No pack amendments, infrastructure, application contracts, baseline rebuild, multi-product matrix, installations, paid/API fallback, generated product imagery, publication, purchase or push. No claim of controlled causation, independent palette discovery, universal guidance validation, native-device testing or full screen-reader conformance. Model identity and effort settings were not exposed for verification. Actual skill exposure is documented in the assessment.
