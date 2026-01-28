---
phase: 01-amadeus-integration
plan: 03
subsystem: infra
tags: [github-actions, workflow, cron, concurrency, ci-cd, deployment]

# Dependency graph
requires:
  - phase: 01-02
    provides: "amadeus_monitor.py (priority route monitoring coordinator)"
provides:
  - "priority_monitor.yml: GitHub Actions workflow running amadeus_monitor.py every 2 hours"
  - "Concurrency groups preventing git push conflicts between priority and daily workflows"
  - "find_deals.yml updated with shared concurrency group and git pull --rebase"
  - "Phase 1 complete: Full Amadeus integration pipeline deployed"
affects: [02-database-migration, 04-alert-state-machine]

# Tech tracking
tech-stack:
  added: []
  patterns: [GitHub Actions concurrency groups, cron scheduling at offset minutes, git pull --rebase for state file conflicts]

key-files:
  created: [.github/workflows/priority_monitor.yml]
  modified: [.github/workflows/find_deals.yml]

key-decisions:
  - "Cron at :15 past the hour to avoid top-of-hour GitHub Actions congestion"
  - "Shared 'detty-state-commit' concurrency group across both workflows"
  - "cancel-in-progress: false to queue runs instead of dropping monitoring windows"
  - "AMADEUS_HOSTNAME=test initially, switch to production after validation"
  - "[skip ci] in commit messages to prevent infinite workflow triggers"

patterns-established:
  - "Concurrency group pattern: all workflows touching state files share 'detty-state-commit' group"
  - "State commit pattern: git pull --rebase + conditional commit + [skip ci] tag"
  - "Workflow dispatch: all monitoring workflows include workflow_dispatch for manual testing"

# Metrics
duration: 3min
completed: 2026-01-28
---

# Phase 1 Plan 03: GitHub Actions Workflow Summary

**Priority route monitoring workflow running every 2 hours via GitHub Actions cron, with shared concurrency group preventing git push conflicts between priority monitor and daily deal finder**

## Performance

- **Duration:** 3 min
- **Started:** 2026-01-28T03:00:00Z
- **Completed:** 2026-01-28T03:03:00Z
- **Tasks:** 2 (1 auto + 1 human-verify checkpoint)
- **Files created:** 1
- **Files modified:** 1

## Accomplishments
- Created priority_monitor.yml running amadeus_monitor.py every 2 hours at :15 past the hour
- Added shared "detty-state-commit" concurrency group to both priority_monitor.yml and find_deals.yml
- Updated find_deals.yml with git pull --rebase before push to handle concurrent state updates
- All required secrets (Amadeus + email + Google Sheets) passed through to the workflow
- Manual workflow_dispatch trigger available for testing before Amadeus credentials are set
- User verified the complete Amadeus integration system (Plans 01-03) and approved

## Task Commits

Each task was committed atomically:

1. **Task 1: Create priority_monitor.yml and update find_deals.yml** - `831df53` (feat)
2. **Task 2: Human verification checkpoint** - approved (no commit, verification only)

## Files Created/Modified
- `.github/workflows/priority_monitor.yml` - New workflow: 2-hour cron, all Amadeus + email secrets, concurrency group, state file commits with [skip ci]
- `.github/workflows/find_deals.yml` - Added concurrency group "detty-state-commit" and git pull --rebase in commit step

## Decisions Made
- **Cron offset at :15:** Avoids GitHub Actions top-of-hour congestion per research recommendations. The priority monitor runs at H:15 while the daily workflow runs at its existing schedule.
- **cancel-in-progress: false:** Queued runs still execute rather than being cancelled. This ensures no monitoring windows are lost if two runs overlap.
- **AMADEUS_HOSTNAME=test:** Starts in Amadeus test environment. Switch to "production" after validating with test data and confirming API credentials work.
- **[skip ci] commit tag:** State file commits include [skip ci] in the message to prevent infinite workflow trigger loops.
- **git pull --rebase in both workflows:** Handles the case where one workflow pushes state files while another is running, preventing push failures.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required

**External services require manual configuration before the workflow runs successfully:**

1. **Amadeus API credentials:**
   - Go to developers.amadeus.com -> My Self-Service Workspace -> Create New App
   - Get API Key and API Secret
   - Run: `gh secret set AMADEUS_CLIENT_ID` and `gh secret set AMADEUS_CLIENT_SECRET`

2. **Test with manual dispatch:**
   - Go to GitHub repo -> Actions -> "Priority Route Monitor (Amadeus)" -> Run workflow
   - Check logs for route checks, API call count, cross-validation results

3. **Switch to production (after test validation):**
   - Update `AMADEUS_HOSTNAME` in priority_monitor.yml from `test` to `production`

## Phase 1 Completion Status

With Plan 03 complete, Phase 1 (Amadeus Integration) is fully delivered:

| Plan | Deliverable | Status |
|------|------------|--------|
| 01 | amadeus_client.py + price_tracker.py | Complete |
| 02 | cross_validator.py + amadeus_monitor.py | Complete |
| 03 | priority_monitor.yml + find_deals.yml update | Complete |

**Requirements satisfied:**
- DISC-01: Monitor 6 priority routes every 2 hours via Amadeus Cheapest Date Search
- DISC-02: Cross-validate Amadeus prices against Google Flights before alerting (zero single-source alerts)
- DISC-03: Scan full date ranges for priority routes (Cheapest Date Search returns year of prices)

## Next Phase Readiness
- Phase 1 is complete -- all 3 plans executed, all code committed, user verified
- Amadeus API credentials remain the only blocker for live operation (manual setup step)
- Phase 2 (Database Migration) can begin -- Phase 1 validates that multiple data sources work together
- State files (price_cache.json, alert_cooldown.json) will be committed via git until Phase 2 replaces them with Turso

---
*Phase: 01-amadeus-integration*
*Completed: 2026-01-28*
