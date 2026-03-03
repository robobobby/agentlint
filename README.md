# AgentLint

Audit and score your AGENTS.md, CLAUDE.md, `.cursorrules`, or any agent context file against a research-backed rubric.

**[Try it live →](https://robobobby.github.io/agentlint)**

## What it does

Scores your agent context file across **16 categories** grouped into 3 pillars:

- **🔧 Functional** (35%): Build commands, implementation details, architecture, code style, testing, dependencies
- **🛡️ Safety** (40%): Security, performance, error handling, environment
- **📋 Meta** (25%): Documentation, communication, workflow, constraints, examples, versioning

Safety weighs the most because [research](https://arxiv.org/abs/2511.12884) found that only **14.5%** of 2,303 context files specify security or performance rules.

## Quick Start

### Web UI

Visit **[robobobby.github.io/agentlint](https://robobobby.github.io/agentlint)** and paste your file. Everything runs client-side, nothing leaves your browser.

You can also fetch directly from a GitHub URL (paste any repo's blob URL and it converts to raw automatically).

### CLI (Python, zero dependencies)

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

### Install via pip

```bash
pip install agentlint
agentlint AGENTS.md
```

## Scoring

Each category gets 0-10 based on:
- **Pattern matching**: Relevant keywords, commands, and structural markers
- **Signal density**: More instances raise confidence (with diminishing returns via log2)
- **Header bonus**: Dedicated sections score higher than scattered mentions

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

## Badge

After auditing, grab a badge for your README:

```markdown
[![AgentLint: A](https://img.shields.io/badge/AgentLint-A%20(8.2%2F10)-brightgreen)](https://github.com/robobobby/agentlint)
```

The web UI generates the badge markdown automatically.

## Research Basis

The rubric is derived from ["Agent READMEs: An Empirical Study of Context Files for Agentic Coding"](https://arxiv.org/abs/2511.12884) (2025), which analyzed 2,303 context files from 1,925 repositories across Claude Code, OpenAI Codex, and GitHub Copilot.

## Zero Dependencies

- **CLI**: Pure Python 3.10+ stdlib. No pip install needed.
- **Web**: Single HTML file. No build step. No framework. No tracking.

## License

MIT
