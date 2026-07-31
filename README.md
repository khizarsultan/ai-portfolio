# AI & ML Portfolio — Khizar Sultan

A collection of production-style AI and Machine Learning projects across healthcare,
cybersecurity, and finance. Every project is not just code — each one is **live and
interactive**, so you can open a page, enter your own input, and see the model's prediction
and its reasoning in real time.

This document is written for a general reader. It explains what each project does, how it is
built, what you get out of it, and why it matters — without assuming a technical background.

---

## What is in here

| Project | Domain | What it does |
|---|---|---|
| Prior Authorization Agent | Healthcare | A team of AI agents that handles a medical insurance approval from start to finish, with a human as the final approver. |
| Clinical Documentation Agent | Healthcare | A team of AI agents that drafts a visit note and its medical codes, recorded only after a clinician signs off. |
| Diabetes Prediction | Healthcare | Estimates a patient's diabetes risk from routine health data and explains the result. |
| Malicious URL Detection | Cybersecurity | Reads a web link and flags it as safe, phishing, malware, or defacement. |
| SMS Spam Detection | Cybersecurity | Flags scam or spam text messages and highlights the exact words that gave them away. |
| Credit Card Fraud Detection | Finance | Spots fraudulent card transactions in data where fraud is extremely rare. |

All six projects are live demos you can try in the browser. The two Healthcare agent systems —
the Prior Authorization Agent and the Clinical Documentation Agent — are the flagship, most
involved systems.

---

## Purpose

The goal is to show real, working AI — not slideware. Each project answers a concrete question
a business actually asks:

- Healthcare: *Is this patient at risk?* and *Can we automate the paperwork safely?*
- Cybersecurity: *Is this link or message dangerous?*
- Finance: *Is this transaction fraud?*

In every case the model gives an answer **and** shows the evidence behind it, so a human can
trust it, check it, and stay in control.

---

## The projects in plain terms

### 1. Prior Authorization Agent (Healthcare)

**The problem.** Before some medical procedures happen, a doctor's office has to get the
insurer's approval — "prior authorization." It is slow, manual, and error-prone.

**What it does.** Five specialised AI agents work as a team: one checks whether approval is even
needed, one verifies the patient's coverage, one assembles the request, one submits it to the
insurer, and one automatically writes an appeal if it gets denied. A human reviewer signs off on
every denial and escalation — the AI never denies care on its own.

**How it is designed.** The agents are coordinated by a controller that follows fixed rules and
cannot loop forever. Crucially, the final yes/no decision is made by a **deterministic rules
engine, not the AI** — the AI only reads, reasons, and drafts. Sensitive patient identifiers are
stripped out before anything leaves the machine, and every action is written to a permanent,
tamper-proof audit log.

**Output and impact.** For each case you get the decision, a plain-English explanation of why,
and an appeal letter when needed — all traceable step by step. It recovers denials and handles
the tricky multi-step cases that a single AI prompt gets wrong, while keeping a human in charge.
It runs entirely on synthetic data — no real patients, no real insurer.

### 2. Clinical Documentation Agent (Healthcare)

**The problem.** Writing up a patient visit — the note plus the diagnosis and billing codes —
takes doctors hours and is where costly coding errors creep in.

**What it does.** Five specialised AI agents work as a team: one cleans up the visit input, one
drafts the SOAP note (Subjective, Objective, Assessment, Plan), one extracts the ICD-10 and CPT
codes, one validates them, and one writes the note to the record — but only after a clinician
reviews and signs off. The clinician can sign, edit, or reject; nothing is filed on its own.

**How it is designed.** Because writing is easy to get plausibly wrong, the safety net is not the
AI. Every code is checked against the real ICD-10/CPT code lists and invented codes are dropped;
any claim in the note that is not supported by the visit input is flagged for a human; and the
record is never written until a clinician signs. Identifiers are stripped before anything leaves
the machine, and every step is logged.

**Output and impact.** A complete SOAP note, validated codes each with a reason, and a
plain-English summary — filed only with a human signature. It produces better-grounded notes and
safer codes than a single AI prompt, and it runs on synthetic data — no real patients.

### 3. Diabetes Prediction (Healthcare)

**The problem.** Identifying diabetes risk early from routine measurements.

**What it does.** You enter basic health data — age, BMI, blood glucose, HbA1c, and a few
history flags — and the model returns a risk score.

**How it is designed.** It learned from 100,000 real anonymized patient records. The model is
tuned to catch positive cases (better to flag and check than to miss), and it explains which
factors drove each prediction.

**Output and impact.** A clear probability plus the top contributing factors, so a clinician can
see *why* a patient was flagged rather than trusting a black box.

### 4. Malicious URL Detection (Cybersecurity)

**The problem.** Dangerous web links (phishing, malware) look almost identical to safe ones.

**What it does.** Paste any URL and it classifies the link as benign, phishing, malware, or
defacement.

**How it is designed.** It learned from 651,000 URLs. Instead of visiting the link, it reads the
text of the address itself — length, odd symbols, number of subdomains, suspicious words — and
judges from those signals alone, so it is fast and safe to run.

**Output and impact.** An instant verdict with the specific red flags it found in the link.

### 5. SMS Spam Detection (Cybersecurity)

**The problem.** Scam and spam text messages that trick people into clicking or paying.

**What it does.** Paste a message and it tells you whether it is spam or legitimate.

**How it is designed.** It uses a transparent, word-based model. Because of how the model works,
it can point to the **exact words** that pushed a message toward "spam" — this is a true
explanation, not a guess after the fact.

**Output and impact.** A verdict plus a highlighted list of the words that flagged the message,
so the reasoning is fully visible.

### 6. Credit Card Fraud Detection (Finance)

**The problem.** Fraud is rare — fewer than 2 in 1,000 transactions — which makes it easy to
miss and easy to fake good results.

**What it does.** It scores a transaction as genuine or fraudulent.

**How it is designed.** It learned from 284,807 real transactions where only 0.17% were fraud.
It uses techniques built for this severe imbalance and is measured on metrics that are honest at
this ratio (precision-recall), not misleading "accuracy."

**Output and impact.** A fraud probability with the factors behind it — the kind of signal a
payments team would use to hold or review a transaction.

---

## Architecture

The portfolio is a single repository with a clean split between the website and the models.

```
portfolio/
├── site/            The public website (Next.js + Tailwind) and the live ML demos
│   ├── app/         Pages, including one live demo page per model
│   └── api/         The ML models running as small serverless functions (Python)
├── healthcare/      Prior Authorization Agent + the diabetes model and MLOps pipeline
├── cybersecurity/   Malicious URL and SMS spam models
├── finance/         Credit card fraud model
└── data/            Public datasets used for training (not shipped to the website)
```

**How the live demos work.** The website is built with Next.js and hosted free on Vercel, so it
is always online and fast. The four ML models run **on the same platform** as small Python
serverless functions — there is no separate server to keep running. When you submit an input,
the page calls its model function, gets a prediction back, and shows the result with its
explanation. Each demo has its own shareable web address.

**How the agent is built.** The Prior Authorization Agent uses a multi-agent framework
(LangGraph) where each agent has one narrow job and a strict, least-privilege set of permissions.
Every step is validated against a shared contract and recorded in an audit trail, and the whole
run can be traced for cost, speed, and reasoning.

---

## Design principles

The same ideas run through every project:

- **Explainable, not a black box.** Every prediction comes with the evidence behind it.
- **Human stays in control.** The AI assists and drafts; people make the final call, especially
  in healthcare.
- **Honest evaluation.** Models are judged on metrics that match the problem (for example,
  precision-recall for rare fraud), not on numbers that flatter.
- **Privacy by design.** Sensitive data is minimized and redacted; the healthcare work runs on
  synthetic data only.
- **Simple to run and share.** Free hosting, always-on website, one link per demo.

---

## Try it

- Visit the website to browse all projects and open any live demo.
- Each ML demo page lets you enter your own input and see the prediction and explanation
  immediately.

To run the site locally:

```bash
cd site
npm install
npm run dev        # opens at http://localhost:3000
```

Note: a plain local run serves the website; the Python model functions run on the deployed site
(or via `vercel dev`).

---

## Impact in one line

Five working systems that turn a hard question — *Is this risky? Is this fraud? Is this link
safe? Can we automate this safely?* — into an instant, explainable answer that a person can
trust and act on.
