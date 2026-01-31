"""Daily Sales Report Generator

Parses `transactions.log` and `dispense.log` and generates a comprehensive sales
report for a given date. The report includes:
- Items sold (counts)
- Estimated revenue per item (if `item_list.json` with prices is present)
- Total revenue (from per-item prices, or from transactions as fallback)
- Number of transactions
- Top items (by count)
- Hourly sales breakdown

Usage (CLI):
    python -m reports.sales_report --date 2025-01-11
    python -m reports.sales_report         # generates report for YESTERDAY by default

Output:
    ./logs/reports/YYYY-MM-DD-sales-report.txt
    ./logs/reports/YYYY-MM-DD-sales-report.json

"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import re
from typing import Dict, Tuple, Optional

# Try to import the project's SystemLogger to find log directory and configuration
try:
    from system_logger import SystemLogger, get_logger
except Exception:
    SystemLogger = None


DATE_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \| \w+\s* \| (?P<msg>.+)$")
DISPENSE_RE = re.compile(r"\[.*\] Dispensed (?P<qty>\d+)x (?P<item>.+)$")
PAYMENT_RE = re.compile(r"Payment received: .* = PHP(?P<amount>\d+(?:\.\d{1,2})?)(?: \(for (?P<item>.+)\))?")
TXN_TOTAL_RE = re.compile(r"Transaction completed.*Total: PHP(?P<amount>\d+(?:\.\d{1,2})?)")


def find_log_dir() -> Path:
    """Return the logging directory as configured, or fallback to ./logs."""
    if SystemLogger:
        try:
            logger = SystemLogger()
            d = logger.get_log_directory()
            if d:
                return Path(d)
        except Exception:
            pass
    return Path('./logs')


def load_item_prices(project_root: Path) -> Dict[str, float]:
    """Load item prices from `item_list.json` if present. Returns mapping name -> price."""
    candidates = [project_root / 'item_list.json', project_root / 'config' / 'item_list.json']
    for p in candidates:
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                prices = {}
                # item_list.json is expected to be a list of items
                if isinstance(data, dict) and 'items' in data:
                    items = data['items']
                else:
                    items = data
                for it in items:
                    name = it.get('name')
                    price = it.get('price')
                    if name and isinstance(price, (int, float)):
                        prices[name] = float(price)
                if prices:
                    return prices
            except Exception:
                continue
    return {}


def parse_dispense_log(filepath: Path, target_date: str) -> Tuple[Counter, Dict[int, int]]:
    """Parse dispense.log for target_date (YYYY-MM-DD).

    Returns:
        item_counts: Counter of item_name -> quantity sold
        hourly_counts: dict hour (0-23) -> total items sold in that hour
    """
    item_counts = Counter()
    hourly = defaultdict(int)

    if not filepath.exists():
        return item_counts, hourly

    with filepath.open('r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            m = DATE_RE.match(line.strip())
            if not m:
                continue
            ts = m.group('ts')
            if not ts.startswith(target_date):
                continue
            msg = m.group('msg')
            md = DISPENSE_RE.search(msg)
            if not md:
                continue
            item = md.group('item').strip()
            qty = int(md.group('qty'))
            item_counts[item] += qty
            hour = int(ts[11:13])
            hourly[hour] += qty

    return item_counts, hourly


def parse_transaction_log(filepath: Path, target_date: str) -> Tuple[int, float, Counter]:
    """Parse transactions.log for target_date.

    Returns:
        txn_count: number of 'Transaction completed' entries
        total_payments: sum of payment amounts found
        item_payments: Counter of item_name -> amount (from 'Payment received ... (for ITEM)')
    """
    txn_count = 0
    total_payments = 0.0
    item_payments = Counter()

    if not filepath.exists():
        return txn_count, total_payments, item_payments

    with filepath.open('r', encoding='utf-8', errors='ignore') as fh:
        for line in fh:
            m = DATE_RE.match(line.strip())
            if not m:
                continue
            ts = m.group('ts')
            if not ts.startswith(target_date):
                continue
            msg = m.group('msg')
            if 'Transaction completed' in msg:
                txn_count += 1
                md = TXN_TOTAL_RE.search(msg)
                if md:
                    total_payments += float(md.group('amount'))
            else:
                mp = PAYMENT_RE.search(msg)
                if mp:
                    amt = float(mp.group('amount'))
                    total_payments += amt
                    it = mp.group('item')
                    if it:
                        item_payments[it.strip()] += amt

    return txn_count, total_payments, item_payments


def generate_report_for(date: str, project_root: Optional[Path] = None) -> Dict:
    project_root = (project_root or Path('.')).resolve()
    log_dir = find_log_dir()

    reports_dir = Path(log_dir) / 'reports'
    reports_dir.mkdir(parents=True, exist_ok=True)

    dispense_log = Path(log_dir) / 'dispense.log'
    transactions_log = Path(log_dir) / 'transactions.log'

    item_counts, hourly = parse_dispense_log(dispense_log, date)
    txn_count, total_payments, item_payments = parse_transaction_log(transactions_log, date)

    # Load item prices if available
    prices = load_item_prices(project_root)

    # Compute per-item revenue (only when price is known), otherwise try per-item payments as fallback
    item_revenue = {}
    total_revenue = 0.0

    if prices:
        for item, qty in item_counts.items():
            price = prices.get(item)
            if price is not None:
                revenue = price * qty
                item_revenue[item] = revenue
                total_revenue += revenue
            else:
                item_revenue[item] = None
    else:
        # Use item_payments as fallback to estimate revenue per item
        for item, amt in item_payments.items():
            item_revenue[item] = amt
            total_revenue += amt

    # If we found transaction totals but no per-item price mapping, prefer transaction totals for overall revenue
    if not prices and total_payments > total_revenue:
        total_revenue = total_payments

    # Add any payment amounts that aren't matched to items (e.g., 'Transaction completed')
    # As a safety, ensure total_revenue at least equals total_payments
    if total_payments > total_revenue:
        total_revenue = total_payments

    # Top items
    top_items = item_counts.most_common(10)

    # Prepare report dict
    report = {
        'date': date,
        'total_items_sold': sum(item_counts.values()),
        'distinct_items_sold': len(item_counts),
        'transactions': txn_count,
        'total_revenue': round(total_revenue, 2),
        'per_item_counts': dict(item_counts),
        'per_item_revenue': {k: (round(v, 2) if isinstance(v, (int, float)) else None) for k, v in item_revenue.items()},
        'top_items': top_items,
        'hourly_counts': dict(sorted(hourly.items())),
        'payments_unassigned_total': round(max(0.0, total_payments - sum(v for v in item_revenue.values() if isinstance(v, (int, float)))), 2)
    }

    # Write reports: text + json
    fname_base = f"{date}-sales-report"
    txt_path = reports_dir / f"{fname_base}.txt"
    json_path = reports_dir / f"{fname_base}.json"

    txt = format_report_text(report)
    txt_path.write_text(txt, encoding='utf-8')
    json_path.write_text(json.dumps(report, indent=2), encoding='utf-8')

    # Optionally send email when configured in project's config.json
    try:
        cfg_path = project_root / 'config.json'
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            email_cfg = cfg.get('email', {}) if isinstance(cfg, dict) else {}
            if email_cfg.get('enabled'):
                try:
                    from reports import emailer
                    subject = email_cfg.get('subject_template', 'RAON Sales Report - {date}').format(date=date)
                    body = txt
                    attachments = [str(txt_path), str(json_path)]
                    sent = emailer.send_email_with_attachments(email_cfg, subject, body, attachments)
                    if sent:
                        print('Report emailed successfully')
                    else:
                        print('Report email failed')
                except Exception as e:
                    print(f'Failed to send report email: {e}')
    except Exception:
        pass

    # Optionally upload reports to S3 and generate presigned links
    try:
        cfg_path = project_root / 'config.json'
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            s3_cfg = cfg.get('s3', {}) if isinstance(cfg, dict) else {}
            if s3_cfg.get('enabled'):
                try:
                    from reports import s3_uploader

                    bucket = s3_cfg.get('bucket')
                    region = s3_cfg.get('region')
                    expires = int(s3_cfg.get('expires_seconds', 86400) or 86400)
                    extra_args = s3_cfg.get('extra_args') or {}

                    uploaded_keys = []
                    for p in (txt_path, json_path):
                        key = f"reports/{p.name}"
                        try:
                            uploaded_key = s3_uploader.upload_file_to_s3(p, bucket, key=key, region=region, extra_args=extra_args)
                            uploaded_keys.append(uploaded_key)
                            print(f"Uploaded {p.name} to s3://{bucket}/{uploaded_key}")
                        except Exception as e:
                            print(f"S3 upload failed for {p.name}: {e}")

                    # Generate presigned URL for the JSON (or first uploaded) file
                    if uploaded_keys:
                        try:
                            presigned = s3_uploader.generate_presigned_url(bucket, uploaded_keys[0], expires_in=expires, region=region)
                            print(f"Presigned URL (expires in {expires}s): {presigned}")

                            # Optionally email the link
                            if s3_cfg.get('email_link'):
                                try:
                                    if 'email_cfg' not in locals():
                                        email_cfg = cfg.get('email', {})
                                    if email_cfg.get('enabled'):
                                        from reports import emailer
                                        subject = email_cfg.get('subject_template', 'RAON Sales Report - {date}').format(date=date)
                                        body = f"Daily sales report uploaded to S3: {presigned}\n\nThis link will expire in {expires} seconds."
                                        ok = emailer.send_email_with_attachments(email_cfg, subject, body, [])
                                        if ok:
                                            print('S3 link emailed successfully')
                                        else:
                                            print('Failed to email S3 link')
                                except Exception as e:
                                    print(f'Failed to email S3 link: {e}')

                        except Exception as e:
                            print(f"Failed to generate presigned URL: {e}")
                except Exception as e:
                    print(f"S3 integration error: {e}")
    except Exception:
        pass

    return report


def format_report_text(report: Dict) -> str:
    lines = []
    lines.append(f"Sales Report for {report['date']}")
    lines.append('=' * 40)
    lines.append(f"Total Items Sold: {report['total_items_sold']}")
    lines.append(f"Distinct Items Sold: {report['distinct_items_sold']}")
    lines.append(f"Transactions: {report['transactions']}")
    lines.append(f"Total Revenue: PHP{report['total_revenue']:.2f}")
    lines.append('')

    lines.append('Top items:')
    for item, cnt in report['top_items']:
        rev = report['per_item_revenue'].get(item)
        rev_str = f" — PHP{rev:.2f}" if isinstance(rev, (int, float)) else ''
        lines.append(f"  • {item}: {cnt} sold{rev_str}")
    lines.append('')

    lines.append('Per-item breakdown:')
    for item, cnt in sorted(report['per_item_counts'].items(), key=lambda x: -x[1]):
        rev = report['per_item_revenue'].get(item)
        rev_str = f" — PHP{rev:.2f}" if isinstance(rev, (int, float)) else ''
        lines.append(f"  • {item}: {cnt}{rev_str}")
    lines.append('')

    lines.append('Hourly counts:')
    for hour, cnt in report['hourly_counts'].items():
        lines.append(f"  {hour:02d}:00 - {cnt} items")
    lines.append('')

    lines.append(f"Payments unassigned to items: PHP{report['payments_unassigned_total']:.2f}")

    return '\n'.join(lines)


def _default_date_str(yesterday: bool = True) -> str:
    today = datetime.now().date()
    if yesterday:
        d = today - timedelta(days=1)
    else:
        d = today
    return d.isoformat()


def test_email(recipient: Optional[str], project_root: Optional[Path] = None) -> bool:
    """Send a small test email to verify SMTP config.

    If `config.json` exists it will be used; otherwise a sane Gmail default is
    constructed (smtp.gmail.com:587) and the recipient defaults to the
    `recipient` argument or `bsece4araon@gmail.com`.
    """
    project_root = (project_root or Path('.')).resolve()
    cfg_path = project_root / 'config.json'

    # Load existing config or build a default Gmail test config
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
            email_cfg = cfg.get('email', {}) if isinstance(cfg, dict) else {}
        except Exception:
            email_cfg = {}
    else:
        email_cfg = {}

    # Ensure we have a recipient
    recipient = recipient or (email_cfg.get('to')[0] if email_cfg.get('to') else 'bsece4araon@gmail.com')

    # Fill defaults if missing
    if not email_cfg.get('smtp_server'):
        email_cfg['smtp_server'] = 'smtp.gmail.com'
    if not email_cfg.get('smtp_port'):
        email_cfg['smtp_port'] = 587
    if 'use_tls' not in email_cfg:
        email_cfg['use_tls'] = True
    if not email_cfg.get('username'):
        # Default username to the recipient for quick testing
        email_cfg['username'] = recipient
    if not email_cfg.get('from'):
        email_cfg['from'] = recipient
    if not email_cfg.get('to'):
        email_cfg['to'] = [recipient]
    if not (email_cfg.get('password_env') or email_cfg.get('password')):
        # Recommend using env var RAON_SMTP_PASSWORD
        email_cfg['password_env'] = 'RAON_SMTP_PASSWORD'

    print(f"Testing SMTP send to: {recipient} via {email_cfg['smtp_server']}:{email_cfg['smtp_port']}")
    print('Make sure the SMTP password is available via the configured environment variable (e.g. RAON_SMTP_PASSWORD).')

    try:
        from reports import emailer
        subject = f"RAON Test Email - {datetime.now().date().isoformat()}"
        body = "This is a test email from the RAON sales report system. If you received this, SMTP settings are working." 
        ok = emailer.send_email_with_attachments(email_cfg, subject, body, [])
        if ok:
            print('Test email sent successfully!')
        else:
            print('Test email FAILED. See errors above and verify SMTP settings and password.')
        return bool(ok)
    except Exception as e:
        print(f'Failed to run email test: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='Generate daily sales report')
    parser.add_argument('--date', help='Date YYYY-MM-DD (default: yesterday)', default=_default_date_str(True))
    parser.add_argument('--project-root', help='Project root to search for item_list.json', default=str(Path('.')))
    parser.add_argument('--test-email', action='store_true', help='Send a test email (uses config.json or Gmail defaults)')
    parser.add_argument('--test-recipient', help='Override recipient for --test-email')
    args = parser.parse_args()

    if args.test_email:
        success = test_email(args.test_recipient, Path(args.project_root))
        if success:
            print('Email test completed successfully.')
        else:
            print('Email test failed.')
        return

    report = generate_report_for(args.date, Path(args.project_root))
    print(f"Report generated for {args.date}")
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
