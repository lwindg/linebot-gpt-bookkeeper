<!--
Sync Impact Report:
Version: 1.1.0 (language requirement addition)
Modified Principles: N/A
Added Sections: Communication and Documentation Language (under Development Workflow)
Removed Sections: N/A
Changes from 1.0.0:
  - Added clear language separation: Traditional Chinese for internal planning, English for code artifacts
  - Traditional Chinese (正體中文): spec.md, plan.md, tasks.md, team discussions
  - English: code, comments, PR, commits, diagrams, technical terms, logs, README
Templates Status:
  ✅ plan-template.md - no changes required (language-agnostic structure)
  ✅ spec-template.md - no changes required (language-agnostic structure)
  ✅ tasks-template.md - no changes required (language-agnostic structure)
Follow-up TODOs: None
-->

# LINE Bot GPT Bookkeeper Constitution

## Core Principles

### I. MVP-First Development

Every feature MUST start as a Minimum Viable Product (MVP) that delivers immediate user value.

**Rules**:
- Implement the simplest solution that solves the core user problem
- Each user story must be independently testable and deliverable
- Prioritize P1 features; defer P2/P3 until MVP validates the approach
- No speculative features—only build what users explicitly need

**Rationale**: Rapid validation and iteration beat comprehensive planning. MVP-first ensures we learn fast, fail fast, and deliver value continuously without wasting effort on unused features.

### II. Quality Through Testing

Code quality is non-negotiable, but testing must be pragmatic and focused on user scenarios.

**Rules**:
- Write tests for all user-facing functionality and critical paths
- Focus on integration tests that validate end-to-end user journeys
- Unit tests are optional—use only where complexity demands isolation
- All tests must pass before deployment
- Test coverage targets behavior, not arbitrary percentage goals

**Rationale**: Testing ensures reliability and enables confident refactoring. User-journey tests provide maximum value with minimal overhead compared to exhaustive unit testing.

### III. Simplicity Over Perfection

Avoid over-engineering. Choose the simplest solution that works.

**Rules**:
- Prefer direct implementations over abstraction layers (e.g., no Repository pattern unless proven necessary)
- No premature optimization—optimize only when performance problems are measured
- Avoid adding frameworks, libraries, or patterns "for future flexibility"
- Every complexity decision MUST be justified with concrete current need
- Default to fewer files, fewer layers, fewer dependencies

**Rationale**: Complexity is debt. Simple code is easier to understand, test, and modify. YAGNI (You Aren't Gonna Need It) principles keep development fast and maintenance low.

### IV. Convenience and Developer Experience

Developer efficiency directly impacts delivery speed. Reduce friction everywhere.

**Rules**:
- Automate repetitive tasks (linting, formatting, testing, deployment)
- Clear error messages and logging for rapid debugging
- Local development must work with minimal setup
- Documentation is code comments + runnable quickstart—no separate manual unless necessary
- Use conventions over configuration where possible

**Rationale**: Time spent on tooling setup, debugging cryptic errors, or searching for documentation is time not spent delivering features. Good DX compounds productivity gains.

### V. Usability and User Value

Every decision must optimize for end-user value and usability.

**Rules**:
- User experience takes priority over technical elegance
- Features must solve real user pain points, not theoretical problems
- Gather user feedback early and iterate based on actual usage
- Performance goals must be user-centric (response time, reliability)
- Error handling must be user-friendly, not developer-friendly

**Rationale**: The bot exists to serve users. Technical decisions that don't improve user outcomes are distractions.

## Development Workflow

### Communication and Documentation Language

Specifications and internal design documents MUST use Traditional Chinese (正體中文). All code-related artifacts MUST use English.

**Traditional Chinese (正體中文) - For Internal Planning**:
- Specification documents (spec.md)
- Planning documents (plan.md, research.md, data-model.md)
- Task descriptions (tasks.md)
- Team internal discussions and clarifications
- User stories and acceptance criteria

**English - For Code and External Artifacts**:
- All source code (variable names, function names, class names)
- Code comments and docstrings
- Commit messages
- Pull request titles and descriptions
- Diagrams and flowcharts (use English labels)
- Technical terms and API references
- Error messages and log outputs
- README and external-facing documentation

**Rationale**: Traditional Chinese for internal planning ensures precise requirement capture and fast team understanding. English for all code artifacts ensures international collaboration readiness, tool compatibility, and alignment with global development standards.

### Feature Development Process

1. **Specify**: Define user scenarios and acceptance criteria (spec.md)
2. **Plan**: Research and design technical approach (plan.md + research artifacts)
3. **Clarify**: Resolve underspecified areas before implementation
4. **Task**: Break down into dependency-ordered, independently testable tasks (tasks.md)
5. **Implement**: Execute tasks in priority order (P1 → P2 → P3)
6. **Validate**: Test against original acceptance criteria

**Checkpoint Gates**:
- No implementation without user scenarios defined
- No tasks without technical plan
- No deployment without passing tests

### Test Strategy

- **Integration Tests**: Required for all user journeys (LINE message flow → GPT → response)
- **Contract Tests**: Required for external API integrations (LINE API, OpenAI API)
- **Unit Tests**: Optional—use only for complex business logic requiring isolation
- **Manual Testing**: Required for MVP validation before first release

### Incremental Delivery

- Each user story must be independently deployable
- P1 stories constitute the MVP—deploy and validate before P2/P3
- Use feature flags or branches to isolate incomplete work
- Every deployment must be a releasable increment

## Technical Constraints

### Mandatory Quality Standards

- **Security**: No hardcoded secrets in code (use environment variables)
- **Error Handling**: All external API calls must handle failures gracefully
- **Logging**: Log all user interactions and errors for debugging
- **Performance**: LINE webhook responses must complete within 3 seconds (platform limit)

### Technology Stack

- **Language**: Python 3.11+
- **Framework**: Flask (minimal web framework)
- **APIs**: LINE Messaging API, OpenAI API
- **Testing**: pytest for integration/unit tests
- **Deployment**: Environment-specific (dev/prod) configuration via env vars

### Avoid Unless Justified

- ORM frameworks (use direct database queries if database needed)
- Complex state management (keep bot stateless or use simple session storage)
- Microservices architecture (monolith until proven bottleneck)
- Frontend frameworks (bot interface is LINE app)

## Governance

### Constitution Authority

This constitution supersedes all other development practices and preferences. When in doubt, refer back to the five core principles: MVP-First, Quality Through Testing, Simplicity Over Perfection, Convenience and Developer Experience, and Usability and User Value.

### Compliance Requirements

- All PRs must include justification for any complexity introduced
- Code reviews must explicitly verify: Does this align with constitution principles?
- Any deviation from principles requires documented rationale in PR description
- Constitution violations block merge unless explicitly approved as exception

### Amendment Process

1. Propose amendment with rationale and impact analysis
2. Document what problem the amendment solves
3. Update version following semantic versioning:
   - **MAJOR**: Removing or redefining core principles (backward incompatible)
   - **MINOR**: Adding new principle or expanding existing guidance
   - **PATCH**: Clarifications, wording improvements, typo fixes
4. Propagate changes to all dependent templates (plan, spec, tasks)
5. Commit with changelog in sync impact report

### Complexity Justification Template

When violating simplicity principle, document in plan.md:

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [Pattern/library added] | [Specific current problem] | [Why simpler solution insufficient] |

**Version**: 1.1.0 | **Ratified**: 2025-11-11 | **Last Amended**: 2025-11-11
