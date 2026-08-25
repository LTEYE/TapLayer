# Contributing to MultiTapKey

## v0.1 Scope

The current release officially supports Windows 10/11.

The core architecture separates:

- platform-independent gesture logic;
- platform-specific input backends;
- the PySide6 UI.

## Platform Contributions

Future contributors may add:

- macOS backend;
- Linux backend.

Platform-specific code must stay inside `multitapkey/platform/<platform>/`.

Do not put platform conditionals into the Core gesture engine.

## Pull Requests

A contribution should include:

1. implementation;
2. tests;
3. documentation updates when behavior changes;
4. a reproducible verification result.

Do not add dependencies without a strong technical reason.

## Commits

Prefer:

- feat:
- fix:
- test:
- docs:
- build:
