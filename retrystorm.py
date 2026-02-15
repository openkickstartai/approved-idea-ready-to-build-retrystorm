"""RetryStorm - Microservice retry/timeout topology static analyzer."""
import yaml
from dataclasses import dataclass, field


@dataclass
class ServiceConfig:
    name: str
    timeout_ms: float
    max_retries: int
    has_circuit_breaker: bool
    calls: list = field(default_factory=list)


@dataclass
class Finding:
    rule: str
    severity: str
    message: str
    path: list = field(default_factory=list)


def parse_duration(s):
    """Parse duration string to milliseconds."""
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if s.endswith("ms"):
        return float(s[:-2])
    if s.endswith("s"):
        return float(s[:-1]) * 1000
    if s.endswith("m"):
        return float(s[:-1]) * 60000
    return float(s)


def load_topology(source):
    """Load service topology from a YAML file path or dict."""
    if isinstance(source, dict):
        data = source
    else:
        with open(source) as f:
            data = yaml.safe_load(f)
    services = {}
    for name, cfg in data.get("services", {}).items():
        retry = cfg.get("retry", {})
        attempts = retry.get("max_attempts", 1) if isinstance(retry, dict) else int(retry)
        services[name] = ServiceConfig(
            name=name,
            timeout_ms=parse_duration(cfg.get("timeout", "30s")),
            max_retries=max(attempts, 1),
            has_circuit_breaker=bool(cfg.get("circuit_breaker")),
            calls=cfg.get("calls", []),
        )
    return services


def detect_retry_amplification(services, threshold=10):
    """Find paths where cumulative retry factor exceeds threshold."""
    findings = []

    def walk(name, path, product):
        svc = services.get(name)
        if not svc:
            return
        current = product * svc.max_retries
        if len(path) > 1 and current > threshold:
            findings.append(Finding(
                rule="retry-amplification", severity="error",
                message=f"Retry amplification {current}x along {' -> '.join(path)}",
                path=list(path),
            ))
        for callee in svc.calls:
            if callee not in path:
                walk(callee, path + [callee], current)

    for name in services:
        walk(name, [name], 1)
    return findings


def detect_timeout_inversion(services):
    """Find caller-callee pairs where caller timeout < callee timeout."""
    findings = []
    for name, svc in services.items():
        for callee_name in svc.calls:
            callee = services.get(callee_name)
            if callee and svc.timeout_ms < callee.timeout_ms:
                findings.append(Finding(
                    rule="timeout-inversion", severity="warning",
                    message=f"{name} timeout ({svc.timeout_ms}ms) < {callee_name} ({callee.timeout_ms}ms)",
                    path=[name, callee_name],
                ))
    return findings


def detect_circuit_breaker_gaps(services):
    """Find services making calls without circuit breaker protection."""
    findings = []
    for name, svc in services.items():
        if svc.calls and not svc.has_circuit_breaker:
            callees = ", ".join(svc.calls)
            findings.append(Finding(
                rule="circuit-breaker-gap", severity="warning",
                message=f"'{name}' calls [{callees}] without circuit breaker",
                path=[name],
            ))
    return findings


def analyze(services, threshold=10):
    """Run all detectors and return combined findings."""
    return (detect_retry_amplification(services, threshold)
            + detect_timeout_inversion(services)
            + detect_circuit_breaker_gaps(services))


def to_sarif(findings):
    """Convert findings to SARIF 2.1.0 format."""
    rules, seen = [], set()
    for f in findings:
        if f.rule not in seen:
            seen.add(f.rule)
            rules.append({"id": f.rule, "shortDescription": {"text": f.rule.replace("-", " ").title()}})
    results = [{"ruleId": f.rule, "level": "error" if f.severity == "error" else "warning",
                "message": {"text": f.message},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": "topology.yaml"}}}]}
               for f in findings]
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "RetryStorm", "version": "0.1.0",
                     "rules": rules}}, "results": results}]}
