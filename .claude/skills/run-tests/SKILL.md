# run-tests skill

Auto-invoke this skill whenever you need to run backend tests. Do NOT use background processes or polling loops — always run tests as a **foreground Bash command** so output is captured directly.

## Command

Always use the wrapper script, which ensures the correct venv Python is used:

```bash
cd /home/brandon-coloe/dev/spinshare && backend/scripts/test.sh [args]
```

Never call `pytest` directly. Never use `python -m pytest` without `.venv/bin/python`.

## Common invocations

```bash
# All tests
backend/scripts/test.sh

# Single file
backend/scripts/test.sh app/routers/groups_test.py -v

# Single directory
backend/scripts/test.sh app/routers/ -v

# Specific test class or function
backend/scripts/test.sh app/routers/groups_test.py::TestGroupCreate -v

# Keyword filter
backend/scripts/test.sh -k "TestGroupCreate" -v

# Short output (no verbose)
backend/scripts/test.sh app/routers/groups_test.py -q --tb=short
```

## After tests run

- If any tests **fail**, read the full traceback and fix the underlying issue before moving on.
- Never skip or suppress failing tests without explicit user approval.
- Mark task #6 (or current task) as `completed` only after all tests pass.
