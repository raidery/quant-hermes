---
name: llm-wiki
description: "Karpathy's LLM Wiki — build and maintain a persistent, interlinked markdown knowledge base. Ingest sources, query compiled knowledge, and lint for consistency."
version: 2.1.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [wiki, knowledge-base, research, notes, markdown, rag-alternative]
    category: research
    related_skills: [obsidian, arxiv, agentic-research-ideas]
    config:
      - key: wiki.path
        description: Path to the LLM Wiki knowledge base directory
        default: "~/wiki"
        prompt: Wiki directory path
---

# Karpathy's LLM Wiki

## User Context

- **Vault**: User has `~/documents/second-brain/` — a PARA-based vault with LogiMind conventions (CLAUDE.md at vault root)
- **Quant research**: New domain planned alongside existing AI/Agent content
- **Multi-domain**: A single vault supports multiple domains via subdirectories (e.g., `wiki/quant/`) and shared PARA categories

Build and maintain a persistent, compounding knowledge base as interlinked markdown files.
Based on [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

Unlike traditional RAG (which rediscovers knowledge from scratch per query), the wiki
compiles knowledge once and keeps it current. Cross-references are already there.
Contradictions have already been flagged. Synthesis reflects everything ingested.

**Division of labor:** The human curates sources and directs analysis. The agent
summarizes, cross-references, files, and maintains consistency.

## When This Skill Activates

Use this skill when the user:
- Asks to create, build, or start a wiki or knowledge base
- Asks to ingest, add, or process a source into their wiki
- Asks a question and an existing wiki is present at the configured path
- Asks to lint, audit, or health-check their wiki
- References their wiki, knowledge base, or "notes" in a research context

## Wiki Location

Configured via `skills.config.wiki.path` in `~/.hermes/config.yaml`:

```yaml
skills:
  config:
    wiki:
      path: ~/documents/second-brain
```

> **Note**: If the vault already has a `CLAUDE.md` or `log.md`, read them first — the vault may have its own conventions (e.g., PARA system, LogiMind workflow) that take precedence over this skill's defaults.

## Architecture: Three Layers

```
wiki/
├── SCHEMA.md           # Conventions, structure rules, domain config
├── index.md            # Sectioned content catalog with one-line summaries
├── log.md              # Chronological action log (append-only, rotated yearly)
├── raw/                # Layer 1: Immutable source material
│   ├── articles/       # Web articles, clippings
│   ├── papers/         # PDFs, arxiv papers
│   ├── transcripts/    # Meeting notes, interviews
│   └── assets/         # Images, diagrams referenced by sources
├── entities/           # Layer 2: Entity pages (people, orgs, products, models)
├── concepts/           # Layer 2: Concept/topic pages
├── comparisons/        # Layer 2: Side-by-side analyses
└── queries/            # Layer 2: Filed query results worth keeping
```

**Layer 1 — Raw Sources:** Immutable. The agent reads but never modifies these.
**Layer 2 — The Wiki:** Agent-owned markdown files. Created, updated, and
cross-referenced by the agent.
**Layer 3 — The Schema:** `SCHEMA.md` defines structure, conventions, and tag taxonomy.

## Resuming an Existing Wiki (CRITICAL — do this every session)

When the user has an existing wiki, **always orient yourself before doing anything**:

① **Read `SCHEMA.md`** — understand the domain, conventions, and tag taxonomy.
② **Read `index.md`** — learn what pages exist and their summaries.
③ **Scan recent `log.md`** — read the last 20-30 entries to understand recent activity.

Only after orientation should you ingest, query, or lint. This prevents:
- Creating duplicate pages for entities that already exist
- Missing cross-references to existing content
- Contradicting the schema's conventions
- Repeating work already logged

## Initializing a New Wiki

When the user asks to create or start a wiki:

1. Determine the wiki path (default `~/wiki`)
2. Create the directory structure above
3. Ask the user what domain the wiki covers — be specific
4. Write `SCHEMA.md` customized to the domain
5. Write initial `index.md` with sectioned header
6. Write initial `log.md` with creation entry
7. Confirm the wiki is ready and suggest first sources to ingest

## Core Operations

### 1. Ingest

When the user provides a source (URL, file, paste), integrate it into the wiki:

① **Capture the raw source:** save to appropriate `raw/` subdirectory
② **Discuss takeaways** with the user
③ **Check what already exists** — search index.md and find existing pages
④ **Write or update wiki pages** — create pages meeting Page Thresholds
⑤ **Update navigation:** add to `index.md`, append to `log.md`
⑥ **Report what changed**

### 2. Query

When the user asks a question about the wiki's domain:

① **Read `index.md`** to identify relevant pages
② **search_files across wiki files** for key terms
③ **Read the relevant pages**
④ **Synthesize an answer**, cite wiki pages
⑤ **File valuable answers back** to `queries/` or `comparisons/`
⑥ **Update log.md**

### 3. Lint

When the user asks to lint or audit the wiki:

① Orphan pages — pages with no inbound `[[wikilinks]]`
② Broken wikilinks — `[[links]]` pointing to non-existent pages
③ Index completeness — every wiki page in `index.md`
④ Frontmatter validation — all required fields present
⑤ Stale content — pages not updated in 90+ days
⑥ Contradictions — conflicting claims across pages
⑦ Page size — flag pages over 200 lines
⑧ Tag audit — all tags in SCHEMA.md taxonomy
⑨ Log rotation — if log.md exceeds 500 entries
⑩ **Report findings with specific file paths**
⑪ **Append to log.md**

## Obsidian Integration

The wiki directory works as an Obsidian vault out of the box:
- `[[wikilinks]]` render as clickable links
- Graph View visualizes the knowledge network
- YAML frontmatter powers Dataview queries
- The `raw/assets/` folder holds images referenced via `![[image.png]]`

For best results:
- Set Obsidian's attachment folder to `raw/assets/`
- Enable "Wikilinks" in Obsidian settings
- Install Dataview plugin for queries

## Pitfalls

- **Never modify files in `raw/`** — sources are immutable
- **Always orient first** — read SCHEMA + index + recent log before any operation
- **Always update index.md and log.md** — skipping this makes the wiki degrade
- **Don't create pages for passing mentions** — follow Page Thresholds
- **Frontmatter is required** — it enables search, filtering, and staleness detection
- **Tags must come from the taxonomy** — freeform tags decay into noise
- **Handle contradictions explicitly** — don't silently overwrite
