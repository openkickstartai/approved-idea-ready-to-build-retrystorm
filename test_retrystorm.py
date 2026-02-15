"""Tests for RetryStorm analyzer."""
import json
import os
import subprocess
import sys
import tempfile
import yaml
from retrystorm import (
    load_topology, detect_retry_amplification, detect_timeout_inversion,
    detect_circuit_breaker_gaps, analyze, parse_duration, to_sarif,
)

HEALTHY = {"services": {
    "api": {"timeout": "10s", "retry": {"max_attempts": 2},
            "circuit_breaker": {"threshold": 5}, "calls": ["backend"]},
    "backend": {"timeout": "3s", "retry": {"max_attempts": 1},
                "circuit_breaker": {"threshold": 3}, "calls": []},
}}

UNHEALTHY = {"services": {
    "gateway": {"timeout": "3s", "retry": {"max_attempts": 3}, "calls": ["svc-a"]},
    "svc-a": {"timeout": "5s", "retry": {"max_attempts": 4}, "calls": ["svc-b"]},
    "svc-b": {"timeout": "2s", "retry": {"max_attempts": 3}, "calls": []},
}}


def test_parse_duration_variants():
    assert parse_duration("5s") == 5000.0
    assert parse_duration("200ms") == 200.0
    assert parse_duration("2m") == 120000.0
    assert parse_duration(500) == 500.0


def test_healthy_topology_no_issues():
    topo = load_topology(HEALTHY)
    findings = analyze(topo)
    assert len(findings) == 0


def test_retry_amplification_detected():
    topo = load_topology(UNHEALTHY)
    findings = detect_retry_amplification(topo, threshold=10)
    assert len(findings) > 0
    assert all(f.rule == "retry-amplification" for f in findings)
    # gateway(3) * svc-a(4) * svc-b(3) = 36
    messages = " ".join(f.message for f in findings)
    assert "36x" in messages


def test_timeout_inversion_detected():
    topo = load_topology(UNHEALTHY)
    findings = detect_timeout_inversion(topo)
    # gateway(3000ms) < svc-a(5000ms)
    assert len(findings) == 1
    assert findings[0].rule == "timeout-inversion"
    assert "gateway" in findings[0].message
    assert "svc-a" in findings[0].message


def test_circuit_breaker_gaps_detected():
    topo = load_topology(UNHEALTHY)
    findings = detect_circuit_breaker_gaps(topo)
    # gateway and svc-a have calls but no circuit breaker
    assert len(findings) == 2
    names = [f.path[0] for f in findings]
    assert "gateway" in names
    assert "svc-a" in names


def test_sarif_output_structure():
    topo = load_topology(UNHEALTHY)
    findings = analyze(topo, threshold=10)
    sarif = to_sarif(findings)
    assert sarif["version"] == "2.1.0"
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "RetryStorm"
    assert len(run["results"]) == len(findings)
    rule_ids = {r["id"] for r in run["tool"]["driver"]["rules"]}
    assert "retry-amplification" in rule_ids
    assert "timeout-inversion" in rule_ids


def test_load_from_yaml_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(HEALTHY, f)
        path = f.name
    try:
        topo = load_topology(path)
        assert "api" in topo
        assert topo["api"].timeout_ms == 10000.0
        assert topo["api"].max_retries == 2
    finally:
        os.unlink(path)


def test_cli_json_output():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(UNHEALTHY, f)
        path = f.name
    try:
        cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cli.py")
        result = subprocess.run(
            [sys.executable, cli, path, "--format", "json"],
            capture_output=True, text=True,
        )
        assert result.returncode == 1  # has errors
        data = json.loads(result.stdout)
        rules = {item["rule"] for item in data}
        assert "retry-amplification" in rules
        assert "circuit-breaker-gap" in rules
    finally:
        os.unlink(path)
