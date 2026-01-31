# Sales Report Generator 📊

This module generates a daily sales report by parsing `transactions.log` and `dispense.log` found in the project's log directory.

Usage

- Generate a report for yesterday (default):
  ```bash
  python -m reports.sales_report
  ```

- Generate for a specific date:
  ```bash
  python -m reports.sales_report --date 2025-01-11
  ```

Output

- `./logs/reports/YYYY-MM-DD-sales-report.txt` (human readable)
- `./logs/reports/YYYY-MM-DD-sales-report.json` (machine readable)

Notes

- If `item_list.json` is present (project root), prices will be used to estimate per-item revenue.
- If prices are not available, total daily revenue is estimated from transactions found in `transactions.log`.

Automating daily runs (systemd timer example)

Create `/etc/systemd/system/raon-sales-report.service`:

```
[Unit]
Description=RAON daily sales report

[Service]
Type=oneshot
WorkingDirectory=/path/to/raon-vending-rpi4-main
ExecStart=/usr/bin/python3 -m reports.sales_report
```

Create `/etc/systemd/system/raon-sales-report.timer`:

```
[Unit]
Description=Run RAON sales report daily at 00:05

[Timer]
OnCalendar=*-*-* 00:05:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start the timer:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now raon-sales-report.timer
```

This will generate the report for the previous day (default) and save it under `./logs/reports/`.

Email reports

You can enable automatic emailing of the daily report by adding an `email` section to your `config.json` following the example in `config.example.json`. For security, prefer setting the SMTP password in an environment variable and referencing it via `password_env` (example: `"password_env": "RAON_SMTP_PASSWORD"`). The report generator will attach both the TXT and JSON report files and send them to the configured recipients after report generation.
