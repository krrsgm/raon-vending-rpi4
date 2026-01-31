"""Simple email helper to send sales reports as attachments.

Reads SMTP config passed as a dict (see `config.example.json` > `email`). Preferred usage is to store passwords in an environment
variable (e.g. `password_env: "RAON_SMTP_PASSWORD"`).

Example config (from config.json):
{
  "email": {
    "enabled": true,
    "smtp_server": "smtp.example.com",
    "smtp_port": 587,
    "use_tls": true,
    "username": "user@example.com",
    "password_env": "RAON_SMTP_PASSWORD",
    "from": "raon@example.com",
    "to": ["owner@example.com"],
    "subject_template": "RAON Sales Report - {date}"
  }
}

"""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Dict, List, Optional


def _read_password(cfg: Dict) -> Optional[str]:
    # prefer environment variable by name
    env_key = cfg.get('password_env') or cfg.get('password_env_name')
    if env_key:
        return os.environ.get(env_key)
    # fallback to direct password in config (not recommended)
    return cfg.get('password')


def _ensure_list(x) -> List[str]:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [str(x)]


def send_email_with_attachments(cfg: Dict, subject: str, body: str, attachments: List[str]) -> bool:
    """Send an email using SMTP with attachments.

    cfg: dictionary taken from config.json['email']
    subject: email subject
    body: plain-text body
    attachments: list of file paths to attach

    Returns True on success, False otherwise.
    """
    server = cfg.get('smtp_server')
    port = int(cfg.get('smtp_port', 587) or 587)
    use_tls = bool(cfg.get('use_tls', True))
    username = cfg.get('username')
    password = _read_password(cfg)

    if not server or not username or not (password):
        print('Email config incomplete: missing server/username/password')
        return False

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg.get('from', username)
    to_list = _ensure_list(cfg.get('to') or cfg.get('recipients'))
    if not to_list:
        print('No recipients configured for email')
        return False
    msg['To'] = ', '.join(to_list)
    msg.set_content(body)

    # Attach files
    for fp in attachments:
        try:
            p = Path(fp)
            if not p.exists():
                continue
            maintype = 'application'
            subtype = 'octet-stream'
            with p.open('rb') as f:
                data = f.read()
            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=p.name)
        except Exception as e:
            print(f'Failed to attach {fp}: {e}')

    try:
        if port == 465:
            with smtplib.SMTP_SSL(server, port, timeout=30) as smtp:
                smtp.login(username, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(server, port, timeout=30) as smtp:
                smtp.ehlo()
                if use_tls:
                    smtp.starttls()
                    smtp.ehlo()
                smtp.login(username, password)
                smtp.send_message(msg)
        return True
    except Exception as e:
        print(f'Failed to send email: {e}')
        return False
