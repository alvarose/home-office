# Waiting for you

Everything that waits on the user: decisions, pushes, merges, staging checks, environment, data. One row per thing, written by `ho.py waiting add` (never by hand). The user answers in chat; the conductor records it with `ho.py waiting answer`. Answered rows move to "Answered" and are never deleted: they are how the waiting time is measured (`ho.py waiting stats`).

## Open

| id | since | project | work | kind | action | blocks |
|---|---|---|---|---|---|---|

## Answered

| id | since | project | work | kind | action | blocks | answered | answer | acted |
|---|---|---|---|---|---|---|---|---|---|
