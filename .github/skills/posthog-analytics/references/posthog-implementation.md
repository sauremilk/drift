# PostHog Implementation Reference

Use this reference when the main skill is loaded and concrete setup details are needed.

## Python Server-Side Example

Use a small wrapper module instead of importing the SDK everywhere.

```python
import os

from posthog import Posthog


def build_posthog_client() -> Posthog | None:
    api_key = os.getenv("POSTHOG_API_KEY")
    host = os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
    if not api_key:
        return None
    return Posthog(project_api_key=api_key, host=host)


class Analytics:
    def __init__(self) -> None:
        self._client = build_posthog_client()

    def capture_event(self, distinct_id: str, event: str, properties: dict | None = None) -> None:
        if self._client is None:
            return
        self._client.capture(distinct_id=distinct_id, event=event, properties=properties or {})

    def identify_user(self, distinct_id: str, properties: dict | None = None) -> None:
        if self._client is None:
            return
        self._client.identify(distinct_id=distinct_id, properties=properties or {})

    def shutdown(self) -> None:
        if self._client is not None:
            self._client.shutdown()
```

Recommended usage:

- build one shared instance at application startup
- use `shutdown()` for workers, scripts, or commands that exit quickly
- capture only business-relevant properties

## Python Event Checklist

Before adding an event, define:

- `event`: stable snake_case action name
- `distinct_id`: stable user, account, workspace, or anonymous identifier
- properties: only fields needed for analysis
- failure behavior: analytics failure must not fail the core request unless explicitly required

## Browser Example

Initialize once near the root of the app.

```javascript
import posthog from 'posthog-js'

export function initAnalytics() {
    const apiKey = import.meta.env.VITE_POSTHOG_API_KEY
    const apiHost = import.meta.env.VITE_POSTHOG_HOST || 'https://us.i.posthog.com'

    if (!apiKey) {
        return
    }

    posthog.init(apiKey, {
        api_host: apiHost,
        capture_pageview: true,
        autocapture: false,
    })
}

export function trackEvent(event, properties = {}) {
    posthog.capture(event, properties)
}
```

Recommended usage:

- enable page view capture only once
- keep autocapture disabled unless the team explicitly wants broad UI telemetry
- wrap `posthog.capture()` in a local helper to keep naming and payloads consistent

## Identity Guidance

- call identify after login or after a stable account id is known
- keep anonymous and authenticated journeys conceptually separate
- only use aliasing when the product flow genuinely requires user stitching

## Group Analytics

For B2B or workspace-centric apps, use group context only when it helps answer a product question.

Examples:

- workspace plan tier
- organization size bucket
- deployment type

Avoid copying entire domain objects into event properties.

## Feature Flags

PostHog can also evaluate feature flags. Use that only if the task actually includes rollout logic.
Do not expand a pure analytics task into a flagging migration unless the user asks for it.

## Review Checklist

- initialization is centralized
- no committed secrets
- event names are consistent
- low-value noise is avoided
- analytics failure does not break the main flow
- short-lived processes flush or shut down cleanly