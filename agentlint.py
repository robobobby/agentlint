#!/usr/bin/env python3
"""
AgentLint — AGENTS.md Auditor & Scorer

Scores agent context files (AGENTS.md, CLAUDE.md, .cursorrules, etc.)
against a rubric derived from an empirical study of 2,303 context files
(arxiv:2511.12884) and context engineering best practices.

16 instruction categories grouped into 3 pillars:
  - Functional: what the agent needs to DO
  - Safety: what the agent must NOT do or must protect
  - Meta: how the agent should COMMUNICATE and ORGANIZE

Each category is scored 0-10 based on presence and quality of instructions.
Overall grade: A+ through F.

Zero API cost. Pure text analysis. No dependencies beyond Python stdlib.
"""

import re
import json
import sys
import math
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─── Rubric Definition ───────────────────────────────────────────────

@dataclass
class CategoryResult:
    name: str
    slug: str
    pillar: str
    score: float  # 0-10
    max_score: float  # always 10
    signals_found: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    description: str = ""
    prevalence: str = ""  # from the study


CATEGORIES = [
    # ── Functional Pillar ──
    {
        "name": "Build & Run Commands",
        "slug": "build_run",
        "pillar": "functional",
        "description": "Commands to build, install dependencies, start dev servers, and run the project.",
        "prevalence": "62.3% of files include this",
        "weight": 1.0,
        "patterns": [
            (r'(?i)\b(npm|yarn|pnpm|pip|cargo|go|make|gradle|maven)\s+(install|build|run|start|dev|test)', 3, "Package manager commands"),
            (r'(?i)\b(docker|docker-compose|podman)\b', 2, "Container commands"),
            (r'(?i)```\s*(bash|sh|shell|zsh|cmd|powershell)?\s*\n', 2, "Code blocks with shell commands"),
            (r'(?i)\b(build|compile|bundle|deploy)\s+(command|step|instruction)', 2, "Build instructions"),
            (r'(?i)(getting\s+started|quick\s*start|setup|installation)', 1, "Setup section"),
        ],
        "suggestions_if_missing": [
            "Add build/install commands (e.g., `npm install`, `pip install -r requirements.txt`)",
            "Include dev server startup command",
            "Specify the package manager you use",
        ],
    },
    {
        "name": "Implementation Details",
        "slug": "implementation",
        "pillar": "functional",
        "description": "Specific guidance on how code should be written: patterns, idioms, libraries to use.",
        "prevalence": "69.9% of files include this",
        "weight": 1.0,
        "patterns": [
            (r'(?i)\b(use|prefer|always|never|avoid)\b.{0,40}\b(pattern|library|framework|module|function|class|method)\b', 3, "Implementation guidance"),
            (r'(?i)\b(import|require|include|from)\b.{0,30}\b(instead|rather|not)\b', 2, "Import preferences"),
            (r'(?i)\b(singleton|factory|observer|decorator|middleware|hook|provider)\b', 2, "Design patterns mentioned"),
            (r'(?i)\b(do\s+not|don\'t|never|avoid|prefer|always|must)\b', 2, "Directive language"),
            (r'(?i)\b(convention|guideline|rule|standard|practice)\b', 1, "Convention references"),
        ],
        "suggestions_if_missing": [
            "Specify which libraries/frameworks the agent should use",
            "Document coding patterns and idioms preferred in this project",
            "Add 'always/never' rules for common implementation decisions",
        ],
    },
    {
        "name": "Architecture",
        "slug": "architecture",
        "pillar": "functional",
        "description": "System architecture, directory structure, component relationships.",
        "prevalence": "67.7% of files include this",
        "weight": 1.0,
        "patterns": [
            (r'(?i)\b(architect|structure|layout|organization|hierarchy)\b', 2, "Architecture language"),
            (r'(?i)(directory|folder|file)\s+(structure|layout|tree|organization)', 3, "Directory structure"),
            (r'(?i)\b(component|module|service|layer|package|namespace)\b.{0,30}\b(responsible|handles|manages|contains)\b', 3, "Component responsibilities"),
            (r'(?i)(src|lib|app|packages?|modules?|components?)/\w+', 2, "Path references"),
            (r'(?i)\b(monorepo|microservice|serverless|modular|layered|hexagonal|clean\s+arch)\b', 2, "Architecture pattern"),
            (r'(?i)```\s*(text|plaintext|ascii|tree)?\s*\n[├│└─\s\w/.\-]+', 3, "File tree diagram"),
        ],
        "suggestions_if_missing": [
            "Document the project's directory structure with a tree diagram",
            "Describe major components/modules and their responsibilities",
            "Explain the architecture pattern used (monorepo, microservices, etc.)",
        ],
    },
    {
        "name": "Code Style",
        "slug": "code_style",
        "pillar": "functional",
        "description": "Formatting, naming conventions, linting rules, code organization preferences.",
        "prevalence": "~55% of files include this",
        "weight": 0.8,
        "patterns": [
            (r'(?i)\b(eslint|prettier|black|ruff|rubocop|gofmt|rustfmt|clang-format)\b', 3, "Linter/formatter tools"),
            (r'(?i)\b(naming\s+convention|camelCase|snake_case|PascalCase|kebab-case)\b', 3, "Naming conventions"),
            (r'(?i)\b(indent|tab|space|semicolon|quote|bracket)\b.{0,20}\b(style|prefer|use|convention)\b', 2, "Formatting preferences"),
            (r'(?i)\b(type|strict|any)\b.{0,15}\b(check|safe|annotation|hint)\b', 2, "Type safety guidance"),
            (r'(?i)\b(comment|docstring|jsdoc|tsdoc|javadoc)\b', 1, "Documentation style"),
        ],
        "suggestions_if_missing": [
            "Specify your linter/formatter (ESLint, Prettier, Black, etc.)",
            "Document naming conventions (camelCase for variables, PascalCase for classes, etc.)",
            "Add type safety preferences (strict TypeScript, type hints, etc.)",
        ],
    },
    {
        "name": "Testing",
        "slug": "testing",
        "pillar": "functional",
        "description": "Test commands, testing frameworks, coverage expectations, test file conventions.",
        "prevalence": "~50% of files include this",
        "weight": 1.0,
        "patterns": [
            (r'(?i)\b(test|spec|jest|pytest|mocha|vitest|cypress|playwright|rspec)\b', 2, "Testing frameworks"),
            (r'(?i)\b(npm|yarn|pnpm)\s+(test|run\s+test)', 3, "Test run commands"),
            (r'(?i)\b(coverage|assertion|mock|stub|fixture|snapshot)\b', 2, "Testing concepts"),
            (r'(?i)\b(unit\s+test|integration\s+test|e2e|end.to.end)\b', 2, "Test types"),
            (r'(?i)\b(test\s+file|\.test\.|\.spec\.|__tests__|tests/)\b', 2, "Test file conventions"),
            (r'(?i)\b(before|after)\s+(each|all|commit|push|merge)\b.{0,20}\b(test|run)\b', 1, "Test hooks"),
        ],
        "suggestions_if_missing": [
            "Add test run command (e.g., `npm test`, `pytest`)",
            "Specify testing framework and conventions",
            "Document test file naming/location conventions",
            "Set coverage expectations",
        ],
    },
    {
        "name": "Dependencies",
        "slug": "dependencies",
        "pillar": "functional",
        "description": "Dependency management, version constraints, approved/forbidden packages.",
        "prevalence": "~40% of files include this",
        "weight": 0.7,
        "patterns": [
            (r'(?i)\b(dependency|dependencies|package|module)\b.{0,30}\b(manage|install|add|update|upgrade|pin|lock)\b', 3, "Dependency management"),
            (r'(?i)\b(version|semver|pin|lock|freeze|constraint)\b', 1, "Version management"),
            (r'(?i)\b(do\s+not|don\'t|never|avoid)\b.{0,30}\b(install|add|import|require)\b', 3, "Forbidden dependencies"),
            (r'(?i)\b(approved|allowed|preferred|blessed)\b.{0,15}\b(package|library|dependency)\b', 2, "Approved packages"),
            (r'(?i)(package\.json|requirements\.txt|Cargo\.toml|go\.mod|Gemfile|pyproject\.toml)', 2, "Dependency file references"),
        ],
        "suggestions_if_missing": [
            "List approved/preferred libraries for common needs",
            "Specify any forbidden dependencies",
            "Document dependency management approach (lockfiles, version pinning, etc.)",
        ],
    },
    # ── Safety Pillar ──
    {
        "name": "Security",
        "slug": "security",
        "pillar": "safety",
        "description": "Security guidelines, secrets handling, authentication, authorization patterns.",
        "prevalence": "14.5% of files include this (CRITICAL GAP)",
        "weight": 1.2,
        "patterns": [
            (r'(?i)\b(security|secure|vulnerability|exploit|attack|threat)\b', 2, "Security language"),
            (r'(?i)\b(secret|credential|api.key|token|password|auth)\b.{0,30}\b(never|don\'t|do\s+not|avoid|protect|store|manage)\b', 4, "Secrets management"),
            (r'(?i)\b(sanitize|escape|validate|injection|xss|csrf|sqli)\b', 3, "Input validation/injection"),
            (r'(?i)\b(encrypt|hash|ssl|tls|https|certificate)\b', 2, "Encryption"),
            (r'(?i)\b(rbac|permission|authorize|authenticate|oauth|jwt)\b', 2, "Auth patterns"),
            (r'(?i)\b(\.env|environment\s+variable|secret|vault|keychain)\b', 2, "Env/secrets management"),
        ],
        "suggestions_if_missing": [
            "⚠️ CRITICAL: Only 14.5% of context files specify security rules",
            "Add secrets handling rules (never hardcode API keys, use env vars)",
            "Specify input validation requirements",
            "Document authentication/authorization patterns",
            "Add rules for handling user data and PII",
        ],
    },
    {
        "name": "Performance",
        "slug": "performance",
        "pillar": "safety",
        "description": "Performance requirements, optimization guidelines, resource constraints.",
        "prevalence": "14.5% of files include this (CRITICAL GAP)",
        "weight": 1.0,
        "patterns": [
            (r'(?i)\b(performance|optimize|optimization|efficient|latency|throughput)\b', 2, "Performance language"),
            (r'(?i)\b(cache|memoize|debounce|throttle|lazy|eager)\b', 2, "Optimization patterns"),
            (r'(?i)\b(memory|cpu|bandwidth|rate.limit|timeout|concurrent)\b', 2, "Resource constraints"),
            (r'(?i)\b(bundle\s*size|tree.shak|code.split|chunk|minif)\b', 2, "Build optimization"),
            (r'(?i)\b(n\+1|query|index|batch|paginate|stream)\b.{0,20}\b(optim|avoid|use|prefer)\b', 3, "Data access optimization"),
            (r'(?i)\b(benchmark|profil|measure|metric)\b', 1, "Performance measurement"),
        ],
        "suggestions_if_missing": [
            "⚠️ CRITICAL: Only 14.5% of context files specify performance rules",
            "Add performance-sensitive patterns (caching, pagination, lazy loading)",
            "Document resource constraints (memory limits, timeout values)",
            "Specify data access patterns to avoid (N+1 queries, unbounded selects)",
        ],
    },
    {
        "name": "Error Handling",
        "slug": "error_handling",
        "pillar": "safety",
        "description": "Error handling patterns, logging, monitoring, graceful degradation.",
        "prevalence": "~25% of files include this",
        "weight": 0.9,
        "patterns": [
            (r'(?i)\b(error|exception|fault|failure)\b.{0,30}\b(handle|catch|throw|raise|report|log)\b', 3, "Error handling guidance"),
            (r'(?i)\b(try|catch|except|finally|rescue|recover)\b', 1, "Exception keywords"),
            (r'(?i)\b(log|logging|logger|console\.(log|error|warn))\b', 2, "Logging guidance"),
            (r'(?i)\b(graceful|fallback|retry|circuit.breaker|backoff)\b', 3, "Resilience patterns"),
            (r'(?i)\b(monitor|alert|notification|sentry|datadog|newrelic)\b', 2, "Monitoring"),
            (r'(?i)\b(never\s+swallow|always\s+log|propagate|re.?throw)\b', 2, "Error handling rules"),
        ],
        "suggestions_if_missing": [
            "Specify error handling patterns (how to catch, when to throw)",
            "Document logging conventions (levels, format, what to log)",
            "Add resilience patterns (retry, fallback, circuit breaker)",
        ],
    },
    {
        "name": "Environment",
        "slug": "environment",
        "pillar": "safety",
        "description": "Environment configuration, deployment targets, env-specific behavior.",
        "prevalence": "~35% of files include this",
        "weight": 0.7,
        "patterns": [
            (r'(?i)\b(environment|env)\b.{0,20}\b(variable|config|setting|production|staging|development|local)\b', 3, "Environment config"),
            (r'(?i)\b(\.env|dotenv|config\.yml|config\.json)\b', 2, "Config file references"),
            (r'(?i)\b(production|staging|development|local|ci|cd)\b.{0,20}\b(environment|deploy|build|config)\b', 2, "Environment types"),
            (r'(?i)\b(docker|kubernetes|k8s|terraform|aws|gcp|azure|vercel|netlify|heroku)\b', 2, "Infrastructure references"),
            (r'(?i)\b(deploy|deployment|hosting|infrastructure)\b', 1, "Deployment language"),
        ],
        "suggestions_if_missing": [
            "Document environment variables and their purpose",
            "Specify environment-specific behavior (dev vs prod)",
            "Add deployment target and infrastructure notes",
        ],
    },
    # ── Meta Pillar ──
    {
        "name": "Documentation",
        "slug": "documentation",
        "pillar": "meta",
        "description": "Documentation standards, inline comments, README maintenance, API docs.",
        "prevalence": "~45% of files include this",
        "weight": 0.7,
        "patterns": [
            (r'(?i)\b(document|documentation|doc|docs)\b.{0,30}\b(update|maintain|write|add|include)\b', 3, "Documentation guidance"),
            (r'(?i)\b(comment|docstring|jsdoc|tsdoc|readme)\b.{0,30}\b(require|must|always|every|each)\b', 3, "Documentation requirements"),
            (r'(?i)\b(api\s+doc|swagger|openapi|typedoc|sphinx)\b', 2, "API documentation tools"),
            (r'(?i)\b(changelog|release\s+note|migration\s+guide)\b', 2, "Change documentation"),
        ],
        "suggestions_if_missing": [
            "Add documentation standards (when to add comments, docstrings)",
            "Specify README/changelog update requirements",
        ],
    },
    {
        "name": "Communication",
        "slug": "communication",
        "pillar": "meta",
        "description": "How the agent should communicate: commit messages, PR descriptions, response format.",
        "prevalence": "~40% of files include this",
        "weight": 0.8,
        "patterns": [
            (r'(?i)\b(commit\s+message|conventional\s+commit|semantic\s+commit)\b', 3, "Commit message format"),
            (r'(?i)\b(pull\s+request|pr|merge\s+request|mr)\b.{0,30}\b(description|template|format|title)\b', 3, "PR format"),
            (r'(?i)\b(response|output|format|explain|verbose|concise|brief)\b.{0,20}\b(format|style|tone)\b', 2, "Response format"),
            (r'(?i)\b(branch\s+naming|branch\s+name|feature/|fix/|hotfix/)\b', 2, "Branch naming"),
            (r'(?i)\b(git\s+flow|trunk|main\s+branch|develop|release)\b', 1, "Git workflow"),
        ],
        "suggestions_if_missing": [
            "Specify commit message format (Conventional Commits, etc.)",
            "Document PR/MR description requirements",
            "Add branch naming conventions",
        ],
    },
    {
        "name": "Workflow",
        "slug": "workflow",
        "pillar": "meta",
        "description": "Development workflow, CI/CD integration, review process, deployment steps.",
        "prevalence": "~50% of files include this",
        "weight": 0.8,
        "patterns": [
            (r'(?i)\b(workflow|pipeline|ci|cd|ci/cd|github\s+actions|gitlab\s+ci|jenkins)\b', 2, "CI/CD references"),
            (r'(?i)\b(review|approve|merge|deploy)\b.{0,30}\b(process|step|workflow|before|after)\b', 2, "Review process"),
            (r'(?i)\b(pre.commit|post.commit|hook|husky|lint.staged)\b', 2, "Git hooks"),
            (r'(?i)\b(step\s*\d|phase\s*\d|stage\s*\d|first|then|next|finally)\b.{0,30}\b(build|test|deploy|review)\b', 2, "Workflow steps"),
            (r'(?i)\b(automat|manual|trigger|schedule|cron)\b.{0,20}\b(deploy|build|test|check)\b', 1, "Automation"),
        ],
        "suggestions_if_missing": [
            "Document the development workflow (branch → PR → review → merge)",
            "Specify CI/CD pipeline expectations",
            "Add pre-commit or pre-push requirements",
        ],
    },
    {
        "name": "Constraints & Boundaries",
        "slug": "constraints",
        "pillar": "meta",
        "description": "Explicit boundaries on what the agent should NOT do, scope limits, forbidden actions.",
        "prevalence": "~30% of files include this",
        "weight": 1.0,
        "patterns": [
            (r'(?i)\b(never|do\s+not|don\'t|must\s+not|forbidden|prohibited|disallowed)\b', 2, "Prohibition language"),
            (r'(?i)\b(scope|boundary|limit|restrict|confine|only)\b.{0,30}\b(change|modify|edit|touch|access)\b', 3, "Scope boundaries"),
            (r'(?i)\b(ask|confirm|check|verify)\b.{0,20}\b(before|first|prior)\b', 2, "Approval requirements"),
            (r'(?i)\b(out.of.scope|off.limits|read.only|do\s+not\s+modify)\b', 3, "Explicit boundaries"),
            (r'(?i)\b(safe|careful|cautious|conservative)\b.{0,20}\b(change|approach|modify|edit)\b', 1, "Caution language"),
        ],
        "suggestions_if_missing": [
            "Add explicit 'never do X' rules for destructive operations",
            "Specify scope boundaries (which files/dirs are off-limits)",
            "Add approval requirements for sensitive actions",
        ],
    },
    {
        "name": "Examples",
        "slug": "examples",
        "pillar": "meta",
        "description": "Code examples, sample outputs, reference implementations that demonstrate expectations.",
        "prevalence": "~35% of files include this",
        "weight": 0.6,
        "patterns": [
            (r'(?i)\b(example|sample|demo|reference|template)\b', 2, "Example language"),
            (r'```[\w]*\n[\s\S]{20,}?\n```', 3, "Code blocks with content"),
            (r'(?i)\b(good|bad|correct|incorrect|right|wrong)\b.{0,15}\b(example|way|approach)\b', 2, "Good/bad examples"),
            (r'(?i)\b(e\.g\.|for\s+instance|for\s+example|such\s+as)\b', 1, "Inline examples"),
        ],
        "suggestions_if_missing": [
            "Add code examples showing preferred patterns",
            "Include good vs. bad examples for common decisions",
        ],
    },
    {
        "name": "Versioning & Maintenance",
        "slug": "versioning",
        "pillar": "meta",
        "description": "Version management, release process, migration strategies, tech debt handling.",
        "prevalence": "~20% of files include this",
        "weight": 0.5,
        "patterns": [
            (r'(?i)\b(version|release|semver|changelog|migration)\b', 2, "Versioning language"),
            (r'(?i)\b(deprecat|legacy|tech.debt|refactor|upgrade)\b', 2, "Maintenance language"),
            (r'(?i)\b(backward|forward)\s+compat', 2, "Compatibility"),
            (r'(?i)\b(breaking\s+change|major|minor|patch)\b', 2, "Version semantics"),
        ],
        "suggestions_if_missing": [
            "Document versioning strategy (semantic versioning, etc.)",
            "Add guidelines for handling deprecation and tech debt",
        ],
    },
]


# ─── Scoring Engine ──────────────────────────────────────────────────

def score_category(text: str, category: dict) -> CategoryResult:
    """Score a single category against the input text."""
    signals = []
    raw_score = 0.0

    for pattern, points, label in category["patterns"]:
        matches = re.findall(pattern, text)
        if matches:
            count = len(matches)
            # Diminishing returns: first match = full points, subsequent = log bonus
            effective = points + (math.log2(count) * 0.5 if count > 1 else 0)
            raw_score += effective
            signals.append(f"{label} ({count}x)")

    # Normalize to 0-10 scale
    # Max theoretical: sum of all pattern points * ~1.5 for multiple matches
    max_raw = sum(p[1] for p in category["patterns"]) * 1.3
    normalized = min(10.0, (raw_score / max_raw) * 10.0) if max_raw > 0 else 0.0

    # Quality bonus: longer, more detailed sections score higher
    # Check for markdown headers mentioning this category
    header_pattern = r'(?i)^#{1,4}\s+.*\b(' + '|'.join(
        category["slug"].replace('_', '|').split('|')[:2]
    ) + r')\b'
    if re.search(header_pattern, text, re.MULTILINE):
        normalized = min(10.0, normalized + 1.5)

    suggestions = category["suggestions_if_missing"] if normalized < 4.0 else []
    if 4.0 <= normalized < 7.0:
        suggestions = [category["suggestions_if_missing"][0]] if category["suggestions_if_missing"] else []

    return CategoryResult(
        name=category["name"],
        slug=category["slug"],
        pillar=category["pillar"],
        score=round(normalized, 1),
        max_score=10.0,
        signals_found=signals,
        suggestions=suggestions,
        description=category["description"],
        prevalence=category["prevalence"],
    )


def compute_overall_grade(pillar_scores: dict[str, float]) -> str:
    """Compute letter grade from weighted pillar scores."""
    # Safety weighs more because it's the critical gap
    weighted = (
        pillar_scores.get("functional", 0) * 0.35 +
        pillar_scores.get("safety", 0) * 0.40 +
        pillar_scores.get("meta", 0) * 0.25
    )

    if weighted >= 9.0: return "A+"
    if weighted >= 8.0: return "A"
    if weighted >= 7.0: return "A-"
    if weighted >= 6.5: return "B+"
    if weighted >= 6.0: return "B"
    if weighted >= 5.5: return "B-"
    if weighted >= 5.0: return "C+"
    if weighted >= 4.5: return "C"
    if weighted >= 4.0: return "C-"
    if weighted >= 3.5: return "D+"
    if weighted >= 3.0: return "D"
    if weighted >= 2.0: return "D-"
    return "F"


def compute_readability(text: str) -> dict:
    """Compute Flesch Reading Ease score."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = re.findall(r'\b\w+\b', text)

    if not words or not sentences:
        return {"score": 0, "grade": "N/A", "word_count": 0, "sentence_count": 0}

    # Simple syllable counter
    def count_syllables(word):
        word = word.lower()
        count = 0
        vowels = 'aeiouy'
        if word[0] in vowels:
            count += 1
        for i in range(1, len(word)):
            if word[i] in vowels and word[i-1] not in vowels:
                count += 1
        if word.endswith('e'):
            count -= 1
        if word.endswith('le') and len(word) > 2 and word[-3] not in vowels:
            count += 1
        return max(1, count)

    total_syllables = sum(count_syllables(w) for w in words)
    asl = len(words) / len(sentences)  # avg sentence length
    asw = total_syllables / len(words)  # avg syllables per word

    fre = 206.835 - (1.015 * asl) - (84.6 * asw)

    if fre >= 60: grade = "Standard"
    elif fre >= 30: grade = "Difficult"
    else: grade = "Very Difficult"

    return {
        "score": round(fre, 1),
        "grade": grade,
        "word_count": len(words),
        "sentence_count": len(sentences),
    }


def analyze_structure(text: str) -> dict:
    """Analyze markdown structure."""
    lines = text.split('\n')
    headers = {f"h{i}": 0 for i in range(1, 7)}
    header_texts = []

    for line in lines:
        match = re.match(r'^(#{1,6})\s+(.+)', line)
        if match:
            level = len(match.group(1))
            headers[f"h{level}"] += 1
            header_texts.append({"level": level, "text": match.group(2).strip()})

    total_headers = sum(headers.values())
    line_count = len(lines)
    code_blocks = len(re.findall(r'```', text)) // 2

    depth = "shallow"
    if headers["h4"] > 3 or headers["h5"] > 0:
        depth = "deep"
    elif headers["h3"] > 5:
        depth = "moderate"

    return {
        "headers": headers,
        "header_texts": header_texts,
        "total_headers": total_headers,
        "total_lines": line_count,
        "code_blocks": code_blocks,
        "depth": depth,
    }


@dataclass
class AuditResult:
    overall_grade: str
    overall_score: float
    pillar_scores: dict[str, float]
    categories: list[CategoryResult]
    readability: dict
    structure: dict
    top_suggestions: list[str]
    stats: dict

    def to_dict(self) -> dict:
        return {
            "overall_grade": self.overall_grade,
            "overall_score": self.overall_score,
            "pillar_scores": self.pillar_scores,
            "categories": [asdict(c) for c in self.categories],
            "readability": self.readability,
            "structure": self.structure,
            "top_suggestions": self.top_suggestions,
            "stats": self.stats,
        }


def audit(text: str) -> AuditResult:
    """Run a full audit on an agent context file."""
    # Score each category
    results = []
    for cat in CATEGORIES:
        result = score_category(text, cat)
        results.append(result)

    # Compute pillar averages (weighted)
    pillar_scores = {}
    for pillar in ["functional", "safety", "meta"]:
        pillar_cats = [(r, c) for r, c in zip(results, CATEGORIES) if r.pillar == pillar]
        if pillar_cats:
            weighted_sum = sum(r.score * c["weight"] for r, c in pillar_cats)
            weight_total = sum(c["weight"] for _, c in pillar_cats)
            pillar_scores[pillar] = round(weighted_sum / weight_total, 1)
        else:
            pillar_scores[pillar] = 0.0

    overall_score = round(
        pillar_scores.get("functional", 0) * 0.35 +
        pillar_scores.get("safety", 0) * 0.40 +
        pillar_scores.get("meta", 0) * 0.25,
        1
    )
    grade = compute_overall_grade(pillar_scores)

    # Readability and structure
    readability = compute_readability(text)
    structure = analyze_structure(text)

    # Top suggestions: prioritize safety gaps, then low-scoring categories
    all_suggestions = []
    for r in sorted(results, key=lambda x: (0 if x.pillar == "safety" else 1, x.score)):
        for s in r.suggestions:
            all_suggestions.append(s)

    stats = {
        "categories_covered": sum(1 for r in results if r.score >= 3.0),
        "categories_total": len(results),
        "coverage_pct": round(sum(1 for r in results if r.score >= 3.0) / len(results) * 100),
    }

    return AuditResult(
        overall_grade=grade,
        overall_score=overall_score,
        pillar_scores=pillar_scores,
        categories=results,
        readability=readability,
        structure=structure,
        top_suggestions=all_suggestions[:10],
        stats=stats,
    )


# ─── CLI ─────────────────────────────────────────────────────────────

def format_bar(score: float, width: int = 20) -> str:
    """Create a text-based progress bar."""
    filled = int(score / 10.0 * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {score:.1f}/10"


def format_grade_color(grade: str) -> str:
    """Return ANSI-colored grade."""
    colors = {
        "A+": "\033[92m", "A": "\033[92m", "A-": "\033[92m",
        "B+": "\033[93m", "B": "\033[93m", "B-": "\033[93m",
        "C+": "\033[33m", "C": "\033[33m", "C-": "\033[33m",
        "D+": "\033[91m", "D": "\033[91m", "D-": "\033[91m",
        "F": "\033[31m",
    }
    reset = "\033[0m"
    color = colors.get(grade, "")
    return f"{color}{grade}{reset}"


def print_report(result: AuditResult):
    """Print a formatted audit report to stdout."""
    reset = "\033[0m"
    bold = "\033[1m"
    dim = "\033[2m"

    print()
    print(f"{bold}╔══════════════════════════════════════════════════════════╗{reset}")
    print(f"{bold}║              AgentLint Audit Report                     ║{reset}")
    print(f"{bold}╚══════════════════════════════════════════════════════════╝{reset}")
    print()

    # Overall grade
    print(f"  Overall Grade:  {format_grade_color(result.overall_grade)}")
    print(f"  Overall Score:  {result.overall_score:.1f}/10")
    print(f"  Coverage:       {result.stats['categories_covered']}/{result.stats['categories_total']} categories ({result.stats['coverage_pct']}%)")
    print()

    # Readability
    r = result.readability
    print(f"  {bold}Readability{reset}")
    print(f"    Flesch Score: {r['score']} ({r['grade']})")
    print(f"    Words: {r['word_count']}  |  Sentences: {r['sentence_count']}")
    print()

    # Structure
    s = result.structure
    print(f"  {bold}Structure{reset}")
    print(f"    Lines: {s['total_lines']}  |  Headers: {s['total_headers']}  |  Code blocks: {s['code_blocks']}")
    print(f"    Depth: {s['depth']}")
    print()

    # Pillar scores
    pillar_names = {"functional": "Functional", "safety": "Safety", "meta": "Meta"}
    pillar_icons = {"functional": "🔧", "safety": "🛡️", "meta": "📋"}
    print(f"  {bold}Pillar Scores{reset}")
    for pillar, score in result.pillar_scores.items():
        icon = pillar_icons.get(pillar, "")
        name = pillar_names.get(pillar, pillar)
        print(f"    {icon} {name:12s} {format_bar(score)}")
    print()

    # Category details
    for pillar in ["functional", "safety", "meta"]:
        icon = pillar_icons.get(pillar, "")
        name = pillar_names.get(pillar, pillar)
        print(f"  {bold}{icon} {name} Categories{reset}")
        print()

        for cat in result.categories:
            if cat.pillar != pillar:
                continue
            # Score color
            if cat.score >= 7:
                sc = "\033[92m"
            elif cat.score >= 4:
                sc = "\033[93m"
            else:
                sc = "\033[91m"

            print(f"    {cat.name}")
            print(f"      Score: {sc}{cat.score:.1f}/10{reset}  {format_bar(cat.score)}")
            if cat.signals_found:
                signals_str = ", ".join(cat.signals_found[:5])
                print(f"      {dim}Found: {signals_str}{reset}")
            if cat.suggestions:
                for sug in cat.suggestions[:2]:
                    print(f"      💡 {sug}")
            print()

    # Top suggestions
    if result.top_suggestions:
        print(f"  {bold}Top Suggestions{reset}")
        for i, sug in enumerate(result.top_suggestions[:8], 1):
            print(f"    {i}. {sug}")
        print()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="AgentLint — Audit and score agent context files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  agentlint AGENTS.md                    Audit a file
  agentlint CLAUDE.md --json             Output as JSON
  agentlint .cursorrules --json --pretty Pretty JSON output
  cat AGENTS.md | agentlint -            Read from stdin
        """,
    )
    parser.add_argument("file", nargs="?", default="-", help="File to audit (- for stdin)")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    parser.add_argument("--html", action="store_true", help="Output as HTML report")
    args = parser.parse_args()

    # Read input
    if args.file == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found", file=sys.stderr)
            sys.exit(1)

    if not text.strip():
        print("Error: Empty input", file=sys.stderr)
        sys.exit(1)

    # Run audit
    result = audit(text)

    # Output
    if args.json:
        indent = 2 if args.pretty else None
        print(json.dumps(result.to_dict(), indent=indent))
    elif args.html:
        print(generate_html_report(result))
    else:
        print_report(result)


def generate_html_report(result: AuditResult) -> str:
    """Generate a standalone HTML audit report."""
    grade_colors = {
        "A+": "#22c55e", "A": "#22c55e", "A-": "#22c55e",
        "B+": "#eab308", "B": "#eab308", "B-": "#eab308",
        "C+": "#f97316", "C": "#f97316", "C-": "#f97316",
        "D+": "#ef4444", "D": "#ef4444", "D-": "#ef4444",
        "F": "#dc2626",
    }
    grade_color = grade_colors.get(result.overall_grade, "#6b7280")

    pillar_labels = {"functional": "Functional", "safety": "Safety", "meta": "Meta"}
    pillar_icons = {"functional": "🔧", "safety": "🛡️", "meta": "📋"}

    # Build category HTML
    categories_html = ""
    for pillar in ["functional", "safety", "meta"]:
        cats = [c for c in result.categories if c.pillar == pillar]
        icon = pillar_icons.get(pillar, "")
        label = pillar_labels.get(pillar, pillar)
        pscore = result.pillar_scores.get(pillar, 0)

        categories_html += f'<div class="pillar-section"><h3>{icon} {label} <span class="pillar-score">{pscore}/10</span></h3>'
        for cat in cats:
            bar_pct = cat.score / 10.0 * 100
            if cat.score >= 7:
                bar_color = "#22c55e"
            elif cat.score >= 4:
                bar_color = "#eab308"
            else:
                bar_color = "#ef4444"

            signals_html = ""
            if cat.signals_found:
                signals_html = '<div class="signals">' + ", ".join(cat.signals_found[:5]) + '</div>'

            suggestions_html = ""
            if cat.suggestions:
                suggestions_html = '<ul class="suggestions">'
                for s in cat.suggestions[:3]:
                    suggestions_html += f'<li>{s}</li>'
                suggestions_html += '</ul>'

            categories_html += f'''
            <div class="category">
                <div class="category-header">
                    <span class="category-name">{cat.name}</span>
                    <span class="category-score" style="color: {bar_color}">{cat.score}/10</span>
                </div>
                <div class="bar-track"><div class="bar-fill" style="width: {bar_pct}%; background: {bar_color}"></div></div>
                <div class="category-desc">{cat.description}</div>
                <div class="prevalence">{cat.prevalence}</div>
                {signals_html}
                {suggestions_html}
            </div>'''
        categories_html += '</div>'

    # Build suggestions HTML
    suggestions_html = ""
    for i, s in enumerate(result.top_suggestions[:8], 1):
        suggestions_html += f'<li>{s}</li>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>AgentLint Audit Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif; background: #0a0a0f; color: #e5e5e5; line-height: 1.6; }}
.container {{ max-width: 800px; margin: 0 auto; padding: 2rem 1rem; }}

.header {{ text-align: center; margin-bottom: 2rem; }}
.header h1 {{ font-size: 1.5rem; font-weight: 600; color: #fff; letter-spacing: -0.02em; }}
.header p {{ color: #888; font-size: 0.85rem; margin-top: 0.25rem; }}

.grade-card {{
    background: linear-gradient(135deg, #18181b 0%, #1a1a2e 100%);
    border: 1px solid #2a2a3e;
    border-radius: 12px;
    padding: 2rem;
    text-align: center;
    margin-bottom: 1.5rem;
}}
.grade {{ font-size: 4rem; font-weight: 800; color: {grade_color}; line-height: 1; }}
.grade-label {{ color: #888; font-size: 0.85rem; margin-top: 0.5rem; }}
.grade-score {{ color: #ccc; font-size: 1.1rem; margin-top: 0.25rem; }}

.stats-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 0.75rem;
    margin-bottom: 1.5rem;
}}
.stat-card {{
    background: #18181b;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 1rem;
    text-align: center;
}}
.stat-value {{ font-size: 1.4rem; font-weight: 700; color: #fff; }}
.stat-label {{ font-size: 0.75rem; color: #888; margin-top: 0.15rem; }}

.pillar-section {{ margin-bottom: 1.5rem; }}
.pillar-section h3 {{ font-size: 1.1rem; font-weight: 600; color: #fff; margin-bottom: 0.75rem; border-bottom: 1px solid #2a2a3e; padding-bottom: 0.5rem; }}
.pillar-score {{ float: right; color: #888; font-weight: 400; font-size: 0.9rem; }}

.category {{
    background: #18181b;
    border: 1px solid #2a2a3e;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.5rem;
}}
.category-header {{ display: flex; justify-content: space-between; align-items: center; }}
.category-name {{ font-weight: 600; font-size: 0.95rem; }}
.category-score {{ font-weight: 700; font-size: 0.95rem; }}
.bar-track {{ height: 4px; background: #2a2a3e; border-radius: 2px; margin: 0.5rem 0; }}
.bar-fill {{ height: 100%; border-radius: 2px; transition: width 0.5s ease; }}
.category-desc {{ font-size: 0.8rem; color: #888; }}
.prevalence {{ font-size: 0.75rem; color: #666; font-style: italic; margin-top: 0.15rem; }}
.signals {{ font-size: 0.8rem; color: #a3a3a3; margin-top: 0.35rem; }}
.suggestions {{ list-style: none; margin-top: 0.5rem; }}
.suggestions li {{ font-size: 0.8rem; color: #fbbf24; padding: 0.15rem 0; }}
.suggestions li::before {{ content: "💡 "; }}

.suggestions-section {{ background: #18181b; border: 1px solid #2a2a3e; border-radius: 8px; padding: 1.25rem; margin-top: 1.5rem; }}
.suggestions-section h3 {{ font-size: 1rem; font-weight: 600; margin-bottom: 0.75rem; }}
.suggestions-section ol {{ padding-left: 1.25rem; }}
.suggestions-section li {{ font-size: 0.85rem; color: #ccc; padding: 0.2rem 0; }}

.footer {{ text-align: center; margin-top: 2rem; color: #555; font-size: 0.75rem; }}
.footer a {{ color: #888; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>AgentLint</h1>
        <p>Agent Context File Audit Report</p>
    </div>

    <div class="grade-card">
        <div class="grade">{result.overall_grade}</div>
        <div class="grade-score">{result.overall_score}/10</div>
        <div class="grade-label">{result.stats['categories_covered']}/{result.stats['categories_total']} categories covered ({result.stats['coverage_pct']}%)</div>
    </div>

    <div class="stats-row">
        <div class="stat-card">
            <div class="stat-value">{result.readability['word_count']}</div>
            <div class="stat-label">Words</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{result.structure['total_headers']}</div>
            <div class="stat-label">Sections</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{result.structure['code_blocks']}</div>
            <div class="stat-label">Code Blocks</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{result.readability['score']}</div>
            <div class="stat-label">Readability (FRE)</div>
        </div>
    </div>

    {categories_html}

    <div class="suggestions-section">
        <h3>Top Suggestions</h3>
        <ol>{suggestions_html}</ol>
    </div>

    <div class="footer">
        <p>Powered by AgentLint — based on research from <a href="https://arxiv.org/abs/2511.12884" target="_blank">arxiv:2511.12884</a></p>
        <p>Rubric derived from empirical study of 2,303 agent context files</p>
    </div>
</div>
</body>
</html>'''


if __name__ == "__main__":
    main()
