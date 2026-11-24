# Agent Lab website design specification, revision 4

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

Date: 6 October 2026. Revision: response to the supplied design corrections. Scope: a visual and interaction handoff only. Status: **proposed for human review; no visual approval is implied by delivery**.

This specification accompanies `IMPLEMENTATION_PLAN.md`, the separate horizontal design plates, and `REFERENCE_BOARD.md`. It does not implement a frontend, choose an execution backend, or change the generic persisted domain model. `sources/` remains read-only. The user's current brief and `AGENTS.md` outrank earlier exploratory project documents.

## 1. Design decision and evidence boundary

Reading this as: a cinematic project vision and pitch for students, vibe coders, casual AI users, and technically curious non-experts, resolving into practical discovery and a minimal private workspace.

This revision preserves the six-scene narrative, public/private distinction, measured grids, version-aware editing, skip behavior, and accessibility work. It corrects the earlier monochrome interpretation, unrelated-poster risk, rewritten narrative, and promotion of concept art as resource proof. Original files belong to the archived v1 handoff and do not override this revision.

The organizing visual sequence is **overload and confusion → communication friction → selection and translation → refinement → the possibility of polished output → calm discovery**. The homepage is a vision and pitch, not an enlarged catalog header. **Continuity takes priority over layout variety.** Repeating a coherent camera, object, material, light, and typographic anchor is preferable to six unrelated impressive compositions.

| Surface | DESIGN_VARIANCE | MOTION_INTENSITY | VISUAL_DENSITY | Reason |
| --- | ---: | ---: | ---: | --- |
| Narrative entrance | 7 | 6 | 3 | Shared cinematic world; transitions explain a continuous idea. |
| Discovery and resource detail | 5 | 2 | 4 | Calm editorial browsing and useful real previews. |
| Private/team workspace | 3 | 1 | 5 | Stable search, configure, pin, duplicate, and save controls. |

These values describe intended behavior, not implemented motion. The image plates remain static design references. No animation or website is implemented by this handoff.

**Palette, lighting, and generated visual revisions are proposals for review, not independently accepted final brand decisions.** The proposal in section 3 makes the candidate concrete enough to inspect. It does not infer approval from the user's request for controlled color. Use Agent Lab as ordinary text on discovery/workspace only. Remove the top-left name from all narrative frames. Do not invent a logo, monogram or partner mark. N2 uses separately sourced official GitHub/Figma marks as requested, without endorsement claims.

| Visual category | Permitted role | Evidence boundary |
| --- | --- | --- |
| Narrative/metaphorical artwork | Brain overload, communication friction, fragmented information, selection, translation, refinement. | Does not demonstrate a resource's actual capability or depict measured agent internals. |
| Interface design reference | Layout, hierarchy, placement, state, and responsive direction. | Does not prove an implemented product or actual catalog content. |
| Real product/output example | An attributable output from an actual prompt, skill, tool, MCP, agent configuration, or website task. | Needs relevant provenance, source/rights information, and a claim matching its evidence. |

Classification belongs in the handoff manifest and review chrome. **Do not place “Illustrative sample,” “Demo preview,” decorative captions, invented badges, or proof disclaimers inside the product merely to label a mockup.** Use only approved story copy, necessary interface labels, real resource metadata, and explicitly approved supporting text. Review metadata can explain what a plate is without becoming proposed page content.

Concept art must not be promoted as the output of a frontend-design prompt or a recommended skill. The fact that an image generator created a brain image does not make it evidence that a website resource works. No real website transformation example was supplied. N5 therefore uses the user's Pinterest question and no fabricated website pair. Future evidence-capture slots exist in handoff records only.

## 2. References and visual continuity

`REFERENCE_BOARD.md` records the retained websites, added interactive/3D examples, motion/video references, supplied Pinterest references/images, and observation limits. Reference screenshots, videos, code libraries, and pins are research material unless separately licensed and selected. Adapt properties; do not reproduce any one scene, layout, object, or full sequence.

### Shared scene world

The accepted correction direction uses a glossy dark anatomical brain with precisely etched luminous circuits, following the supplied brain reference. Reject the former fibreglass, braided-wire and metallic-strand sculpture treatment. Keep graphite mass, restrained titanium tablet edges and transparent cyborg crown/orb shells; cyan and ember signals carry the narrative. No arbitrary palette change is introduced.

N1 and N2 are the same brain. N3 reveals that brain inside the primary cyborg; a second entity introduces the handoff. N4 follows the selected signals to a tablet, N5 approaches that tablet, and N6 pulls back to reveal the tablet connected to an undulating network with glowing resource orbs. N4 uses the palm-projected holographic montage; N5/N6 share the standalone tablet and new blue webpage. The transition between these is authored explicitly. Camera motion changes framing continuously, without teleporting or swapping geometry.

Use a fixed 50mm-equivalent lens, upper-left key light and deep navy environment throughout. Camera position may dolly/track; avoid lens changes, light-direction resets and unrelated cuts. The six generated stills are art-direction keyframes, not geometrically exact frames of a delivered animation. The authored source scene must resolve any raster identity or framing differences using the continuity contract in `design-handoff/NARRATIVE_CONTINUITY.md`.

All six titles share one right-side, left-aligned anchor. No Agent Lab top-left wordmark, playback controls or changing text quadrants. The public discovery and workspace retain their existing calm visual system.

## 3. Foundation tokens

All dimensions below are CSS pixels. This is **palette proposal P2**, awaiting user review with the revised plates and reference board. Deep neutral is the proposed default for the narrative, discovery, and workspace. A coherent optional light theme is specified as a future candidate for discovery/workspace, not as a required first-release control; the narrative retains the reviewed cinematic scene world once approved and never flips theme between beats. A theme selection on another route must not recolor actual output evidence.

### 3.1 Proposed color tokens

| Token | Proposed deep theme | Optional light discovery/workspace | Use |
| --- | --- | --- | --- |
| `surface.page` | `#0E1218` | `#F3F6F8` | Page canvas, story copy-safe field. |
| `surface.raised` | `#171E27` | `#E6ECF1` | Inputs, picker, dialogs. |
| `surface.hover` | `#222E3A` | `#DCE5EC` | Hover/selection fill, never sole selected cue. |
| `text.primary` | `#F2F5F7` | `#18222D` | Display, body, control text. |
| `text.secondary` | `#B8C3CF` | `#4F6070` | Necessary real metadata and helper text. |
| `line.decorative` | `#33414F` | `#CBD6DF` | Nonessential group separators. |
| `line.control` | `#667787` | `#718293` | Required control boundaries. |
| `action.fill` | `#79D9E8` | `#006B82` | Main action, stable across scenes. |
| `action.hover` | `#58BED0` | `#005B70` | Hover on primary action. |
| `action.active` | `#43B2C5` | `#004C5E` | Pressed primary action. |
| `action.text` | `#0E1218` | `#F3F6F8` | Main action text. |
| `focus.outer` | `#79D9E8` | `#006B82` | 2px keyboard outline. |
| `focus.gap` | `#0E1218` | `#F3F6F8` | 2px offset/gap. |
| `scene.ember` | `#FF9367` | Not an interface token | Overload/conflicting signal emission. |
| `scene.cyan` | `#79D9E8` | Not an interface token | Communication and resolving signal emission. |
| `scene.bridge` | `#A8A1E8` | Not an interface token | Limited N3 transition candidate, only if needed to join ember/cyan visually. |

Interface action color stays consistent. Narrative emission changes gradually; it is not a new brand palette per scene. Do not use scene colors as invented quality, error, or success badges. Errors and confirmations remain explicit text plus shape and state. Any later semantic color choice requires review in its own context.

| Scene | Proposed color progression | Limits |
| --- | --- | --- |
| N1 | Deep graphite with a low ember trace and faint cool separation. | Object remains readable; no whole-screen orange wash. |
| N2 | Ember is strongest along crowded, competing pathways. | Emission occupies <=20% of visible artwork; background and text-safe field remain deep-neutral. |
| N3 | Ember recedes on the sending side; cyan emerges on the receiving side. | Optional violet bridge occupies <=5% of artwork, never a purple background gradient. |
| N4 | Cyan continuity replaces intersecting warm paths. | Retain a small ember remnant only to connect the preceding scene. |
| N5 | Graphite/titanium surface is refined and clean with controlled cyan edge light. | It is a conceptual transition into the user's website question, not a fake website screenshot. |
| N6 | Few aligned cyan paths at low intensity resolve into the discovery canvas. | No ambient loop, new color family, or dramatic lighting reset in discovery. |

Calculated contrast ratios for these proposed solid token pairs:

| Pair | Deep theme | Optional light theme |
| --- | ---: | ---: |
| Primary text / page | 17.15:1 | 14.82:1 |
| Secondary text / page | 10.50:1 | 5.97:1 |
| Control boundary / page | 4.07:1 | 3.64:1 |
| Primary action / page and action-text contrast | 11.54:1 | 5.65:1 |
| Primary text / raised surface | 15.33:1 | 13.51:1 |
| Secondary text / raised surface | 9.39:1 | 5.44:1 |
| Control boundary / raised surface | 3.64:1 | 3.32:1 |

Ember against the deep page is 8.60:1, but artwork emission is not a text color prescription. Calculation follows WCAG sRGB linearization and `(Lmax + 0.05) / (Lmin + 0.05)`. These are token measurements, not a rendered-page accessibility audit; verify opacity, image overlaps, hover states, and actual compositing after implementation. Decorative separators never serve as the sole input or focus boundary.

### 3.2 Proposed gradient, lighting, and shadow rules

The background is the deep page token. Gradients support object illumination and readable text; they are not independent decorative blobs.

- Narrative emission can fade from the relevant scene color to transparent within the existing circuit/object silhouette. Intensity rises during confusion and becomes lower and more directional during resolution.
- A page-colored protection field may cover the fixed right-side copy region. It is opaque under text and fades only into the art outside the glyph footprint. Do not introduce the former lower/left copy zones or an arbitrary visible gradient.
- Do not create a full-screen purple-to-blue or pink-to-orange gradient, rainbow material, gradient headline, illuminated button edge, or glowing border around every object.
- Restrained glow is permitted inside conceptual emission because luminous signals are part of the user's requested narrative. It is not permitted on search results, workspace rows, navigation, or form inputs.
- A dialog can have one `0 16px 48px` shadow at 28% dark opacity plus its real border. Discovery groups and workspace rows remain flat.

No animated grain, noisy lens flare, cursor trail, decorative code, or fake HUD. The visual's light and material provide the atmosphere.

### 3.3 Typography

Use the bundled/licensed Geist Sans and Geist Mono assets listed in the asset manifest. Keep their OFL notices. The future frontend must self-host; use `font-display: swap`, preload only the above-fold sans font, and use a metric-adjusted system sans fallback. Do not introduce an additional display serif, decorative monospace, or fake condensed face.

| Role | Desktop >=1280 | Tablet 768-1279 | Mobile <768 | Weight / tracking |
| --- | --- | --- | --- | --- |
| Shared story title | 42 / 47 | 32 / 37 in side layout; 36 / 41 when stacked | 36 / 41 at 390; 30 / 35 at 320 | 500, -0.035em |
| Discovery page title | 48 / 52 | 40 / 44 | 32 / 36 | 500, -0.035em |
| Detail title | 40 / 46 | 36 / 42 | 30 / 35 | 500, -0.03em |
| Workspace page title | 32 / 38 | 28 / 34 | 26 / 32 | 500, -0.025em |
| Section title | 28 / 34 | 26 / 32 | 24 / 30 | 500, -0.02em |
| Feature item title | 24 / 30 | 22 / 28 | 21 / 27 | 500, -0.015em |
| Story support | 22 / 30 | 18 / 26 | 18 / 26 | 400, -0.01em |
| Body | 17 / 26 | 17 / 26 | 16 / 25 | 400, normal |
| Interface and buttons | 15 / 22 | 15 / 22 | 16 / 24 | 500, normal |
| Caption / helper | 14 / 21 | 14 / 21 | 14 / 21 | 400, normal |
| Version / small code | 13 / 20 | 13 / 20 | 13 / 20 | Geist Mono 400, normal |

Notation is font-size / line-height. All body and input text is at least 16px on narrow screens except captions and compact identifiers. Text columns cap at 62ch; story support caps at 40ch. Titles cap at the prescribed column span. The exact approved narrative may require three or four lines; preserve its words rather than enforce an arbitrary two-line slogan rule. Use natural wrapping, balance only short headings, and never force an awkward line break to match generated lettering. Do not add all-caps eyebrows or other display microcopy. Resource types use sentence case.

Do not use version stamps, numbered sections, tiny precision labels, or faux run metadata on marketing scenes. Actual versions belong in resource detail and workspace controls. Do not style numeric provenance as decoration.

### 3.4 Spacing, edges, and iconography

Spacing scale: **4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96, 128**. Use 4px only for tight related elements; normal component gaps are 12-24px; distinct content groups use 32-48px; public editorial sections use 96px desktop, 64px tablet, 48px mobile.

Corners: media and editorial panels 0px; inputs, buttons, selected-result surfaces 4px; dialogs and mobile sheets 8px at exposed corners. No pills or decorative rounded cards. Circle is reserved for an actual radio indicator. A carousel is not required.

Use one icon family: Phosphor regular, at 20px with 1.5px visual stroke; 16px only beside version or copy metadata. Icon-only controls need a visible tooltip on hover/focus and an accessible name. Their target remains 44px. No emoji, custom-drawn pictograms, brand-like symbol, or invented trust mark.

Layer scale: content 0; sticky navigation 10; anchored popover 20; mobile save bar 30; modal scrim 40; dialog/sheet 50; transient nonblocking confirmation 60. Focus indicators must not be clipped by overflow.

## 4. Measured responsive framework

### 4.1 Site grid

| Viewport | Outer margin | Content width | Columns | Gap | Column width | Nav |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1440 | 64 | 1312 | 12 | 24 | 87.33 | 72 |
| 1024 | 40 | 944 | 8 | 24 | 97 | 72 |
| 768 | 32 | 704 | 6 | 20 | 100.67 | 64 |
| 390 | 20 | 350 | 4 | 16 | 75.5 | 64 |
| 320 | 16 | 288 | 4 | 12 | 63 | 64 |

For widths above 1440, cap content at 1312 and center it. Media may bleed to the viewport edge where specified. At intermediate widths, margins interpolate only by breakpoint: 16 below 360, 20 from 360-639, 24 from 640-767, 32 from 768-1023, 40 from 1024-1279, 64 from 1280. At 1280 the content width is 1152. Never use arbitrary per-section outer margins.

Grid children use `min-width: 0`; tracks use `minmax(0, 1fr)`. Long resource names wrap; hashes truncate visually with a copy/reveal control; neither creates horizontal page overflow. Code blocks scroll inside their own region. Images have declared aspect ratios. All sticky elements account for navigation height and safe-area insets.

### 4.2 Common header

At 1440/1024: name at grid start; links **Explore resources**, **Suggest a resource**, and **Workspace** on one line at the right; 32px link gaps; existing account controls, if present, in a labelled overflow menu. A theme selector belongs there only if the optional light variant is later approved; this handoff does not require new theme-switch UI. The entire header stays within 72px. Public pages do not foreground sign-in before the main task. Workspace can show the current personal/team context only if the backend supports such a context.

At 768 and below: name left and **Menu** control right. The menu is a native keyboard-accessible disclosure or dialog with the same navigation links and any already-approved account controls. No multilevel navigation. At 320 use a 16px name; all hit areas remain 44px. Menu items are plain rows, not tiles.

The entrance has no header identifier. N1-N5 show the exact narrative typography and artwork, with official ecosystem marks only in N2. They have no visible Play story, Pause, Previous, Next, Enter, Skip, Explore action, progress control, or keyboard-help caption. N6 adds only **Explore resources** and **Suggest a resource** as its final actions. Ordinary public navigation starts in discovery.

## 5. Narrative entrance: N1-N6

The entrance is one automatically playing six-scene story, approximately 36 seconds, for an eligible first visit. An ordinary eligible keypress skips the whole sequence directly to discovery; tapping the bare scene artwork provides the touch/pointer equivalent. Returning visits, direct links, reduced-motion, and data-saving preferences bypass the intro. Explicit `/story` replay follows the contract below. No visible playback or skip controls are added.

Story copy is live HTML, never burned into a bitmap. Generated plates demonstrate composition, not exact final typesetting. Each scene has one meaningful title; no fake facts, testimonials, or measured productivity claims are added.

### 5.1 Exact scene content and shared composition

The canonical words remain unchanged. All six use the same right-side text anchor. N2 and N4 retain their heading/support split.

| ID | Exact storyline | Art direction |
|---|---|---|
| N1 | Transform your AI workflow without needing years of experience. | Same glossy circuit brain, centered in the left art field; quiet cyan routes and sparse ember junctions. |
| N2 | More tools. More plugins. More confusion. How do we know what actually gets results? | Same brain and pose, expanding gently into hotter ember overload; three warning signs. Official GitHub and Figma marks are separate, unmodified ecosystem references. |
| N3 | Add more agents and coordination gets harder; poor handoffs can erode productivity gains. | Camera pulls back from that brain to reveal its cyborg cranial dome, then a second entity across a fragmented exchange. |
| N4 | Why Agent Lab? We study, test, select, and curate what your AI system actually needs. | Selected cyan signals feed a holographic panel projected from the cyborg palm, displaying the four-part montage. This composition appears only in N4. |
| N5 | Ever wondered how to build the website you saw on Pinterest? | A standalone tablet displays the new blue editorial webpage. Cyborg and hand are absent; a cyan connection foreshadows the network. |
| N6 | Find the tools you need now, or join us and help shape what comes next. | Pull back from the same tablet into undulating cyan network terrain. Five glowing glass orbs sit at connected nodes and suggest other sites or skills. |

N2 heading: “More tools. More plugins. More confusion.” Support: “How do we know what actually gets results?” N4 heading: “Why Agent Lab?” Support: “We study, test, select, and curate what your AI system actually needs.” Other scenes use the complete sentence as their title. N6 retains only Explore resources and Suggest a resource. N4 describes the remit, not a tested status for every resource.

### 5.2 Scene geometry and alignment

Desktop reference canvas 1440 × 810. No narrative header or header reservation. Art occupies approximately x=0–900; primary copy anchor x=922 (64% width), y=243 (30% height), right inset 64px, available width 454px. Keep this top-left anchor identical for all six scenes. Artwork must stay behind x=61% within the title's vertical band; use the existing page-tone protection field only if needed for contrast. Do not shift text to compensate for a busy image; reframe the art.

Use Geist Sans 42/47, weight 500, letter-spacing -0.035em for the shared narrative headline role at 1440. N2/N4 support is 22/30 with 24px separation. Do not change the title size scene by scene. N6 actions follow title by 28px, gap 12px, height at least 44px, 4px radius, wrapping if necessary. At 1024 use the same normalized right anchor with 32/37 heading and 18/26 support. The 32px art/copy separation is measured between actual lit geometry and glyph bounds, not image bounds.

For 768px and below, use the same stable text-first stack for every scene: 32px horizontal inset at 768, 20px at 390, 16px at 320. Heading 36/41 at 390, 30/35 at 320; support 18/26. Media follows by 24px as a contained landscape frame. N6 actions follow text before media. Do not resize or reposition the text from scene to scene, force portrait cropping, or move the text between corners. Keep both cyborgs, tablet connector and resource orbs visible. At short heights or text enlargement use normal document scrolling rather than clipping or tiny type.

### 5.3 Scene-specific responsive behavior

All scenes share the above layout. N1/N2 preserve the same full brain in the media field; N3 contains both entities and their transfer; N4 contains sorting path and tablet; N5 contains the tablet; N6 contains tablet, junction and at least three orb nodes. The network must not disappear in a mobile decorative crop. Do not introduce extra mobile headings, captions or controls. Browser review composites use this stacking rule for readability and are static layout specimens, not an implemented entrance.

### 5.4 Automatic entrance and whole-sequence bypass

An eligible first visit starts the 36-second sequence automatically. There are no visible playback, skip, stepping, progress, or helper controls. N1-N5 contain only the exact narrative typography and artwork; no Agent Lab name appears in the narrative corner. Official ecosystem marks occur within N2 artwork only. N6 holds still with Explore resources and Suggest a resource; it never automatically navigates away.

While focus is on the active story surface or page body, an unmodified printable character, Space, Enter, ArrowRight, ArrowLeft, or Escape skips **the entire sequence** to `/explore`. None of these keys advances or reverses one scene. Ignore key repeats, cancel all queued scene transitions/media, mark the visit preference, and navigate once without an exit animation. A single tap/click on bare scene artwork has the same effect. Exclude interactive descendants, text selection, and scroll/drag gestures; activating N6's links follows their actual destinations.

Preserve native activation on focused links/buttons, input/textarea/select/contenteditable behavior, IME composition, Tab/Shift+Tab, PageUp/PageDown/Home/End, modifier-only keys, modified shortcuts, and browser/OS/assistive-technology commands. No listener remains on discovery/workspace routes. Do not add a visible “press any key” caption to explain the behavior.

Timed scene changes do not move focus or issue live announcements. Keep a semantic, sequential representation of the six approved beats available to assistive technology without repeatedly replacing its reading target; visual timing must not dictate reading order. Normal route focus policy can operate after user-initiated navigation, but the story itself does not force focus onto its surface or each new scene.

If the document becomes hidden, stop motion/timers immediately. On return, show the static N6 invitation instead of resuming or restarting; no Resume/Play UI appears. Repeated visits in the session bypass the full sequence; unavailable persistent storage uses in-memory/session state without trapping the user.

Direct `/explore`, resource, suggestion, and workspace links bypass the intro. Explicit `/story` replays automatically under ordinary preferences. Under reduced-motion or data-saving preferences, explicit `/story` renders all six beats as one readable static document, with N6's final actions; it has no timed playback or global story-key listener. The existing discovery footer may link to this route. No new replay control is inserted into N1-N5.

### 5.5 N5 and the future real-output gate

The user explicitly requested a tablet showing something that appears to be a webpage. N4 uses the user-supplied website montage; N5/N6 use the new reference-inspired black/blue editorial webpage. These remain narrative visuals, not genuine resource results or Pinterest captures. N4 uses the supplied montage; N5/N6 share the new blue editorial webpage. No fabricated before/after comparison, measured improvement, source attribution or claim of a resource producing that site is permitted.

The real website transformation evidence slot remains missing and handoff-only. No empty evidence panels or disclaimers are inserted into the product. A future real example requires the capture contract in section 11 and separate placement review. Resource previews must continue to use genuine outputs or omit their media.

## 6. Public discovery: D1-D3

Discovery inherits the same deep-neutral canvas, Geist typography, cyan action token, and restrained material cues; the optional light variant uses the same semantic system. Its content is still; there is no cinematic transition, autoplay, parallax, hover tilt, expanding hover gallery, or mandatory masonry layout. Real outputs are the preferred imagery. When no output exists, use a plain text preview of the actual resource or a labelled type marker, not unrelated concept art masquerading as a result.

### 6.1 D1: discovery opening and editorial collection

Lead with the necessary heading **Explore resources**. No additional tagline is required. The primary action is the search input, labelled **Search resources**. Leave the placeholder empty unless a useful example is explicitly approved. Do not invent starter queries or collection labels merely to fill the composition.

At 1440: title occupies columns 1-8, search width 864px max and height 56px, 32px below the title. Search and category links sit above a 64px gap. Category links are plain text tabs: All, Prompts, Skills, Plugins & tools, MCPs, Agents & setups. A comprehension-help control can be added for MCPs only when its explanation is necessary and approved in that context; the vocabulary table below is internal guidance. The interface can use category-specific text without declaring MCP universally superior or equivalent to a skill.

Below the lead, use one editorial feature at columns 1-8 and two smaller supporting entries at columns 10-12, with the remaining column as whitespace. The main feature's actual output is 16:10; title and one-sentence use case sit below. The supporting entries have compact 4:3 output crops and plain text. No enclosing cards, elevation, or hover overlays. If only one eligible item exists, show one feature and leave deliberate breathing room; do not invent two fillers.

At 1024: feature spans five columns and supporting entries three, with a 24px gap. At 768: feature spans four columns, supporting list two; search is full-width. Below 768: all items become one column; the featured media is 16:10, smaller entries become 96px-wide image + text rows. At 320: those rows become full-width image above text if titles cannot fit legibly. Category controls wrap or use a labelled **Resource type** select; no clipped mystery tab strip.

### 6.2 D2: results and search

D2 is the focused browse/search composition. It can follow D1's lead or be reached directly with a query. Use a 56px-high search field up to 864px wide, followed 24px below by a plain horizontal filter row: Resource type (192px), Works with (224px), and More filters (144px), separated by 16px. Sort is right-aligned when there is room. Evidence sits inside More filters; do not expose a permanent dense filter sidebar. Results begin 32px below this row and use the full content grid.

Default order is task relevance returned by the real search service. Recently added is available only if actual catalog dates exist. If relevance ranking is unsupported, expose only truthful existing sort options; never invent a Recommended score. Applied filters are individually removable labelled controls. A guessed user intent may inform suggestions, but must not silently become a hard filter.

Each result is an open row with a 192 x 120 output/actual resource preview, a flexible text column, and a 44px secondary action with the accessible name **Add to setup**. This opens a target setup/agent/version choice; it is not a separate bookmark library. Item title 24/30; one-line outcome, then 14/21 metadata. Show at most resource type, compatibility, and evidence label on the collapsed row. Tags are text links, not six chips per item. Row vertical padding 24px and only one separator between distinct results. A resource that has no preview uses a 192px-wide actual text excerpt or type label, without fake illustration.

At 1024: search occupies full width up to 864px, the filter row remains below, preview 144 x 90, result title 22/28. At 768: **Filters** opens an accessible sheet with Apply / Clear; the result preview is 144 x 90 with text alongside. At this width keep the active filter summary as plain text beside Filters and move sort into the sheet if it cannot fit. At 390: preview is full width 16:10 only for visually useful outputs; compact resources use text first with the Add to setup control at the title's right. At 320 the Add to setup control moves to a labelled row action if it would squeeze the title. No horizontal page scrolling.

Search state is reflected in the URL so a shared discovery link bypasses the entrance and reproduces the query/filter state. Maintain scroll position and keyboard focus when returning from detail. Use a stable paginated **Show more** action when needed; no infinite scroll that makes the footer unreachable. Do not imply completeness with a fabricated total count.

### 6.3 D3: resource detail

The top block shows the actual resource name, a plain-language “what it helps with” description, resource type, author/source attribution, and an honest evidence status. At 1440, main content spans eight columns (866.67px); the action/metadata rail spans columns 10-12 (310px) with the intervening column reserved as whitespace. At 1024 use five and three columns. At 768 and below, move primary actions immediately after the title and before the media; the rest is one column.

Content order:

1. Title and intended use, followed by **Add to setup** and **View source** as applicable. View source opens the attributed original page; it is not a blanket assertion about its license.
2. Genuine output or faithful resource excerpt, accompanied only by necessary actual source/task metadata. Media uses contain for evidence and crop only for an editorial non-evidence preview.
3. **When to use it** and **What you need** in plain prose with short lists.
4. **How to try it**, with copyable actual prompt/configuration or a verified external instruction link. Do not promise one-click installation without a real supported installer.
5. **Versions and evidence**, in an accessible disclosure if longer than one screen. Include exact source/version, license if known, tested context if any, limitations, and provenance links.
6. A small related-resource list of at most three relevant items; omit rather than invent relevance.

Evidence labels are **Documented**, **Inspected**, **Tested**, **Measured**, and **No Lab test yet**, using the exact minimum-basis definitions in `design-handoff/CONTENT_AND_EVIDENCE.md`. These are scoped evidence descriptions, not decorative certifications or an automatic ranking ladder. A listed resource may be useful without a Lab test. Conceptual narrative images must not be promoted as frontend-resource output examples. A resource detail plate can specify the image position using an actual supplied relevant output; if none exists, use the resource's real text or leave that optional product region absent. Product UI does not need a decorative mock/demo label; the review wrapper and manifest identify the plate's status. Never present a row of universal quality scores or compare incomparable tasks.

On mobile, action buttons are 44px high, stacked only when required, and the main body remains in reading order. Copyable code/text is in a contained raised panel with Copy at the top-right outside the horizontal scrolling content. On copy success the label reads **Copied** for 2 seconds; failures read **Could not copy. Select the text and copy it manually.**

### 6.4 Public resource vocabulary

| Label | Plain-language explanation |
| --- | --- |
| Prompt | Instructions you give an AI for a particular task. |
| Skill | A reusable procedure that helps an AI handle a kind of task. |
| Tool | A capability an AI can use to get information or take an action. |
| Plugin | A package that adds capabilities to a supported application. |
| MCP | A standard connection that lets supported AI applications use tools and data. |
| Agent | An AI configured for a responsibility, with particular instructions and available capabilities. |
| Setup | A saved choice of agents, resources, versions, and settings. |
| Benchmark | A defined task and evaluation used to compare systems under stated conditions. A later capability, not an empty first-release navigation destination. |

These are internal vocabulary explanations, not automatically approved public supporting copy. Expose a definition only when necessary for a specific comprehension decision and approved in that context. Do not add permanent help paragraphs beside every result. Taxonomy remains a view over project-owned resource concepts. It is not authorization to collapse resource kinds or change backend contracts.

## 7. Private/team workspace: W1-W2

The workspace should feel like a useful work surface: saved setups, resource search, a focused configuration editor. It has no activity dashboard, chart area, decorative metrics, team feed, avatars, comments, invitations, or reporting module. Authentication, authorization, and persisted behavior must match the actual backend. A team context may be selected only if an existing supported context exists; do not invent a collaboration system for this design.

### 7.1 W1: saved setups

Header: **Saved setups**, a setup search field, and **New setup**. At 1440 content is centered at a maximum width of 1120px. The list begins 40px below the header. Each row has setup name, a one-line purpose, actual last-saved timestamp, and a labelled overflow button. Rows are 96px minimum, with 24px vertical spacing; no content cards. A lightweight list can omit the timestamp if unavailable rather than fabricate “just now.”

The overflow offers **Duplicate**, **Rename**, and **Remove setup**. These are distinct actions with clear names. Remove setup requires confirmation identifying the setup and only removes the selected saved setup. Duplicate creates a separate editable setup using the same pinned references where authorized; it does not silently copy secrets or launch execution.

At 1024/768 use the full content grid. At 390/320 search is full width below the title; New setup follows as a full-width primary action; row actions are at the right of the title and metadata flows below. Long names wrap up to two lines before truncation with the full name available on focus or detail.

Empty state: **No saved setups**. Action: New setup. No additional promotional empty-state paragraph is required. Search-empty state is distinct: **No setups match this search.** Action: Clear search. Neither uses a decorative robot image.

### 7.2 W2: setup editor

The editor is one page. At 1440 use three columns within the 12-column grid: agent selector in columns 1-2 (198.67px), editor in columns 3-9 (755.33px), and resource picker in columns 10-12 (310px), with 24px gaps between regions. At 1024 move the agent selector into a top row, then use a 608px editor, 24px gap, and 312px picker, totaling 944px. Search is fast and persistent within the editor; it does not open an unrelated marketplace route for every addition.

Top area: editable setup name; optional purpose; **Save**; a concise save state. The main editor presents one active agent at a time with a simple agent selector when more than one exists. Resource assignments are explicitly attached to the selected agent. Do not portray multiple agents as an unordered shared bag of resources. The composition area groups **Prompts**, **Skills**, **Plugins & tools**, **MCPs**, and **Model & settings**. These are open sections with a title, content, and Add action; they are not feature cards. Model/settings fields are edited directly; their section does not need a redundant Add action.

Each assigned resource row shows name, kind where useful, exact version/reference, a version pin control, Replace, and Remove. Use at most two visible metadata lines. Expanded detail reveals source and compatibility rather than showing hashes everywhere. The model/settings section uses a model select and only supported, labelled settings. Advanced settings are behind a disclosure; no arbitrary temperature defaults or provider-specific fields are invented.

For a multi-agent setup, each agent has a stable visible name and separate assignment state. An agent can use the same resource as another agent through a separate binding. Ordering is explicit only where it has actual semantics. Drag-and-drop is optional and can never be the only way to change order; provide Move up / Move down if ordering is supported.

At 768 and below: place the selected-agent control above the one-column editor. Resource search opens a separate full-height dialog labelled **Find resources**; it does not squeeze a third column beside the editor. At 390/320: selecting Add or Replace opens a full-height sheet with search at top, results below, and Close. Only one sheet is open at a time. Selected resource details appear before confirmation. The save area can be sticky at bottom, 64px + safe-area inset, with an equal spacer in content so it never covers fields or errors. When the keyboard is open, keep the focused field visible and allow the save area to return to normal flow if needed.

### 7.3 Workspace behavior details

| Action/state | Required behavior and copy |
| --- | --- |
| Add | Preview the chosen resource and target agent, then commit the assignment. Return focus to the added row. |
| Remove resource | Remove only that assignment from the current draft. Provide Undo in the row region or a brief confirmation. Do not delete the catalog resource. |
| Replace | Keep the old assignment until the new selection is confirmed. Preserve compatible settings only; show what will reset before confirmation. |
| Pin version | Default to an exact known resource revision. Show **Pinned to {version}**. Do not silently follow future releases. |
| New version available | Show **New version available** beside version controls. Let the user inspect and explicitly replace. No silent update. |
| Missing/unavailable version | Keep the saved reference visible, show **This version is unavailable. Your saved reference is preserved.**, and offer Replace or Remove. Do not silently substitute latest. |
| Dirty draft | Show **Unsaved changes** as text; Save enabled when valid. A route change offers Keep editing / Discard changes / Save, with Save available only when validation and persistence can complete. |
| Saving | Label **Saving…**; prevent duplicate submission while keeping the editor readable. |
| Saved | Show **Saved** only after confirmed persistence, with actual timestamp where supported. |
| Save error | **Your changes are still here. Try saving again.** Keep the draft and offer Try again. |
| Revision conflict | **This setup changed since you opened it. Your edits have been kept.** Offer Reload saved and Save as copy only where supported; never silently overwrite the newer revision. |
| Validation failure | Inline message beside the specific field/resource, error summary at top linking to each invalid item. Block false success. |
| Duplicate | Name starts **{original name} copy** and is editable. Announce the new setup, preserving pinned references and supported settings. |
| Later execution | Saving stores a configuration for later harness execution. No Run, Deploy, Test now, or execution-progress controls are introduced by this handoff. |

Resource addition is configuration, not permission to install software, authorize a connector, execute a tool, transmit secrets, or run a model. If connection setup is necessary, show its supported status and a factual next step. The website does not claim that saving a setup proves it can execute successfully.

## 8. Suggestion flow: C1

Use a dedicated calm page or modal route according to `IMPLEMENTATION_PLAN.md`, with a maximum form width of 640px. Title: **Suggest a resource**. No additional support line is required. Required fields are **Resource link** and **What does it help with?** Optional fields are **Name**, **Type, if you know it**, and **Example link**. Below the fields, show **Suggestions are reviewed before appearing publicly.** Do not request email by default. The submitted content is a suggestion, not a public listing or automatic endorsement.

At 1440/1024 the form is centered within the content region, aligned as one readable column with 24px field gaps and 8px label/helper spacing. At 768 it fills up to 640px. At 390/320 it fills the content width. Labels remain above controls; URL values can scroll inside their field. The textarea is 144px high initially and vertically resizable.

Submit label: **Send suggestion**. Pending: **Sending…**. Confirmed success: **Suggestion received** with **This confirms receipt, not selection or testing.** and Explore resources and Suggest another as clear separate choices. If the endpoint is not available, the future frontend must show a truthful unavailable state rather than a fake successful toast. The handoff itself submits nothing.

Errors: **Enter a full link to the resource.**; **Tell us what it helps with.**; or **Your suggestion was not sent. Your text is still here.** Show these inline, retain values, and announce the summary. Never publish pasted prompts, private setup details, or notes simply because the form was submitted.

## 9. Interaction states and accessibility

### 9.1 Component state matrix

| Component | Rest / hover | Focus / active | Loading / disabled | Empty / error / success |
| --- | --- | --- | --- | --- |
| Primary action | Cyan action fill; hover uses `action.hover`, press uses `action.active`, with the same `action.text`. | 2px focus outline + 2px page gap; active translates 1px down for 80ms. | Text pending state; disabled remains legible and has `disabled` semantics. No fake spinner-only button. | State text adjacent, never color alone. |
| Text link | Underline on hover; real inline prose links underlined at rest. | Same focus outline; no movement. | No disabled link pretending to work; use text with explanation. | External-source failures do not erase the URL. |
| Search/input | Raised surface, 1px control border, 12px horizontal inset. | Border 2px inset without layout shift; visible ring. | Loading results leaves entered text intact. | Clear accessible error text below; label remains visible. |
| Result row | Title underline and slight surface tint on hover; whole row is not a nest of competing links. | Title/link and Add to setup have separate tab stops. | Static skeleton shapes match final media and text lengths. | No matches gives Clear filters; retrieval error gives Try again. |
| Category tab | Plain text, 12px vertical padding. | Selected uses a 2px underline and current state semantics. | Do not disable unrelated categories during retrieval. | Count labels appear only if actual counts exist. |
| Add to setup | Labelled action or icon with the same accessible name according to available width. | Opens target setup, agent, and version selection; not a bookmark toggle. | Wait for the acknowledged assignment before reporting success. | Failure retains the selected target and old configuration; retry is explicit. |
| Version selector | Current exact version in clear text. | Accessible listbox/select; keyboard search where supported. | Disabled option includes why it is unavailable. | Missing version remains identifiable; no automatic substitution. |
| Modal/sheet | Opaque surface, clear title and Close. | Focus trap, Escape cancels/closes, including destructive confirmations, and returns focus to the trigger. Committing destruction always requires explicit affirmative activation. | Keep close available during retrieval. | Error appears within the dialog without dropping context. |
| Copy action | Copy label aligned outside content viewport. | Keyboard activation and visible focus. | Prevent repeat while actual write is pending if necessary. | Copied confirmation; selectable text fallback on failure. |
| Skeleton | Quiet blocks using raised/hover values; no fabricated text. | Not focusable, hidden from accessibility tree. | Static, no shimmer; region has meaningful loading status. | Replaced in place without shifting layout. |

Destructive actions use explicit verbs, outline/control text, and confirmation when the change is persisted. A danger color is unnecessary. Avoid disabling controls without explaining the unmet prerequisite near the control.

### 9.2 Navigation, keyboard, and reading order

Use landmarks, one H1 per route, logical heading levels, and source order matching the mobile reading order. Discovery/workspace use their ordinary Skip to content link; do not reintroduce a visible entrance-control bar through this pattern. Links navigate and buttons change state. Search forms submit with Enter. Do not put a button inside a linked result row. All controls have visible names; icon-only controls have accessible labels and tooltips.

Minimum interactive target is 44 x 44px; close neighbors have at least 8px separation. A small visible icon may sit within the full target. Focus must remain visible when sticky headers/save bars are present. Menus, tabs, dialogs, disclosures, and comboboxes use their correct interaction pattern rather than a hand-built click-only imitation.

At 200% zoom, content reflows; at 400% zoom and a 1280px browser viewport, the resulting 320px layout remains usable without two-dimensional page scrolling. Long titles, translated copy, and browser-default increased font sizes cannot overlap actions. At high contrast/forced colors, keep real borders, outlines, and text state cues.

Concept artwork that adds nothing beyond adjacent copy is decorative with empty alt text. Where the composition conveys information, use concise descriptions such as **Two artificial figures exchange fragments that do not align. Concept illustration.** Real evidence alt text names the page/task and visible comparison state without interpreting superiority. Provide an adjacent text explanation of differences; alt text alone is not an evaluation.

## 10. Motion specification and asset prerequisites

Motion connects scenes in the narrative; discovery and workspace use only immediate state feedback. This handoff specifies future motion and implements none. A still image is a poster, not a rigged 3D asset, depth map, animation, or video. The frontend must not invent a WebGL world, morph, or camera path from a bitmap during implementation.

### 10.1 Shared timeline and keyframes

The approximately 36-second entrance remains N1 6s, N2 6s, N3 7s, N4 6s, N5 6s, N6 5s including transitions; final N6 holds. No visible playback, step, Enter or Skip buttons. Existing immediate whole-sequence bypass and reduced-motion behavior remain binding.

The requested visual target is an authored continuous camera journey. A poster dissolve is a fallback only; it does not satisfy the continuous reveal by itself. Use one source scene rendered to a finite video or a prepared real-time scene. Do not synthesize geometry from these PNGs in the frontend. See `design-handoff/NARRATIVE_CONTINUITY.md` for object IDs, screen-space targets, camera intervals and node semantics.

| Interval | Required visual change | Continuity rule |
|---|---|---|
| 4.8–7.2s | N1 brain expands to overload, emission warms and warning glyphs appear. | Same brain mesh, center and orientation; 1.00→1.08 scale; no dissolve to a different object. |
| 10.4–14s | Dolly back to reveal brain within cyborg crown, then second entity. | Brain is already parented inside the head; no late insertion or visible mesh swap. |
| 17.2–20.8s | Track with the fragmented exchange into the sorting path and tablet. | Primary cyborg recedes left; selected paths physically meet tablet edge. |
| 23.6–26.4s | Approach the tablet while sorting plane recedes. | Intentional N4→N5 change: the holographic montage resolves to the standalone tablet and new blue webpage. Preserve continuous camera motion; cyborg/palm leaves the frame. |
| 29.2–33.4s | Pull back to reveal network terrain and resource orbs. | Tablet remains continuously visible; connector terminates at an actual mesh junction; orbs are anchored to other junctions. |
| 33.4s onward | Settle at N6; final actions available. | No loop, bouncing orbs, perpetual scan, autoplay navigation or extra interface. |

Copy stays screen-anchored, separate from the camera. Prefer zero position motion. Optional vertical drift is at most 6px over 2s, with one shared easing curve; never change quadrants. Use at most 250ms crossfade for phrase replacement, fixed anchor and size, no character effects. Readable copy is fully opaque during holds. Camera transitions use smooth start/end velocity, e.g. cubic-bezier(.45,0,.2,1); decelerate before final N6.

### 10.2 Required motion source for the continuous target

Supply one authored source scene or pre-rendered finite video with matching posters. Required named objects: `brain_main`, `cyborg_primary`, `cyborg_secondary`, `signal_fragments`, `selection_gate`, `tablet_main`, `tablet_screen`, `tablet_connector`, `network_terrain`, `resource_orb_01` through `resource_orb_05`. Preserve a single brain asset, a single tablet mesh and screen texture, camera transforms/keyframes, light settings, scale and axes. If real-time delivery is chosen, export optimized glTF/GLB plus authored clips and textures; static geometry alone is insufficient. If video is chosen, supply reviewed WebM/MP4 renditions, exact 36s duration, color profile, mobile-safe framing and still fallback.

These motion source files are not delivered by this design-only task. The six new PNGs are composition/material targets and static fallbacks after review; they do not prove exact animated identity continuity. Resolve still-to-still geometry differences in source production before calling the animation complete. Do not install engines or implement the website in this handoff.

### 10.3 Ordinary interface motion

Hover/focus feedback: 120ms, no glowing edge or object motion. Active press: 1px translation for 80ms. Dialog entry: opacity plus <=8px translate over 160ms; exit 120ms. Search results remain still, with optional 120ms replacement fade that does not delay keyboard use. Loading skeletons are static. No card tilt, autoplay feed, floating rows, parallax preview, or cinematic route transition in discovery/workspace.

### 10.4 Reduced motion and constrained delivery

For `prefers-reduced-motion: reduce` or a data-saving preference: send an ordinary first visit directly to discovery. Explicit `/story` preserves the user's replay intent as a static, readable six-beat document with the final two actions. Disable autoplay, transforms, camera motion, parallax, morphing, and animated scrubbing. Do not add playback controls or a global key handler to that static document.

For slow networks without an explicit data-saving preference, use the lightweight still-poster track and keep bypass available from the first frame. Never block keyboard/tap bypass on images, fonts, a model, or a remote library. If media fails, the approved copy remains on the deep canvas. If JavaScript fails, use a readable document-flow story with ordinary final links; no invisible timed gate prevents reaching discovery.

## 11. Asset placement, provenance, and evidence requirements

### 11.1 Manifest and revision crosswalk

The current package uses six new text-free N1–N6 masters in `design-handoff/narrative-v3/` plus the six unchanged utility plates D1–D3/W1–W2/C1 in `visuals-v2/`. Their older folder name does not make them obsolete; each is explicitly retained in the v3 manifest. The old v2 narrative plates and A1–A6 masters are superseded. Twelve scenes are reviewable in the HTML gallery; narrative text and official marks are separate DOM overlays so exact copy and alignment are inspectable.

### 11.2 Placement, safe areas, and motion role

Every narrative master is landscape with art primarily left and a quiet right field. Live copy uses the fixed anchor from section 5. On small screens contain the entire source below text. N6's low network may run under the CTA region only if a page-tone scrim preserves text/control contrast; never place bright nodes directly behind glyphs. All conceptual media is non-interactive; the final resource links carry navigation. Orbs are metaphorical resource nodes, not ranked entries, live metrics or a graph editor. The handoff defines five orb nodes with mini site/code glyphs as proposed semantic cues, no fake brands or arbitrary labels.

N2 includes the official GitHub and Figma marks as separate unmodified assets. Place GitHub at normalized (0.075,0.12), Figma at (0.50,0.12), each within a calm solid dark backplate and with required clear space, outside the title field. Avoid attributing warnings to those specific products. No other brand is implied. Refer to `brand-assets/README.md` for sources and usage conditions. Fonts and existing resource specimens retain their provenance.

### 11.3 Evidence capture contract

A publication-ready comparison must include all of the following:

1. A task identifier and original request, intended audience, acceptance criteria, permission to publish, and the relevant source/artifact versions.
2. Baseline output and final output as saved source or immutable artifacts. The baseline must be a genuine usable baseline, not intentionally sabotaged to make the method look better.
3. Model/provider/version where available; harness; prompt/skill/tool/plugin/MCP revisions; settings; and which agent received which resource. Do not claim access to hidden reasoning.
4. A change record separating information selected, its representation, recipient, retrieval, and execution scheduling where practical. If multiple factors change, describe the bundle without single-factor causal claims.
5. Before and after screenshots at identical viewports, capture scale, content state, fonts, and loading completion: at minimum 1440 x 1000 and 390 x 844, plus the full-page originals if needed. Preserve timestamps and file hashes.
6. Evaluation notes tied to criteria: visual hierarchy, mobile behavior, accessibility checks, broken links, or task completion as relevant. Include failures, missing measurements, and human judgments labelled as judgments.
7. Actual cost/latency if measured, with a stated measurement boundary. Omit rather than estimate without basis.
8. A reviewer-approved public summary, source/reproduction links where permitted, and caveats. A screenshot comparison demonstrates captured appearance, not universal productivity gains or benchmark superiority.

Until that bundle exists, N5 uses the exact Pinterest question without a visible evidence placeholder. The future capture slot is recorded only in the handoff manifest. Resource cards can still show genuine outputs with limited claims when their provenance supports those limited claims. Design approval, rights approval, and result-claim approval are separate statuses.

## 12. Performance targets and future validation

These are implementation targets, not results measured in this handoff.

| Area | Target / budget |
| --- | --- |
| Core Web Vitals | LCP <2.5s, INP <200ms, CLS <0.1 at the 75th percentile after launch measurement. |
| First-view narrative art | <=220KB mobile, <=400KB desktop transfer per chosen derivative; use a smaller acceptable still if quality/budget conflict. |
| Initial discovery route | <=350KB image transfer above the fold; no narrative art prefetch on a direct link. |
| Font transfer | <=160KB compressed above fold; preload one necessary font file only. Verify actual font export budget. |
| Poster-only entrance enhancement | <=60KB gzip incremental script target beyond shared navigation; no 3D engine or video player for that track. |
| Optional prepared 3D/video | Select and measure only after motion assets and delivery track are approved. Load only on an eligible narrative route with a poster-first path; bypass never waits for the engine. Discovery must not import the cinematic engine. Record the actual compressed scene/clip/engine budget before implementation acceptance. |
| Search responsiveness | Immediate input echo; debounce remote query 200ms where needed; cancel stale responses; show retained results while loading. |
| Layout stability | Declare media dimensions/aspect ratio; reserve loading-result space; do not shift focused controls. |

Do not optimize an image by making its subject or an actual output unreadable. If targets cannot be met, reduce visual complexity before reducing legibility. The future implementation must measure representative mobile hardware/network conditions and actual built bundles. An image plate or static review board cannot establish these results.

## 13. Review and implementation acceptance matrix

A completed handoff is not a completed website. The acceptance checks below are requirements for the later frontend work and the human design decision.

| Check | Handoff requirement | Later implementation verification |
| --- | --- | --- |
| Scope | Plan, specification, separate plates, asset provenance; no frontend implementation. | Implement only after the user authorizes that work. |
| Visual approval | Each asset and direction has an explicit status; no self-declared user approval. | Use approved files only; keep pending candidates out of release assets. |
| Narrative completeness | N1-N6 tell promise, overload, handoff, selection, output, invitation. | Walk through all scenes at five specified widths and short viewport height. |
| Evidence honesty | N5 exact Pinterest question; missing real-output capture recorded in handoff only; no fabricated before/after. | Show only verified artifacts with provenance and proportionate claims. |
| Entrance escape | Automatic first visit, whole-sequence key/tap bypass, no visible story controls, explicit replay, and bypass states specified. | Test first visit, repeat visit, direct detail link, back button, browser shortcuts, focus, IME, and no-JS fallback. |
| Visual hierarchy | Typeface, spacing, grids, coherent proposed deep-neutral palette with controlled narrative color progression, distinct calm/public and private surfaces. | Compare screenshots against approved plates; fix layout, not text via image overlays. |
| Responsive behavior | Explicit 1440/1024/768/390/320 behavior and per-scene fallbacks. | No overlap, clipped control, or horizontal page overflow at those widths or 200/400% zoom. |
| State completeness | Rest, hover, focus, active, disabled, loading, empty, error, saved, stale version specified. | Use real backend states and failure paths; no success before persistence. |
| Accessibility | Semantic structure, 44px targets, focus, captions, reduced motion, contrast values. | Automated checks plus keyboard, screen-reader, theme, forced-color, zoom, and motion tests. |
| Workspace integrity | Agent-specific assignments, exact pins, remove/swap/duplicate/save behavior. | Verify correct target agent, existing saved configuration preservation, and draft recovery on failure. |
| Publication | No stock/reference image licensing assumed; generated concepts separated from outputs. | Check production asset rights, notices, and claims. |
| Performance | Explicit targets and constrained-delivery fallbacks. | Measure actual frontend; do not claim pass from this document. |

Design-specific inspection also checks: no invented logo; no fake testimonials or scores; no all-purpose boxed-card grid; no decorative version stamp; no arbitrary gradient or unmotivated glow; consistent shared-world rhythm rather than unrelated posters; no unreadable text over art; no eyebrow on every section; no em-dash or en-dash separator in visible copy; no missing mobile order; no oversized navigation; N6 actions remain usable without compromising the approved copy; no inaccessible keyboard capture; no implicit execution when saving.

## 14. Precedence and change handling

If an image plate contradicts this specification's dimensions, exact copy, accessible behavior, evidence boundary, or approval status, the written specification wins. A human-approved visual revision can update both the relevant plate and this document together. Do not silently resolve a contradiction by inventing a new component, color, animation, resource claim, or architecture.

Exact visible copy, resource definitions, evidence labels, and submission fields in `design-handoff/CONTENT_AND_EVIDENCE.md` are authoritative if sample text diverges. The route and implementation sequence in `IMPLEMENTATION_PLAN.md` govern delivery order. `ASSET_MANIFEST.md` governs actual filenames, motion prerequisites, and approval state. `REFERENCE_BOARD.md` governs what was observed across static, interactive, video, 3D, and Pinterest references and what can be adapted. This specification governs layout and interaction. None of these files turns provisional research into accepted backend architecture.
