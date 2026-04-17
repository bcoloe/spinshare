# CLAUDE.md

The following provides some context on the overall `spinshare` project. There are additional CLAUDE.md files located at various levels of the repository providing additional scoped context to those areas.

## What is `spinshare`?
Spinshare is a web application where users can form groups and share albums for review among each other. The albums are selected from user nominations daily. See [README.md](README.md) for more information.

## Guiding Design Principles
`spinshare` is developed based on the following guiding principles:
1. **Prioritize maintenance**: design and code decisions should seek to minimize maintenance costs. This is to say that code should be modular, self-documenting, and clear in its intent, and that design decisions should favor common patterns and tooling.
2. **Defensive backend + restrictive frontend**: the backend routing should favor defensive coding strategies to encourage robustness. At the same time, frontend components and otherwise interaction points should minimize potential for bad input.
3. **Design for scalability**: although expectations are that this will not service large amounts of traffic, design decisions should favor eventual scaling.
4. **Minimal and sleek**: the application need not be bloated in order to be good. Focus on developing core functionality and presenting it in a clean and sleek fashion first. Frontend design shall focus on minimal, clean, and modern designs that use consistent styling.
5. **Test-driven**: a thoroughly tested backend shall ensure code quality and ultimately product safety.

## Supporting Files
| File | Description |
| ---- | ----------- |
| [README.md](README.md) | Developer-facing high level overview of the project. |
| [DESIGN.md](DESIGN.md) | High-level design and technology decisions. |
