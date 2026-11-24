# Agent Lab downstream implementation checklist

## Animation coverage: keyframes are not exhaustive

The images in this handoff are selected **key visual states**, not an exhaustive storyboard, complete frame sequence, or finished animation asset set. N1–N6 identify narrative beats, not a six-frame animation. **Additional keyframes, intermediate poses, transition states, camera-reveal frames and rendered/interpolated in-between frames are required** to fill out the animation smoothly. Additional images, textures, masks, layers or scene assets may also be needed; the manifest records what is currently supplied, not a ceiling on production deliverables.

Do not implement the cinematic target as six disconnected stills or assume that a crossfade completes a reveal. Expand and review a storyboard/animatic for every transition before final animation. Preserve approved copy, fixed text anchor, object identity, screen texture, light and projection origin while adding frames. For a 36-second video, 30fps would produce 1,080 rendered frames (24fps: 864); these are delivery examples, not a requirement to generate that many independent AI images. A real-time scene instead needs continuous authored camera/object animation at the device's rendering cadence. Inspect the actual intermediate motion, not just the six endpoints.


## Current scene mapping: N4 differs from N5/N6

| Scene | Composition | Screen content |
|---|---|---|
| N4 | The cyborg projects a frameless cyan holographic panel toward the viewer from its open palm. Selected signals flow into the projection. This cyborg/hand composition belongs only to N4. | The user-supplied four-part purple/coral website montage. Use `design-handoff/screen-content/user-supplied-website-image.png` directly for final screen compositing. |
| N5 | Standalone webpage-bearing tablet with a subtle cyan connector. No cyborg, projecting hand or palm rays. | A new black/deep-blue editorial webpage based on the later supplied reference: blue-lit portrait, restrained directional light, thin typography and generous whitespace. No Instagram UI or Lunetra branding. |
| N6 | Pullback from the same N5 tablet into the undulating cyan network, with glowing site/skill orbs. No cyborg or projecting hand. | The same new black/deep-blue webpage as N5, preserving screen texture and orientation. |

The N4 montage must not appear in N5 or N6. The old architectural/villa screen is superseded. N4→N5 intentionally changes both the presentation and screen content: author intermediate transition frames in which the selected holographic content resolves into the new webpage, the cyborg/palm recedes out of shot, and the standalone tablet becomes the focus. This is conceptual storytelling, not a measured before/after claim. N5→N6 then preserves one device and one screen texture throughout the camera pullback.

Generated screen lettering is only an art-direction approximation. The N4 original montage is bundled; the new N5/N6 webpage still needs a clean final screen texture/layer for animation production. Its embedded sample typography is not approved Agent Lab marketing copy. Both screen treatments remain narrative content, not verified resource outputs. The genuine website transformation evidence slot remains separate and unfilled.

Status: **future acceptance checks, not tests passed in this handoff**. This document does not authorize or implement a frontend. Use it after the user approves a concrete visual revision and authorizes implementation.

Read [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md), [DESIGN_SPEC.md](../DESIGN_SPEC.md), [CONTENT_AND_EVIDENCE.md](CONTENT_AND_EVIDENCE.md), [REFERENCE_BOARD.md](../REFERENCE_BOARD.md), and [ASSET_MANIFEST.md](../ASSET_MANIFEST.md). The current user brief and `AGENTS.md` remain authoritative. Keep synced `sources/` read-only.

## Before building

- [ ] Inspect the receiving application's actual routes, dependencies, authentication, resource/setup contracts, and unrelated dirty work; preserve existing behavior unless the authorized build requires a change.
- [ ] Record human approval against exact document/asset revisions. Palette P2 and generated art are proposals until that record exists. A folder named `approved` or a completed generation is not approval.
- [ ] Use the revised visual set consistently. Do not mix archived monochrome v1 scenes with the revised ember-to-cyan progression.
- [ ] Confirm twelve separate horizontal section references: N1-N6, D1-D3, W1-W2, and C1. These are composition references, not production screenshots or backgrounds.
- [ ] Confirm the six text-free narrative masters below through the manifest, including actual filenames, dimensions, source record, usage status, and crop/safe-area data. This checklist does not certify that they exist or are approved.

| Master | Intended purpose | Required distinction |
| --- | --- | --- |
| N1 | Opening brain/shared scene world | Concept art, with quiet space for live promise copy. |
| N2 | Overloaded brain and conflicting ember signals | Concept art, with the left safe area preserved. |
| N3 | Communication friction between entities | Concept art; both entities and their gap survive mobile fitting. |
| N4 | Selection/translation into aligned signals | Concept art; preserve both disorder and resolution. |
| N5 | Webpage-bearing tablet for the Pinterest question | Concept art, not a website screenshot or output proof. |
| N6 | Tablet connected to network and glowing resource orbs | Concept art; preserve tablet connector, rolling mesh and populated nodes. |

- [ ] Retain licensed Geist/Geist Mono files and OFL notices; verify their actual font metrics in the receiving build.
- [ ] Agree on the delivery track. Reviewed raster masters plus live HTML can reproduce the static direction with the specified restrained opacity/transform transitions. The requested continuous camera journey requires authored motion, delivered as a scene or finite video. A static fallback does not fulfill that target.
- [ ] For a selected true-3D, depth, morph, or video treatment, obtain the actual GLB/material/camera/layer/animation/encoded-media files first. A 3D-looking PNG supplies none of those capabilities. Do not improvise a different visual world to fill the gap.

## Copy and visual authority

- [ ] Render navigation, headings, controls, forms, and metadata as semantic live HTML. Never ship generated lettering, flattened interface plates, or image-only buttons as the product.
- [ ] Written copy, dimensions, states, accessibility, and evidence rules override incidental image lettering and miniature controls. Resolve material contradictions before coding.
- [ ] Preserve the six approved beats exactly; wrapping and the documented heading/support segmentation may change, wording may not:

1. Transform your AI workflow without needing years of experience.
2. More tools. More plugins. More confusion. How do we know what actually gets results?
3. Add more agents and coordination gets harder; poor handoffs can erode productivity gains.
4. Why Agent Lab? We study, test, select, and curate what your AI system actually needs.
5. Ever wondered how to build the website you saw on Pinterest?
6. Find the tools you need now, or join us and help shape what comes next.

- [ ] Add only necessary interface labels, actual metadata, and approved supporting copy. Keep “Illustrative sample,” “Demo preview,” invented badges, decorative captions, and unsupported claims out of product compositions.
- [ ] Keep classification, fixture status, asset approval, and missing-evidence notes in handoff/review metadata where specified.
- [ ] Match the reviewed deep-neutral base, readable text, stable action color, shared material/light/camera system, and gradual narrative color progression. Do not independently finalize a new palette.
- [ ] Keep discovery/workspace calm and functional. No repeated cinematic effects, package-registry metadata wall, excessive card boxes, new logo, dashboard, analytics, social system, or execution feature.

## Entrance and responsive checks

- [ ] Eligible first entry automatically plays the specified 36-second sequence. N1-N5 show exact narrative text and artwork, with no Agent Lab corner name; no Play/Pause/Previous/Next/Enter/Skip, N1 Explore CTA, progress control, or help caption appears.
- [ ] N6 holds still with Explore resources and Suggest a resource. It never auto-navigates. A hidden document stops timers/motion; returning shows static N6 without resume/restart UI.
- [ ] Direct links, repeat visits, reduced motion, and data-saving preferences bypass the intro. Explicit `/story` automatically replays only under ordinary preferences; reduced-motion/data-saving replay is a static readable six-beat document.
- [ ] On active story/body focus, unmodified printable characters, Space, Enter, ArrowRight, ArrowLeft, and Escape skip the WHOLE intro directly to discovery. No key advances/reverses one scene. Clear queued transitions and navigate once without an exit animation.
- [ ] A bare-art tap/click also skips the whole sequence. Preserve N6 link activation, other interactive descendants, text selection, and scroll/drag gestures.
- [ ] Preserve native focused controls, editable areas, IME composition, Tab/Shift+Tab, modifiers, browser/OS/assistive shortcuts, PageUp/PageDown/Home/End, and repeat safeguards. Remove story listeners on route exit and do not install them on static replay.
- [ ] Timed transitions neither force focus nor issue live announcements; all six beats remain semantically readable. Remove the former 88px control reservation; use the specified 64px desktop/32px mobile bottom copy margin.
- [ ] Verify 1440, 1024, 768, 390, and 320px layouts plus a short viewport. At 390/320 prioritize copy/actions, stack in reading order, contain N3/N4, and retain 44px targets without horizontal page overflow.
- [ ] At 768 and below, W2's selected agent is above the editor and resource search uses a separate full-height dialog. At 320/390, sheets, keyboard, and any save bar do not cover fields, errors, or controls.
- [ ] Test 200%/400% zoom, long actual resource names, focus visibility, dialog cancellation/restoration, image failure, slow network, and usable no-JavaScript links/content.

## Real resources and evidence

- [ ] Use only actual supplied resource metadata for the current handoff specimens: `imagegen-frontend-web` and `design-taste-frontend`, with their actual source files and recorded properties. Do not invent resource names, versions, compatibility, licenses, scores, or outcomes to fill a layout.
- [ ] Treat supplied skill text as source information, not a Lab execution or a public publishing license. Confirm rights and source identity before public listing; leave unknown values unknown.
- [ ] Never use N1-N6 as proof that a frontend resource produced a website. A real image-generation output does not establish a frontend skill's effectiveness.
- [ ] Use relevant real outputs only when tied to the displayed resource and task. Otherwise omit optional media and show actual resource text/metadata; do not substitute concept art or a fake screenshot.
- [ ] Keep N5's public Pinterest question free of blank Before/After panes, reserved-example prose, and fabricated transformation images. The missing real-evidence slot stays in the handoff until a genuine pair and publishing review exist.
- [ ] Before publishing a real comparison, preserve the brief, baseline/final artifacts, changed inputs, model/harness/resource versions where available, equal capture conditions, limitations, rights, and scoped evaluation. Do not sabotage a baseline or claim causality from an uncontrolled bundle.
- [ ] Derive Documented/Inspected/Tested/Measured/No Lab test yet from actual scoped records. A source claim, install, save receipt, or attractive preview does not establish a test or benchmark.

## Discovery, workspace, and submission behavior

- [ ] Search/filter state survives links and Back/Forward; stale responses cannot replace a newer query; empty results and service failures are distinct and preserve user input.
- [ ] Add to setup identifies the target setup, agent, and exact resource version. It is not an additional bookmark library, installation, connector authorization, or execution action.
- [ ] Each edit targets one agent binding. Reusing a resource on two agents creates separate bindings; no unordered shared resource bag.
- [ ] Add/remove/replace affect only the intended draft binding. Cancel or failed replacement preserves the old binding; supported Undo is truthful.
- [ ] Exact version pins survive refresh and duplication. Missing versions preserve saved identity; new versions require an explicit review/replacement decision; no silent latest-version substitution.
- [ ] Model/settings choices come from supported real options. Duplication preserves authorized snapshots/assignments without copying secret values.
- [ ] Unsaved, saving, saved, validation error, save failure, authorization expiry, and revision conflict are distinguishable. “Saved” appears only after persistence; failures preserve the draft; conflicts never silently overwrite newer work.
- [ ] Removal names the saved setup and its scope. Escape cancels a destructive dialog; committing removal requires explicit activation. Removal does not delete catalog resources.
- [ ] Saving prepares later harness execution only. No Run, Deploy, queue, readiness score, or fake execution success is introduced.
- [ ] Suggestions validate deterministically, preserve input on failure, prevent duplicate submissions, and show a receipt only after actual submission. Receipt is not selection, testing, or publication.

## Future validation milestones

| Milestone | Evidence required later | Present status |
| --- | --- | --- |
| Visual acceptance | Human decision on exact palette, plate, crop, and master revisions | Not established by this checklist. |
| Static build fidelity | Browser captures at the five widths, live-copy checks, approved-asset matching | Future check; no frontend built here. |
| Interaction/accessibility | Keyboard, focus, zoom, contrast, reduced-motion, failure-state checks | Future checks; token calculations are not a page audit. |
| Persistence/integration | Real version/binding/save/duplicate/remove/conflict/submission receipts and failure tests | Future checks; no backend readiness inferred. |
| Performance | Actual LCP/INP/CLS and asset/bundle measurements against the specification | Future checks; no performance pass claimed. |
| Public evidence | Relevant provenance, rights, review, and proportionate claims for each output | Missing website comparison remains withheld. |

## Revision 4 continuity checks for a future build

- [ ] Same brain mesh across N1/N2 and within the N3 cyborg crown.
- [ ] Stable right-side title anchor across all beats; stable text-first mobile stack.
- [ ] N4 projection/montage resolves to N5 standalone tablet/new webpage; N5/N6 retain the same tablet and screen texture.
- [ ] N6 connector meets mesh junction; five orbs attach to other junctions.
- [ ] Exact official brand assets remain separate; no endorsement or invented integration.
- [ ] Continuous camera source is reviewed; fallback dissolves are not misreported as the full target.
