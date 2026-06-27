# QA Report — main..HEAD — 2026-06-26

## Summary

**Backend:** 230 passing, 0 failing  
**Frontend (Jest):** 53 passing, 0 failing  
**E2E (Playwright):** 78 passing, 4 skipped, 0 failing  
**Bugs found:** 0  
**New tests written:** 28 (across 2 new files)

---

## Commits in scope (`git log main..HEAD`)

| SHA | Message |
|-----|---------|
| 01b1f04 | test: add mobile nav functional tests — hamburger + drawer coverage |
| 6f0d27b | feat: hamburger menu + side drawer for mobile navigation |
| ad31c7c | ci: add TEST_MODE + AUTH_TEST_MODE env vars to playwright job |
| a4feadf | fix: resolve all e2e test failures |
| 9724808 | feat: full e2e coverage — nightly job API + authenticated dashboard UI |
| 56aedf1 | feat: unread tracking — NEW badge, delta strip, PATCH /watchlist/{ticker}/read |

---

## New Tests Written

| File | Tests added |
|------|-------------|
| `backend/tests/test_watchlist_read.py` | 6 tests — `PATCH /watchlist/{ticker}/read` happy path, 404, 401, DB write, no-analysis no-op, user scoping |
| `backend/tests/test_unread_digest.py` | 22 tests — 8 digest integration tests (never-read, no-analysis, already-read, verdict-flip, no-change, days_since_read) + 13 `_change_summary()` unit tests covering all 7 signal triggers |

---

## Bugs Found

None.

---

## Coverage Gaps (not auto-covered)

- `_change_summary()` orphan-prev path (line 83–85): `last_read_analysis_id` points to a deleted analysis — covered by the router but no isolated unit test
- Frontend `handleMarkRead()` optimistic update — no Jest test; verified visually via Playwright screenshots
- Delta strip clearing on collapse (`onToggle` + `setDigest`) — no Jest test

---

## All Test Results

### Backend — `pytest tests/ -v`
```
230 passed, 256 warnings in 27.68s
```

### Frontend — `npm test`
```
PASS __tests__/filter.test.ts
PASS __tests__/utils.test.ts
PASS __tests__/basic.test.ts

Test Suites: 3 passed, 3 total
Tests:       53 passed, 53 total
Time:        0.476s
```

### E2E — `npm run test:e2e`
```
78 passed, 4 skipped (30.9s)
Skipped: tests requiring seeded DB data, conditionally skipped when seed not present
```
