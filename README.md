# Gmail Prize Alerts

A local Windows Python project for 23118637@siswa.um.edu.my. No AI service, GitHub, hosting or subscription is required.

## Start here

Open PowerShell in C:\Users\chuay\gmail-prize-alerts. All commands below run there; activation of the virtual environment is unnecessary.

1. Authorize Gmail:

```powershell
.\.venv\Scripts\python.exe -m prize_alerts authorize
```

Choose **23118637@siswa.um.edu.my**, even though chuayujien@gmail.com owns the Google Cloud project. Approve Gmail read-only permission. The command checks the actual Gmail profile before saving token.json. Do not create token.json yourself. Do not paste any credentials into chat.

If Google setup is incomplete: sign into https://console.cloud.google.com/ as the personal project owner, select **Gmail Prize Alerts**, open **APIs & Services > Library > Gmail API > Enable**. Open **Google Auth Platform > Audience**: External, and add the student account under Test users while Testing. Under **Data Access**, add only https://www.googleapis.com/auth/gmail.readonly. Under **Clients**, use a Desktop app client, download its JSON directly to this folder as credentials.json. An existing Desktop configuration was found in credentials.json.json and copied to credentials.json; both are ignored by Git. Their presence does not establish which Cloud project or audience configuration they belong to.

2. Open .env locally using Notepad:

```powershell
notepad .env
```

Replace only the TELEGRAM_BOT_TOKEN placeholder with your BotFather token, save and close. Never paste it in chat. Open your bot in Telegram, press **Start**, and send **hello**. Then:

```powershell
.\.venv\Scripts\python.exe -m prize_alerts telegram-setup
```

This saves the private chat ID into .env. If multiple private chats appear, it lists their IDs and requires you to select explicitly:

```powershell
.\.venv\Scripts\python.exe -m prize_alerts telegram-setup --chat-id YOUR_PRIVATE_ID
```

Updates expire after 24 hours; send another hello if none appear. A webhook or another polling program using this bot can interfere; use a bot dedicated to this project.

3. Test Telegram, then Gmail without delivery:

```powershell
.\.venv\Scripts\python.exe -m prize_alerts telegram-test
.\.venv\Scripts\python.exe -m prize_alerts dry-run
```

Dry-run prints counts only, does not send alerts, and does not mark windows completed. It may create an empty local database and refresh OAuth credentials. It intentionally does not print email bodies.

4. Perform the manual end-to-end test:

Send a message from another account to your student inbox with subject `Prize test`, body `Register for the prize at https://example.org/register?test=1&utm_source=manual`. Use an explicit window containing its received timestamp (end must be after the message):

```powershell
.\.venv\Scripts\python.exe -m prize_alerts dry-run --start 2026-10-21T00:00:00+08:00 --end 2026-10-22T00:00:00+08:00
.\.venv\Scripts\python.exe -m prize_alerts run --start 2026-10-21T00:00:00+08:00 --end 2026-10-22T00:00:00+08:00
```

Adjust dates to your test. The second command sends ALL matched messages in that window to your configured private chat. Verify the subject, sender, original wording and full query string in Telegram. example.org is only a test link; no links are followed by the program.

## Daily use and recovery

```powershell
.\.venv\Scripts\python.exe -m prize_alerts run
.\.venv\Scripts\python.exe -m prize_alerts recover
.\.venv\Scripts\python.exe -m prize_alerts status
```

`run` scans closed 08:00-to-08:00 Malaysia windows and delivers queued parts. Before 08:00 the most recent boundary is yesterday at 08:00. First normal run starts with the latest closed daily window; it does not download your entire history. After initialization all missed windows are recovered from the earliest stored scheduled window. Explicit windows do not advance the daily cursor. `recover` retries queued deliveries without scanning Gmail. Repeating an explicit scan does not routinely repeat sent parts. To backfill earlier dates use both --start and --end with timezone offsets. Explicit windows are inclusive at start, exclusive at end, and may have arbitrary lengths.

Individual messages are retrieved with pagination and checked against Gmail internalDate milliseconds. Read, unread and archived received messages are included. Spam, Trash, drafts and sent-only messages are excluded. No thread-level matching is used. Keywords prize, prizes, and win use case-insensitive whole-word boundaries. Gmail candidate queries use dates only so local keyword matching is authoritative.

Plain text is preferred when a MIME email includes alternatives. HTML is decoded and visible paragraphs extracted when no plain text exists. Subject and From header values are decoded from email encoding. Original prize paragraphs and instruction paragraphs are copied without paraphrasing. HTML layout whitespace is necessarily converted into text. Attachments and OCR are excluded. Participation identification uses deterministic keyword/context rules; ambiguous layouts can include extra plausible links or miss a link. Check Gmail when the fallback is present. Footer links are filtered by label and URL; inspect real manual results before relying on extraction. No URL is shortened, followed, or stripped of tracking parameters.

Telegram uses plain text with previews disabled. Long alerts split without discarding characters, counting UTF-16 units conservatively. Normal URLs stay intact when they fit; a single URL longer than a Telegram message necessarily crosses message boundaries and must be reassembled by joining consecutive parts. Email content cannot introduce Telegram markup. Each delivered part is committed separately. A crash/network timeout after Telegram accepts a part but before SQLite records success can cause a duplicate on retry; Telegram has no sendMessage idempotency key. Rate limits and temporary failures are retried; failures remain pending. Keep the same database to retain deduplication. Changing the destination does not reset sent status.

## Windows Task Scheduler — enable only after manual verification

No task is registered or enabled by the project installation. After the manual tests pass, and only when you choose to enable it:

```powershell
.\setup-task.ps1
```

This registers a **disabled** task. Review it in Start > Task Scheduler > Task Scheduler Library > Gmail Prize Alerts > Properties. Its action uses the absolute path `C:\Users\chuay\gmail-prize-alerts\.venv\Scripts\python.exe`, arguments `-m prize_alerts run`, and working directory `C:\Users\chuay\gmail-prize-alerts`.

When you have explicitly confirmed activation:

```powershell
.\setup-task.ps1 -EnableAfterManualTest
```

Type ENABLE at the local prompt. If local PowerShell execution policy blocks your own reviewed script, run `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\setup-task.ps1` (append -EnableAfterManualTest only when ready). This is process-local policy handling.

Set Windows Settings > Time & language > Date & time > Time zone to **(UTC+08:00) Kuala Lumpur, Singapore**. The script checks Windows zone ID `Singapore Standard Time`; Python independently uses Asia/Kuala_Lumpur. Daily trigger is 08:00 local Windows time. Settings include run as soon as possible after a missed start, wake to run, ignore overlapping instances, allow battery operation, and three retries five minutes apart. An additional OS file lock prevents overlapping CLI commands. Wake timers depend on your PC firmware/power plan. A powered-off PC cannot run; sleep wake is not guaranteed. Leave the computer powered, logged in, with internet. The default task runs in your interactive user session; running while logged out requires configuring that option in Task Scheduler and supplying your Windows credentials locally. It is not configured by this script. Recovery runs missed scan windows at the next successful invocation. Disable in Task Scheduler at any time.

## Google token lifetime and university policy

External apps in Testing using Gmail scopes get refresh tokens expiring after seven days. Reauthorize when needed. For ongoing personal use review **Google Auth Platform > Audience > Publish app** to move to In production, then obtain a new token through authorize. Production does not guarantee permanent tokens: revocation, inactivity and organizational policy can invalidate them. Personal-use exceptions may avoid verification for an app used only by you, but unverified warnings and user caps can apply. Gmail read-only is a restricted scope; do not assume public distribution is exempt from verification.

Official references:
- https://developers.google.com/identity/protocols/oauth2#expiration
- https://developers.google.com/identity/protocols/oauth2/production-readiness/overview
- https://developers.google.com/identity/protocols/oauth2/production-readiness/restricted-scope-verification
- https://support.google.com/cloud/answer/13464321
- https://developers.google.com/workspace/gmail/api/guides/filtering
- https://core.telegram.org/bots/api#sendmessage

If sign-in says access_denied, check the student test user first. For admin_policy_enforced or an organization-blocked app, ask the university Google Workspace administrator to review the Desktop OAuth client ID and approve Gmail read-only access under Admin console > Security > Access and data control > API controls > App access control. Do not bypass university controls. Generic CLI errors deliberately omit third-party exception details because they can contain secrets. Check the browser's error screen locally; never share tokens or credential JSON. A wrong-mailbox error requires removing token.json locally and reauthorizing as the student account. API disabled errors require enabling Gmail API in the owning Cloud project.

## Files, privacy and tests

- prize_alerts/core.py: deterministic email extraction, matching, windows and splitting.
- prize_alerts/__main__.py: CLI, OAuth, Gmail, Telegram, locking and SQLite recovery.
- credentials.json: downloaded Desktop OAuth client configuration; local secret.
- token.json: OAuth-generated authorization and refresh token; local secret.
- .env: bot token and chat ID; .env.example contains placeholders only.
- alerts.sqlite3: scan windows, message IDs, complete queued alert text, and per-part delivery status; sensitive local data.
- .run.lock: OS-managed overlap lock; file may remain after exit and is safe to leave.
- requirements.txt: dependency ranges; requirements-lock.txt records installed versions.
- tests/: offline tests; setup-task.ps1: scheduler preparation/activation helper.

No email bodies, tokens or credential contents are logged. Console operational output can contain dates, counts and metadata. The database contains email excerpts and sender/subject data for reliable retries, so protect this Windows account and local backups. Git exclusions cover secrets, virtual environments, database sidecars and logs; Git is available but no repository/remote has been created.

Reinstall and run offline tests:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Offline tests cover keyword boundaries, Malaysia boundaries, message filtering, MIME plain/HTML links, URL parameter preservation, missing links, lossless splitting, Gmail pagination and per-part delivery recovery. They do not establish that your Google/Telegram credentials or Windows scheduling work; those require manual verification.

Each Telegram part ends with the email Date header converted to Malaysia time, for example `Sent: Tue, Oct 20, 4:11 PM (Malaysia time)`. If that header is missing or invalid, Gmail received time is used and explicitly labelled. Scan boundaries still use Gmail received timestamps.

The footer uses each message's own sender Date dynamically, converted to Malaysia time. Mailing-list delivery can happen later than the sender timestamp displayed here.

## Scheduling activation record

The user approved scheduling after successful Gmail and Telegram manual tests. On 21 October 2026, Windows task `Gmail Prize Alerts` was registered and verified enabled/Ready, daily at 08:00 with Windows zone Singapore Standard Time (Malaysia UTC+08). The first planned window is 20 October 08:00 through 21 October 08:00 and is recorded as pending for recovery. The task uses the absolute virtual-environment Python and project working directory, Interactive logon, StartWhenAvailable and WakeToRun. Remain signed in; wake support depends on Windows power settings. The task had not yet run when enabled. Existing delivered message parts remain deduplicated.

## Free hosted deployment

See [GITHUB_SETUP.md](GITHUB_SETUP.md) for private GitHub Actions deployment, encrypted persistent delivery state, repository secrets, manual cloud tests and the final scheduling switch. Cloud scheduling is gated off until SCHEDULE_ENABLED=true.
