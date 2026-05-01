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
git clone https://github.com/yourusername/punch.git
cd punch
```

### 2. Configure your environment

```bash
cp .env.example .env
```

Open `.env` in a text editor and fill in your details:

```
BUSINESS_NAME=Your Name
BUSINESS_ADDRESS=123 Main Street
BUSINESS_CITY_STATE_ZIP=Springfield, MA 01101
BUSINESS_EMAIL=you@example.com
BUSINESS_PHONE=413-555-1234

# Generate a secret key:
# python3 -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=paste-your-generated-key-here

POSTGRES_PASSWORD=choose-a-strong-password
DATABASE_URL=postgresql://punch:choose-a-strong-password@db:5432/punch
```

**Important:** `POSTGRES_PASSWORD` in the `.env` must match the password in `DATABASE_URL`.

### 3. Start Punch

```bash
docker-compose up -d
```

First run will take a minute or two while Docker builds the image.

### 4. Open Punch

Go to `http://your-server-ip:5000` in your browser.

You'll be greeted with a first-run setup screen. Create your username and password.

---

## Synology NAS Setup

1. Install **Container Manager** from Package Center (DSM 7.2+)
2. Copy the `punch` folder to your Synology (via File Station or `scp`)
3. Open **Container Manager → Project → Create**
4. Point it at the `punch` folder
5. Docker Compose will handle the rest

Access it at `http://your-synology-ip:5000`.

### With Tailscale (recommended for private access)

If you have Tailscale installed on your Synology and your phone:
- Access Punch at `http://your-tailscale-hostname:5000` from any device on your tailnet
- No port forwarding, no public exposure

---

## Adding Punch to Your Phone's Home Screen

**iOS Safari:**
1. Go to `http://your-server:5000/time/punch`
2. Tap the Share button → "Add to Home Screen"
3. Name it "Punch"

**Android Chrome:**
1. Go to `http://your-server:5000/time/punch`
2. Tap the menu (⋮) → "Add to Home screen"

---

## Importing from Harvest

Export your time entries from Harvest:
1. In Harvest: **Reports → Time → Detailed**
2. Set your date range (all time if you want full history)
3. Click **Export → CSV**

Then run the import:

```bash
# Copy your CSV into the punch folder first
docker-compose exec app python scripts/import_harvest.py /path/to/harvest_export.csv
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

1. Go to a client's page
2. Click **Invoice [Month]** in the top right
3. Review the line items (retainer + any overage)
4. Add notes if needed, click **Create Invoice**
5. Download the PDF and email it

### Marking an invoice paid

1. Go to **Invoices**
2. Click the invoice number
3. Click **Mark paid**

---

## Updating Punch

```bash
git pull
docker-compose up -d --build
```

Your database is stored in a Docker volume and is not affected by updates.

---

## Backup

Your data lives in the `postgres_data` Docker volume. To back it up:

```bash
docker-compose exec db pg_dump -U punch punch > punch_backup_$(date +%Y%m%d).sql
```

To restore:

```bash
cat punch_backup_20250101.sql | docker-compose exec -T db psql -U punch punch
```

---

## Configuration Reference

All configuration is in `.env`. Key variables:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Flask session secret. Generate once, never change. |
| `DATABASE_URL` | PostgreSQL connection string. |
| `POSTGRES_PASSWORD` | Database password (must match DATABASE_URL). |
| `BUSINESS_NAME` | Your name/business — appears on all invoices. |
| `BUSINESS_ADDRESS` | Street address on invoices. |
| `BUSINESS_CITY_STATE_ZIP` | City/state/zip on invoices. |
| `BUSINESS_EMAIL` | Your email on invoices. |
| `BUSINESS_PHONE` | Your phone on invoices. |
| `INVOICE_START_NUMBER` | First invoice number (default: 1001). |
| `TZ` | Timezone (default: `America/New_York`). |

---

## License

MIT. Use it, fork it, share it. Attribution appreciated but not required.

---

## Origin

Built because Harvest got sold to private equity and nerfed the free tier. Sometimes that's all the motivation you need.
