#!/usr/bin/env bash
set -euo pipefail

# This script is invoked in the backend container by compose.test.yml.
alembic upgrade head
FASTAPI_ENV=development pytest tests/ "$@"
