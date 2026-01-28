# Phase 02: Database Migration - User Setup Required

**Generated:** 2026-01-28
**Phase:** 02-database-migration
**Status:** Incomplete

## Overview

This phase introduces Turso as the database for price observations and alert state. You need to:
1. Create a Turso account and database
2. Get credentials and add them as environment variables

## Environment Variables

| Status | Variable | Source | Add to |
|--------|----------|--------|--------|
| [ ] | `TURSO_DATABASE_URL` | Turso Dashboard -> Your database -> Connect -> libsql URL | `.env` and GitHub Secrets |
| [ ] | `TURSO_AUTH_TOKEN` | Turso Dashboard -> Your database -> Connect -> Auth token | `.env` and GitHub Secrets |

## Account Setup

1. **Create Turso Account**
   - Go to [turso.tech](https://turso.tech)
   - Sign up (free tier includes 5GB storage, 500M row reads)

2. **Create Database**
   - In Turso Dashboard, click "Create Database"
   - Name: `detty-flight-deals` (or your preferred name)
   - Region: Choose closest to your users (or keep default)

3. **Get Credentials**
   - Click on your database
   - Go to "Connect" tab
   - Copy the libsql URL (looks like `libsql://your-db-name.turso.io`)
   - Click "Create Token" to generate an auth token
   - Copy the auth token

## GitHub Secrets Configuration

Add secrets for GitHub Actions:

```bash
gh secret set TURSO_DATABASE_URL --body "libsql://your-db-name.turso.io"
gh secret set TURSO_AUTH_TOKEN --body "your-auth-token-here"
```

## Local Development

For local development, create `.env` file:

```bash
echo 'TURSO_DATABASE_URL=libsql://your-db-name.turso.io' >> .env
echo 'TURSO_AUTH_TOKEN=your-auth-token-here' >> .env
```

**Note:** The `.env` file should already be in `.gitignore` to prevent committing secrets.

## System Dependencies (Local Development Only)

libsql requires cmake for building from source:

```bash
# macOS
brew install cmake

# Then install Python dependencies
pip install -r requirements.txt
```

**Note:** GitHub Actions has cmake pre-installed, so this is only needed for local development.

## Verification

After setup, verify the connection works:

```bash
python3 -c "
import os
os.environ['TURSO_DATABASE_URL'] = 'your-url-here'  # or use .env
os.environ['TURSO_AUTH_TOKEN'] = 'your-token-here'
from db import TursoClient
client = TursoClient()
print(f'Turso available: {client._turso_available}')
# Should print: Turso available: True
"
```

## Fallback Behavior

If Turso credentials are not configured:
- TursoClient initializes with `_turso_available = False`
- All write operations return `False`
- All read operations return `None`
- The system continues to work using JSON files (existing behavior)

This graceful degradation ensures monitoring continues even without database access.

---
**Once all items complete:** Mark status as "Complete"
