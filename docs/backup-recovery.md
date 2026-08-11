# Backup & Disaster Recovery

Priority 9 of this security-hardening pass. **PostgreSQL is the only
real source of truth** in this system — every other stateful component
is either a cache/broker that can be safely lost and rebuilt (Redis:
Celery task queue + django-redis cache — losing it loses in-flight
background jobs and cached data, never anything that can't be
regenerated or re-derived) or user-uploaded files (`backend/media/` —
`Business.logo`, `Product.image`, `KnowledgeDocument.file`,
`MessageAttachment.file`). This doc covers backing up both; Postgres is
the one that actually matters for data integrity.

## What's backed up, and how

`scripts/backup-db.ps1` — `pg_dump` in custom compressed format (`-Fc`,
not a plain `.sql` text dump — supports selective and parallel restore,
and is meaningfully smaller). Reads connection details from `.env`
(same pattern as `scripts/create-db.ps1`/`migrate.ps1`), writes to
`backups/waba_<db>_<timestamp>.dump` at the project root (gitignored —
a database dump is real customer data and must never be committed),
and prunes dumps older than `-RetentionDays` (default 14) for that same
database name, so re-running it on a schedule doesn't grow `backups/`
forever.

```powershell
.\scripts\backup-db.ps1                    # default 14-day retention
.\scripts\backup-db.ps1 -RetentionDays 30  # keep a month
```

**Live-verified**: run against the real dev database this session,
produced a real 0.26 MB compressed dump.

## Restoring

`scripts/restore-db.ps1 -BackupFile <path> -Force` — **destructive**
(drops and recreates every object in the target database via
`pg_restore --clean --if-exists`), so it has two independent gates
before it touches anything:

1. `-Force` is required — running it bare prints what it *would* do and
   exits `1` without touching the database.
2. Even with `-Force`, it prompts for the database name to be typed back
   exactly — anything else (including empty input) aborts with nothing
   touched.

**Live-verified, without actually destroying real data**: both gates
tested directly — running without `-Force` correctly refused and exited
`1`; running with `-Force` under a non-interactive shell (this session's
own tooling can't supply an interactive terminal prompt) correctly
failed the confirmation step rather than silently proceeding. Neither
test touched the real dev database, which still has this entire
session's accumulated seed/test data intact.

```powershell
.\scripts\restore-db.ps1 -BackupFile ".\backups\waba_whatsapp_business_ai_20260811-131148.dump" -Force
# -> prompts: Type the database name ('whatsapp_business_ai') to confirm
```

If the backup predates a migration applied since it was taken, run
`scripts\migrate.ps1` immediately after restoring.

## Media files

`backend/media/` (user uploads: business logos, product images,
knowledge base documents, message attachments) isn't covered by
`backup-db.ps1` — it's plain files on disk, not database rows. For the
current local-filesystem storage backend (`USE_S3=False`, the dev
default), back it up with any file-level tool (a scheduled `robocopy`/
`rsync` to another disk or a cloud storage target). Once `USE_S3=True`
is actually used in a real deployment, the object storage provider's own
versioning/replication (e.g. S3 versioning + cross-region replication)
is the more appropriate mechanism — not a job for this repo's own
scripts.

## Recommended schedule (not automated in this repo)

No `scripts/backup-db.ps1` invocation is wired into `celery beat`, a
Windows Scheduled Task, or a cron job — that's a deployment-environment
decision (what always-on host actually runs it, where the resulting
`.dump` files get shipped off-box to) that doesn't belong hardcoded into
application code. Recommended starting point once a real deployment
target exists:

- **Daily** full `pg_dump` via `backup-db.ps1` (or the equivalent on
  the real production OS), shipped to storage physically separate from
  the database host itself (a local-disk-only backup doesn't survive
  the disk/server it's sitting next to failing).
- **14–30 day retention** (the script's own default, tunable via
  `-RetentionDays`) for daily dumps; consider a longer-retention monthly
  archive tier if compliance/support needs ever require looking back
  further.
- For a real production Postgres instance, **WAL archiving / continuous
  archiving** (point-in-time recovery) is a meaningfully stronger
  guarantee than daily full dumps alone — a managed Postgres provider
  (RDS, Cloud SQL, etc.) typically provides this out of the box; a
  self-hosted instance would need `pgbackrest`/`wal-g` or similar. Not
  set up here since there's no real production Postgres host yet (see
  `docs/ROADMAP.md`'s Phase 16, Docker/deployment).

## Disaster recovery runbook

**Scenario: database corrupted or accidentally destructive migration/
query.**

1. Stop the application (`scripts/stop.ps1` or the equivalent process
   manager in production) — prevents further writes against a bad
   state while recovering.
2. Identify the most recent good backup in `backups/` (or wherever
   production ships them).
3. `scripts\restore-db.ps1 -BackupFile <path> -Force`, confirm the
   database name when prompted.
4. `scripts\migrate.ps1` if the backup predates a since-applied
   migration.
5. Restart the application, smoke-test (`docs/*.md` "verified live"
   sections across this project show the pattern — log in, hit a few
   core endpoints per app).

**Scenario: the entire server/host is lost.**

1. Provision a new host; follow `docs/development.md`'s setup steps
   (or the production equivalent) to get Postgres/Redis/the app running.
2. Restore the database from the most recent off-box backup (step 3
   above).
3. Restore media files from wherever they were backed up (see "Media
   files" above) — or accept the gap if a business's logo/product
   images/uploaded documents were never off-box backed up, and note
   that gap in the incident writeup.
4. Regenerate `.env` secrets (`DJANGO_SECRET_KEY`, `JWT_SIGNING_KEY`,
   `FIELD_ENCRYPTION_KEY`, `WHATSAPP_APP_SECRET`, etc.) **only if** the
   old host's `.env` is confirmed lost too — if `FIELD_ENCRYPTION_KEY`
   is lost without the old host's `.env`, every already-encrypted
   WhatsApp token and MFA secret in the restored database becomes
   permanently undecryptable (`core.crypto.decrypt_secret` would raise
   `InvalidToken` for all of them) — businesses would need to reconnect
   WhatsApp and every user would need to re-enroll MFA from scratch.
   **This is the single most consequential secret to actually back up
   safely** (a password manager / secrets vault, not just "on the old
   server"), independent of the database backup strategy above.

## Limitations / not built

- No automated backup schedule wired into this repo (see above — a
  deployment-environment decision, not application code).
- No WAL archiving / point-in-time recovery setup (see above).
- No off-box shipping of backup files built into `backup-db.ps1` itself
  — it writes locally; getting the `.dump` file to separate storage is
  left to whatever scheduler/pipeline actually runs it.
- No automated restore testing / backup integrity verification job (a
  "restore this backup into a scratch database and run a smoke test on
  it" job is the gold standard for actually trusting backups — not
  built this phase).
