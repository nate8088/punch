# Punch

Simple time tracking and invoicing for freelancers. Self-hosted, no subscriptions, no nonsense.

**Built for:** Solo contractors who bill one or more clients, some on retainer, some hourly. Punch tracks your hours, generates invoices, and stays out of your way.

---

## Features

- **Punch in/out** — mobile-friendly timer screen, works from your phone browser
- **Manual time entry** — add entries by hand with date, time, and notes
- **Retainer billing** — fixed monthly rate with a configurable hour cap; overage tracked automatically
- **Hourly billing** — standard rate × hours
- **Monthly invoices** — auto-generated from your logged hours with one click
- **Auto-invoicing** — automatically generate and optionally send invoices on the 1st of each month
- **Project/manual invoices** — custom line items for one-off work
- **PDF download** — clean, professional invoice PDF for emailing
- **Harvest import** — bring in your history from Harvest via CSV export
- **Multi-device** — runs on your own hardware, accessible from phone + desktop via Tailscale (or any network)

---

## Requirements

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- That's it.

Designed to run on a Synology NAS, home server, or cheap VPS. Tested on Docker 24+.

---

## Quick Start

### 1. Get the files

```bash
git clone https://github.com/nate8088/punch.git
cd punch
```

### 2. Configure your environment

```bash
cp .env.example .env
```

Open `.env` and fill in three values:

```
# Generate a secret key:
# python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=paste-your-generated-key-here

POSTGRES_PASSWORD=choose-a-strong-password
DATABASE_URL=postgresql://punch:choose-a-strong-password@db:5432/punch
```

**Important:** `POSTGRES_PASSWORD` and the password in `DATABASE_URL` must match.

Business details (name, address, email, etc.) are configured inside the app under **Settings** — not in `.env`.

### 3. Start Punch

```bash
docker compose up -d
```

First run will take a minute or two while Docker builds the image.

### 4. Open Punch

Go to `http://your-server-ip:8088` in your browser.

You'll be prompted to create an account, then redirected to Settings to fill in your business details.

---

## Synology NAS Setup

1. Install **Container Manager** from Package Center (DSM 7.2+)
2. Copy the `punch` folder to your Synology (via File Station or `scp`)
3. Open **Container Manager → Project → Create**
4. Point it at the `punch` folder
5. Docker Compose will handle the rest

Access it at `http://your-synology-ip:8088`.

### With Tailscale (recommended for private access)

If you have Tailscale installed on your Synology and your phone:
- Access Punch at `http://your-tailscale-hostname:8088` from any device on your tailnet
- No port forwarding, no public exposure

---

## Adding Punch to Your Phone's Home Screen

**iOS Safari:**
1. Go to `http://your-server:8088/time/punch`
2. Tap the Share button → "Add to Home Screen"
3. Name it "Punch"

**Android Chrome:**
1. Go to `http://your-server:8088/time/punch`
2. Tap the menu (⋮) → "Add to Home screen"

---

## Importing from Harvest

Export your time entries from Harvest:
1. In Harvest: **Reports → Time → Detailed**
2. Set your date range (all time if you want full history)
3. Click **Export → CSV**

Then run the import:

```bash
docker compose exec app python scripts/import_harvest.py /path/to/harvest_export.csv
```

The script will interactively match Harvest client names to your Punch clients. It's safe to run multiple times — duplicate entries are detected and skipped.

---

## Usage

### Setting up a retainer client

1. Go to **Clients → New Client**
2. Set **Billing mode: Retainer**
3. Enter:
   - **Monthly retainer amount** — the fixed fee you invoice each month
   - **Included hours** — your soft cap (e.g. 12). Hours above this show as overage — you decide whether to bill them.
   - **Overage rate** — hourly rate if you do invoice overages

### Logging time

**From your phone:**
- Tap the **Clock** link in the nav (or open the home screen shortcut)
- Select a client, tap **Punch In**
- Tap **Punch Out** when done
- You'll be taken to an edit screen to add a description

**Manually:**
- Go to **Time → New Entry**
- Set client, date/time, and duration

### Generating a monthly invoice

1. Go to a client's detail page
2. Click **Invoice [Month]** in the top right
3. Review the line items (retainer + any overage)
4. Add notes if needed, click **Create Invoice**
5. Download the PDF and email it

### Auto-invoicing

Punch can automatically generate invoices on the 1st of each month:

1. Go to **Settings → Email / SMTP** and configure your outgoing mail server
2. Go to **Settings → Auto-invoicing** and choose a mode:
   - **Draft mode** — creates a draft invoice and emails you a notification to review it
   - **Send mode** — sends the PDF directly to the client and CCs you
3. On each client's edit page, enable **Auto-generate monthly invoice**

If Punch is down on the 1st, it will catch up and generate any missed invoices on next startup.

### Marking an invoice paid

1. Go to **Invoices**
2. Click the invoice number
3. Click **Mark paid**

---

## Updating Punch

```bash
git pull
docker compose up -d --build
```

Your database is stored in a Docker volume and is not affected by updates.

---

## Backup

Your data lives in the `postgres_data` Docker volume. To back it up:

```bash
docker compose exec db pg_dump -U punch punch > punch_backup_$(date +%Y%m%d).sql
```

To restore:

```bash
cat punch_backup_20250101.sql | docker compose exec -T db psql -U punch punch
```

---

## Configuration Reference

All business details and app preferences are configured inside Punch under **Settings**. The `.env` file only needs three values:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret. Generate once, never change. |
| `DATABASE_URL` | PostgreSQL connection string. |
| `POSTGRES_PASSWORD` | Database password (must match `DATABASE_URL`). |

---

## License

MIT. Use it, fork it, share it. Attribution appreciated but not required.

---

## Origin

Built because Harvest got sold to private equity and nerfed the free tier. Sometimes that's all the motivation you need.
