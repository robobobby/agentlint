#!/usr/bin/env python3
"""Tests for AgentLint scoring engine."""

import sys
sys.path.insert(0, '.')
from agentlint import audit, score_category, compute_readability, analyze_structure, CATEGORIES


def test_empty_file():
    result = audit("")
    # Empty should fail, but audit() requires non-empty via CLI
    # Direct call with whitespace
    result = audit("   \n  \n  ")
    assert result.overall_grade in ("F", "D-"), f"Empty file should score F or D-, got {result.overall_grade}"
    assert result.overall_score < 2.0
    print("✅ Empty file → F/D-")


def test_minimal_file():
    text = """# AGENTS.md
## Setup
Run `npm install` to install dependencies.
Run `npm run dev` to start the dev server.
"""
    result = audit(text)
    assert result.stats["categories_covered"] >= 1
    assert result.overall_score < 5.0
    print(f"✅ Minimal file → {result.overall_grade} ({result.overall_score}/10), {result.stats['categories_covered']} categories")


def test_comprehensive_file():
    text = """# AGENTS.md

## Architecture
```
src/
├── api/         # Route handlers
├── services/    # Business logic
├── models/      # Database models
└── utils/       # Shared utilities
```

## Build & Run
```bash
npm install
npm run dev
npm run build
docker-compose up
```

## Code Style
- Use ESLint + Prettier
- Naming: camelCase for variables, PascalCase for classes
- Strict TypeScript (never use `any`)

## Testing
```bash
npm test
npm run test:coverage
```
Use Jest for unit tests. Test files: `*.test.ts`.

## Security
- NEVER hardcode API keys or secrets
- Use environment variables via dotenv
- Validate all user input with Zod
- Use helmet for HTTP security headers
- JWT tokens expire in 1 hour

## Performance
- Use Redis caching for expensive queries
- Paginate all list endpoints (max 100 items)
- Lazy load heavy modules
- Rate limit: 100 req/min per user

## Error Handling
- Use custom AppError class
- Always log errors with context
- Never swallow exceptions
- Use circuit breaker for external calls

## Environment
- `.env.local` for development
- Three environments: development, staging, production
- Deploy via GitHub Actions to AWS ECS

## Communication
- Conventional Commits format
- Branch naming: feature/JIRA-123-description
- PR must include: what, why, how to test

## Workflow
1. Create branch from main
2. Implement + write tests
3. Run lint and test locally
4. Open PR, get review
5. Squash merge to main

## Constraints
- Do NOT modify database schemas directly
- Do NOT access files outside src/
- Never delete data, use soft deletes
- Ask before modifying CI/CD config

## Examples

### Good
```typescript
async function getUser(id: string): Promise<User> {
  const user = await prisma.user.findUnique({ where: { id } });
  if (!user) throw new AppError('Not found', 404);
  return user;
}
```
"""
    result = audit(text)
    assert result.overall_score >= 4.0, f"Comprehensive file should score >= 4.0, got {result.overall_score}"
    assert result.stats["categories_covered"] >= 8
    assert result.pillar_scores["safety"] >= 5.0
    print(f"✅ Comprehensive file → {result.overall_grade} ({result.overall_score}/10), {result.stats['categories_covered']} categories")


def test_security_gap_detection():
    """Files without security rules should flag it."""
    text = """# AGENTS.md
## Build
npm install && npm run dev

## Testing
npm test

## Code Style
Use Prettier and ESLint.
"""
    result = audit(text)
    security_cat = next(c for c in result.categories if c.slug == "security")
    assert security_cat.score < 3.0, f"No security content should score low, got {security_cat.score}"
    assert any("CRITICAL" in s for s in security_cat.suggestions), "Should suggest security rules"
    print(f"✅ Security gap detected (score: {security_cat.score})")


def test_readability():
    text = "This is a simple sentence. This is another one. Short words are easy."
    r = compute_readability(text)
    assert r["score"] > 50, f"Simple text should be readable, got {r['score']}"
    assert r["word_count"] >= 10
    print(f"✅ Readability: {r['score']} ({r['grade']})")


def test_structure():
    text = """# Title
## Section One
### Subsection
## Section Two
### Sub A
### Sub B
#### Deep
"""
    s = analyze_structure(text)
    assert s["headers"]["h1"] == 1
    assert s["headers"]["h2"] == 2
    assert s["headers"]["h3"] == 3
    assert s["headers"]["h4"] == 1
    assert s["depth"] in ("shallow", "moderate", "deep")
    print(f"✅ Structure: {s['total_headers']} headers, depth={s['depth']}")


def test_each_category_independently():
    """Verify each category can score > 0 with appropriate input."""
    test_texts = {
        "build_run": "```bash\nnpm install && npm run dev\n```\nRun `docker-compose up` for setup.",
        "implementation": "Always use hooks. Never use class components. Prefer the factory pattern. Must follow conventions.",
        "architecture": "The directory structure is: src/components/ for UI, src/services/ for business logic. Monorepo architecture.",
        "code_style": "Use ESLint with Prettier. Follow camelCase naming convention. Strict TypeScript.",
        "testing": "Run `npm test` for unit tests. Use Jest with fixtures. Test files go in __tests__/.",
        "dependencies": "Never install lodash. Pin versions. Approved packages: axios, zod.",
        "security": "Never hardcode API keys. Validate input. Use JWT authentication. Encrypt at rest.",
        "performance": "Cache expensive queries. Debounce user input. Optimize bundle size with tree shaking.",
        "error_handling": "Catch all errors. Log with context. Use retry with exponential backoff. Monitor via Sentry.",
        "environment": "Use .env files. Production on AWS. Staging environment for QA.",
        "documentation": "Always add JSDoc comments. Every function must have docstring. Update README documentation when adding features. Maintain the changelog.",
        "communication": "Use Conventional Commits. Branch naming: feature/JIRA-123. PR must describe what and why.",
        "workflow": "CI/CD via GitHub Actions. Pre-commit hooks with Husky. Deploy after review.",
        "constraints": "Never modify the database directly. Do not edit files outside src/. Ask before deploying.",
        "examples": "For example, a good approach:\n```typescript\nconst result = await service.process(input);\nif (!result) throw new Error('Failed');\n```",
        "versioning": "Follow semantic versioning. Document breaking changes in changelog. Handle deprecated APIs.",
    }

    for slug, text in test_texts.items():
        cat = next(c for c in CATEGORIES if c["slug"] == slug)
        result = score_category(text, cat)
        assert result.score > 0, f"Category '{slug}' should score > 0 with test text, got {result.score}"
        print(f"  ✅ {cat['name']}: {result.score}/10 ({len(result.signals_found)} signals)")


def test_json_output():
    result = audit("# Test\n## Build\nnpm install\n## Security\nNever hardcode secrets.")
    d = result.to_dict()
    assert "overall_grade" in d
    assert "categories" in d
    assert len(d["categories"]) == 16
    print("✅ JSON serialization works")


if __name__ == "__main__":
    print("\n🔍 AgentLint Test Suite\n")

    test_empty_file()
    test_minimal_file()
    test_comprehensive_file()
    test_security_gap_detection()
    test_readability()
    test_structure()

    print("\n📋 Individual category tests:")
    test_each_category_independently()

    print()
    test_json_output()

    print("\n✅ All tests passed!\n")
