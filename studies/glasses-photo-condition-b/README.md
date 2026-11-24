# AGO-102 · Condition B — S02 + photo v0.1

## Intent

Independent Morrow Frames campaign for AGO-100's accepted `separate-three` comparison. This condition supplements unchanged S02/shared notes with the exact approved **photo v0.1** appendix only. It does not implement the narrow appendix. The identical product prompt is retained verbatim under `inputs/`.

The full accepted AGO-99 plan and submitted choice were read before editing. The selected choice was three separate independent builds, not bundled appendices. No additional product setting was submitted. Font, alignment, exact geometry and palette remain open. Required visible content: one optical frame, sample S$120 price, short copy, working local View frame action and explicit demo identification. No checkout, reviews, endorsements or certifications.

This is an experimental deliverable for a coordinator, not a change to Agent Orchestrator or the instruction pack. No installation, external model invocation, publication, push or merge is required or performed.

## What changed

Fresh static HTML/CSS/JavaScript in this directory, with no previous trial or sibling code/design consulted:

1. Dark Morrow Frames masthead: wordmark at left, desktop study label in the middle, fictional/demo label at right.
2. Editorial introduction at desktop left: small category label, large Georgia headline “A little light. A different perspective.”, short frame copy and a small study number.
3. Dominant real photograph at desktop right: sunlit glasses on wood, both lenses and bridge recognizable. Its bottom caption credits Hữu Phú. No image filters or raster edits.
4. Contrasting cream offer panel below the introduction: The Round / Ink, S$120 sample price and View frame button. This is one fictional frame, not a product catalog.
5. Muted footer: concept-only and no-sale disclosures.
6. Native local dialog: enlarged shared detail photograph, frame name/copy, colour/style/sample price, explicit fictional-photo disclaimer and Close button. Escape closes and returns focus.
7. Phone layout: introduction, photograph, offer, footer in document order. The complete 390px page is 990px tall; the action is below the initial 844px viewport.

### Original inspected before building

Actual original R03 opened through the image-reading tool:
`/Users/yanqinwang/Library/Application Support/firstmate-3000/crewmates/6430d9cc/evidence/R03.png`

R03 SHA-256: `0ba4a1159ce950fcde7ac94cdd8ad4434a9452a65e47586fba09badd14ac4027`.

Visible observations: diagonal bands of light reveal a hand, scoop, beans and reflective steel. Dark quiet regions support oversized white copy and an olive action. A pale, bounded product card floats on the right; it carries a bag, product copy, price and controls. The scene establishes craft through materials and light, not darkness alone. Original ratings and commercial claims are not copied.

Intentional departures: separate editorial type/photo columns rather than overlaid copy; serif headline rather than large sans; stationary cream offer block rather than floating photographic product card; window/wood/glasses scene rather than roasting equipment. These follow the open geometry/type allowance. No original reference pixels appear in the campaign.

### Inputs, asset changes and exposure

`inputs/S02-product-presentation.md`, `SHARED-NOTES.md`, `S02-R03-photo-v0.1.md` and `product-prompt.md` are exact copies of the shared handoff. `R03-source-index.json` and `photographic-provenance.json` preserve source context. The original reference and full accepted plan remain at the supplied coordinator/source-card paths; neither is redistributed in the campaign.

- Base S02 SHA-256: `72425dd548a9514b1fa61ffb4cf088e79e63cc9872dd6e6095e1c4267c0dce5c`.
- Shared notes SHA-256: `7ebe6a33431eaef5b97e5dbb2aa22c1d046e286aef9cb11b385009d6b850ad6e`.
- Photo appendix SHA-256: `649db871dc0b79fbc420d43fa9aa8570eaf5c598bb305da638225a5795d872ee`.
- `assets/scene.jpg` original bytes unchanged: `7deb5cafd1cf4aa088d41b9d4c4a6ccf94511cd4286b34bd9a44585e57360cc9`.
- `assets/detail.png` supplied same-frame crop unchanged: `731533bd3103bb2363703ae0842c4d683bd529e5a13b68b7941f248faf3354e4`.
- Shared crop box: (880, 2050, 2650, 3020) from the 3456×5184 original; supplied by coordinator, not edited here.
- Scene uses CSS cover cropping with object-position 50% 51% desktop and 50% 53% phone. Detail uses full supplied crop. No colour, exposure, masking, retouch or image-generation operation.
- No improved or replacement asset was found or requested. Thus there is no new unequal-access asset to coordinate.
- Actual tools: file reading/editing, shell, Node 26.0.0, Python 3.12.10, Chrome 155.0.8059.79 with task-isolated temporary profile and dependency-free CDP client. No MCP, Figma, installations, network fonts or remote product requests.
- Actual skills read: `minimalist-ui`, `ui-ux-pro-max`. Two local ui-ux-pro-max searches: `eyewear campaign photographic editorial --design-system`, then `photographic craft editorial --domain style`. Generic enterprise/pink defaults were not adopted; editorial whitespace/type guidance was applicable. No skill output was persisted into shared instructions.
- Full approved card exposure necessarily included descriptions of the narrow hypothesis. The narrow appendix file, sibling outputs and historical trial outputs/code were not opened. This disclosure matters: do not describe the condition as blind to H2.
- The model identity/version and effort/settings are not surfaced to this worker session. They are **unknown**, not the installed Codex defaults; the coordinator should record host-side actual model/settings before claiming equal execution. No separate model process was invoked.
- No artificial time or correction budget. Product correction iterations: zero after initial rendering. The browser harness needed modality/event fixes; those did not change product code and are documented separately in evidence.

## Verified

Serve this directory, without dependencies:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory studies/glasses-photo-condition-b
```

Open `http://127.0.0.1:8766/`. The campaign also uses only local relative resources, with no framework/build step.

An isolated Chrome CDP browser was launched with its user-data directory under this task's temporary folder, not the person's browsing profile. Its actual measured viewports were 1440×1080 and 390×844, DPR 1. Screenshots are real browser renders, not resized mockups. Images/fonts were loaded before capturing viewport, full-page and open-dialog states at each required width. All six pictures were visually inspected (desktop full-page equals its viewport).

Functional checks are separate from visual judgment:

```sh
node studies/glasses-photo-condition-b/verify.mjs 9444 http://127.0.0.1:8766
node --check studies/glasses-photo-condition-b/app.js
node --check studies/glasses-photo-condition-b/verify.mjs
git diff --check
```

`verify.mjs` uses Node's built-in WebSocket and an already running, isolated Chrome debugging endpoint. It creates/closes its own page and installs nothing. Passed at 1440×1080, 390×844, 320×844, 650×900, 768×1024 and 1024×768:

- Actual requested viewport dimensions, loaded descriptive images, expected frame and S$120 price.
- No horizontal page overflow.
- Real Tab navigation reaches View frame with a visible outline; Enter opens the named dialog and focuses Close.
- Modal tab navigation does not enter background campaign controls.
- Escape dismisses the dialog and restores View frame focus.
- Pointer click opens the dialog; Close dismisses it.
- No browser runtime exceptions or failed resource requests.

No existing product tests cover this isolated static experiment. Python runtime/ledger tests are unrelated and were not run. This is not a full accessibility audit or a native-phone test.

### Visual assessment, separate from functionality

At 1440px, directional window light preserves both lens outlines, bridge highlights, wood grain and shadows. Text is outside the photo, and the cream offer panel separates the price/action. A large vertical quiet interval under the copy is deliberate editorial spacing, not missing content.

At 390px, the frame remains identifiable in a square-ish scene; headline/body copy remain outside the photograph. The offer follows the scene and is fully visible on scrolling, but price/action are not visible together in the initial 844px viewport. Tiny editorial captions are secondary, not essential product instructions. The phone glasses are smaller than in the dialog; only one scene is available, not a genuine second angle or manufacturing detail.

**H1 recommendation: inconclusive pending coordinator comparison with A.** B alone demonstrates that the proposed light/material/contrast language can be implemented; it does not show that it improves unchanged S02. Retain the exact photo v0.1 wording as a candidate, not a validated pack amendment. Compare B's photo region, cream offer and dialog with A before keep/revise/drop. Do not attribute observed quality to the wording alone: asset composition, serif choice, skill exposure and model/execution variation also matter. H2 is not this condition's evaluation.

### Retained evidence for AGO-100

Outside the working copy:
`/Users/yanqinwang/Library/Application Support/firstmate-3000/crewmates/dcdece75/evidence/`

- `B-1440-viewport.png`, `B-1440-full.png`, `B-1440-dialog.png`.
- `B-390-viewport.png`, `B-390-full.png`, `B-390-dialog.png`.
- `render-metrics.txt`: actual dimensions, DPR, full-page height and image load state.
- `functional-checks.jsonl`: final behavioral results.
- `harness-corrections.txt`: failed test-harness attempts and their diagnosis, with no hidden product repair.

The coordinator must retain these outside a working copy before this child task's evidence-retention window expires. Durable source, approved text inputs, exact photograph bytes, reproducible checks and this assessment live in this directory and its local commit; screenshots are deliberately not committed. Do not remove this working copy until the coordinator has the local commit/output.

## Risk

Medium: this is exploratory evidence, not an isolated causal finding. One original photograph plus a crop limits view diversity. Source license review is not commercial product clearance. Model/effort equality needs coordinator-side confirmation. The builder saw both hypothesis descriptions in the mandatory full plan. Skill exposure may differ among builders and must be compared honestly.

## Not done

No A/C comparison or pack amendment; no claim that H1 is supported. No generative/vector product images, replacement photography, invented material specification, functional checkout, public site, paid/API route, install, push or merge. No Agent Orchestrator runtime, documentation contract, frozen study or unrelated file was changed. Every visible element listed in the recorded design brief was built.

Plan limitations exposed: the prepared kit is one frame/angle plus a crop, not an independent scene/detail shoot. Equal model/settings were not visible to this worker, so the plan's equality assumption cannot be verified here. Exact-candidate appendix isolation is imperfect when the builder is also required to read the full accepted card containing both hypotheses. These limit interpretation rather than authorizing a different test.
