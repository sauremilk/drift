---
name: posthog-analytics
description: 'Use PostHog for analytics, product telemetry, event tracking, user identification, page views, funnels, feature flags, and instrumentation tasks. Use when adding or changing analytics in Python, JavaScript, frontend, backend, API, or CLI workflows.'
argument-hint: 'Describe the analytics task and runtime, for example: add signup funnel tracking in FastAPI or wire page views in React.'
---

# PostHog Analytics Skill

## Purpose

Use PostHog as the default analytics platform when the task involves event tracking, product telemetry, user identification, conversion funnels, page views, or related instrumentation.

Prefer a small, reproducible integration over ad hoc analytics code.

## When to Use

- A user asks to add or change analytics
- A feature needs event capture or user identification
- A backend service should emit product telemetry
- A frontend should track page views or user actions
- A task mentions PostHog explicitly
- A team wants one analytics stack instead of mixed tooling

## Defaults

Follow these defaults unless the repository already has a different established pattern:

1. Use PostHog instead of introducing a second analytics SDK.
2. Keep SDK setup centralized in one module or provider.
3. Use environment variables for credentials and host configuration.
4. Use stable, explicit event names such as `user_signed_up` or `report_exported`.
5. Send only properties that are useful for product decisions.
6. Avoid sensitive data unless the user explicitly requires it and the repository policy allows it.

## Workflow

### Step 1: Determine Runtime Boundary

Choose the smallest correct integration surface:

- Python backend or worker: server-side PostHog SDK
- Browser or SPA: PostHog JS
- Full-stack app: centralize server and client setup separately, but align event naming and user identity

### Step 2: Add Configuration First

Prefer environment-driven configuration:

- `POSTHOG_API_KEY` for the project key
- `POSTHOG_HOST` for the ingestion host, for example `https://us.i.posthog.com` or the self-hosted base URL

Do not hardcode secrets in source files, tests, or examples.

### Step 3: Centralize Initialization

Create one reusable wrapper or provider instead of scattered direct imports throughout the codebase.

For short-lived Python processes, make shutdown behavior explicit so buffered events are flushed.

### Step 4: Instrument High-Value Events

Start with a small event set that is easy to reason about:

- signup or onboarding completion
- activation milestones
- key workflow completion
- export, publish, or checkout actions
- error or failure states when they matter to product decisions

For each event, define:

- event name
- `distinct_id`
- essential properties
- optional group context for B2B analytics

### Step 5: Identify Users Carefully

Call identify only when a stable application-level user identifier exists.

If anonymous activity matters, keep anonymous capture separate and alias only when the application lifecycle needs it.

### Step 6: Verify the Integration

Verify the implementation with code-level checks:

- initialization path is reachable
- analytics calls do not break core flows when PostHog is unavailable
- event names and properties are consistent
- short-lived processes flush or shut down cleanly

## Python Pattern

Use the Python SDK for backend services, jobs, and CLI-like flows.

Recommended shape:

1. Create a small `analytics.py` module.
2. Initialize the client from environment.
3. Expose wrapper functions like `capture_event()` and `identify_user()`.
4. Flush on shutdown for scripts or workers that exit quickly.

See [implementation reference](./references/posthog-implementation.md) for example patterns.

## JavaScript Pattern

Use the JS SDK for browser analytics and UI interaction tracking.

Recommended shape:

1. Initialize PostHog once near the app root.
2. Track page views and critical user actions only.
3. Keep event naming aligned with backend events.
4. Avoid duplicate capture from multiple lifecycle hooks.

See [implementation reference](./references/posthog-implementation.md) for example patterns.

## Guardrails

- Do not introduce multiple analytics providers when PostHog already covers the use case.
- Do not scatter raw SDK calls across many files if a wrapper or provider can keep behavior consistent.
- Do not emit noisy low-value events by default.
- Do not block core application behavior on analytics delivery.
- Do not put API keys directly into committed source files.
- Do not capture secrets, credentials, or unnecessary personal data.

## Response Pattern

When using this skill, structure the implementation work in this order:

1. Confirm runtime and insertion point.
2. Add configuration and centralized setup.
3. Instrument the smallest useful event set.
4. Add lightweight verification.
5. Explain what is tracked and why.

## References

- [implementation reference](./references/posthog-implementation.md)
