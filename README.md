# deck (Python skeleton)

A CLI to deploy, backup, and migrate services across Docker/Kubernetes/SSH targets. This is a **skeleton**: commands print plans and placeholders; wire your providers next.

## Quickstart

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .

# See help
deck --help

# Inspect services list
deck status

# Inspect status (JSON)
deck status example-service --json

# List targets (and probe)
deck targets

deck targets --check --json

# Plan a deploy
deck deploy example-service

# Apply a deploy (no real provider yet)
deck deploy example-service --apply

# Plan a migration
deck migrate example-service --to node-docker-02