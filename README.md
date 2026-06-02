# Matilda Dashboard

Update flow:
1. regenerate `stats.json` from the source dashboard data
2. commit and push
3. Vercel redeploys automatically

Public dashboard loads `stats.json` from the same site.

Canonical working URL for the dashboard is the localtunnel endpoint when Vercel auth is enabled:
- https://oleg-chatstats2.loca.lt/
