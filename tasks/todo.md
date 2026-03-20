# Meridian TODO

## v1.1 Polish & Reliability (shipped 2026-03-20)
- [x] Phase 5: Lint Cleanup
- [x] Phase 6: Nyquist Compliance
- [x] Phase 7: Roadmap Automation

## v1.2 Feature Parity (shipped 2026-03-20)
- [x] Phase 8: Quick Workflow — /fast, /do, /note, /next
- [x] Phase 9: Quality Gates — regression, coverage, stubs, UAT audit
- [x] Phase 10: Session Intelligence — handoff, debug KB, decision IDs
- [x] Phase 11: Security & PR Hygiene — security module, /pr-branch

## v1.3 Advanced Capabilities (shipped 2026-03-20)
- [x] Phase 12: Developer Experience — /profile, /seed, discussion log
- [x] Phase 13: Execution Resilience — interactive executor, node repair
- [x] Phase 14: Agent Intelligence — MCP discovery, context awareness

## v1.4 Feature Expansion
- [ ] Phase 15: Execution Learning — `/meridian:learn` (learning table, auto-capture, prompt injection)
- [ ] Phase 16: Edit Scope Lock — `/meridian:freeze` (directory lock via settings, advisory safety)
- [ ] Phase 17: Structured Retrospective — `/meridian:retro` (velocity trends, shipping streaks, action items)
- [ ] Phase 18: Office Hours Mode — `--deep` flag on `/meridian:plan` (5 forcing questions)
- [ ] Phase 19: Session Awareness — PID-based concurrent session detection
- [ ] Phase 20: Cross-Model Review — `--cross-model` flag on `/meridian:review` (secondary AI CLI)

### Implementation Notes
- **Schema v5 migration**: learning table + review.model column (Phases 15 & 20)
- **Phases 15-16**: Ship first (highest value)
- **Phases 17-19**: Independent, can parallelize
- **Phase 20**: Stretch — requires secondary CLI (codex/gemini/aider)

## Stats
- Tests: 740 passing
- Python modules: 24 in scripts/
- Slash commands: 29
- Milestones shipped: v1.0, v1.1, v1.2, v1.3
