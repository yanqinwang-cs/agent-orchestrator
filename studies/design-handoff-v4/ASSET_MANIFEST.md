# Agent Lab visual asset manifest, revision 4

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

6 October 2026. The user accepted the correction direction; these newly generated pixels remain pending review. No asset is silently promoted to human-approved. This release contains six selected narrative masters, three revised and three retained and six explicitly retained practical surface plates. In REVIEW.html, exact narrative copy and official marks are separate live overlays. There are 12 reviewable surfaces and 12 unique current raster assets, not 18 new images.

## Current images

| ID | File | Role | Dimensions | Status |
|---|---|---|---|---|
| N1 | [N1-circuit-brain.png](design-handoff/narrative-v3/N1-circuit-brain.png) | narrative_concept_master | 1672 × 941 | Pending human review |
| N2 | [N2-overloaded-brain.png](design-handoff/narrative-v3/N2-overloaded-brain.png) | narrative_concept_master | 1672 × 941 | Pending human review |
| N3 | [N3-cyborg-reveal.png](design-handoff/narrative-v3/N3-cyborg-reveal.png) | narrative_concept_master | 1672 × 941 | Pending human review |
| N4 | [N4-cyborg-projects-hologram.png](design-handoff/narrative-v4/N4-cyborg-projects-hologram.png) | narrative_concept_master | 1672 × 941 | Pending human review |
| N5 | [N5-blue-editorial-tablet.png](design-handoff/narrative-v4/N5-blue-editorial-tablet.png) | narrative_concept_master | 1672 × 941 | Pending human review |
| N6 | [N6-blue-webpage-network.png](design-handoff/narrative-v4/N6-blue-webpage-network.png) | narrative_concept_master | 1672 × 941 | Pending human review |
| D1 | [07-discovery-overview.png](design-handoff/visuals-v2/07-discovery-overview.png) | design_reference | 1672 × 941 | Pending human review |
| D2 | [08-discovery-results.png](design-handoff/visuals-v2/08-discovery-results.png) | design_reference | 1672 × 941 | Pending human review |
| D3 | [09-resource-detail.png](design-handoff/visuals-v2/09-resource-detail.png) | design_reference | 1672 × 941 | Pending human review |
| W1 | [10-workspace-saved-setups.png](design-handoff/visuals-v2/10-workspace-saved-setups.png) | design_reference | 1672 × 941 | Pending human review |
| W2 | [11-workspace-configuration.png](design-handoff/visuals-v2/11-workspace-configuration.png) | design_reference | 1672 × 941 | Pending human review |
| C1 | [12-contribution-suggestion.png](design-handoff/visuals-v2/12-contribution-suggestion.png) | design_reference | 1672 × 941 | Pending human review |

## Placement and motion

N1–N6 share a right-side title anchor at 64% width / 30% height in the desktop design, with art on the left. Mobile uses one text-first stack and contained landscape artwork. N6 must retain the tablet connector and visible resource orbs. See [DESIGN_SPEC.md](DESIGN_SPEC.md) and [NARRATIVE_CONTINUITY.md](design-handoff/NARRATIVE_CONTINUITY.md).

The PNGs are narrative concept art and static fallbacks after review. They are not meshes, rigs, source scenes, video or real resource results. A continuous authored scene/video is required for the requested brain-to-cyborg and tablet-to-network camera journey. The stills do not prove matching animated topology or exact texture identity. No motion file is supplied in this design-only revision.

## Exact metadata and sources

[ASSET_MANIFEST.json](design-handoff/ASSET_MANIFEST.json) records each current file's dimensions, bytes, SHA-256 hash and status. [GENERATION_PROMPTS.json](design-handoff/GENERATION_PROMPTS.json) records the six exact new generation prompts and retained utility asset lineage. Model/seed were not exposed by the generation tool. No stock license or rights warranty is invented.

[Official GitHub/Figma SVGs](design-handoff/brand-assets/README.md) were searched and downloaded from their owners before composing N2. Preserve their bytes, colors, proportions and clear space; do not imply endorsement or an integration. Their presence is subject to the owners' trademark terms. These marks are not Agent Lab logos.

The user-supplied brain and network images guide material and composition; they remain reference-only, not production assets. The new N4–N6 tablet webpage is an explicitly requested narrative concept, not a real website-output example or Pinterest screenshot. The genuine before/after capture slot remains absent and handoff-only. Use the capture contract in DESIGN_SPEC.md before publishing any result claim.

Geist/Geist Mono variable fonts and OFL.txt remain bundled in [fonts](design-handoff/fonts/README.md), under the previously recorded official v1.7.2 provenance. Utility resource specimens remain grounded in the supplied skill sources. No invented version, benchmark, rating or compatibility status is introduced.

## Approval and history

[approved/](design-handoff/approved/README.md) contains no image files until the user approves exact hashes and uses. Direction acceptance is recorded separately from final asset acceptance. Approved files can then be copied without destroying their generation history.

V2 narrative images are superseded. V2 documents and metadata are preserved in `design-handoff/archive/v2/`; the existing v2 zip remains historical. The six utility images retain their `visuals-v2/` paths intentionally and are named individually in the current manifest. V1 remains historical. Current archives need not ship rejected narrative art.
