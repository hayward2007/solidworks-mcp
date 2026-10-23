# Design Studio implementation plan

Date: 2026-10-21 (Asia/Seoul)

## Goal and acceptance

Extend the existing SolidWorks MCP with a local, evidence-based mechanical design
investigation workflow usable from a terminal, Claude and Codex. Prioritize the
quality of an iteration over the length of its context. Keep CAD actuation on the
Windows host; run knowledge, numerical screening and review on macOS/Linux too.

An iteration must preserve the baseline, identify datums and protected interfaces,
explain dimensions, compare alternatives, check quantitative requirements, describe
manufacturing and appearance, and produce an inspectable review packet. A recorded
human review is required before the system issues an implementation handoff. No
human review is inferred from an agent saying "approved".

## Existing system

- `solidworks_mcp/server.py`: 34 MCP tools, eagerly imports Windows COM.
- `verification.py`: native part/assembly reports, renders, export, interference.
- `knowledge.py`: in-memory Markdown substring retrieval, no persistence/provenance.
- `gears/`, `topopt/`: dedicated numerical and CAD workflows; preserve these.
- Instructions currently favor short specifications and low image/token usage.
  This conflicts with the requested product-design quality priority.

## Architecture

1. Portable design package, lazy package imports and installable `sw-design` CLI.
2. SQLite knowledge index, bilingual lexical retrieval, stable section/hash citations,
   explicit source authority and date, quality-first mandatory context; compact is opt-in.
3. Content-addressed local artifacts and evidence ledger. Preserve original bytes;
   distinguish observations, calculations, assumptions and third-party reports.
4. Read-only native SolidWorks capture and portable STL geometry inspection.
   Tessellation cannot recover original feature intent, exact fits or surface continuity.
5. Versioned structured proposals, executable analytical checks, quantitative gates,
   aesthetic/manufacturing review, immutable revisions and hash-bound review records.
6. Standalone portable MCP server plus shared tools in the existing Windows server.
   Explicit human review is exposed in the CLI, not as an MCP tool.
7. Detailed guides, source registry, a complete worked example and a CLI demo that
   remains awaiting review. No invented SolidWorks, simulation or product evidence.

## Validation

Test bilingual retrieval and refresh/deletion, provenance and stale artifacts,
analytical values and failure cases, malformed/contradictory packets, approval
invalidation, project isolation, CLI lifecycle, and real MCP stdio initialization
and tool calls. Run the existing portable numerical/installer regression suites.
Windows COM operation must be reported as unverified on this macOS host.

## Scope boundary

REA is inspiration for the inspect -> evidence -> explain -> change interaction,
not a dependency or a mechanical CAD decompiler. Do not install REA or a model API,
silently call a paid provider, or claim recovery of original feature history from
images/STL. Native CAD changes remain agent-driven through the existing tools,
following the reviewed handoff; this iteration adds the review system itself.
