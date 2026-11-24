# Agent Lab handoff, revision 4

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

Start with [REVIEW.html](REVIEW.html), a static review document. The same revision is available in the existing Lavish session. Its selectors navigate the handoff, not the proposed entrance.

- [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md): retained public/private scope and revised six-beat entrance.
- [DESIGN_SPEC.md](../DESIGN_SPEC.md): layout, type, spacing, color, responsive and interaction rules.
- [NARRATIVE_CONTINUITY.md](NARRATIVE_CONTINUITY.md): precise persistent-object and camera contract.
- [CORRECTIONS_v3.md](CORRECTIONS_v3.md): receipt for every submitted Lavish correction.
- [ASSET_MANIFEST.md](../ASSET_MANIFEST.md), ASSET_MANIFEST.json and GENERATION_PROMPTS.json: current files, exact hashes and provenance.
- `narrative-v3/`: six new clean narrative masters. Text is composed separately in the review document.
- `visuals-v2/`: six retained utility plates named by the current manifest; old narrative images in that folder are historical and excluded from the v3 zip.
- `brand-assets/`: official downloaded GitHub/Figma SVGs and source/usage notes.
- `fonts/`: existing Geist files with OFL license.

No frontend, animation, backend or route is implemented. The requested continuous camera sequence requires a separately authored source scene/video. Genuine before/after evidence is still absent. Final image approval remains pending; do not treat generation or review selection as approval.
