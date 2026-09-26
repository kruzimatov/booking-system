# AI usage log

One row per notable moment: what I asked, what the AI produced, what I checked or changed, and why.

| Phase | What I asked | What AI produced | What I checked or changed | Why |
|---|---|---|---|---|
| Planning | Architecture plan for the booking task | First plan: schema, endpoints, `SELECT FOR UPDATE` on booking rows against double booking | Asked for a senior-level review of the plan; 34 issues were found and fixed before any code | Locking booking rows does not stop two inserts into an empty slot (no rows exist to lock), so the lock moved to the provider row and exclusion constraints became the guarantee |
