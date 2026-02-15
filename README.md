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

## Examples

Run the included example topologies to see RetryStorm in action:

### Healthy baseline (zero issues)

```bash
python cli.py examples/healthy_topology.yaml
```

Expected output: `✅ No resilience issues found.` (exit code 0)

### Simple chain with timeout inversion

```bash
python cli.py examples/simple_chain.yaml
```

Expected output: 1 issue — a timeout inversion where the frontend caller (2 s)
is shorter than its backend callee (5 s). Exit code 0 (warning only).

### Retry amplification fan-out

```bash
python cli.py examples/retry_amplification.yaml
```

Expected output: multiple issues — retry amplification factors exceeding 100×
across fan-out paths (5×5×5 = 125×, 5×4×5 = 100×), plus circuit breaker gap
warnings on every service. Exit code 1.

### Kitchen sink (all problem types)

```bash
python cli.py examples/kitchen_sink.yaml
```

Expected output: many issues — retry amplification (20× and 48× paths), timeout
inversions (gateway 2 s → auth 5 s, order 3 s → inventory 8 s), and circuit
breaker gaps on gateway, auth-service, and inventory-service. Exit code 1.

### Output formats

```bash
# JSON output for programmatic consumption
python cli.py examples/kitchen_sink.yaml --format json

# SARIF output for GitHub code scanning integration
python cli.py examples/kitchen_sink.yaml --format sarif > results.sarif

# Lower threshold to surface smaller amplification risks
python cli.py examples/retry_amplification.yaml --threshold 5

# Strict mode: exit 1 on any finding including warnings
python cli.py examples/simple_chain.yaml --strict
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
