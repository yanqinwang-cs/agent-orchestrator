# AGO-108 · Ceramic vase assessment

## Intent

Implement the captain's accepted AGO-107 Ceramic vase · Ember and linen direction as **one local exploratory campaign**, testing the four bundled hypotheses against actual design output. The aim is a stronger coherent photographic composition and image-derived colour, not similarity scoring or a rebuilt control. The selected palette was supplied: this run cannot demonstrate independent palette discovery or isolate causal effects of individual instructions.

## What changed

A standalone fictional **Hollow Form** campaign lives in `site/`; no orchestration application code changed. The original locally authored linear H mark and two-line wordmark sit at the upper left. A large linen serif headline, “A quiet room. A warm presence.”, and a short proposition occupy the left of the desktop scene. The full-source photograph occupies the right, with its dark surroundings joining the page and its pale tabletop remaining visible. The copper vase retains its fluted ribs, asymmetric shading and actual rectangular window reflections. A separate linen offer below the copy contains Ember vase, the explicit S$90 sample price and a bordered honey View details button. The local modal repeats the product/price, a visual description and no-sale disclosure, with a Close button. The footer gives visible fictional-demo/no-sales disclosure and Cindy Bartillon/Unsplash credit. Phone layouts deliberately stack headline, photograph, offer/action and footer, without text over the vase.

Colours remain exactly the accepted `#040404`, `#C9BC9C`, `#C7722C`, `#DCB278`, with dark action labels. No global colour filter, synthetic reflection or old olive treatment is used. Edge fades are fitted to the selected photo's dark left/top surroundings and the tabletop bottom; the offer remains bounded. There are no palette explanations, instruction text or builder rationale on the visitor page.

### Original R03 and deliberate departures

I directly inspected the actual 2048 × 1536 R03 extracted from the original companion archive and verified its expected hash. R03 shows a roasting environment with diagonal light, metal highlights and coffee behind a large white headline, a deliberate outline emblem and a separate pale product offer. It does not establish the CSS technique producing the surrounding continuity. The ceramic result transfers the scene/offer relationship, not the source brand, claims, olive action, typeface or geometry. The new serif headline, restrained two-line identity, copper/linen colours and simpler single-product detail action are intentional originality, not fidelity failures. Unlike the busier source, this photograph naturally offers a dark negative field. The quieter result cannot prove that the same instructions work with a busy or brightly lit source.

### First pass and corrections, not a second run

The first product implementation is retained in commit `4db69b0`. All first-pass viewport/full-page, focus and modal captures remain outside the project as `initial-*`; first-pass browser checks are `initial-checks.json` and `initial-final-transcript.txt`.

- Desktop already preserved material depth, deliberate identity, obvious action and a distinct offer. This was not missing from the first pass.
- The 390px first pass had a recognisable but small vase and more unused dark scene space. I enlarged/repositioned the photograph for phone widths and reduced scene height.
- At 320px, the first button's arrow wrapped below its label. I kept the button contents together and arranged the price above a full-width action at the smallest width.
- The native single-control modal did not keep every tested Tab/Shift-Tab step inside the document dialog. The background remained native-modal/inert, but this did not satisfy the explicit focus-containment check. I added a single-control Tab cycle; six forward/reverse steps now remain on Close at every tested width.
- I increased the smallest identity/disclosure/footer text for readability, without changing the palette.
- The first crop correction cut off the rim at the intermediate 720px zoom-equivalent layout. I retained that evidence as `revision1-*`, then added an intermediate-width composition that keeps the complete rim and base. The final `corrected-*` views were recaptured after the last product edit.

These are execution corrections, not evidence that the initial instructions alone ensured success. The approved photograph and palette proved suitable; the assumption that phone crop settings could serve intermediate/zoomed layouts was wrong. No plan element was omitted.

## Verified

### Product-level checks and evidence

`python3 studies/ceramic-campaign/verify.py --evidence <external-evidence-folder> --phase corrected --record` passed with the preinstalled **Chrome/153.0.8010.12** and disposable profiles. The runner creates its own loopback-only server and never reads personal browser state. It verified:

- Actual `innerWidth`/`innerHeight`: **1440 × 1080**, **390 × 844**, **320 × 844**, and **720 × 540 at device scale 2**. Each has matching document width, zero horizontal overflow, decoded 2400 × 3600 photograph and the required content.
- Viewport **and full-page** screenshots at each size. I opened and visually inspected the desktop scene, first/corrected full narrow pages, 320px offer, first/intermediate/final zoom crops and desktop/phone modal. The final full-page zoom view retains the complete vase, offer/action and footer. The narrow viewport does not contain the entire campaign above the fold; scrolling is intentional and no above-fold constraint was imposed.
- 200% **zoom-equivalent reflow**, using a 720 × 540 CSS viewport rendered at 2× for a 1440 × 1080 physical window. This tests the same reduced layout space and enlarged rendering, not operation of the native browser zoom menu. Native menu zoom and real-device testing are not claimed.
- Keyboard skip link → Tab → View details → Enter; initial focus on Close; six forward/reverse Tab checks; Escape → trigger focus return. Pointer opening and keyboard Close also pass. The final accessibility tree exposes the named Ember vase dialog and named Close button. The same product, S$90 and disclosure appear in the actual open dialog.
- The 8.44-second **once-playing GIF**, 1280 × 720, records actual real-time keyboard Enter/open, contained Tab, Escape/return, Space/reopen and Enter/Close. Its poster is a real open-dialog frame; the background is intentionally scrolled to the action. The existing encoder exposes PNG/VP8 but no H.264, so I used the permitted GIF fallback without installing an encoder. The file is approximately 1.1 MB and has no loop extension.
- Text-background measurements against actual composited page and modal screenshots, with text hidden temporarily for background sampling. Main headline and proposition: **10.892:1**; button labels: **10.429:1**; modal text: at least **10.429:1**. The lowest measured page text run is the small copper header slash at **5.600:1**. All normal runs exceed 4.5:1 and large runs exceed 3:1. Measurements use specified foreground colour, not anti-aliased fringe pixels, and conservatively inspect the entire rendered text rectangle.
- The dark 2px control boundary against linen is **10.892:1**, and against honey is **10.429:1**. The keyboard ring around offer/dialog buttons is dark against linen (**10.892:1**); credit-link focus uses honey against charcoal (**10.429:1**). Normal/hover/pressed label fills yield **10.429:1 / 10.892:1 / 5.733:1**. The boundary is necessary because honey versus linen alone is not 3:1. Focus and control states retain explicit boundaries rather than relying on hue.
- Actual visible DOM copy contains the demo, no-sale message, price and credit, without palette/composition rationale. I also read the rendered page and open dialog. This is a runtime copy check, not a source-string test offered as visual proof.
- Task browser manual opening and View details produced the correct named modal; final reload showed **zero console messages/errors**, and local image/script/style requests succeeded. Credit is an ordinary link opening its attributed source in a new tab; no external purchase or form was submitted.

Runtime results and measurements are retained externally as `corrected-checks.json`, `corrected-transcript.txt`, `corrected-*-accessibility.json`, text-hidden measurement screenshots, before/after captures, the recording and the task-browser console/network transcripts. The outcome card shows selected originals and actual first/final output together. No screenshot, recording or runtime evidence file is committed.

### Hypotheses: visible support and refutation

| Hypothesis | Visible support | Refutation or qualification | Assessment |
| --- | --- | --- | --- |
| Image-led colour preserves material depth | Original photo and final desktop/right scene and narrow/centre scene retain copper ribs, shadowed left side and bright reflected windows; linen offer relates to tabletop, not coffee olive. | Palette was preselected; unfiltered photography inherently carries much of the depth. No evidence of independent palette discovery or a causal instruction effect. | **Supported in this result; keep the preservation guidance.** |
| Scene/offer separation improves atmosphere | Desktop photo joins the surrounding charcoal without a panel border; tabletop/light continue behind and beside a distinct linen offer. Phone scene spans the page independently of the bounded offer. | Asset's naturally dark negative space makes this easier. Bottom fade remains visibly designed, not a claim of seamless documentary realism. The intermediate correction hid the rim. | **Supported after inspection; revise the crop/transition check.** |
| Deliberate identity and buttons clarify hierarchy | Upper-left H mark/wordmark reads as an identity, not incidental copy. The bordered honey button stands apart inside the offer. Label, role, focus and modal action work. | Recognition is an author's visual judgement, not a user-recognition study. At 320px the initial arrow wrapped; focus containment needed a repair. | **Supported visually; keep core wording, retain functional acceptance checks.** |
| Narrow recomposition preserves the campaign | Final 390px and 320px full pages preserve headline → identifiable complete vase → offer/action → disclosure; the 320px button has its own row. Final 720px zoom-equivalent crop preserves rim/base. | Initial subject was small, arrow wrapped; the first crop correction failed at intermediate width. Final success depends on corrective inspection, not first-pass compliance. | **Mixed first pass, supported final; revise explicit inspection guidance.** |

No score or “better than AGO-100” causal claim is assigned. The earlier assessment supplied the targets, not a model/asset/tool-matched control.

### Clause-by-clause instruction-pack recommendations

These are proposed wording only; both packs remain unchanged. “Keep” means useful here, not validated universally. No tested clause warrants dropping on this evidence.

| Current clause | Recommendation | Evidence and alternative explanation | Exact proposed wording/change |
| --- | --- | --- | --- |
| Builder-only clarification / no customer-facing rationale | **Keep** | Actual page/modal contain only campaign copy and disclosure. The separate product prompt also forbids rationale, so attribution is shared. | No change. |
| Apply only when photography leads, not whenever an image exists | **Keep provisionally; applicability boundary inconclusive** | This is a genuinely image-led page. No documentary/listing or decorative-image case was tested. | No change; do not broaden its trigger from this run. |
| Inspect photo; derive supporting colours; preserve material/light variation | **Keep** | Copper, table linen and dark surroundings are coherent; ribs/highlights survive. The supplied palette and strong original image are alternative explanations. | No change. |
| Respect supplied brand and semantic colours while maintaining contrast | **Inconclusive beyond supplied palette** | The approved colours pass; no conflicting established brand or semantic-status palette was tested. | No change; do not claim broader validation. |
| Atmospheric flow, image-specific transitions, necessary overlays | **Revise** | Desktop succeeds, but the intermediate phone-derived crop lost the rim. Crop/fade inspection matters more than a particular gradient recipe. This was execution error, not proof that the clause caused it. | “Let atmospheric photography connect to the page through transitions fitted to that image, using only necessary overlays. Preserve recognisable subject features, material detail and real highlights at each crop, including zoomed layouts.” |
| Distinguish bounded offers/controls; allow useful detail/gallery/listing/documentary cards | **Keep for offers/detail; other formats inconclusive** | Offer and accessible local detail surface benefit from clear boundaries. Gallery/listing/documentary formats were not tested. | Retain the existing final two sentences of the atmospheric paragraph unchanged after the proposed replacement above. |
| Original deliberate mark/wordmark readable at its displayed size | **Keep** | Header mark and Hollow Form remain legible in actual desktop/phone captures. This is one author judgement, not trademark clearance or a recognition study. | No change. |
| Obvious primary button via shape, contrast, weight, placement and explanatory label | **Keep** | Bordered honey action reads distinctly and works. Border, not fill colour alone, supplies control contrast; at smallest width label layout needed repair. | No mandatory new sentence. Use the narrow-layout inspection cue below rather than a growing list of button recipes. |
| Narrow crop/content recomposition without forcing text over imagery | **Revise** | Final sequence works; initial phone subject was small, initial 320px arrow wrapped and intermediate correction cut the rim at zoom-equivalent width. | “On narrow or zoomed layouts, recompose crop and content into a readable sequence without forcing text over photography. Inspect intended identifying features and the primary action at the smallest and intermediate widths; keep each button's label and directional icon together.” |
| S02 photography pointer | **Keep; effectiveness inconclusive** | The supplied pointer reaches the current shared section. No alternate routing experiment was run. | No change. S01/S08/S10 pointer reachability is outside this test. |
| Corrected R03 observation | **Keep** | Direct inspection shows the roasting environment, directional light and metal behind the headline, with distinct pale offer/price/add control. It does not prove a reflection/blur technique. | Keep the exact candidate observation already captured in `inputs/candidate-addendum.md`. |

The two proposed replacements are short inspection cues, not mandates for these fonts, a fixed crop, a repeated fade, saturated colour, a reflection layer or identical geometry. They target actual failure modes without treating every implementation repair as proof of pack weakness.

### Tool and skill exposure

I authored the page and evaluated it in this crewmate session. Model identity, model equality with earlier runs, effort and hidden prompt settings were not verifiable. No secondary model, live API, paid service or generation fallback was invoked. I read the `ui-ux-pro-max` and `better-accessibility` skills and the latter's focus/keyboard reference; I ran the former's local `ceramic editorial campaign --design-system` search. Its generic Swiss/dashboard direction and pink palette were unsuitable and were **not** adopted over the accepted ceramic direction. Native dialog, explicit focus, actual contrast and narrow reflow guidance were applied. This is not a skill-free or model-matched trial. Merely reading installed-tool help while locating capture access was not an MCP invocation; no MCP server or alternate sign-in was used.

Desktop Chrome 155 answered the cheap version/preflight call but aborted loopback navigation. The already-installed cached Chromium 153 and a new scratch profile worked. Initial CDP key events also needed their character payload to represent Enter correctly. Those were tool/execution-harness issues, not failures of the campaign instructions. Native-modal Tab containment and crop/layout errors were actual implementation limitations and were corrected separately.

### Repository gate

No installations were allowed. I reused already installed/cached pytest 8.4.2, pytest-asyncio, Ruff 0.15.21 and mypy libraries directly, with `src` on `PYTHONPATH`; I did not run a dependency-resolving `uv run`.

Commands and outcomes:

- `python3 -m pytest -q` with existing library paths: **80 passed**.
- `python3 -m mypy src` with existing library paths: **no issues in 22 source files**.
- Existing Ruff executable: `ruff check .` and `ruff format --check .`: **passed**, 31 Python files formatted.
- `python3 -m orchestrator.cli --help`, `--version`, `validate-config config/project.example.toml`: **passed**, version 0.1.0 and valid example project.
- `python3 scripts/check_starter.py`: **passed**, 16 TOML files, 11 agents, six workflows.
- `node --check studies/ceramic-campaign/site/main.js`, `python3 -m py_compile studies/ceramic-campaign/verify.py`, `git diff --check`: **passed**.
- SHA-256 comparison of all **37 original pack files** against the captured manifest: **zero changes**. Selected photograph and archive R03 hashes match the approved values.

## Risk

**Low.** The change is confined to a standalone local experiment and its documentation, with no runtime dependencies, application contracts, saved user data or external submissions. The photograph's depicted-design rights and the fictional identity are not commercially cleared. Keep it a local, no-sale demo.

## Not done

No accepted visible element was omitted. Both instruction packs and original historical sources remain unchanged; proposed wording is not a pack release. No baseline or product matrix, independent palette-discovery test, causal comparison, user-recognition study, broad format validation, publication, push, purchase or merge occurred. Native browser-menu zoom, real phone hardware, other browser engines and an actual screen-reader session were not exercised; the explicit zoom-equivalent rendering, accessibility tree and keyboard checks do not claim full accessibility conformance. Approval to build did not authorize merging; the completed local work is offered for a separate completion decision.
