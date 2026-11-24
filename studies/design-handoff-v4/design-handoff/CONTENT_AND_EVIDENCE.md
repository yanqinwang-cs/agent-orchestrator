# Agent Lab content and evidence contract

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

Date: 6 October 2026. Revision v3. Companion to [IMPLEMENTATION_PLAN.md](../IMPLEMENTATION_PLAN.md), [DESIGN_SPEC.md](../DESIGN_SPEC.md), [REFERENCE_BOARD.md](../REFERENCE_BOARD.md), and [ASSET_MANIFEST.md](../ASSET_MANIFEST.md).

This document supplies copy and truthfulness rules for the handoff. It is not a record of experiments, public catalog approval, or user approval of generated images.

## Voice and audience

Write for someone who can use an AI application but may not know how a plugin differs from a skill. The homepage is a cinematic project vision and pitch. Discovery then helps the visitor understand a resource before opening technical details. Preserve the user's exact six narrative beats instead of replacing them with shorter generic marketing statements.

Only the approved storyline, necessary interface text, real resource metadata, and explicitly approved supporting text belong on the website. Do not add decorative captions, speculative resource names, invented feature labels, “Illustrative sample,” “Demo preview,” or claims to fill space. A visual that works without words should remain free of extra words. Classification and approval labels belong in the handoff/review metadata, not on the public composition.

Use “setup” in the interface for a saved combination of resources and settings. Use “configuration” when explaining the exact versioned record. Use “agent” only when there is a specific acting component or preset. Do not call every tool an agent, every prompt a skill, or every saved setup a workflow.

Avoid unexplained infrastructure vocabulary in public headings. “Where it works,” “What you need,” “See an example,” and “View source” are more useful than architecture labels. Retain exact technical names in provenance and advanced details.

No claim of universal effectiveness, universal compatibility, guaranteed productivity, or superiority of one representation. The project studies which information and interfaces a particular downstream decision needs. It remains open to single-agent and multi-agent systems, different models and harnesses, and different representations.

## Entrance copy lock

Use real HTML for all production text; generated lettering in visual plates is approximate composition reference. This table is the one canonical copy source and supersedes divergent lettering in both v1 and v2 plates. Preserve the full wording and punctuation. The headline/support split is a layout decision, not permission to edit the sentence.

| Plate | Headline | Supporting copy | Action |
|---|---|---|---|
| N1 | Transform your AI workflow without needing years of experience. | | No visible action controls |
| N2 | More tools. More plugins. More confusion. | How do we know what actually gets results? | No visible action controls |
| N3 | Add more agents and coordination gets harder; poor handoffs can erode productivity gains. | | No visible action controls |
| N4 | Why Agent Lab? | We study, test, select, and curate what your AI system actually needs. | No visible action controls |
| N5 | Ever wondered how to build the website you saw on Pinterest? | | No visible action controls |
| N6 | Find the tools you need now, or join us and help shape what comes next. | | Explore resources; Suggest a resource |

The user confirmed there is no existing website transformation example and explicitly requested an evidence slot. That slot is handoff-only. It is recorded as missing real before/after evidence in the manifest, not drawn as empty rectangles on the public page. N5 publicly uses only the approved Pinterest question and the continuing refined visual composition. The later explicit tablet request authorizes a generated webpage inside the narrative device. This is conceptual and must not be called a real resource output or Pinterest screenshot. Do not add placeholder explanations, borrowed Pinterest artwork, pretend resource results, or action controls. Future genuine examples belong to a separately reviewed placement.

“Explore resources” is the necessary label for discovery intent and “Suggest a resource” for contribution intent. They appear as the final N6 pair and on the appropriate calm product surfaces. N1 has no duplicate CTA. The user's latest instruction removes visible Play story, Pause, Previous, Next, Enter and Skip controls from every entrance scene. Do not add a visible keyboard hint, playback badge, progress counter, or replacement label. All former control guidance, v1 slogans, filler labels, and evidence-slot captions are superseded.

An eligible first visit automatically plays approximately 36 seconds, then holds at N6. An ordinary eligible key skips the entire sequence directly to discovery; a tap on bare scene art provides the same bypass on touch devices. Native final CTA activation, focus navigation, modifier shortcuts, IME and repeated-key exceptions follow the implementation plan. There is no scene-by-scene key advancement. Hidden-document playback stops and returns as static N6. Returning visits, direct links, reduced motion and save-data bypass to discovery; explicit `/story` under reduced motion/save-data is a static six-beat document. These are implementation rules, not extra words to print over the artwork.

N4 describes the Lab's intended activity. The published catalog must show actual evidence status where relevant. Do not let a broad “test” statement imply that an untested listed resource has passed a Lab evaluation. “Join us” in N6 leads to the existing suggestion/contribution path; it does not authorise inventing a social network, signup programme, or collaboration feature.

## Functional copy

### Discovery

| Element/state | Copy |
|---|---|
| Explore title | Explore resources |
| Search label | Search resources |
| Type control | All; Prompts; Skills; Plugins & tools; MCPs; Agents & setups |
| Target filter | Works with |
| Optional filter | Evidence |
| No results | No resources match these filters. |
| No-results action | Clear filters |
| Search failure | Search is unavailable right now. Your query is still here. |
| Search recovery | Retry |
| Unknown compatibility | Compatibility not checked |
| Missing evidence | No Lab test yet |
| Source link | View source |
| Add action | Add to setup |
| Copied state | Copied |
| Copy failure | Could not copy. Select the text and copy it manually. |

Do not display an empty picture frame or filler caption for a resource without a genuine output preview. A copyable excerpt of its actual prompt or a real input/output example can be useful; otherwise allow its real metadata to carry the item. Unknown does not mean bad, and “no test yet” does not imply the item failed. The functional labels above are required state/navigation text, not decorative badges to scatter across the design.

### Plain-language definitions

| Term | Public explanation |
|---|---|
| Prompt | Instructions you give an AI for a particular task. |
| Skill | A reusable procedure that helps an AI handle a kind of task. |
| Tool | A capability an AI can use to get information or take an action. |
| Plugin | A package that adds capabilities to a supported application. |
| MCP | A standard connection that lets supported AI applications use tools and data. |
| Agent | An AI configured for a responsibility, with particular instructions and available capabilities. |
| Setup | A saved choice of agents, resources, versions, and settings. |
| Benchmark | A defined task and evaluation used to compare systems under stated conditions. |

These are internal vocabulary explanations, not automatically approved website supporting copy and not new canonical backend definitions. Expose a definition only when required for a specific comprehension decision and approved in that context. A package can expose several kinds of capability; display its actual supported structure instead of forcing it into a misleading single label.

### Private workspace

| Element/state | Copy |
|---|---|
| Workspace title | Saved setups |
| Primary creation | New setup |
| Empty heading | No saved setups |
| Search-empty | No setups match this search. |
| Read failure | We could not load your setups. |
| Draft status | Unsaved changes |
| In-progress save | Saving… |
| Confirmed save | Saved |
| Save context | Saved for later execution. |
| Failed save | Your changes are still here. Try saving again. |
| Version pin | Pinned to [actual version] |
| Update available | New version available |
| Missing resource | This version is unavailable. Your saved reference is preserved. |
| Replace action | Replace |
| Replacement commit | Replace in setup |
| Revision conflict | This setup changed since you opened it. Your edits have been kept. |
| Dirty navigation | You have unsaved changes. |
| Dirty choices | Keep editing; Discard changes; Save |
| Removal action | Remove setup |
| Removal confirmation | Remove “[actual setup name]”? |
| Removal scope | This removes the saved setup. It does not delete the resources it uses. |

Bracketed values must come from real records. Model options, provider names, version IDs, timestamps, and counts in comps are examples unless the manifest or data source says otherwise. Never publish a version string invented by the image generator.

### Suggestion form

| Element/state | Copy |
|---|---|
| Heading | Suggest a resource |
| Required field | Resource link |
| Required field | What does it help with? |
| Optional field | Name |
| Optional field | Type, if you know it |
| Optional field | Example link |
| Review note | Suggestions are reviewed before appearing publicly. |
| Submit | Send suggestion |
| Pending | Sending… |
| Receipt | Suggestion received |
| Receipt body | This confirms receipt, not selection or testing. |
| Error | Your suggestion was not sent. Your text is still here. |
| Invalid link | Enter a full link to the resource. |

Do not invent a review turnaround time, reviewer identity, or promise that every submission will be evaluated. Do not request contact details only to make the form feel complete. Success/error feedback is necessary interface text; additional gratitude captions or promotional supporting text are not required.

## Visual truth classes

Every visual asset must have one of the following classifications in the manifest. Every output preview additionally has a source and capture record. Classification is independent of whether someone likes the image. These are handoff/review metadata fields, not public overlay labels, captions, or badges.

| Class | What it is | Permitted placement | Prohibited interpretation |
|---|---|---|---|
| `narrative_concept` | Generated or commissioned metaphorical artwork | Entrance story, with suitable accessibility description | Actual agent internals, measured communication, a resource's actual output, a real experiment |
| `design_reference` | A generated section comp or static design specimen | Handoff/review only | Production output, implemented UI, user approval |
| `real_output` | Captured output from a real task, with provenance | Resource example or N5 when rights and review are complete | Generalised performance proof beyond its method |
| `reference_only` | Third-party site screenshot or inspiration reference | Internal reference research with attribution | A reusable production asset or Agent Lab result |
| `production_asset` | An asset prepared for a specified site placement, with provenance and use information | Production only when its separate review/rights states permit | Evidence of testing unless linked to a separate experiment |

Production approval is a separate state, not a visual class. A concept image can be approved as art while remaining concept art. A real output can have impeccable provenance while still awaiting permission to publish. A generated comp can be selected for handoff while still awaiting human design approval.

The fact that a narrative image was actually generated does not make it evidence for a frontend-design prompt, skill, tool, MCP, or agent setup. The former A1-as-resource-example treatment is retired. A brain/cyborg/signal image remains narrative concept art and must not stand in for a genuine resource output on D1-D3 or a website transformation in N5.

The manifest must record at least the asset ID, file, classification, origin, intended placement, source/generation record, rights/usage note, review status, reviewer/date when actually reviewed, relevant crop/safe area, and alt-text intent. Unknown values remain unknown. Do not synthesize a reviewer name or approval date.

## Resource previews and review metadata

Discovery and detail use real resource names, source links, versions and prerequisites. When an output is shown, it must be tied to that resource and its actual task. A real screenshot of a different website is still not a result produced by the listed resource. A generated concept image is still not a frontend output.

When no real output exists, omit the media and use actual resource text/metadata. Do not draw a fake preview, invent a resource to justify existing artwork, or add “Illustrative sample,” “Demo preview,” “Sample content,” or decorative placeholder labels to the product composition.

If a review file needs temporary content to demonstrate geometry, identify that fact in the review board or manifest outside the product artwork. Do not publish it. Generated incidental text, resource metadata, dates, ratings, version strings, labels, and claims are not authoritative and must not be transcribed into the application.

## Asset versus motion truth

A 2D image of a 3D object is a poster asset. It does not supply a GLB, geometry behind the camera, separate layers, material files, animation rig, morph targets, or interactive lighting. The manifest must separately record which of these actually exist and which are planned.

For layered motion, record actual layer files, transparency, depth ordering, crop and transform bounds. For interactive 3D, record actual model/material/texture/environment files, licences, camera data, named nodes and animation data. For video, record the actual encoded media and poster. Until those files exist, describe motion as proposed and use the specified still fallback.

The colour system is also a proposal for review. A concrete value in the design specification defines what is being proposed; it does not manufacture user acceptance. Preserve the reviewed palette decision separately from asset-generation provenance.

## Evidence labels

Use plain language and progressive disclosure. The short label is a route to evidence, not a badge of universal quality.

| Label | Minimum basis | Expanded explanation must include |
|---|---|---|
| Documented | A maintainer or official source describes the capability | Source URL, relevant version/date, explicit attribution that this is a source claim |
| Inspected | Someone checked the relevant source or behaviour definition | Inspector/date if recorded, exact source/revision, inspected scope, limits |
| Tested | A recorded check was actually executed on the selected configuration | Test/task, input, expected property, observed result, harness/environment, versions, date, failure limitations |
| Measured | An evaluation captured defined metrics | Method, tasks/sample, comparison conditions, model/provider/harness/resources, measured metrics, uncertainty, date, failures |
| No Lab test yet | No appropriate Lab execution evidence exists | Source information may still be available; do not imply absence of all external evidence |

“Verified” is intentionally excluded because it hides scope. “Tested” must always answer tested for what, on which version, and under what conditions. A compatibility test is not a quality benchmark. A maintainer screenshot is an output example with attribution, not a replicated Lab finding.

Do not derive labels from stars, downloads, marketing claims, apparent polish, a successful install, or the availability of source code. A request submitted to a tool does not prove its completion; a saved setup does not prove it ran.

## The N5 real-output gate

The user confirmed no provenance-backed pair of “poor website” and “polished website” exists and requested the evidence slot. The slot is recorded in the handoff/manifest only. The public N5 composition displays the exact approved Pinterest question without empty comparison rectangles or filler copy. Filling the slot later is content work, not permission to fake evidence or implement a website in this design-only task.

Before a transformation pair can be published, capture:

1. A real brief or task and the permission to show its inputs/outputs.
2. The original saved output and revised saved output, with stable source/artifact references.
3. The model/provider/version where available, harness/application, relevant resources and their exact versions, settings, and the observed sequence.
4. The actual changes between attempts: prompt, skill, tool, model, settings, retries, manual intervention, and total time/cost where measured. Unknown values stay unknown.
5. Screenshots at the same viewport, device scale, page position, and capture conditions; preserve complete uncropped originals alongside display crops.
6. A short account of what improved and what still failed, with independent or deterministic checks where possible.
7. A clear study classification: illustrative real example, controlled comparison, or measured benchmark. Do not silently upgrade one category into another.
8. A publishing review decision, source attribution, rights, and redaction of private data where required.

Do not manufacture an intentionally weak baseline solely to make the after image look good. Do not compare different tasks, cherry-pick the best after attempt while hiding retries, or credit a skill when the model and multiple other inputs also changed. A single honest example can demonstrate a possibility, but does not establish a general effect.

Once evidence arrives, any necessary provenance caption must be written from its actual record and reviewed with the placement. State the task, relevant changed inputs and material limitations only when useful to the reader. If a third party produced the example, identify the creator and do not imply Agent Lab ran it. No prewritten speculative caption is approved here.

## Resource publishing checklist

For a resource to appear publicly, supply its actual name, source URL, creator attribution if known, kind, concise capability, appropriate target/host information, material prerequisites, available version identity, licence/rights state, and evidence status. Do not promise compatibility from a matching icon.

An output preview is optional if it would be misleading or irrelevant. When present, record who produced it, with which resource/version when known, whether the Lab reproduced it, and permission/source attribution. Choose output that helps a non-expert decide: a useful page crop, a short research excerpt, a prompt with one actual response, or a playable media example.

Do not scrape and republish assets merely because they are visible on a reference website. The supplied reference sites inform composition, hierarchy, pacing, and materiality. Their copy, marks, imagery, layout combinations, and motion sequences are not a template or asset licence.

## Current project continuity

The live [AGENTS.md](../AGENTS.md) is the project authority. It preserves a flexible experiment and discovery substrate, interchangeable backends, strong baselines, and deterministic control of permissions and effects. The current user brief explicitly opens visual planning for the website; that does not authorize frontend implementation or a backend migration in this task.

[The rebuilt baseline](../research/agent-lab-rebuilt-baseline.md) is research and includes proposed architecture/routing recommendations, not completed experiments. Its claims must not become public measurements without the underlying source and correct scope. [The older product definition](../research/open-agentic-hub-product-definition-2026-09-28.md) supplies useful distinctions between resources, versions, examples, and evidence; its broader developer-marketplace scope does not override the current non-expert audience or minimal private workspace.

Earlier backend work in other checkouts is not revalidated by this design handoff. Do not infer that a catalog API, team system, configuration service, or execution harness is production-ready. Future implementation must inspect actual receiving contracts and report what is present.

## Review record discipline

For a human decision, record the exact asset/document revision, decision, reviewer, date, and any conditions. “Selected by the design agent,” “reviewed for composition,” “approved for implementation,” and “approved for public release” are different outcomes. The user should be able to approve a concrete asset without accidentally approving a performance claim.

Keep unapproved concept files available for inspection in the review area. Keep real output evidence in a separately identified area. Do not use an `approved` folder name to imply approval that has not occurred. If an approved folder is included for the downstream workflow before decisions arrive, its README must explicitly state it is empty pending recorded approval.

## Revision 4 visual interpretation

No Agent Lab corner name appears in N1–N6. Narrative titles share one fixed right-side anchor, with no scene-specific jumping. Official GitHub/Figma marks in N2 identify the ecosystem only. N4 has the palm-projected montage. N5/N6 share the standalone tablet with the new blue editorial webpage; N6 connects it to the network. The new imagery changes no story words or evidence claims.
