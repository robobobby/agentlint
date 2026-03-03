# AgentLint

Audit and score your AGENTS.md, CLAUDE.md, `.cursorrules`, or any agent context file against a research-backed rubric.

## What it does

Scores your agent context file across **16 categories** grouped into 3 pillars:

- **🔧 Functional** (35%): Build commands, implementation details, architecture, code style, testing, dependencies
- **🛡️ Safety** (40%): Security, performance, error handling, environment
- **📋 Meta** (25%): Documentation, communication, workflow, constraints, examples, versioning

Safety weighs the most because the [research](https://arxiv.org/abs/2511.12884) found that only **14.5%** of context files specify security or performance rules. That's a problem.

## Quick Start

### CLI (Python)

```bash
# Score a file
python3 agentlint.py AGENTS.md

# JSON output
python3 agentlint.py CLAUDE.md --json --pretty

# HTML report
python3 agentlint.py .cursorrules --html > report.html

# From stdin
cat AGENTS.md | python3 agentlint.py -
```

### Web UI

Open `web/index.html` in your browser. Paste, audit, done. Everything runs client-side.

## Scoring

Each category gets 0-10 based on:
- **Pattern matching**: Looks for relevant keywords, commands, and structural markers
- **Signal density**: More instances = higher confidence (with diminishing returns)
- **Header bonus**: Dedicated sections for a topic score higher

Overall grade: A+ through F, derived from weighted pillar averages.

## The 16 Categories

| # | Category | Pillar | Study Prevalence |
|---|----------|--------|-----------------|
| 1 | Build & Run Commands | Functional | 62.3% |
| 2 | Implementation Details | Functional | 69.9% |
| 3 | Architecture | Functional | 67.7% |
| 4 | Code Style | Functional | ~55% |
| 5 | Testing | Functional | ~50% |
| 6 | Dependencies | Functional | ~40% |
| 7 | Security | Safety | **14.5%** |
| 8 | Performance | Safety | **14.5%** |
| 9 | Error Handling | Safety | ~25% |
| 10 | Environment | Safety | ~35% |
| 11 | Documentation | Meta | ~45% |
| 12 | Communication | Meta | ~40% |
| 13 | Workflow | Meta | ~50% |
| 14 | Constraints & Boundaries | Meta | ~30% |
| 15 | Examples | Meta | ~35% |
| 16 | Versioning & Maintenance | Meta | ~20% |

## Research Basis

The rubric is derived from ["Agent READMEs: An Empirical Study of Context Files for Agentic Coding"](https://arxiv.org/abs/2511.12884) (2025), which analyzed 2,303 context files from 1,925 repositories across Claude Code, OpenAI Codex, and GitHub Copilot.

Key finding: developers focus heavily on making agents *functional* (build commands, implementation details) but rarely set *guardrails* for security and performance. AgentLint highlights this gap.

## Zero Dependencies

- **CLI**: Pure Python 3.10+ stdlib. No pip install needed.
- **Web**: Single HTML file with inline JS. No build step. No framework.

## License

MIT
