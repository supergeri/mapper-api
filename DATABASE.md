# Database Architecture

## Overview

The mapper-api connects to a **shared Supabase database** that is managed by the web app (`workout-content-transformation`).

```
┌─────────────────────┐     ┌─────────────────────┐
│  Web App (React)    │     │  Mapper API (Python)│
│                     │     │                     │
│  • Migrations ✓     │     │  • No migrations    │
│  • Supabase CLI     │     │  • Supabase client  │
└─────────┬───────────┘     └─────────┬───────────┘
          │                           │
          └───────────┬───────────────┘
                      ▼
            ┌─────────────────────┐
            │  Supabase Database  │
            │                     │
            │  • profiles         │
            │  • workouts         │
            │  • linked_accounts  │
            │  • follow_along_*   │
            └─────────────────────┘
```

## Why No Migrations Here?

1. **Single source of truth** - All migrations live in the web app repo
2. **No version conflicts** - Only one repo runs `supabase db push`
3. **Cleaner separation** - This API is a consumer, not an owner

## Environment Variables

This API needs these Supabase credentials:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJ...  # For backend operations
# OR
SUPABASE_ANON_KEY=eyJ...          # Less privileged
```

**Recommendation**: Use `SUPABASE_SERVICE_ROLE_KEY` for backend APIs to bypass RLS.

## Tables Used by This API

### `workouts`
- `save_workout()` - Insert new workouts
- `get_workouts()` - List user workouts
- `get_workout()` - Get single workout
- `delete_workout()` - Delete workout

### `follow_along_workouts`
- `save_follow_along_workout()` - Insert ingested workout
- `get_follow_along_workouts()` - List user's follow-along workouts
- `get_follow_along_workout()` - Get single follow-along workout
- `update_follow_along_garmin_sync()` - Update Garmin sync status
- `update_follow_along_apple_watch_sync()` - Update Apple Watch sync
- `update_follow_along_ios_companion_sync()` - Update iOS Companion sync

### `follow_along_steps`
- Managed via `follow_along_workouts` (cascade insert/delete)

## Adding New Database Features

If you need to add new tables or columns:

1. **Create migration in web app repo**:
   ```bash
   cd workout-content-transformation-main
   npx supabase migration new your_feature_name
   # Edit the generated .sql file
   npx supabase db push
   ```

2. **Update Python code in this repo**:
   ```python
   # backend/database.py or backend/follow_along_database.py
   def your_new_function():
       supabase = get_supabase_client()
       # ... use the new table/column
   ```

3. **Deploy both**:
   - Deploy web app (runs migration)
   - Deploy mapper-api (uses new schema)

## Running Migrations via GitHub Actions

This repository includes a GitHub Actions workflow that can run Supabase migrations against both development and staging environments.

### Workflow: Database Migrations

The workflow is located at `.github/workflows/migrations.yml` and supports both development and staging environments.

#### How to Run

1. **Navigate to GitHub repository** → Actions tab → "Database Migrations" workflow
2. Click **Run workflow**
3. Select the target environment:
   - `development` - For local/dev testing
   - `staging` - For pre-production validation
4. Click **Run workflow**

#### Required Secrets

Configure the following secrets in your GitHub repository settings for each environment:

**For `development` environment:**
- `SUPABASE_PROJECT_ID` - Development Supabase project ID
- `SUPABASE_DB_URL` - Development database connection string

**For `staging` environment:**
- `SUPABASE_PROJECT_ID` - Staging Supabase project ID
- `SUPABASE_DB_URL` - Staging database connection string

To configure secrets:
1. Go to Repository Settings → Environments
2. Select the environment (development or staging)
3. Add the required secrets

#### Manual Local Migration

For local development, you can also run migrations manually:

```bash
# Install Supabase CLI
npm install -g supabase

# Set database URL
export SUPABASE_DB_URL="postgresql://postgres:[YOUR-PASSWORD]@db.[YOUR-PROJECT].supabase.co:5432/postgres"

# Push migrations
supabase db push --db-url "$SUPABASE_DB_URL"
```

## Schema Reference

See the web app's `supabase/migrations/` folder for the complete schema:

- `001_create_profiles_table.sql`
- `20250120000001_create_linked_accounts_table.sql`
- `20250120000002_create_workouts_table.sql`
- `20250122000000_create_follow_along_workouts.sql`
- `20250130000000_add_ios_companion_sync.sql`
