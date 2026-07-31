// Single source of truth for the portfolio's projects. Demo URLs are read from env so they
// can be updated after each backend is deployed (Hugging Face Space / etc.) WITHOUT a code
// change — keeps the site maintainable post-deploy. Set NEXT_PUBLIC_DEMO_<KEY> in Vercel.

export type Project = {
  slug: string;
  title: string;
  domain: "Healthcare" | "Cybersecurity" | "Finance";
  kind: string;              // e.g. "Agentic AI", "Machine Learning"
  tagline: string;
  description: string;
  highlights: string[];
  stack: string[];
  demoEnv: string;           // env var holding an EXTERNAL live demo URL (e.g. HF Space)
  demoPath?: string;         // INTERNAL live demo route on this site (takes priority)
  repoUrl?: string;
  featured?: boolean;
};

export const PROJECTS: Project[] = [
  {
    slug: "prior-authorization-agent",
    title: "Prior Authorization Agent",
    domain: "Healthcare",
    kind: "Agentic AI",
    tagline: "A multi-agent system that handles a medical prior-authorization end to end.",
    description:
      "Five specialised agents (Checker, Verifier, Assembler, Submitter, Appealer) orchestrated with LangGraph decide if PA is needed, verify coverage, assemble the request, submit it to a payer, and auto-appeal denials — with a human reviewer as the final gate. Every step is written to an append-only audit trail.",
    highlights: [
      "Deterministic payer decision (not the LLM) + hallucination guards",
      "HIPAA Safe-Harbor redaction before any egress; per-agent least-privilege",
      "Full Langfuse tracing: cost, latency, per-step reasoning, eval scores",
      "Beats a single-prompt baseline on multi-step needs-info / appeal cases",
    ],
    stack: ["LangGraph", "LangChain", "NVIDIA NIM", "FastAPI", "React", "Langfuse", "Pydantic"],
    demoEnv: "NEXT_PUBLIC_DEMO_PA_AGENT",
    demoPath: "/demos/prior-auth",
    featured: true,
  },
  {
    slug: "clinical-documentation-agent",
    title: "Clinical Documentation Agent",
    domain: "Healthcare",
    kind: "Agentic AI",
    tagline: "A multi-agent system that turns a patient visit into a signed clinical note.",
    description:
      "Five specialised agents (Intake, SOAP Writer, Coder, Validator, Recorder) orchestrated with LangGraph draft a SOAP note, extract ICD-10/CPT codes, and validate them — but nothing is written to the record until a clinician signs off. Because this is a generation task, the trust anchors are deterministic code-set validation and a mandatory human sign-off; the model only drafts and extracts.",
    highlights: [
      "Mandatory clinician sign-off gate — no autonomous record writes",
      "Codes validated against real ICD-10/CPT sets; invented codes dropped",
      "Grounding + completeness checks flag unsupported claims to human review",
      "HIPAA Safe-Harbor redaction before any egress; full audit trail",
    ],
    stack: ["LangGraph", "LangChain", "NVIDIA NIM", "FastAPI", "React", "Langfuse", "Pydantic"],
    demoEnv: "NEXT_PUBLIC_DEMO_CLINICAL_DOC",
    demoPath: "/demos/clinical-doc",
    featured: true,
  },
  {
    slug: "diabetes-prediction",
    title: "Diabetes Prediction",
    domain: "Healthcare",
    kind: "Machine Learning",
    tagline: "Predict diabetes risk from medical & demographic signals, with explainability.",
    description:
      "Binary classifier over 100k patient records (age, BMI, HbA1c, blood glucose, comorbidities). Handles mild class imbalance and surfaces SHAP explanations so a clinician can see why the model flagged a patient.",
    highlights: [
      "100,000 records · logistic regression / XGBoost",
      "SHAP explainability for every prediction",
      "Probability + threshold tuned for recall on the positive class",
    ],
    stack: ["scikit-learn", "HistGradientBoosting", "pandas", "Next.js", "Vercel"],
    demoEnv: "NEXT_PUBLIC_DEMO_DIABETES",
    demoPath: "/demos/diabetes",
  },
  {
    slug: "malicious-url-detection",
    title: "Malicious URL Detection",
    domain: "Cybersecurity",
    kind: "Machine Learning",
    tagline: "Flag URLs as benign, phishing, malware, or defacement from the raw string.",
    description:
      "Multi-class classifier over 651k URLs. Lexical features are engineered from the raw URL (length, digit/symbol ratios, subdomain depth, suspicious tokens) — a full ML pipeline that runs on CPU.",
    highlights: [
      "651,191 URLs · 4 classes",
      "Lexical feature engineering from raw strings",
      "Paste any URL and get a live classification",
    ],
    stack: ["scikit-learn", "HistGradientBoosting", "pandas", "Next.js", "Vercel"],
    demoEnv: "NEXT_PUBLIC_DEMO_MALICIOUS_URL",
    demoPath: "/demos/malicious-url",
  },
  {
    slug: "credit-card-fraud-detection",
    title: "Credit Card Fraud Detection",
    domain: "Finance",
    kind: "Machine Learning",
    tagline: "Detect fraudulent transactions on severely imbalanced data.",
    description:
      "Binary classifier on the canonical 284,807-transaction benchmark (0.17% fraud). Demonstrates imbalance handling (SMOTE / class weights) and evaluation that actually matters at this ratio — precision-recall and AUPRC, not accuracy.",
    highlights: [
      "284,807 transactions · 0.17% fraud",
      "SMOTE / class-weighting for extreme imbalance",
      "Evaluated on AUPRC and precision-recall, not accuracy",
    ],
    stack: ["scikit-learn", "HistGradientBoosting", "imbalanced-learn", "pandas", "Next.js", "Vercel"],
    demoEnv: "NEXT_PUBLIC_DEMO_FRAUD",
    demoPath: "/demos/credit-card-fraud",
  },
  {
    slug: "sms-spam-detection",
    title: "SMS Spam Detection",
    domain: "Cybersecurity",
    kind: "Machine Learning",
    tagline: "Flag scam / malicious text messages and show which words gave them away.",
    description:
      "A TF-IDF + Logistic Regression classifier that separates spam/malicious SMS from legitimate messages. Because the model is linear, every prediction comes with an exact, per-word explanation — you can see precisely which tokens pushed a message toward spam.",
    highlights: [
      "TF-IDF over 5.6k-term vocabulary · Logistic Regression",
      "True per-token contributions (tfidf × coefficient) — not an approximation",
      "Paste any message and see the words that flagged it",
    ],
    stack: ["scikit-learn", "TF-IDF", "Logistic Regression", "Next.js", "Vercel"],
    demoEnv: "NEXT_PUBLIC_DEMO_SMS_SPAM",
    demoPath: "/demos/sms-spam",
  },
];

export function getProject(slug: string): Project | undefined {
  return PROJECTS.find((p) => p.slug === slug);
}

// Resolve a project's EXTERNAL live demo URL from env (undefined = none set).
export function demoUrl(p: Project): string | undefined {
  const v = process.env[p.demoEnv];
  return v && v.length > 0 ? v : undefined;
}

// The live demo link to render. Internal route wins; else external env URL; else none.
// `internal` tells the UI to use a same-tab <Link> vs an external new-tab <a>.
export function demoLink(p: Project): { href: string; internal: boolean } | undefined {
  if (p.demoPath) return { href: p.demoPath, internal: true };
  const v = demoUrl(p);
  return v ? { href: v, internal: false } : undefined;
}
