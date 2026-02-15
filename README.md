# RetryStorm 🌪️

**Microservice retry/timeout topology static analyzer** — catch cascading failure risks before they hit production.

RetryStorm parses your service topology YAML and detects:

- 🔴 **Retry Amplification** — multiplicative retry factors across call chains (e.g., 3×4×3 = 36x load)
- 🟡 **Timeout Inversion** — caller timeout shorter than callee timeout (guaranteed premature failure)
- 🟡 **Circuit Breaker Gaps** — services calling downstream without circuit breaker protection

## Install

```bash
pip install -r requirements.txt
```

## Usage

Define your topology in YAML:

```yaml
services:
  api-gateway:
    timeout: "3s"
    retry:
      max_attempts: 3
    calls: [user-service, order-service]
  user-service:
    timeout: "5s"
    retry:
      max_attempts: 4
    circuit_breaker:
      threshold: 5
    calls: [user-db]
  order-service:
    timeout: "2s"
    retry:
      max_attempts: 2
    calls: []
  user-db:
    timeout: "1s"
    retry:
      max_attempts: 1
    calls: []
```

Run the analyzer:

```bash
# Human-readable output
python cli.py topology.yaml

# JSON output
python cli.py topology.yaml --format json

# SARIF for GitHub code scanning
python cli.py topology.yaml --format sarif > results.sarif

# Custom retry threshold & strict mode
python cli.py topology.yaml --threshold 5 --strict
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No errors found |
| 1 | Errors found (or warnings with `--strict`) |
| 2 | Configuration loading error |

## Run Tests

```bash
pytest test_retrystorm.py -v
```

## License

MIT
