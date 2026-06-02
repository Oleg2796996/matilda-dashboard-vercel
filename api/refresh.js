import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

export const config = { runtime: 'nodejs' };

export default function handler(req, res) {
  try {
    const repoRoot = process.cwd();
    execFileSync('python3', [join(repoRoot, '..', 'chat_stats_dashboard', 'build_message_log.py')], { stdio: 'inherit' });
    execFileSync('python3', [join(repoRoot, '..', 'chat_stats_dashboard', 'generate_stats.py')], { stdio: 'inherit' });
    const data = JSON.parse(readFileSync(join(repoRoot, 'stats.json'), 'utf8'));
    res.setHeader('Cache-Control', 'no-store');
    res.status(200).json(data);
  } catch (err) {
    res.status(500).json({ error: String(err?.message || err) });
  }
}
