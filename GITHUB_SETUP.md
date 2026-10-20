# Free GitHub Actions setup

The hosted daily schedule is disabled until repository variable SCHEDULE_ENABLED is exactly true. Windows scheduling remains enabled until hosted manual tests succeed and you switch over. GitHub schedule targets 00:00 UTC = 08:00 Malaysia time, with a 00:23 UTC retry. GitHub schedules can run late or be dropped; this is not a guarantee of exactly 08:00 delivery. Fixed daily windows and deduplication still apply.

## 1. Create a private repository

Sign into https://github.com/. Click + at the top right > New repository. Repository name: gmail-prize-alerts. Choose Private. Leave Add README, .gitignore and license unchecked because these files already exist locally. Click Create repository. Copy the repository URL (safe to share in chat). Do not upload .env, token.json, credentials JSON, SQLite files, or .cloud-state-key.

## 2. Upload code

The assistant can configure the Git remote after you provide the repository URL. Git for Windows authenticates in your browser when pushing. Never paste a GitHub token into chat. A private repository must remain private: its alert-state branch contains encrypted operational state and inherited code/history.

## 3. Add three repository secrets

Open your repository > Settings > Secrets and variables > Actions > Secrets > New repository secret. Add each exact name below. Copy its value locally using PowerShell from the project folder (commands do not print secrets):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\copy-github-secret.ps1 -Name STATE_ENCRYPTION_KEY
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\copy-github-secret.ps1 -Name TELEGRAM_BOT_TOKEN
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\copy-github-secret.ps1 -Name TELEGRAM_CHAT_ID
```

Run one command, paste into the corresponding secret Value field and click Add secret, then repeat with the next name. After finishing, clear the clipboard with `Set-Clipboard -Value ''`. Protect clipboard history too. Never share these values in chat. No separate Gmail secret is required: cloud/initial-state.enc already contains your locally authorized token and delivery database, encrypted with STATE_ENCRYPTION_KEY. The key stays in .cloud-state-key locally and in GitHub Secrets remotely. Keep a secure local backup of the project and key. Do not regenerate the key independently of the encrypted state.

## 4. Manual cloud tests

Open Actions > Gmail Prize Alerts > Run workflow. Choose main and command dry-run. Wait for a green check and inspect counts. Next run telegram-test, and verify the Telegram notification. Then run command run and check delivery/state save. Existing sent alerts from local tests are included in encrypted initial state and will not routinely repeat. A successful run creates/updates the alert-state branch's state.enc file. Do not delete or edit that branch. Never run Actions on that state branch; use main. If Actions is restricted, Settings > Actions > General must allow GitHub-owned actions and Read and write workflow permissions; the workflow requests contents:write for state only. Branch rules must permit its writes to alert-state.

## 5. Enable hosted schedule and disable Windows

Only after the cloud tests pass, open Settings > Secrets and variables > Actions > Variables > New repository variable. Name SCHEDULE_ENABLED, value true. Saving enables the hosted schedule. Disable the local task to prevent independent local/cloud histories sending duplicates:

```powershell
Disable-ScheduledTask -TaskName 'Gmail Prize Alerts'
```

Verify in Task Scheduler that the local task is Disabled. To stop cloud scheduling, change SCHEDULE_ENABLED to false. The hosted schedule works with your laptop off. You may close Codex and your browser.

## Reliability, privacy and cost

Standard Ubuntu runner, one serialized workflow, short daily runs and a retry. GitHub Free private-repository minute and storage allowances apply across your account; check Settings > Billing and licensing > Usage. No paid runner is requested. No public web endpoint, domain, Docker or external database is required. Do not enable paid overage if you want a strict free setup.

The runner decrypts state, verifies the authorized mailbox, scans, sends only to the private configured chat, and saves refreshed OAuth credentials plus SQLite back to encrypted state. It attempts state saving even after a scanner failure. Missing or undecryptable existing state stops the job rather than silently resetting deduplication. The latest encrypted state is kept in the private alert-state branch, so it does not expire like an artifact/cache. Git history retains previous ciphertext snapshots; they remain sensitive and decryptable with the key. Repository collaborators able to modify workflows can potentially access secrets; do not grant untrusted write access.

A runner kill or GitHub state-save failure after Telegram accepts a delivery can cause duplicate notifications next time. This cannot be eliminated by SQLite on an ephemeral runner. Normal API/network failures have retries and preserve confirmed part status when state saving succeeds. GitHub concurrency prevents overlapping runs in this workflow; it cannot synchronize an independently enabled Windows scanner. Avoid cancelling active delivery runs. The cloud timeout is 30 minutes. Daily large mail volumes may require further tuning.

Google External/Testing refresh tokens still expire after seven days for Gmail access. Before relying on unattended operation, use Google Auth Platform > Audience to review publishing In production for your private personal use, then reauthorize locally as the student account. To update cloud authorization later, generate a new encrypted bootstrap locally and deliberately replace cloud state/token through a reviewed migration; do not delete delivery history. University restrictions still apply.

Official documentation:
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
- https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions

## Local verification

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Tests verify encrypted state round trips, preservation of sent and pending parts, rejection of wrong keys, and overlap locking, alongside scanner tests. Windows tests are completed locally; the first Actions dry-run also runs the suite on Ubuntu before using real secrets.

## Verified activation

Cloud dry-run (39471776134), Telegram test (39471901626), and normal scan (39472060820) completed successfully. User confirmed receiving the hosted Telegram test. Repository variable SCHEDULE_ENABLED was set to true and verified. Local Windows task Gmail Prize Alerts was disabled and verified Enabled=false. The GitHub daily schedule is now active at 00:00 UTC (08:00 Malaysia), with a 00:23 UTC recovery attempt. Google OAuth publishing status has not been verified; External/Testing expiry remains a configuration item to check.

## Renew cloud Gmail authorization without resetting deliveries

After moving Google OAuth to In production, run `.\.venv\Scripts\python.exe -m prize_alerts authorize` and choose the student account. Then run `.\.venv\Scripts\python.exe -m prize_alerts.cloud sync-token`. This verifies the mailbox, downloads the latest encrypted cloud state, replaces only the OAuth token and saves with an optimistic SHA check. It does not replace cloud delivery history with an older local database. If a concurrent update produces HTTP 409, repeat sync-token after that workflow completes. Do not use prepare to reset an existing cloud deployment.
