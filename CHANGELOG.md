# Changelog

## 0.2.0 — 2026-08-31

- Stream renderable server-sent events from the Lite, Flask, and Django hosts.
- Load htmx 4 extensions only when a component requests them.
- Compose htmx attributes and author modifiers such as `hx.on.before_request`.
- Parameterize first-class IDs with application keys such as `id.message[42]`.
- Add a persistent, responsive AI chat example with an injectable model,
  token streaming, stop, regenerate, and shared routes across all three hosts.
- Exercise the complete chat lifecycle in the cross-host Chromium contract.

## 0.1.1 — 2026-08-31

- Read portable query keys correctly from native Flask and Django multidicts.
- Mark the generated Django CSRF header as inherited for htmx 4.

## 0.1.0 — 2026-08-31

- Split the zero-dependency server into the explicit `hyperclass.lite` host.
- Keep top-level `App` and `hyperclass.wsgi` as backward-compatible aliases.
- Add a native Flask host with native requests, responses, mounting, and URL
  generation.
- Add a native Django URL app with namespaces, method dispatch, URL reversing,
  and htmx CSRF headers.
- Resolve handler URLs lazily through the active host at render time.
- Bind dataclasses from Lite values, Werkzeug `MultiDict`, or Django
  `QueryDict` through one small protocol.
- Run the complete bookmark browser contract against Lite, Flask, and Django.

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
