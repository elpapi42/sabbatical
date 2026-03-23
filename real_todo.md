3. ## 14. MEDIUM — Assistant Tool Logic Duplicates API Endpoint Logic

**Specs affected:** 9_implementation (assistant/tools.py, routers/)

**Issue:** The Assistant's tools (`create_organization`, `add_agent`, `create_task`) perform "the same validation + DB insert as the API endpoint." This means business logic (validation, state transitions, error handling) is duplicated in two places. When a rule changes, both must be updated.

**POV:** Technical — DRY violation, maintenance hazard.

**Recommendation:** Have the Assistant's tools call the API endpoints internally (via `httpx` to localhost, or better, by importing and calling the router handler functions directly as a shared service layer). Extract the business logic into a service layer (`services/organizations.py`, `services/agents.py`, etc.) that both routers and Assistant tools call. Reasoning: a shared service layer is the standard pattern for this and prevents divergence between the two code paths.
