# Khizar Sultan — AI & ML Portfolio

A professional portfolio site that showcases **live, interactive** AI/ML projects (not just
code) across healthcare, cybersecurity, and finance. Built with **Next.js + Tailwind**,
deployed free on **Vercel**. Each project's demo backend runs on **Hugging Face Spaces**; the
site links/embeds them.

## Projects
- **Prior Authorization Agent** (Healthcare · Agentic AI) — flagship multi-agent system.
- **Diabetes Prediction** (Healthcare · ML)
- **Malicious URL Detection** (Cybersecurity · ML)
- **Credit Card Fraud Detection** (Finance · ML)

## Local dev
```bash
cd site
npm install
npm run dev            # http://localhost:3000
```

## Live ML demos (on Vercel, no external host)
The four ML models run **on Vercel itself** as Python serverless functions (`api/*.py`),
each with its own shareable page:

| Demo | Page (URL) | Function |
|---|---|---|
| Diabetes Prediction | `/demos/diabetes` | `api/diabetes.py` |
| Credit Card Fraud | `/demos/credit-card-fraud` | `api/fraud.py` |
| Malicious URL | `/demos/malicious-url` | `api/malicious-url.py` |
| SMS Spam | `/demos/sms-spam` | `api/sms-spam.py` |

Slimmed models (model + preprocessor only, no data) live in `api/models/*.joblib` and ship
with the deploy. `requirements.txt` pins the exact sklearn/numpy/pandas the models were
pickled with. `vercel.json` bundles the models into each function.

> The Python functions run on the deployed site and under `vercel dev` — **not** under a
> plain `next dev` (which serves only the Next.js frontend).

## Maintainability — external demos
Demos hosted **off** this site (e.g. the PA Agent) still read their URL from an env var
(`lib/projects.ts` → `demoEnv`): set `NEXT_PUBLIC_DEMO_PA_AGENT` in Vercel when that backend
goes live. A project with neither an internal `demoPath` nor an env URL shows "Demo coming soon",
so the site is always shippable.

## Deploy (Vercel, free)
1. Push this repo to GitHub.
2. In Vercel: **New Project** → import the repo → set **Root Directory = `site`**.
3. Framework auto-detected (Next.js). Deploy.
4. Add the `NEXT_PUBLIC_DEMO_*` env vars as demos come online; redeploy.
