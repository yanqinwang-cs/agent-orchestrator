# Narrative continuity, revision 4

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

6 October 2026. Design-only contract. These are targets for the future authored scene, not measured coordinates extracted from a delivered animation. The six PNGs communicate look and key states; use this contract to resolve their small framing/geometry differences in production.

## One world and one text system

Use one 50mm-equivalent perspective camera, a fixed upper-left key and faint cool rim. Keep world scale, dark glossy circuit material and lens fixed. Dolly and track rather than cutting, replacing the camera lens or swapping objects. Keep live title top-left at 64% canvas width / 30% height on the desktop reference, left aligned and identical across all beats. Text is screen-space UI, never attached to moving geometry. No corner name, playback controls or hint. N6 alone adds the two destination actions.

All primary artwork should remain left of 61% in the copy's vertical band. Desktop continuity coordinates below are normalized framing targets, not promises that independently generated bitmaps align pixel-for-pixel. Mobile contains the entire artwork below a stable text-first block.

## Persistent objects and camera targets

| Beat | Main object target | What persists | What changes |
|---|---|---|---|
| N1 0–6s | Brain center (.30,.47), width .43 | `brain_main`, its etched routes and orientation | Quiet cyan paths, sparse ember junctions |
| N2 6–12s | Same center; width .46 | Exactly the same mesh and circuits | Up to 8% scale increase, ember congestion, three spatial warning glyphs |
| N3 12–19s | Primary brain projects near (.20,.24); secondary head near (.51,.65) | `brain_main` already parented inside `cyborg_primary` | Dolly back reveals transparent crown, face/torso, then secondary cyborg and broken exchange |
| N4 19–25s | Hologram center (.38,.43), width .36 | Cyborg and open palm visibly originate projection | Selected packets feed the projected four-part montage; this composition is N4 only |
| N5 25–31s | Tablet center (.35,.49), width .39 | N5 `tablet_main` and new blue screen, distinct from N4 hologram | Transition content from N4 montage to new webpage; hand exits, connector remains |
| N6 31–36s | Tablet center (.35,.38), width .22 | Same tablet, angle, texture and physical connector | Pull back/up to reveal rolling network terrain and five anchored orbs |

N1→N2 begins at 4.8s and settles by 7.2s. N2→N3 begins at 10.4s and settles by 14s. N3→N4 spans 17.2–20.8s. N4→N5 spans 23.6–26.4s. N5→N6 spans 29.2–33.4s. These overlap beat boundaries; they are not extra duration. Use smooth velocity continuity and a calm final stop. Copy replaces at beat boundaries with ≤250ms opacity transition, holding its anchor. Optional drift must stay ≤6px over 2s; zero text movement is preferred.

## N6 network construction

The user's supplied network image guides the rolling triangulated mesh, pin-point junctions and depth falloff. It is not a production texture. Use a gently undulating mesh with thin cyan edges and small luminous intersections. No flat generic node diagram, empty ribbon or random spaghetti. The tablet's lower-left connector meets a specific bright junction. Connect that junction through visible mesh edges to other populated junctions.

Use five glass orbs in depth: two foreground, two middle-distance and one distant. Proposed projection targets: (.07,.43), (.16,.25), (.15,.74), (.45,.78), (.59,.59). These match the intended depth balance rather than an interactive resource graph. The tablet remains distinct from the orb nodes. Orbs sit on junctions, not independently drifting in space. Mini webpage/image/code shapes suggest sites/skills without invented resource names, rankings or brands. Keep emission cyan, localized to intersections/cores, with a narrow bloom; the clear glass shell and connecting edges remain legible. No repeated pulses or orbit motion after settling.

The right title and action region takes priority: suppress network brightness behind the text instead of moving the text. Keep the tablet readable enough to recognize a webpage. On mobile, contain the whole image; do not crop away the tablet-to-junction connection.

## N2 marks and warnings

Official downloaded SVGs live in `brand-assets/`. Display them separately from generated art on calm dark patches, retaining original colors/proportions and clear space. GitHub at (.075,.12), Figma at (.50,.12). They are ecosystem references, not advertised integrations or endorsements. Keep the warning glyphs on information routes, away from the marks, so the picture describes coordination overload rather than declaring either product defective. Do not morph, recolor or explode the logos.

## Device screen and evidence

N4 uses the supplied four-part website montage. N5/N6 use the new black/blue editorial webpage. Only N5/N6 share one final screen texture; N4→N5 intentionally transitions content. The screen is not a real Agent Lab result, a Pinterest capture, a measured improvement, or a branded site. Genuine before/after evidence remains a separate unfilled capture slot.

## Delivery and verification

For the full cinematic target, provide one source scene and an authored 36-second finite animation, exported either as optimized prepared real-time assets or reviewed video. Deliver the camera/light keyframes, the same brain/tablet objects, exact device screen texture, named orb nodes, still posters and mobile-safe framing. The current handoff supplies six PNGs and this specification; it does not supply those motion files.

Future verification: inspect each boundary frame-by-frame for object/texture identity, smooth position/scale, connector continuity, legible text, and no jump cut. Check at 1440, 1024, 768, 390 and 320; check reduced-motion/direct-entry bypass and immediate key/tap skip independently of media load. A fallback crossfade is useful for constrained devices, but must never be reported as fulfillment of the continuous camera sequence.

## Additional transition checkpoints required

- N1→N2: congestion onset, mid-expansion, warning appearance and settled overload.
- N2→N3: crown edge reveal, face/shoulder reveal and second entity entering view.
- N3→N4: selected path, forearm lift, open palm, initial projection rays, partial panel and fully formed montage.
- N4→N5: projection and montage resolve; cyborg/palm recedes; new black/blue webpage and standalone tablet become the focus. This content/presentation change is intentional.
- N5→N6: initial pullback, connector/junction reveal, near orbs entering, distant mesh resolving and final settle.

These are semantic checkpoints, not a maximum image count. Add more frames/assets wherever continuity, occlusion, timing or legibility needs them. Review an animatic before final animation. Those intermediate frames are required downstream, not claimed as delivered here.
