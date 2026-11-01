# HMS Database Backup and Restore Runbook

## 1. Purpose and scope

This runbook documents backup, restore, retention, ownership, and recovery verification for the Hostel Management System (HMS).

It covers:

- SQLite for local development.
- PostgreSQL for deployment.
- Restoration into a separate non-production database.
- Verification of database integrity, Django migrations, and representative HMS records.

Production credentials and infrastructure-specific configuration must be managed outside this repository.

## 2. Roles and responsibilities

| Responsibility    | Owner                                                    | Duties                                                  |
| ----------------- | -------------------------------------------------------- | ------------------------------------------------------- |
| Backup operator   | Designated HMS deployment maintainer / database operator | Run scheduled backups and monitor completion.           |
| Restore checker   | A second authorized team member                          | Independently verify backup integrity and restoration.  |
| Recovery approver | HMS technical lead                                       | Approve recovery actions and confirm service readiness. |

The deployment team must assign named individuals before production deployment. The operator and checker should be different people where staffing permits.

## 3. Backup storage and security

### Local development

Store SQLite backups outside the repository. On Windows, a suitable local location is `%LOCALAPPDATA%\HMSBackups`.

### Deployment

Store PostgreSQL backups in encrypted, access-controlled storage separate from the application server and primary database. Use an approved organizational backup service or restricted off-host object storage.

Security requirements:

- Never commit database backups, `.env` files, passwords, or secret configuration to Git.
- Restrict backup access to authorized operators.
- Encrypt backups at rest and during transfer.
- Supply database credentials through an approved secret manager, protected password file, or controlled environment variables. Never place passwords in command-line arguments or scripts.
- Periodically verify that backup files can be read and restored.

## 4. SQLite backup and restore (local development)

The default SQLite database path in this project is `db.sqlite3` in the repository root. The following examples use Python's SQLite online backup API, which is safer than copying a database file while it may be in use.

### 4.1 Create a backup

Run from the project root:

```python
import sqlite3
from pathlib import Path

source = Path("db.sqlite3")
backup_dir = Path.home() / "AppData/Local/HMSBackups"
backup = backup_dir / "hms-backup.sqlite3"

if not source.exists():
    raise FileNotFoundError(source)

backup_dir.mkdir(parents=True, exist_ok=True)
with sqlite3.connect(source) as src:
    with sqlite3.connect(backup) as dst:
        src.backup(dst)

with sqlite3.connect(backup) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
    print("Backup integrity:", result)
    if result != "ok":
        raise RuntimeError("SQLite backup integrity check failed")

print("Backup created:", backup)
```

### 4.2 Restore into a separate test file

Do not overwrite the original database during a restore test. Restore into a separate file:

```python
import sqlite3
from pathlib import Path

backup = Path.home() / "AppData/Local/HMSBackups/hms-backup.sqlite3"
restored = Path.home() / "AppData/Local/HMSBackups/hms-restore-test.sqlite3"

if not backup.exists():
    raise FileNotFoundError(backup)

with sqlite3.connect(backup) as src:
    with sqlite3.connect(restored) as dst:
        src.backup(dst)

with sqlite3.connect(restored) as db:
    result = db.execute("PRAGMA integrity_check").fetchone()[0]
    print("Restore integrity:", result)
    if result != "ok":
        raise RuntimeError("SQLite restore integrity check failed")

print("Restored database:", restored)
```

### 4.3 Verify the SQLite restore

Verify that:

1. `PRAGMA integrity_check` returns `ok`.
2. Expected HMS tables exist.
3. Django can connect to the restored database.
4. `python manage.py showmigrations` shows the expected migrations as applied.
5. `python manage.py migrate --check` reports no unapplied migrations.
6. Representative HMS records can be queried.

For a live SQLite recovery, stop application writes before replacing the database. Preserve the existing database until the restored copy has been validated.

## 5. PostgreSQL backup and restore (deployment)

The commands below use PostgreSQL client utilities and environment-based connection settings. They contain no credentials. Configure `PGHOST`, `PGPORT`, `PGUSER`, and `PGDATABASE` for the intended database. Supply authentication through `PGPASSFILE` or an approved secret manager; do not hard-code passwords.

### 5.1 Create a custom-format backup

PowerShell example:

```powershell
$BackupDir = Join-Path $env:LOCALAPPDATA "HMSBackups"
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$BackupFile = Join-Path $BackupDir "hms-postgres-backup.dump"

pg_dump --format=custom --no-owner --file="$BackupFile" "$env:PGDATABASE"
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL backup failed."
}

Get-Item $BackupFile | Select-Object Name, Length, FullName
```

For deployment, set `$BackupDir` to the approved encrypted backup destination rather than a local workstation directory.

### 5.2 Restore into a separate non-production database

First ensure the target database does not already exist. Create it using an authorized database role:

```powershell
createdb --owner="$env:PGUSER" hms_restore_test
if ($LASTEXITCODE -ne 0) {
    throw "Could not create restore-test database. Check whether it already exists."
}
```

Restore the dump:

```powershell
pg_restore --no-owner --exit-on-error --dbname=hms_restore_test "$BackupFile"
if ($LASTEXITCODE -ne 0) {
    throw "PostgreSQL restore failed."
}
```

Never use a production database as the target for a restore test. Do not drop or overwrite an existing database without explicit approval and a verified recovery plan.

### 5.3 Verify the PostgreSQL restore

Point the Django environment configuration at the restored database (for this project, set `DATABASE_ENGINE=django.db.backends.postgresql` and set `POSTGRES_DB` to the restore database; provide the other `POSTGRES_*` connection settings through the approved secret mechanism).

Run:

```powershell
python manage.py check --database default
python manage.py showmigrations
python manage.py migrate --check
```

Also inspect tables and representative rows:

```powershell
psql -d hms_restore_test -c "\dt"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM accounts_user;"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM rooms_block;"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM rooms_room;"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM rooms_roomapplication;"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM complaints_complaint;"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM fees_feerecord;"
psql -d hms_restore_test -c "SELECT COUNT(*) FROM fees_payment;"
```

Finally, use Django ORM queries to confirm representative records and relationships can be read. Compare restored counts with the backup source's recorded counts.

## 6. Retention policy (proposed)

The following is a recommended baseline for deployment, not a currently implemented or approved production policy. The deployment owner must approve or replace it based on institutional requirements, storage capacity, and applicable policy.

| Backup frequency | Recommended retention |
| ---------------- | --------------------- |
| Daily            | 14 days               |
| Weekly           | 8 weeks               |
| Monthly          | 12 months             |

Keep deployment backups off-host, encrypted, access-controlled, and monitored. Local development backups are temporary recovery copies and are not a substitute for deployment backups. Expired backups should be securely deleted according to the approved policy.

## 7. Restore verification cadence (proposed)

| Activity                                        | Recommended frequency |
| ----------------------------------------------- | --------------------- |
| Check each scheduled backup job                 | After every run       |
| Restore into non-production and verify          | Monthly               |
| Restore test after major schema changes         | Before deployment     |
| Restore test after backup configuration changes | Immediately           |
| Review runbook and access assignments           | Quarterly             |

A successful backup command alone does not prove recoverability; a restore test is required.

## 8. Recovery procedure

1. Declare the incident and identify the recovery approver.
2. Identify the latest valid backup and confirm its size and timestamp.
3. Verify backup integrity where supported.
4. Restore into an isolated non-production database first.
5. Verify schema, migrations, and representative HMS records.
6. Have the independent restore checker review the results.
7. Obtain technical lead approval before production recovery.
8. Coordinate production restoration with the deployment owner and preserve the failed database and logs according to incident procedures.
9. After recovery, verify application health and record the incident outcome.

Do not overwrite a live database without an approved recovery plan. Production recovery must be coordinated with the deployment owner.

## 9. Git exclusion

The repository must exclude local database files, backup artifacts, temporary restore files, and secrets. The current `.gitignore` already excludes `*.sqlite3`, `.env`, and `.env.*` (while allowing `.env.example`). Additional backup patterns should include `/backups/`, `*.dump`, `*.backup`, and `*.bak`.

Before committing, check both staged and untracked files. Never stage backup files or secrets.

## 10. Verification record

Verification performed: 1 November 2026. These are local non-production tests, not a production recovery drill.

### SQLite

- Created a backup using Python's SQLite online backup API.
- Backup integrity check returned `ok`.
- Restored into a separate SQLite file; restore integrity check returned `ok`.
- The restored database contained 18 tables.
- Django connected to the restored file; all listed migrations were applied and no unapplied migrations were reported.
- Queried representative table counts: users 1, blocks 3, rooms 4, room applications 0, room allocations 0, complaints 0, fee records 0, and payments 0.

### PostgreSQL

- Environment: PostgreSQL 17.11 on Windows.
- Source test database: `hms_issue35_backup_source`.
- Restore test database: `hms_issue35_restore_test`.
- Created a custom-format backup (53,859 bytes) and restored it with `pg_restore`; restore exited successfully.
- The restored database contained 17 tables.
- Restored counts: users 2, blocks 1, rooms 1, room applications 1, complaints 1, fee records 1, and payments 1.
- Django database system check passed; `showmigrations` showed all applicable migrations applied; `migrate --check` reported no unapplied migrations.
- Django ORM retrieved the synthetic student's email, room details, and payment amount (`1000.00`).

The PostgreSQL test used synthetic records in dedicated non-production databases. The existing `hostel_concurrency_test` database was not used as the restore target and was left untouched.

## 11. Limitations and follow-up

- Production backup scheduling and storage infrastructure must be configured by the deployment team.
- Retention values, named operators, and checker assignments require deployment-owner approval.
- Production recovery time objective (RTO) and recovery point objective (RPO) must be defined by the deployment owner.
- Restore verification must continue at the cadence approved for the deployment environment.
