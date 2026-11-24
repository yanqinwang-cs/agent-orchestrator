# Agent Lab website implementation plan

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

Date: 6 October 2026. Revision: v4, incorporating the user's visual-direction corrections. Deliverable: design handoff only. This revises the existing plan while retaining useful routes, setup behaviour, and acceptance boundaries. It does not report a built website, a deployed backend, completed experiments, or human approval of the proposed palette or visual artefacts.

## Read this first

Build one coherent identity across three experiences: a cinematic project vision and pitch, calm public discovery, and a minimal private workspace for saved setups. The homepage story introduces why Agent Lab should exist; it is not a catalog landing page in disguise. The public audience is students, vibe coders, casual AI users, and technically curious non-experts. Discovery leads with what a resource helps someone make or do. Explain technical details only when they affect adoption.

The entrance should earn curiosity. Discovery should help someone decide. The workspace should let them prepare and preserve a setup. None of these requires a dashboard, a workflow graph, a universal agent architecture, a leaderboard with invented results, or an automatic installer.

Authority order for implementation:

1. The current user brief and [AGENTS.md](AGENTS.md).
2. This plan for journeys, scope, behaviour, content gates, and acceptance criteria.
3. [DESIGN_SPEC.md](DESIGN_SPEC.md) for precise proposed visual tokens, geometry, motion, and responsive rules.
4. [CONTENT_AND_EVIDENCE.md](design-handoff/CONTENT_AND_EVIDENCE.md) for exact copy, meaning of labels, and evidence rules.
5. [ASSET_MANIFEST.md](ASSET_MANIFEST.md) for actual asset paths, provenance, permitted placement, prerequisites, and review status.
6. Generated section plates for composition and atmosphere. Their pictured text, resource data, output examples, and small UI details are not authoritative.

Read [REFERENCE_BOARD.md](REFERENCE_BOARD.md) alongside the specification for the static, interactive, 3D, motion/video, and supplied Pinterest/image references behind the proposal. The previous version remains in the archive for comparison; new narrative work is under `narrative-v3/`, with six utility plates retained in `visuals-v2/` at the manifest's exact paths.

When two documents conflict, preserve the user's exact six-beat narrative and evidence truth, then resolve the conflict before coding. Do not silently reinterpret a concept image as a product screenshot. Do not carry old marketplace or orchestration scope into this build merely because historical files describe it. Prose in this plan explains implementation requirements; it is not permission to add those words as product captions or decoration.

## Visual revision and continuity

The user confirmed the Lavish corrections: remove the top-left narrative name, use one right-side text anchor, replace strand sculpture with luminous circuits, keep the same brain through overload and cyborg reveal, follow selected signals to a webpage-bearing tablet, then pull back to reveal that tablet connected to rolling cyan network terrain and glowing resource orbs. Use official GitHub/Figma ecosystem marks in N2, separately from generated art.

The current v3 set is six new narrative masters plus six unchanged practical surface plates. See `design-handoff/NARRATIVE_CONTINUITY.md` for the continuous camera/object contract and `design-handoff/CORRECTIONS_v3.md` for the feedback receipt. User approval of this direction authorizes revision; it does not automatically approve every newly generated pixel. Keep final asset approval explicit.

## Handoff inventory and approval boundary

The handoff contains twelve independently inspectable horizontal visual plates, one for each principal section or product surface. Supporting states below reuse those surfaces rather than introducing unrelated visual systems. The design specification is the dimensional source of truth for mobile and interaction states.

| Plate | Surface | Job | Source of visible content |
|---|---|---|---|
| N1 | Entrance promise | Make the value understandable immediately | Approved brief wording; concept artwork |
| N2 | Tool overload | Recognise a familiar source of confusion | Editorial copy; metaphorical brain artwork |
| N3 | Handoff friction | Show why more agents can create coordination work | Qualified copy; metaphorical communication artwork |
| N4 | Study, test, select, curate | Explain Agent Lab's method | Project intent; organised-signal concept artwork |
| N5 | Website aspiration | Connect the pitch to a website the visitor wants to create | Exact Pinterest question; handoff-only evidence slot reserved for later real before/after artefacts |
| N6 | Invitation | Offer exploration or a suggestion | Functional copy and links |
| D1 | Explore landing | Orient visitors around useful outcomes | Curated published catalog content |
| D2 | Search and browse results | Let visitors scan and narrow choices | Search results with evidence states |
| D3 | Resource detail | Explain use, outputs, prerequisites, and provenance | Selected resource version and linked evidence |
| W1 | Saved setups | Find, open, duplicate, and remove saved setups | Private records the user can access |
| W2 | Setup editor | Search, add, remove, swap, pin, and save | Agent-specific resource bindings and settings |
| C1 | Suggest resource | Collect a useful suggestion without implying publication | User input and submission receipt |

An agent selecting an image for this handoff is design selection, not human approval. Consult the manifest's explicit status fields. Move an item into a genuinely approved production set only after the recorded owner approves that exact revision. Do not record approval in anticipation of a later review.

The user confirmed that no real before/after example exists yet and requested an evidence slot. That slot belongs to the handoff and its manifest, not the public page. N5 publicly uses the exact approved question, “Ever wondered how to build the website you saw on Pinterest?”, with clean typography and the continuing visual world, without action controls. Future real examples or links require a separately reviewed placement. It must not show blank evidence rectangles, “Demo preview,” “Illustrative sample,” placeholder explanations, or fabricated transformation screenshots. Real before/after evidence is a later publishing dependency, not an unfinished design task.

## Product boundaries

### Include

- Automatic first-visit cinematic/editorial entrance with immediate keyboard/tap bypass and a persistent replay link. No visible playback or scene-navigation controls.
- Searchable discovery of prompts, skills, plugins/tools, MCP connectors, agents, and saved configuration examples.
- Plain descriptions, genuine output examples where available, prerequisites, source/version links, and clearly qualified evidence.
- Minimal submission form for suggestions; receipt and recoverable errors.
- Private search, saved setups, configuration editing, resource replacement, version pins, duplication, removal, and persistence feedback.
- Responsive and accessible states, proposed deep-theme tokens, keyboard access, and reduced motion. The light discovery/workspace theme is an optional future candidate requiring explicit selection, not mandatory first-release scope.
- A content boundary capable of displaying later benchmark evidence without pretending it exists today.

### Defer

- Harness execution, run scheduling, runtime graphs, logs consoles, benchmark calculation, global rankings, leaderboards, performance analytics, billing, and pricing plans.
- Team chat, comments, presence, activity feeds, invitation flows, role management, and realtime co-editing.
- Universal installation, secret entry, tool execution, model calls, automatic resource updates, or automatic publication of suggestions.
- A new backend schema or framework migration based only on the needs of these mockups.
- A new logo. Use the existing project name as text until a separately approved identity exists.

The word “team” establishes a scope for private resources, not a requirement to build collaboration software. Use an existing workspace boundary and membership system if the implementation already has one. If only a single-user backend is available, implement that truthful scope and do not present inactive team controls.

## Proposed routes and navigation

Route names below are a design recommendation for a new website. Before implementation, inspect existing routing and preserve established public links where practical. This handoff does not authorize renaming existing routes unseen.

| Route | Default state | Navigation and persistence |
|---|---|---|
| `/` | Entrance N1 for an eligible first visit; otherwise Explore | A server-safe routing fallback must remain usable without storage or animation |
| `/story` | Explicit entrance replay; static six-beat document under reduced-motion or save-data | Available from the footer as “Our approach”; must not reset saved visit preference |
| `/explore` | D1 with outcome search | Public entry point; never invokes the entrance |
| `/explore?q=…&type=…&…` | D2 results | Query, explicit filters, and sort in the URL; browser Back restores prior state and scroll |
| `/resources/:slug` | D3 selected current published version | Optional `version` query selects a specific visible version; direct links bypass the entrance |
| `/suggest` | C1 suggestion form | Direct links bypass the entrance; receipt remains on this route |
| `/workspace` | W1 accessible saved setups | Authentication boundary; no cinematic entrance before or after sign-in |
| `/workspace/setups/:id` | W2 selected setup revision | Authorise access before rendering private content; dirty edits never leak into public previews |

Discovery desktop navigation: project name, Explore resources, Suggest a resource, and Workspace. Show the current page with text weight and an underline or structural marker, not colour alone. Use the same labels for the same major CTA intents. The cinematic entrance shows only the project name and approved scene text/art until N6's two final CTAs. Do not show Play story, Pause, Previous, Next, Enter, Skip, or a duplicate N1 Explore action. At widths where discovery navigation cannot fit on one line, collapse it into the menu rather than wrap.

On small discovery/workspace screens, retain the project name and one accessible menu trigger. The menu is a compact disclosure containing the same destinations. No fullscreen animated overlay is necessary. After following a link, close it and move focus appropriately. The cinematic entrance has no menu requirement; a tap on bare scene artwork immediately bypasses it.

## Entrance behaviour contract

### Eligibility and persistence

- Never delay the initial usable screen to ask a remote service whether to show the entrance.
- Mark a session-level start once the first scene is visible so a same-session revisit does not restart the sequence. Store a small versioned persistent seen preference after skip, completion, or settling at the final invitation. Remember the visit on that browser until cleared; story updates do not silently reset it.
- If persistent storage is unavailable, proceed using session/in-memory state. Do not show a modal, retry loop, or repeated entrance within the visit.
- A direct `/explore`, resource, suggestion, or workspace URL bypasses the entrance regardless of stored state.
- Explicit `/story` replay ignores the seen preference for that navigation only when motion/data preferences permit playback.
- Under `prefers-reduced-motion` or save-data, `/` resolves directly to discovery. Explicit `/story` renders a static, naturally scrollable six-beat document with the same approved copy, no autoplay, and no scene keyboard/tap interceptor. It must not silently start playback later.
- When media fails, the copy and navigation remain usable on the theme surface. A blank canvas is not a loading state.

### Pacing and controls

An eligible first visit automatically plays the six scenes over approximately 36 seconds: N1 6s, N2 6s, N3 7s, N4 6s, N5 6s, N6 5s. Preserve readable holds and complete copy; do not shorten the text to meet timing. The sequence ends on a stationary N6 with Explore resources and Suggest a resource, never by automatically navigating away.

There are no visible playback or scene-navigation controls. N1 contains the name, approved promise and art only. An eligible keyboard press skips the entire sequence immediately to discovery; it never advances one scene. A tap/click on bare scene artwork provides the same exit on touch/pointer devices. N6 retains its two real links and their normal activation.

Keyboard/tap behaviour must preserve native access:

- An unmodified printable key, Space, Enter, Escape, ArrowRight, or ArrowLeft on the scene surface or page body skips the whole entrance. Neither arrow steps through scenes or rewinds the story.
- Native activation wins on links and buttons, including the final CTAs. Input, textarea, select, editable content, and text selection are excluded. Ignore IME composition and repeated keydown events.
- Tab and Shift+Tab preserve normal focus navigation. Page Up/Down, Home/End, ArrowUp/Down, modifier-only keys, modified shortcuts, browser/OS commands, and assistive-technology combinations are not intercepted.
- A pointer/touch exit fires only for a deliberate tap on bare scene art/background. A child link/control, text selection, scroll gesture, or pointer drag does not trigger it.
- Do not trap focus, steal browser focus, or advance content because focus moved. A focused final CTA remains stable. Remove entrance listeners on route exit and omit them entirely from discovery, workspace, and static `/story`.
- On skip, stop media immediately, clear queued transitions, navigate once to `/explore`, and focus its heading. Do not delay with an exit animation.
- If the document becomes hidden, stop animation and timers. On return, settle immediately on static N6; do not resume, catch up, restart, or introduce a resume button. Record the entrance as seen.
- Reduced-motion/save-data visitors bypass the timed entrance; explicit replay provides the static document described above. The first scene must not flash before that preference is applied.

Do not require hover, a wheel gesture, sound, or drag to leave. No autoplay audio, scroll hijacking, or pinned horizontal mobile traversal. Planned 3D/layered movement needs the actual source assets listed below. The handoff board remains static; its manual plate selectors are review-document controls, not proposed website controls.

### Section-by-section build brief

| Section | Content and hierarchy | Visual and layout requirement | Interaction and responsive requirement | Acceptance |
|---|---|---|---|---|
| N1: Promise | “Transform your AI workflow without needing years of experience.” | Same glossy circuit brain, centered in the left art field; quiet cyan routes and sparse ember junctions. | Fixed right-side copy; text-first mobile stack; no playback controls. Immediate whole-sequence bypass. | Use the same authored geometry across adjacent scenes, not disconnected posters. |
| N2: Overload | “More tools. More plugins. More confusion. How do we know what actually gets results?” | Same brain and pose, expanding gently into hotter ember overload; three warning signs. Official GitHub and Figma marks are separate, unmodified ecosystem references. | Fixed right-side copy; text-first mobile stack; no playback controls. Immediate whole-sequence bypass. | Use the same authored geometry across adjacent scenes, not disconnected posters. |
| N3: Handoffs | “Add more agents and coordination gets harder; poor handoffs can erode productivity gains.” | Camera pulls back from that brain to reveal its cyborg cranial dome, then a second entity across a fragmented exchange. | Fixed right-side copy; text-first mobile stack; no playback controls. Immediate whole-sequence bypass. | Use the same authored geometry across adjacent scenes, not disconnected posters. |
| N4: Why Agent Lab | “Why Agent Lab? We study, test, select, and curate what your AI system actually needs.” | Selected cyan signals reach the cyborg palm projection, showing the supplied four-part montage in N4 only. | Fixed right-side copy; text-first mobile stack; no playback controls. Immediate whole-sequence bypass. | Conceptual webpage is permitted; genuine before/after evidence remains absent. |
| N5: Website aspiration | “Ever wondered how to build the website you saw on Pinterest?” | The standalone tablet and new black/blue editorial webpage become the focus. No cyborg or hand; a cyan connection foreshadows the network. | Fixed right-side copy; text-first mobile stack; no playback controls. Immediate whole-sequence bypass. | Conceptual webpage is permitted; genuine before/after evidence remains absent. |
| N6: Invitation | “Find the tools you need now, or join us and help shape what comes next.” | Pull back from the same tablet into undulating cyan network terrain. Five glowing glass orbs sit at connected nodes and suggest other sites or skills. | Fixed right-side copy; text-first mobile stack; no playback controls. Explore resources and Suggest a resource only. | Conceptual webpage is permitted; genuine before/after evidence remains absent. |

The exact six beats above and in [CONTENT_AND_EVIDENCE.md](design-handoff/CONTENT_AND_EVIDENCE.md) are canonical. Line breaks may express hierarchy without changing words. Do not add supporting lines, decorative captions, numbered micro-labels, or generic feature badges. Populating N5 with a real example later requires an evidence record and reviewed placement, not an automatic substitution by the frontend.

## Public discovery

### D1: Explore landing

Above the fold, show the necessary heading “Explore resources” and a visibly labelled search field. Task-oriented starting links can appear only when they describe actual reviewed collections or supported catalog queries. Do not invent collection names or populate arbitrary entry prompts merely to complete a composition.

Use one prominent editorial feature when real evidence exists, followed by a varied set of resource features. Resource imagery should show what users get: screenshots, a short output excerpt, a playable preview, or a source-attributed result. An item without visual output uses its plain title and useful description rather than decorative AI art. No Pinterest masonry clone, repeated equal boxed cards, star-count leaderboard, or animated feed.

Kinds remain available as a small browse control: All, Prompts, Skills, Plugins & tools, MCPs, Agents & setups. These are necessary navigation labels. Any additional explanation must serve a real comprehension need and be approved as supporting copy; do not add generic feature labels or decorative technical captions. MCP compatibility remains resource-specific.

Discovery has no entrance effects: no ambient loops, mouse following, hover tilt, scroll scrubbing, or text scrambling. Use motion only for an explicit change of state. The layout, typography, image grade, and restrained accent preserve identity.

**Build acceptance:** the search label is visible; browse links work without cinematic code loading; resources contain real metadata; any internal fixture is identified in review metadata and excluded from public publishing. Do not put “Illustrative sample,” “Demo preview,” or similar filler onto product surfaces.

### D2: Results and browsing

Use a readable editorial list or mixed-width feature grouping, not a package-registry wall of metadata. Each result exposes:

1. Resource title and kind.
2. A short outcome-focused sentence.
3. An output preview if one is real and relevant.
4. Where it works and any material setup prerequisite.
5. A compact evidence label and source attribution.
6. A clear title link to detail; saving is secondary.

Start with type and “Works with” filters. Add evidence filter in a More filters disclosure. Avoid a permanent dense filter sidebar. Search terms and explicit filters persist in the URL. Display applied filters as individually removable controls with readable labels. Do not silently convert guessed intent into hard filters.

Default order is task relevance as supplied by the search service, not popularity presented as quality. “Recently added” is an optional alternative if the catalog supports real dates. No unsupported “best,” “verified,” or percentage match label. Group versions under one resource identity; show fork lineage when relevant, rather than repeating mirrors as separate endorsements.

Loading uses fixed-size placeholders matching the result rhythm, without shimmering if reduced motion is on. Empty results keep the query visible, offer “Clear filters,” and link to Suggest. A search service failure preserves the query and filters and offers Retry. If lexical search is an actual supported fallback, label it; do not simulate semantic capability in the frontend.

On mobile, filters open in a bottom sheet or simple dialog with a labelled Apply action, clear state, a close control, and restored focus. Results remain in document order with readable output previews. Avoid nested horizontal carousels.

**Build acceptance:** query Back/Forward restoration works; no-results and service-error states differ; fast queries cannot allow an old response to replace a newer one; keyboard focus survives filter updates; result metadata does not imply tests that were never run.

### D3: Resource detail

The initial viewport answers “What does it do?”, “What could I make with it?”, and “Will it work here?” A resource page has a leading title/outcome description, real output or useful text example, selected version, primary action, and compact prerequisites. Reveal deeper source and evaluation details below or by disclosure.

| Detail area | Required content | Action and states |
|---|---|---|
| Overview | Kind, title, specific use, material limitations, real output preview when available | Source-external link clearly identified; no forced installation |
| Example | Actual input/task and output, provenance, necessary attribution/alt text | Open full output; no concept art or generated placeholder presented as this resource's output |
| Use it | What the user needs, supported host/target, steps appropriate to this resource | Copy prompt for a prompt; View source for source resources; Add to setup when authenticated |
| Version | Human-readable version plus stable source identity where supplied | A version change updates content, prerequisites, evidence, and save target together |
| Evidence | Documented, inspected, tested, or measured, with exact scope | Open methodology/result when it exists; otherwise “No Lab test yet” |
| Provenance | Creator/source, source path or URL, licence, retrieved/checked date, lineage if relevant | Missing licence/source is explicit; do not infer rights from public availability |

One primary action per resource type. Do not use “Install” if the site only links to instructions. Adding to a setup records a chosen version; it does not install code, connect an account, or execute the resource. If signed out, preserve the pending resource/version through authentication and require a visible target setup/agent selection before saving.

The previous A1 concept-image resource specimen is retired. A cyborg, brain, or signal scene must not become the apparent result of a frontend-design prompt, skill, plugin, MCP, or setup. D3 uses an actual resource and its real source metadata. If a genuine output is absent, omit the output preview and let the real instructions/metadata carry the detail page. Review provenance belongs outside the product composition; do not solve missing content with public “demo” badges or invented resource titles.

Do not combine incompatible measurements into one score. Later benchmark panels must name the task, model/provider/version where available, harness, resource versions, evaluation method, cost/latency scope, date, and failure conditions. Hide the panel until evidence exists; no empty leaderboard navigation at launch.

**Build acceptance:** direct version links render the same version on refresh; unavailable versions retain an explanatory state and source identity; output provenance is no more than one disclosure away; no stale evidence persists after switching versions; unsafe source content is rendered inert.

## Private workspace

### W1: Saved setups

The page is a working shelf: heading, search, New setup, and a compact list of saved setups. Each row contains the name, concise purpose when provided, number or short summary of included agents/resources if derived from real data, and saved/modified state. Do not add graphs, charts, activity feeds, “productivity scores,” or decorative totals.

Primary row action: Open. Secondary menu: Duplicate, Rename, Remove. Duplication creates a new private draft with an editable copy name, retaining exact pinned resource versions, per-agent bindings, model/settings snapshots, and the source setup revision reference where supported. It must not silently resolve every resource to the latest version.

Remove affects the selected saved setup only, never the public catalog or installed local resources. Provide a clear confirmation naming the setup for permanent removal; if the backend supports a reversible trash operation, show Undo using the actual restore capability. Do not offer Undo when the action cannot be reversed.

Empty state: “No saved setups,” with New setup and Explore resources. Search-empty state is distinct: “No setups match this search.” A read failure preserves the surrounding shell and exposes Retry; do not display the empty state after a failed read. No decorative copy or robot image is needed.

If there is an existing team boundary, a small scope selector may distinguish Personal and the selected team. The entire content changes with the authorised scope. No collaborator avatars, chat, notifications, or invitation panel are part of this handoff.

**Build acceptance:** duplicate preserves pins and agent assignments; removal is scoped correctly; no unauthorised setup flashes before an access check; the shell remains usable on an empty workspace.

### W2: Setup editor

Use a restrained composition with the setup identity and Save action at the top. The central area lists the selected agent's resources by type. A resource search panel opens beside the editor on wide screens and as a single focused sheet on small screens. This is a flat editor, not a node canvas.

The default simple setup has one agent. Where the backend supports multiple agents, show a plain agent selector and always identify which agent receives an edit. Reusing one resource on two agents creates two bindings. A shared unordered pile of prompts/tools is not a substitute for assignment.

| Editing task | Interaction contract | Error or edge state |
|---|---|---|
| Add | Search within resource kind, inspect a concise preview, choose a version, confirm Add to the named agent | Known incompatibility prevents commit with explanation; unknown compatibility is labelled, not treated as tested |
| Remove | Remove the chosen binding from the draft; show immediate Undo while unsaved | Does not remove other agent bindings or delete the resource |
| Swap | Select Replace on a binding, search alternatives, compare source/version and material prerequisites, then replace in the draft | Cancel preserves the old binding; a failed validation does not delete the original |
| Pin version | Show selected version and an explicit Pin action if not already pinned; pin exact source identity provided by the backend | Missing revision remains visible as unresolved; never fabricate a pin from a display label |
| Model/settings | Choose among supported options and edit relevant fields under the selected agent | Unsupported options are excluded or explained; no silent fallback to another model or provider |
| Duplicate | Open a new draft preserving snapshots and assignments | Do not inherit secret values; keep only legitimate credential references if the backend supports them |
| Save | Validate then persist the current draft; a receipt changes “Unsaved changes” to “Saved” | Save failure retains edits; conflict exposes Reload saved and Save as copy if supported; never silently overwrite a concurrent revision |

Resource category controls: Prompts, Skills, Plugins & tools, MCPs, and Model & settings. Agent definition/settings live with the selected agent. Show detailed IDs, parameters, and advanced settings in disclosures, retaining plain labels for the main task. Add help only when it is necessary to use a control correctly; do not introduce generic explanatory slogans.

Version pins are visible next to the resource. An upstream update may show “New version available” with a review action; it must not replace a pin automatically. If an upstream item disappears, preserve the saved identity and snapshot with an unavailable state. Let the user replace or remove it deliberately.

Use explicit Save initially. Do not imply cloud persistence from a local draft. On navigation away with unsaved edits, offer Keep editing, Discard changes, and Save only if the relevant operation can complete. Browser close may use the platform's standard unsaved-change mechanism. Authentication expiry retains the draft locally only under the existing privacy/persistence policy and requests sign-in again without claiming success.

Display “Saved for later execution” only after successful persistence. Do not add a Run button, queue widget, or fabricated readiness indicator. Future harness capability must be connected through project-owned contracts in a separately authorised slice.

**Build acceptance:** each mutation has an explicit target agent and resource version; swap is atomic within the draft; a failed save leaves all edits intact; duplicate preserves binding snapshots; pins survive refresh; no edits execute resources or change public catalog entries.

## C1: Suggest resource

Use a short, single-column form. Required: resource link and “What does it help with?” Optional: name if not available from source, resource kind if known, and a link to an output example. Do not request an account, résumé, technical manifest, email address, or file upload unless an existing submission system requires one and the requirement is disclosed.

Before submit, use the exact label “Send suggestion.” State that suggestions are reviewed before appearing publicly. Submit is a deliberate external write and must use the application's actual endpoint, with deterministic validation and a receipt. No optimistic “Published” toast.

Validation appears inline under the corresponding input, with an error summary when several fields fail. A failed submission preserves all input and offers Retry. A confirmed receipt says “Suggestion received” and explains that receipt does not mean selection or testing. Repeated clicks during submission should not create duplicate records. A preview-only build must explicitly say submission is unavailable, never pretend to send.

## View requirements for backend integration

These are information requirements for the client, not a database schema, migration plan, or selection of an execution framework. Map them through adapters to existing project-owned contracts. Verify current backend capabilities before committing to UI affordances.

| View need | Minimum information | Deterministic authority |
|---|---|---|
| Resource identity/version | Stable identity, title, kind, version/revision, source, licence state, compatibility/prerequisites | Backend validates identities and source references; no client-invented pin |
| Example | Task/input reference, output reference, creator/origin, capture conditions, rights, classification | Evidence ownership and published state are authoritative |
| Evidence label | Claim, evidence class, scope, source, date, version context, limitations | Label derived from evidence record; no inferred “tested” from popularity or presence |
| Search result | Matching items, explicit filters, stable cursor or pagination state, known total or unknown | Apply supported filtering and ranking; retain query identity to avoid race errors |
| Saved setup | Authorised scope, setup identity/revision, ordered agents if meaningful, versioned bindings/settings | Access checks and validation before persistence |
| Binding | Target agent, resource identity and exact revision/snapshot, settings, availability | No ambiguous shared ownership; a duplicate preserves the captured binding |
| Save outcome | Success receipt and saved revision, or typed recoverable/conflict/access error | Never mark saved until commit is confirmed |
| Suggestion | Input, submitted source, deduplication/request identity where supported, receipt status | Validate and persist without automatic public publication |
| Future evaluation | Experiment/task, backend/harness, model, resources, artefacts, evaluation, cost/latency, failures | Evaluation rules and results remain outside speculative UI logic |

Inference may assist selection or explanation only within documented bounds. Permissions, changes, saved state, side effects, experimental configuration, and evaluation rules remain under deterministic control. UI descriptions are not instructions to execute a resource.

## Implementation sequence for a later authorised build

### Asset prerequisites and enhanced 3D delivery

Before Codex implements the visual design, resolve the exact asset filenames and approval decisions in [ASSET_MANIFEST.md](ASSET_MANIFEST.md). Available files and planned treatments are separate facts.

| Delivery level | Assets/information that must be ready | Fallback and boundary |
|---|---|---|
| Review handoff, current task | Six new narrative masters in `narrative-v3/` and six retained utility plates in `visuals-v2/`; reference board; proposed palette/specification; classification and approval records | Plates communicate design. They do not prove a frontend or animation exists |
| Faithful static frontend | Reviewed tokens and exact copy; approved clean poster art without generated type; desktop/mobile crops or explicit focal/safe-area data; licensed fonts; real resource metadata; specified no-output states | This uses actual still assets. No canvas, fabricated output, or fake 3D interaction is necessary |
| Layered 2.5D motion | Separate transparent foreground/object/signal/background layers; explicit depth order, focal point and transform limits; matching still poster | A flattened poster cannot expose hidden geometry. Without genuine layers, use restrained whole-poster opacity/transform within the specification |
| Interactive 3D/WebGL | Optimised GLB/glTF meshes; named nodes shared across scenes; PBR materials/textures; camera positions and paths; light/environment setup with rights; scale/axes; desktop/mobile detail strategy | None is implied by a 3D-looking PNG. Without this source set, use the approved poster and mark 3D treatment as planned in handoff metadata |
| Object morph/selection choreography | Compatible topology or authored morph targets/keyframes; node correspondence; timing/easing; occlusion plan; matching poster states | Cross-fading two renders is not a delivered geometric morph. Use a specified still-state transition until correct sources exist |
| Pre-rendered scene/video option | Source render, actual encoded video variants, poster, aspect ratio/crop, loop/end behaviour, and licence/provenance | Do not invent a video path. The poster remains usable when playback is unavailable or reduced motion is requested |
| Genuine resource/output display | Actual resource source/version/rights; genuine result tied to that resource; capture and attribution record | Omit unavailable media. Do not use narrative artwork as resource evidence |
| Future N5 before/after | Matched real output pair and evidence record described in CONTENT_AND_EVIDENCE.md | Evidence slot stays handoff-only; public scene keeps the exact Pinterest question without empty comparison panes |

An implementer must not compensate for absent 3D sources by inventing a different visual world. The poster fallback is designed, not a blank error screen. Adding Three.js/WebGL or another renderer is a later implementation choice after checking the receiving application and complete source assets; this handoff installs no library and implements no animation.

### Establish the receiving project

Read its current AGENTS.md, framework, routes, existing token system, authentication, resource and setup contracts, and dirty working state. Reuse suitable abstractions. Do not make this handoff an excuse to replace the application stack. Confirm the proposed palette, asset paths, approval statuses, and delivery level. Keep N5's absent evidence in handoff metadata; its public design remains the exact question without placeholder rectangles.

**Exit evidence:** a short mapping from this plan to existing routes/contracts; explicit unsupported capabilities; no unrelated edits or schema changes.

### Build the calm public vertical slice

Implement the shared reviewed tokens/navigation and semantic N1-N6 story order, then D1, D2, and D3 with real approved catalog content. Internal fixtures remain isolated from public content and described in review metadata. Include keyboard paths, empty/error/loading states, direct links, selected versions, and provenance. Establish the project pitch as well as discovery before adding enhanced motion.

**Exit evidence:** Explore to search to detail to source works on desktop and mobile; content and version checks pass; accessibility and responsive captures are recorded.

### Add the optional entrance

Add the reviewed narrative treatment to N1-N6 using the actual delivered asset level, visit-state contract, exact semantic copy, and motion preferences. N5 keeps its question-only public state while evidence is absent. Load narrative media only on the story route. Ensure discovery never waits on cinematic or 3D assets.

**Exit evidence:** first-visit automatic playback, full-sequence keyboard/tap bypass, return visit, direct link, hidden-tab return to static N6, disabled storage, media failure, reduced-motion/save-data bypass, and static replay have usable outcomes.

### Add saved setups and editing

Implement W1 and W2 against the validated existing backend. Start with its genuine single-user scope if that is what exists. Complete add/remove/swap/pin/duplicate/save behaviour and failure recovery before extra polish. Do not build execution.

**Exit evidence:** exact pins and agent bindings survive save/reload and duplication; failed save and revision conflict preserve user work; access boundaries hold.

### Add suggestions and content publishing gates

Implement C1 and confirmed submission state only when the actual endpoint exists. Connect production content to explicit evidence and asset publishing gates. Keep fixture data, concept art, and output evidence distinguishable throughout the build.

**Exit evidence:** form validation and duplicate-submit handling work; receipt is confirmed; no submitted item becomes public without the established review process.

### Verify the completed build

Use the acceptance matrix below and the design specification. Record actual checks, failures, and remaining limitations. Do not report a Lighthouse score, browser test, accessibility audit, or measured performance target as achieved without executing it on the built site.

## Acceptance matrix

| Area | Required checks |
|---|---|
| Product scope | No extra dashboard, analytics, leaderboard, pricing, collaboration, or harness features; public copy addresses non-experts |
| Narrative fidelity | All six approved beats preserved verbatim; homepage is a project pitch; no replacement slogans or decorative filler |
| Visual continuity | Same material, lighting, motifs and typography; gradual reviewed colour progression; no unrelated-poster sequence |
| Entrance | No visible playback/navigation controls; N1 has no CTA; N6 retains two CTAs; eligible key/bare-scene tap skips whole sequence; first/return/replay/hidden-tab/preferences correct; direct links bypass |
| Discovery | Search has a label; query/filter state restorable; meaningful empty/loading/error states; no fake results counts or match percentages |
| Detail/evidence | Version and evidence stay aligned; examples state provenance; generated concept art is never proof; missing/unknown values are explicit |
| Workspace | Save confirmed by actual persistence; errors preserve draft; swaps preserve original until accepted; duplicate preserves pins and agent bindings; access checks enforced |
| Suggestions | Required fields clear; valid source URL handling; input retained after failure; repeat submission controlled; receipt does not imply publication |
| Keyboard | Visible focus; sensible order; menus/dialogs return focus; no global story trap; every drag action has another input method |
| Responsive | Inspect at 360, 390, 768, 1024, 1440, and 1920 CSS px; text zoom 200%; narrow 320 CSS px reflow; no hidden actions or horizontal page overflow |
| Theme | All public/private surfaces checked in the selected deep theme; media scrims and forms preserve contrast; no accidental section flip. Test light discovery/workspace only if that optional theme is explicitly selected |
| Motion | Reduced-motion and static fallback inspected; no autoplay sound; motion can stop; state changes remain understandable without movement |
| Performance | Measure actual LCP, INP, CLS on representative pages; targets LCP <2.5s, INP <200ms, CLS <0.1 are targets, not delivered claims |
| Assets | Every shipped asset is in manifest, permission/provenance known, useful crop checked, appropriate alt text, reserved dimensions, no reference-site asset copied without rights |
| 3D readiness | Posters, separated layers, GLB/models, video, and planned motion have distinct statuses; absent geometry never reported delivered |
| Browser | Current Safari, Chrome, Firefox; iOS Safari and Android Chrome where available; test sticky/viewport controls with mobile browser chrome |
| Trust | No fabricated testimonials, logos, adoption counts, benchmarks, research outcomes, or human-approval claims |

## Known gates and decisions left open intentionally

- **Human visual approval:** record actual review decisions in the manifest. This package does not self-certify the user's approval.
- **Real transformation:** N5's evidence slot is complete in handoff metadata only. A matched output pair is required later for proof; the current public scene retains the exact Pinterest question without empty evidence rectangles.
- **Backend delivery:** this task did not validate any older worker's delivery or deployment. Bind future frontend work only to contracts verified in its receiving checkout.
- **Catalog readiness:** design fixtures are not a launch catalog. Source, licence, compatibility, and evidence records must be populated for published resources.
- **Colour direction:** the revised palette/progression is concrete but proposed for review. Do not treat it as an accepted final brand decision or return to a monochrome lock. A new symbol/logo is outside scope.
- **3D source assets:** generated posters convey intended material and camera composition; actual GLB, layers, morph data, environment and/or encoded video must be delivered before implementing corresponding treatments.
- **Execution and benchmarks:** preserved as future optionality, with no controls pretending they work now.

These gates do not prevent reviewing the complete design or implementing independent approved surfaces. They prevent unsupported claims and accidental expansion of the project.
