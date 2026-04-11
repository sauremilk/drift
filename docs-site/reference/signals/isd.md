# Insecure Default Signal (ISD)

**Signal ID:** `ISD`  
**Full name:** Insecure Default  
**Type:** Scoring signal (contributes to drift score)  
**Default weight:** `0.01`  
**Scope:** file_local

---

## What ISD detects

ISD detects **insecure configuration defaults** in code — settings that are safe during development but dangerous in production. This includes `DEBUG=True`, `ALLOWED_HOSTS=["*"]`, `CORS_ALLOW_ALL_ORIGINS=True`, `verify=False` in HTTP clients, and similar patterns. Maps to **CWE-1188: Initialization with an Insecure Default**.

### Before — insecure defaults

```python
# settings.py
DEBUG = True
ALLOWED_HOSTS = ["*"]
CORS_ALLOW_ALL_ORIGINS = True
SECRET_KEY = "development-key"

# api_client.py
response = requests.get(url, verify=False)
```

### After — secure defaults

```python
# settings.py
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "").split(",")
CORS_ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",")
SECRET_KEY = os.environ["SECRET_KEY"]  # fail if not set

# api_client.py
response = requests.get(url)  # verify=True is the default
```

---

## Why insecure defaults matter

- **Development settings reach production** — "I'll fix it later" never happens.
- **AI generates insecure defaults** — LLMs use the simplest working configuration, which is often insecure.
- **`verify=False` disables TLS** — man-in-the-middle attacks become trivial.
- **`ALLOWED_HOSTS=["*"]`** enables host header injection attacks.

---

## How the score is calculated

ISD uses pattern matching on AST assignments:

| Pattern | Risk |
|---|---|
| `DEBUG = True` | Info disclosure, stack traces in production |
| `ALLOWED_HOSTS = ["*"]` | Host header injection |
| `CORS_ALLOW_ALL_ORIGINS = True` | Cross-origin data theft |
| `verify=False` in requests | TLS bypass (MITM) |
| `SECRET_KEY = "..."` (short literal) | Session forgery |

**Severity thresholds:**

| Score range | Severity |
|-------------|----------|
| ≥ 0.7       | HIGH     |
| ≥ 0.5       | MEDIUM   |
| ≥ 0.3       | LOW      |
| < 0.3       | INFO     |

---

## How to fix ISD findings

1. **Use environment variables** — `os.getenv("DEBUG", "false")` defaults to secure.
2. **Fail-closed** — if a critical secret is missing, crash rather than using a fallback.
3. **Separate config files** — use different settings for development, staging, and production.
4. **Never commit `verify=False`** — use proper CA certificates instead.

---

## Configuration

```yaml
# drift.yaml
weights:
  insecure_default: 0.01   # default weight (0.0 to 1.0)
```

---

## Detection details

1. **Scan AST assignments** for known insecure patterns.
2. **Match variable names** against known security-sensitive settings.
3. **Check assigned values** for insecure literals (`True`, `["*"]`, short strings).
4. **Check function calls** for `verify=False` keyword arguments.

ISD is deterministic and AST-only.

---

## Related signals

- **MAZ (Missing Authorization)** — detects missing access control. ISD detects misconfigured security settings.
- **HSC (Hardcoded Secret)** — detects hardcoded credentials. ISD detects insecure defaults that aren't secrets per se.
