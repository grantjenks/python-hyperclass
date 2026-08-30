# Changelog

## 0.0.5 — 2026-08-30

- Carry component CSS with htmx fragment responses.
- Keep a stable page stylesheet target for styles introduced after first load.
- Preserve inherited CSS precedence when fragment styles arrive later.
- Cover the empty-inbox-to-first-bookmark path as a regression.

## 0.0.4 — 2026-08-30

- Declare inherited HTML attribute defaults directly on element classes.
- Override or suppress class defaults from subclasses and element instances.
- Use lazy `name.some_field` objects as form names and selectors.
- Accept first-class names in request values and htmx `include` selectors.
- Exercise declarative fields and links throughout the bookmark application.

## 0.0.3 — 2026-08-30

- Bind submitted form values to annotated Python dataclasses.
- Run applications with `python -m hyperclass module:app`.
- Add live search and inline editing to the bookmark application.
- Replace the project README with an installation-first guide.

## 0.0.2 — 2026-08-30

- Render HTML elements from Python classes and semantic subclasses.
- Compose generated CSS through inheritance and multiple inheritance.
- Author pseudo-state and responsive media styles in Python.
- Use classes, element instances, and first-class IDs as selectors.
- Generate htmx 4 attributes and multi-target partial responses.
- Build full pages and htmx fragments from the same components.
- Route WSGI requests with typed path parameters.
- Define routes as application methods and reverse handlers into URLs.
- Run the persistent SQLite bookmark inbox example.

## 0.0.1 — 2026-08-29

- Reserve the package name and establish the release pipeline.
