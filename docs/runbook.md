# Deployment and recovery runbook

## Runtime layout

`docker-compose.yml` runs PostgreSQL 16, Redis 7, the Django API, Celery worker, Celery beat, and nginx. Nginx serves the Vite build, proxies `/api/`, the configured admin path, and Django `/static/`, and writes access logs without query strings. Django `collectstatic` writes into a named volume shared read-only with nginx. PostgreSQL and Redis data use persistent named volumes.

The API container runs as UID 10001. Its entrypoint waits for PostgreSQL, migrates, collects static assets, and then runs `launch_check --production` unless `RUN_LAUNCH_CHECK` is disabled. The default is enabled. The API must pass its health check before the worker, beat, or web service starts.

## First deploy

1. Install Docker Engine and Docker Compose plugin 2.24 or later. Clone the repository on the deployment host. Configure the host's registry login before deploying private images.
2. Copy `.env.production.example` to `.env.production` and store the filled file in a protected location on the host. This example intentionally contains empty values. Configure `SECRET_KEY`, database credentials, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, a random `ADMIN_URL`, image references, and TLS proxy settings. Keep `.env.production` out of source control.
3. Configure the TLS ingress to reach the web container on the host's loopback binding. It must overwrite `X-Forwarded-Proto` with the original request scheme. Set `TRUST_PROXY_HEADERS=True` only when that trust boundary is enforced. The application hostnames and trusted origins come from the environment; no public hostname is built into these assets.
4. Validate the production Compose model and start the data services:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml config --quiet
   docker compose --env-file .env.production -f docker-compose.yml up -d db redis static-init
   docker compose --env-file .env.production -f docker-compose.yml up -d --wait db redis
   ```

5. Apply migrations and create the first operator while ingress is still closed:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml run --rm --no-deps --entrypoint python api manage.py migrate --noinput
   docker compose --env-file .env.production -f docker-compose.yml run --rm --no-deps --entrypoint python api manage.py createsuperuser
   ```

   `createsuperuser` creates a Django superuser. Assign the GaariDoc admin role to that account through the trusted admin workflow or a controlled Django shell operation; Django's `is_staff` alone does not grant the application admin role.
6. Import reviewed diagnostic content and have a reviewer approve/publish enough flows for the launch gate. During this closed-ingress bootstrap only, set `RUN_LAUNCH_CHECK=0` in the protected environment if an API container is needed to use the admin UI. Do not expose traffic while the gate is disabled. Re-enable it immediately afterward.
7. Check readiness, then start the full stack with the gate enabled:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml run --rm --no-deps --entrypoint python api manage.py launch_check --production
   docker compose --env-file .env.production -f docker-compose.yml up -d --remove-orphans --wait
   docker compose --env-file .env.production -f docker-compose.yml ps
   ```

   The API entrypoint repeats the launch check before Gunicorn starts. A nonzero gate result prevents the API becoming healthy and blocks the web, worker, and beat dependencies.

## Normal deployment and launch gate

The Deploy GitHub Actions workflow runs only after the CI workflow succeeds on `main`. Configure the repository variable `CONTAINER_REGISTRY` and the secrets `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH`, `DEPLOY_SSH_KEY`, and `DEPLOY_KNOWN_HOSTS`. The deployment host must already be authenticated to the image registry and have `.env.production` installed. The workflow builds and pushes commit-tagged API and web images, updates the Compose file, applies migrations, then runs `python manage.py launch_check --production` against the production database before replacing the running services. The gate is a blocking command; the API startup gate also remains enabled.

To inspect or run the gate manually:

```sh
docker compose --env-file .env.production -f docker-compose.yml exec api python manage.py launch_check --production
docker compose --env-file .env.production -f docker-compose.yml exec api python manage.py launch_check --production --min-flows 3
```

Do not route traffic if the command fails. The output names each failed check and the offending records. Fix or review the data, then rerun the gate. Change the overall minimum with `LAUNCH_MIN_FLOWS` or the command option.

## Rollback

1. Keep the previous API and web image tags available in the registry. Set `API_IMAGE` and `WEB_IMAGE` in the deployment environment to the last known-good tags.
2. Run `docker compose --env-file .env.production -f docker-compose.yml pull api worker beat web`, then `docker compose --env-file .env.production -f docker-compose.yml up -d --remove-orphans --wait`.
3. Check health and logs with `docker compose --env-file .env.production -f docker-compose.yml ps` and `docker compose --env-file .env.production -f docker-compose.yml logs --tail=200 api web worker beat`.

Database migrations must remain backward-compatible with the previous image for a rollback to be safe. For an incompatible schema change, restore a verified backup to a new database and point the rolled-back deployment at that database; do not run an unreviewed reverse migration against production.

## Secret rotation

- Rotate `SECRET_KEY` through the secret manager, update `.env.production`, and recreate API, worker, and beat. This invalidates JWTs signed with the previous key; users may need to sign in again.
- Rotate database credentials by creating a replacement PostgreSQL role, granting it the required database privileges, updating `POSTGRES_USER`/`POSTGRES_PASSWORD` and the role configuration, then recreating application containers. Do not print the secret in a terminal transcript or CI log.
- Rotate S3 credentials or the storage-provider IAM role independently. Confirm a backup upload and test download after rotation.
- Rotate LLM and Sentry credentials in their provider consoles, update their environment variables, and recreate the API/worker. Leave optional integrations unset when unused.
- Rotate SSH deploy keys and registry tokens in GitHub and the deployment host. Update GitHub Actions secrets and remove the old host key or token after confirming the new deployment.

## Backup schedule and retention

`scripts/backup.sh` creates a PostgreSQL custom-format dump, uploads it to `s3://$S3_BUCKET/$BACKUP_PREFIX/` using the AWS CLI, and removes objects older than `BACKUP_RETENTION_DAYS`. Install the AWS CLI on the deployment host. Set `S3_ENDPOINT_URL` for an S3-compatible provider and `AWS_DEFAULT_REGION` as required. Prefer an instance/workload IAM role; otherwise inject `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` through the host's secret manager. The script never writes credentials into the dump or its output.

Install a daily systemd timer or cron job at the chosen off-peak time. For systemd, use a protected `EnvironmentFile` with `S3_BUCKET`, `BACKUP_PREFIX`, `BACKUP_RETENTION_DAYS`, optional S3 endpoint/region, and `COMPOSE_ENV_FILE` pointing to `.env.production`; use the machine's IAM identity for S3 access where possible. Run the script once manually after installing the schedule and verify the object exists in the bucket. Retention defaults to 30 days if unset; configure a longer period if policy requires it.

```sh
COMPOSE_ENV_FILE=/srv/gaaridoc/.env.production sh /srv/gaaridoc/scripts/backup.sh
```

Never put credentials in the crontab line or command arguments. Use a root-readable systemd environment file or a managed workload identity.

## Restore drill (NFR-14: recovery under 4 hours)

Perform a restore drill at least quarterly and after changing PostgreSQL, the backup format, or S3-compatible storage. Target recovery time is under four hours from incident declaration to verified service. Record start/end times and the backup object used.

1. Select a recent backup and verify the database and Compose environment are healthy. Keep production traffic on the existing database during a drill.
2. Inject S3 access through the host IAM role/secret manager and set `COMPOSE_ENV_FILE` to the production Compose environment file. Create a unique, empty restore target name that is different from `POSTGRES_DB`.
3. Restore into the new database. The script refuses to overwrite the configured live database and refuses an existing database name:

   ```sh
   RESTORE_CONFIRM=YES RESTORE_TARGET_DB=restore_drill_YYYYMMDD \
     sh scripts/restore.sh s3://BUCKET/PREFIX/BACKUP.dump
   ```

4. Check the restored schema and row counts, then run the launch gate against the restored database using a one-off API container with `DB_NAME` set to the restore target:

   ```sh
   docker compose --env-file .env.production -f docker-compose.yml run --rm \
     -e DB_NAME=restore_drill_YYYYMMDD api python manage.py launch_check --production
   ```

   Run a sample diagnosis and confirm the reviewer/admin login works before accepting the drill.
5. Delete the drill database after recording the result. To recover production, keep the old database intact, update `POSTGRES_DB`/application DB configuration to the verified restored database during a controlled maintenance window, and recreate the app services. Verify health, launch gate, diagnosis, notifications, and admin access before reopening traffic.

The restore script requires `RESTORE_CONFIRM=YES`, creates a separate database, and never drops or overwrites the live database. This supports validation before promotion and makes the restore drill safe to repeat.

## Adding a mechanic

Mechanics register through the app. New mechanic accounts and profiles remain unverified until an admin/reviewer completes the verification process. Confirm identity and workshop details outside the user-submitted fields, approve the profile through the reviewer/admin workflow, and verify the profile is marked verified before it appears as a verified mechanic. Never grant staff or reviewer privileges to a mechanic account as part of ordinary verification.

## Local development stack

Copy `.env.production.example` to the ignored root `.env` and fill local-only `SECRET_KEY`, PostgreSQL user/password, `ADMIN_URL`, and local allowed/CSRF origins. The automatic `docker-compose.override.yml` enables Django debug mode, draft content, local HTTP cookies, disables only the production launch gate, and binds web/database ports to loopback. Then run:

```sh
docker compose config --quiet
docker compose up --build
```

Open the configured local web port. For production operations always pass `--env-file .env.production -f docker-compose.yml`; this omits the local override.
