# Offline harness foundation v1

This authorized foundation precedes experiments. It is a separate `agent_harness`
package, not an integration with `agent_lab` or the legacy coordinator. Website,
creation/catalog/composition APIs, saved revisions, existing databases, Codex,
and the old runtime are unchanged. No database, migration, server or cloud
service is introduced.

## Install and reproduce

Python 3.12+ and the committed lock are required. Framework dependencies are an
optional extra; importing `agent_harness` or its records needs only Pydantic.

```sh
uv sync --locked --extra harness --group dev
uv run --locked --extra harness pytest -q tests/test_harness_records.py tests/test_harness_offline.py
uv run --locked --extra harness python -m agent_harness.demo
uv run --locked --extra harness ruff check .
uv run --locked --extra harness ruff format --check .
uv run --locked --extra harness mypy src
uv lock --check
```

The demo executes the real framework stack. It prints JSON receipts for a
single agent, a replacement model using identical instructions and topology,
a two-agent handoff, an uppercase fixture tool with a supplied price estimate,
capability rejection, acknowledged cancellation, and uncertain stop delivery.
No provider sign-in, AWS account, API key or credit balance is required.

The pinned stack is Deep Agents 0.4.11, LangChain 1.2.12, LangGraph 1.1.2 and
LangGraph prebuilt 1.0.8. Prebuilt is explicitly pinned because a newer version
resolved with this stack but failed to import. The lock pins all transitives.
Provider SDKs are transitive dependencies of Deep Agents, not enabled bindings.
The baseline extra-free install does not install these frameworks.

## Architecture and public values

```text
Frozen Invocation v1 (identity, content fingerprint, agents, bounds, supplied prices)
  -> OfflineHarness.start -> preflight (all agents; no model factory on rejection)
  -> fixed LangGraph StateGraph: agent_0 [-> agent_1] -> END
       each node: create_deep_agent(injected offline model, StateBackend, guard)
       Deep Agents' LangGraph executes model and permitted fixture-tool calls
  -> frozen Outcome v1 (outputs, usage/estimates, versions, status/effect evidence)
```

`records.py` depends only on Python and Pydantic. Records reject extra fields,
are deeply immutable through scalar values and tuples, and serialize as JSON.
Schema version 1 rejects unknown versions. There is no experiment, dataset,
evaluation or benchmark schema. A caller supplies invocation, input and
configuration identities; the content fingerprint additionally identifies all
resolved instructions, model bindings, tools, bounds and prices. `start`
revalidates and snapshots the specification, including unchecked Pydantic copies.

Each `Agent` has independent instructions, a provider/model/revision binding,
declared tool names, and required capabilities. Harness identity
`deepagents-offline-v1`, host identity `local-asyncio`, and model/provider identity
are separate. Accepted model bindings and library/Python versions accompany
outcomes, including failures before a final agent output. Framework objects,
model construction options and scripted responses remain adapter-local; generic
values have no credential or provider-client fields.

`OfflineBinding` injects a fresh `OfflineChatModel` factory plus advertised
capabilities. Two deterministic bindings can replace each other without changes
to task instructions or scheduling. Unknown bindings, insufficient capabilities,
and unavailable tools reject the invocation before any model factory is called.
Every admitted model must support tool calls, as required by Deep Agents. Model
instances cannot be reused across agents or invocations. Exhausted scripts fail;
there is no default provider or fallback model.

The one- or two-agent topology is deliberately fixed and acyclic. In the
handoff, the first final text becomes the second agent's input; it does not spawn
arbitrary subagents or send hidden conversation state. LangGraph owns scheduling;
the host only monitors completion/deadlines and explicit stops. A step means one
model or tool call, counted across both agents. Framework recursion limits are
also explicit. Limits preserve completed first-agent output when the second is
not permitted to run. A rejected/failed invocation is never automatically retried.

## Permissions and offline boundary

The only available fixture tool is async `uppercase`, a pure string operation.
Tools must be explicitly declared. Guard middleware removes Deep Agents' default
filesystem, shell, todo and subagent tools from model schemas and rejects any
attempt to invoke them, including hallucinated names. `StateBackend` holds any
framework filesystem state in memory; no filesystem backend, store, checkpoint,
skills or memory file is configured. A denied tool terminates the invocation;
it is not converted into an invitation to retry. LangSmith tracing is disabled
inside the graph even if enabled in the caller's environment.

Tests prohibit socket connection/DNS and process launches while exercising real
framework calls, including attempted undeclared `execute`, `task`, filesystem,
todo and unknown tools. No live provider test is a default dependency.

This is an offline fixture adapter, **not an OS sandbox for arbitrary Python
code**. Injected factories and model subclasses are trusted test code; malicious
Python can bypass in-process protections. Only the supplied offline model and
pure fixture tools are supported here. Live-provider or arbitrary-plugin
adapters need their own reviewed network, permission and stop-delivery boundary.
Long synchronous blocking code can block the event loop; time bounds here apply
to the asynchronous fixtures, not hostile code or remote work.

## Stops, uncertainty and effects

`start` returns a `Handle`; `await handle.outcome()` returns one immutable receipt.
`handle.stop(request_id)` requests cooperative cancellation and is idempotent
while running. A stop after termination returns `None` and invents no
acknowledgement. Cancelling an outcome waiter does not cancel the invocation;
use `stop` explicitly. One host rejects reuse of invocation identity, including
failed/uncertain attempts. This in-memory guard is not durable cross-host replay
protection or distributed recovery.

Evidence has distinct sequential observations and actors:

1. `started` by the adapter, when admitted;
2. `stop_requested` by caller or deadline-monitoring host, with request identity;
3. `stop_acknowledged` only when the local graph task cancels and every model
   active at the request explicitly acknowledges cancellation;
4. `terminal` by the host, with status;
5. `effects`, separately recording `not_started`, `local_settled` or `unknown`.

A deadline or explicit stop cancels the graph task once and waits at most the
specified grace interval. Missing acknowledgement produces `uncertain` and
never implies remote effects stopped. If the local task finishes without
model acknowledgement during grace, effects can be `local_settled` while
stop status remains uncertain. Graph cancellation alone is not a model's
acknowledgement: LangGraph can cancel its wrapper after a model suppressed
cancellation and finished. An outstanding task produces `unknown` effects;
a later cleanup cannot rewrite the frozen receipt. `wait_local_settlement` is a
fixture cleanup helper and may wait for that task; it is not a bounded remote
cleanup operation. There is no replay, retry, distributed reconciliation or
remote cleanup guarantee. `local_settled` describes only this process's completed
graph and pure/in-memory fixture effects.

Failure evidence uses fixed safe labels (`adapter_failure`, `permission_denied`,
`step_limit`, etc.), never raw exception text or provider payloads. Intended agent
outputs are retained as data, not secret-scanned or claimed safe for publication.

## Usage and supplied estimates

Each completed agent optionally retains token counts, elapsed time is recorded
for the invocation, and a supplied price can identify the binding, currency,
input/output rate, tokens per rate unit, source and effective date. Usage is known
only when every model response in that agent reports it; no local tokenizer
invents billable usage. Partial/failed agent usage is currently unknown.

Estimates are per-agent, not billed cost or a cross-currency total. For example,
100 input and 20 output tokens at USD 2 and USD 6 per million tokens estimates
USD 0.00032. Actual zero tokens or zero supplied rates give zero; absent token
counts or prices give `amount: null` with an explicit reason. Decimal arithmetic
retains supplied rate precision. No price scraping, provider verification,
cheapest-model routing, AWS credit assumption, live providers, hosted execution,
experiments or benchmark evaluation is implemented.

## Validation boundary

The dedicated offline integration tests cover model replacement, the actual
handoff and fixture tool result, preflight, denied built-ins, shared step bounds,
sanitized failures, deadlines, explicit/idempotent stops, missing acknowledgements,
waiter cancellation, immutable receipt/input identities, usage and estimates.
Record tests run without the extra; integration tests skip when it is absent.
The harness gate must explicitly install `--extra harness` so a skip cannot count
as proof. Recheck the selected existing legacy offline suite for dependency
compatibility; do not modify excluded website/composition tests for this slice.
