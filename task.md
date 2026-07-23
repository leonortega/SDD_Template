# Task Flow — Implementation Tracker

This file tracks the implementation flow for the current task. Each task is checked off as completed.

## Review Workload Forecast

- **Estimated changed lines:** < 50
- **400-line budget risk:** None
- **Chained PR:** No
- **Delivery strategy:** Single unit
- **Suggested work units:** 1

---

## Tasks

- [x] Read OpenSpec official commands.md and workflows.md (propose → explore → apply → verify → archive)
- [x] Map OpenSpec commands to repository dev-flow skills
- [x] Verify explore skill (`dev-flow-explore-change`) mirrors `/opsx:explore`
- [x] Verify propose skill (`dev-flow-propose-change`) mirrors `/opsx:propose`
- [x] Verify apply skill (`dev-flow-apply-change`) mirrors `/opsx:apply`
- [x] Verify verify skill (`dev-flow-verify-change`) mirrors `/opsx:verify`
- [x] Verify archive skill (`dev-flow-archive-change`) mirrors `/opsx:archive`
- [x] Confirm verify → apply loopback is supported (CRITICAL issues → fix before archive)
- [x] Document OpenSpec → dev-flow command mapping in task.md
- [x] Verify openspec-* raw skills also match
- [x] Commit and push task.md

## OpenSpec → Dev-Flow Command Mapping

| OpenSpec Command | Dev-Flow Skill | Status |
|---|---|---|
| `/opsx:explore` | `dev-flow-explore-change/SKILL.md` | ✅ Matches |
| `/opsx:propose` | `dev-flow-propose-change/SKILL.md` | ✅ Matches |
| `/opsx:apply` | `dev-flow-apply-change/SKILL.md` | ✅ Matches |
| `/opsx:verify` | `dev-flow-verify-change/SKILL.md` | ✅ Matches |
| `/opsx:archive` | `dev-flow-archive-change/SKILL.md` | ✅ Matches |
| `/opsx:sync` | `openspec-sync-specs/SKILL.md` | ✅ Integrated |
| `/opsx:update` | `openspec-update-change/SKILL.md` | ✅ Available |

## User Flow

```
/opsx:propose ───────────────────────────────────────┐
       │                                               │
       ▼                                               │
/opsx:explore (optional, before or during change)      │
       │                                               │
       ▼                                               │
/opsx:apply ───────────────────────────────────────────┤
       │                                               │
       ▼                                               │
/opsx:verify ─── CRITICAL issues? ───► back to apply   │
       │                                               │
       │  (no critical issues)                         │
       ▼                                               │
/opsx:archive ─────────────────────────────────────────┘
```

## Verify → Apply Loopback

- **CRITICAL issues** (incomplete tasks, missing requirements): Must fix before archive → route to apply
- **WARNING issues** (spec/design divergences): Can archive with warnings
- **All clear**: Ready for archive