# QuickSight Dashboard Access Scanner

## Overview

An inventory and access-review dashboard that lists QuickSight dashboards, inspects sharing principals, and exports a filtered report with publication timestamps.

**Technologies:** Python · Streamlit · Boto3 · pandas · Amazon QuickSight

**Engineering focus:** Cloud inventory, access-review workflows, AWS API pagination, and operational reporting.

## Features

- Paginated dashboard discovery and per-dashboard permission inspection.
- Flags potentially broad sharing using namespace and group-name heuristics.
- Filters by the sharing flag and days since publication.
- Displays summary counts and exports the filtered inventory as CSV.

## Limitations

- Local implementation reviewed; no AWS account was scanned.
- The broad-sharing flag is a heuristic, not a complete effective-permissions audit.
- Last publication time measures publishing activity; it does not establish dashboard viewership or actual usage.
- Account identifiers, principals, dashboard names, and exported reports must be replaced with synthetic examples for public demos.

This is a prototype. Live AWS behavior and production readiness have not been verified.

## Local setup

Requires Python 3 and AWS credentials configured for an account you are authorized to use. Use a sandbox account with synthetic resources for demonstrations.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

```sh
streamlit run app.py
```

## Data handling

Local configuration, credentials, generated reports, spreadsheets, and asset bundles are excluded from this repository. Do not commit real account configuration, customer data, or secrets. AWS access uses configured local profiles or the SDK credential chain; no credentials are supplied.

## Validation

Python syntax was checked without executing application code. No AWS requests or deployment tests were run. The dependency list is not version-locked.
