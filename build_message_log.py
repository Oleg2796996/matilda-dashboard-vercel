#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('/home/oleg/.openclaw')
SESSIONS_DIR = ROOT / 'agents/main/sessions'
SESSIONS_JSON = SESSIONS_DIR / 'sessions.json'
MEMORY_DIR = Path('/home/oleg/.openclaw/workspace/memory')
OUT = Path('/home/oleg/.openclaw/workspace/chat_stats_dashboard/event_ledger.jsonl')
INCOMING = Path('/home/oleg/.openclaw/workspace/chat_stats_dashboard/incoming_telegram.jsonl')
WINDOW_DAYS = 30

BLOCK_RE = re.compile(
    r'Conversation info \(untrusted metadata\):\n```json\n(?P<conv>\{.*?\})\n```\n\nSender \(untrusted metadata\):\n```json\n(?P<sender>\{.*?\})\n```',
    re.S,
)


def iter_transcript_paths():
    paths = sorted(p for p in SESSIONS_DIR.glob('*.jsonl') if p.name != 'sessions.json')
    if not paths and SESSIONS_JSON.exists():
        session = json.loads(SESSIONS_JSON.read_text(encoding='utf-8')).get('agent:main:main')
        if session and session.get('sessionFile'):
            paths = [Path(session['sessionFile'])]
    return paths


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text':
                    parts.append(item.get('text', ''))
                elif 'text' in item:
                    parts.append(str(item.get('text', '')))
        return '\n'.join(p for p in parts if p)
    return ''


def parse_blocks(text: str, source: str):
    rows = []
    for m in BLOCK_RE.finditer(text):
        try:
            conv = json.loads(m.group('conv'))
            sender = json.loads(m.group('sender'))
        except Exception:
            continue
        sender_id = str(conv.get('sender_id') or '').strip()
        message_id = str(conv.get('message_id') or '').strip()
        timestamp = str(conv.get('timestamp') or '').strip()
        label = (sender.get('label') or conv.get('sender') or '').strip()
        username = str(sender.get('username') or '').strip()
        if not sender_id or not message_id or not timestamp or not label:
            continue
        rows.append({
            'source': source,
            'message_id': message_id,
            'sender_id': sender_id,
            'sender': label,
            'username': username,
            'timestamp': timestamp,
        })
    return rows


def parse_dt(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc)
    if isinstance(value, str):
        try:
            if value.endswith('Z'):
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            return datetime.fromisoformat(value)
        except ValueError:
            m = re.match(r'^[A-Za-z]{3}\s+(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})\s+GMT([+-]\d{1,2})$', value)
            if m:
                date_s, time_s, off_s = m.groups()
                sign = 1 if off_s.startswith('+') else -1
                hours = int(off_s[1:])
                tz = timezone(sign * timedelta(hours=hours))
                return datetime.fromisoformat(f'{date_s}T{time_s}:00').replace(tzinfo=tz)
    return None


def load_existing_keys():
    keys = set()
    if not OUT.exists():
        return keys
    for line in OUT.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        keys.add((row.get('sender_id', ''), row.get('message_id', ''), row.get('timestamp', '')))
    return keys


def collect_rows():
    rows = []
    seen = set()

    def add_rows(source, text):
        for row in parse_blocks(text, source):
            key = (row['sender_id'], row['message_id'], row['timestamp'])
            if key in seen:
                continue
            seen.add(key)
            rows.append(row)

    for transcript in iter_transcript_paths():
        if not transcript.exists():
            continue
        for line in transcript.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get('type') != 'message':
                continue
            msg = obj.get('message', {})
            if msg.get('role') != 'user':
                continue
            text = extract_text(msg.get('content'))
            if text.strip():
                add_rows(transcript.name, text)

    for md in sorted(MEMORY_DIR.glob('2026-*.md')):
        add_rows(md.name, md.read_text(encoding='utf-8'))

    for line in INCOMING.read_text(encoding='utf-8').splitlines() if INCOMING.exists() else []:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        key = (row.get('sender_id', ''), row.get('message_id', ''), row.get('timestamp', ''))
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    rows.sort(key=lambda r: (r.get('timestamp') or '', r.get('source') or '', r.get('message_id') or ''))
    return rows


def main():
    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    existing = load_existing_keys()
    new_rows = []
    for row in collect_rows():
        key = (row['sender_id'], row['message_id'], row['timestamp'])
        if key in existing:
            continue
        existing.add(key)
        new_rows.append(row)

    if new_rows:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        with OUT.open('a', encoding='utf-8') as fh:
            for row in new_rows:
                fh.write(json.dumps(row, ensure_ascii=False) + '\n')

    # prune ledger to only 30-day window for all downstream calculations
    if OUT.exists():
        kept = []
        for line in OUT.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            dt = parse_dt(row.get('timestamp'))
            if dt is None or dt < cutoff:
                continue
            kept.append(row)
        OUT.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in kept), encoding='utf-8')


if __name__ == '__main__':
    main()
