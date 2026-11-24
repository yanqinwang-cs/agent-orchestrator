# Local reference sections and frozen sample

This bounded AGO-70 addition implements AGO-69's accepted placement A: a separate sample page reached from a compact entry after “Browse all six examples” in discovery. It is local-only, not a deployed website or a new experiment.

## View it

From the project root:

```sh
python3 -m http.server 8766 --bind 127.0.0.1 --directory website
```

Open `http://127.0.0.1:8766/discovery.html`. The frozen sample also opens directly at `http://127.0.0.1:8766/samples/four-instructed-runs/`.

No install, build, provider, account or internet connection is needed. The gallery uses system fonts and local images. Native inspection supports Tab, arrow-key scrolling, Escape, and restored focus. Download original serves the same file as Open original.

## Receiving website basis

This checkout has a bounded static reference surface, not a complete implemented website. `discovery.html` imports the retained AGO-11 editorial sketch's styles and simulated website behavior, with its accepted feature/visible/beside settings. Its header, discovery copy, search, type filters, feature, two supporting resources, browse action and footer are unchanged. Discovery now also has the approved AGO-76 compact Browse references row below its introduction and before catalog search. The frozen study entry remains immediately after “Browse all six examples.” The obsolete review prose and design-choice questions are not copied into this receiving preview. A 390px preview toggle remains demo-only.

Workspace, editor, suggestions and catalog remain the original sketch's simulations; they were not implemented or connected to the orchestration service. Their continued presence is not a website-build or catalog-publication claim. The old retained draft remains untouched. Its source SHA-256 is `050c4abb3239465312a1ce2519dc1df6484930ff67263e07268f04e3c2cd4a79`.

## Source-linked reference sections

AGO-77 implements accepted arrangement A: `references/frontend/`, `references/blender/` and `references/workflows/` are directly addressable static pages. Frontend keeps its one Studies link to the existing sample, separate from the purpose-first source library and authored instruction sets. Blender separates Modelling and Animation. Everyday workflows separates Simple workflows and Build an agent; that heading leads to references elsewhere, not an embedded builder.

The four external entries are Blender’s Modeling and Animation & Rigging manuals, Node-RED’s Creating your first flow, and Langflow’s Quickstart (Simple Agent). No instruction packs, rewritten tutorials, executable templates or catalog records are imported. Reference metadata lives in static HTML, separate from the simulated catalog. Reading local entries needs no account; following an external source needs internet access.

Each entry displays purpose, source, format, prerequisites, software/model/hosting/upkeep caveats, licence summary and No Lab test yet. Details discloses version, source-check date, attribution, rights notes and limitations. Unknown facts say Not stated. Model-provider access and possible usage costs stay visible for Langflow; free software is not a free-run claim. The entry links only navigate and never install, run, download or add a setup.

Search uses `q`; Blender and Everyday workflows use `topic`, while Frontend uses `purpose` in GET addresses. Subtopic links retain the submitted query; Back and reload restore that address. Unknown topics fall back to All, no matches expose Clear filters, and the result count announces the page result. Native controls retain visible keyboard focus. Without JavaScript, all entries remain readable, but search/filtering is unavailable. No search state is stored outside the address.

To run the rendered reference checks, serve the project root and open `/tests/references_browser.html`, then choose Run browsing checks. It exercises real 390px pages, labelled search, announcements, details, subtopics, query/reload recovery, unknown input, no matches, clearing, source destinations and the existing study link. Manually follow both external-source journeys and use Back to confirm recovery; external services are not automated test dependencies.

## Purpose-first Frontend organization

AGO-83's accepted organization is implemented only on Frontend design. Five primary purpose categories are Landing / campaign, Portfolio / case study, Article / docs, Dashboard / app and Shop / checkout. All currently contain zero source samples. Purpose links retain submitted search; search retains purpose; Back, reload and Clear filters recover address state. Unknown purposes fall back to All. Search separately filters the retained study; purpose selection never classifies or hides study evidence. No samples, authored sets or validation claims are invented.

The metadata disclosure defines cross-cutting visual-language tags, separate density and light/dark mode, site/page/section/component scope, site-family foundations, page-specific exceptions, audience/action/content/screen context, source/rights and optional borrow/avoid/freedom notes. These are metadata conventions, not assignments to nonexistent samples. A sample is retained once with a primary purpose and related purposes. Style browsing becomes useful only after real tagged samples arrive; there are no fabricated style results or instruction packs.

Screenshots and site links alone are sufficient future input. Notes about what to borrow or avoid, scope, fidelity and constraints are optional; unknown facts remain Not stated. This static site has no upload, intake storage or compilation service. Compilation and new instruction sets wait for actual samples and a request. Future authored sets must link sources and state version and status; authorship is not validation. Existing unlisted drafts remain unlisted and catalog examples remain examples.

`frontend/frontend.js` handles this bounded empty-library browsing separately, leaving the shared Blender/workflow filter unchanged. The rendered browsing checks now cover all five empty purposes, metadata disclosure, study independence, query retention, Back/reload, unknown input, no matches and clearing. Existing frozen archive verification remains unchanged. No harness, hold, provider, publication or experiment is involved.

## Frozen evidence and new presentation

`samples/four-instructed-runs/DEFAULT-EVIDENCE.html`, `PROVENANCE.json` and `SHA256SUMS` are exact copies of AGO-69's retained archive. The original is 4,551,392 bytes, SHA-256 `dcea2bbb71fec9ec1a1726b40f4feb6cb5f989a7f0f4433d31f27c0791f6793a`. The eight PNGs in `images/` are decoded without transformation from its embedded images, and retain their recorded hashes. These are intended sample assets, not development screenshots.

`index.html`, `sample.css`, `sample.js` and `REVIEW.html` are separate new presentation. The notice handles the original's missing wider-comparison link without altering that link or pretending its target was supplied. No original styling, condition labels, image bytes, credits or claimed hashes have been changed.

The wrapper groups captures by run in original order: full required skills, full control, minimal required skills, minimal control. Each group pairs desktop (1440 × 900) and narrow (390 × 844) images. It preserves the subjective observation, discloses invitation-only scope and unverified skill exposure, and does not score effectiveness. Photograph credits remain in every image and are transcribed without inventing missing source URLs.

## Verify

```sh
python3 -m unittest discover -s tests -p 'test_frozen_website.py' -v
```

For repeatable rendered checks, serve the project root (without `--directory website`) and open `/tests/frozen_website_browser.html`. It loads the actual sample in a 390px frame, checks all eight native dimensions and scrollability, and exposes controls for reviewing each run. Every boolean result should be true.

The standard-library tests serve the actual static files, compare downloaded archive and image hashes with frozen provenance, decode embedded originals for byte equality, check PNG dimensions, and follow all new local gallery/notice links. Browser verification separately covers the rendered discovery placement, all run pairs, narrow stacking, keyboard inspection/scrolling/focus restoration, original navigation, and the missing-comparison notice. There were no existing frontend end-to-end tests in this checkout.

No new runs, prompts, settings, skill logs, failed attempts or complete-page designs were supplied or fabricated. The original's frozen-design HTML hashes remain unverified claims. Publication requires a separate usage-rights and attribution review; embedded credits alone do not clear that gate.
