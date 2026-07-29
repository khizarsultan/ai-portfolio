"""Langfuse observability (planv4 Part D) — the single tracing + eval layer.

Feature-flagged (config.LANGFUSE_ENABLED). When off, or the SDK/keys are missing, every entry
point is a safe no-op — observability must NEVER break the PA pipeline. When on, each PA case
becomes one trace/session; LangGraph's CallbackHandler auto-nests a span per node and an
observation per LLM/tool call, so per-step reasoning, tokens, latency, cost and errors are
captured. We add custom scores (correctness, reliability, hallucination, escalation) and
demographic tags for the fairness dashboards.

Compliance (D6): PII masking is enabled on the client, reusing the Safe Harbor scrubber, so
patient-style fields are redacted in traces even though the demo data is synthetic."""
from __future__ import annotations
import logging

from src import config
from src.compliance import redact
from src.llm.structured import STATS

log = logging.getLogger("observability")

_client = None
_CallbackHandler = None


def _mask(data):
    """SDK-path mask hook: scrub Safe Harbor identifiers from any string in an observation."""
    try:
        if isinstance(data, str):
            return redact.scrub_text(data)
        if isinstance(data, dict):
            return {k: _mask(v) for k, v in data.items()}
        if isinstance(data, list):
            return [_mask(v) for v in data]
    except Exception:
        return data
    return data


def _mask_otel(*, params):
    """Export-stage mask for spans created by the LangChain CallbackHandler (D6).

    The handler writes OTEL spans directly, bypassing the SDK `mask`. Here we scrub the
    input/output/metadata attribute values (which carry the traced state + LLM I/O) so no
    Safe Harbor identifier reaches Langfuse."""
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
    patches = {}
    for ident, span in params.spans.items():
        set_attrs = {}
        for key, value in span.attributes.items():
            if isinstance(value, str) and any(t in key for t in ("input", "output", "metadata")):
                scrubbed = redact.scrub_text(value)
                if scrubbed != value:
                    set_attrs[key] = scrubbed
        if set_attrs:
            patches[ident] = OtelSpanPatch(set_attributes=set_attrs)
    return MaskOtelSpansResult(span_patches=patches)


def _init():
    """Lazily build the Langfuse client + register model pricing. Best-effort."""
    global _client, _CallbackHandler
    if _client is not None or not config.LANGFUSE_ENABLED:
        return
    if not (config.LANGFUSE_PUBLIC_KEY and config.LANGFUSE_SECRET_KEY):
        log.warning("LANGFUSE_ENABLED but keys missing — tracing disabled.")
        return
    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
        _client = Langfuse(
            host=config.LANGFUSE_HOST,
            public_key=config.LANGFUSE_PUBLIC_KEY,
            secret_key=config.LANGFUSE_SECRET_KEY,
            mask=_mask,                 # SDK-native observations
            mask_otel_spans=_mask_otel, # LangChain handler spans
        )
        _CallbackHandler = CallbackHandler
        _register_pricing()
    except Exception as e:  # SDK missing or bad config — degrade to no-op
        log.warning("Langfuse init failed (%s) — tracing disabled.", e)
        _client = None


def _register_pricing():
    for name, price in config.MODEL_PRICING.items():
        try:
            _client.create_model(
                model=name, match_pattern=f"(?i)^{name}$",
                input_price=price["input"] / 1_000_000,
                output_price=price["output"] / 1_000_000,
                unit="TOKENS",
            )
        except Exception:
            pass  # already registered or unsupported — fine


def enabled() -> bool:
    _init()
    return _client is not None


def get_client():
    """The raw Langfuse client (for dataset/experiment scripts), or None if disabled."""
    _init()
    return _client


def _age_band(age: int) -> str:
    if age < 18:
        return "0-17"
    if age < 40:
        return "18-39"
    if age < 65:
        return "40-64"
    return "65+"


def _agent_label(final: dict) -> str:
    if not final.get("needs_pa"):
        return "AUTO_CLEAR"
    if not final.get("coverage_ok"):
        return "NOT_COVERED"
    d = final.get("decision")
    return d.outcome.value if d else "NEEDS_INFO"


def trace_url(case_id: str) -> str | None:
    """Deep-link to the case's session in Langfuse (used by the React 'View full trace')."""
    if not config.LANGFUSE_ENABLED:
        return None
    if config.LANGFUSE_PROJECT_ID:
        return f"{config.LANGFUSE_HOST}/project/{config.LANGFUSE_PROJECT_ID}/sessions/{case_id}"
    return config.LANGFUSE_HOST


class _Tracer:
    """Context manager wrapping one PA case run. No-op unless Langfuse is enabled.

    Langfuse SDK v4 is OTEL-based: the langchain CallbackHandler owns the trace (auto-nesting
    a span per node and an observation per LLM/tool call). We pass trace attributes via the
    runnable-config metadata keys the handler parses, then attach custom scores by trace id
    after the run."""

    def __init__(self, case, actor_role: str):
        self.case = case
        self.role = actor_role
        self.handler = None
        self._snap = None

    def __enter__(self):
        if not enabled():
            return self
        try:
            self._snap = (STATS.calls, STATS.first_try_ok, STATS.failed)
            self.handler = _CallbackHandler()
        except Exception as e:
            log.warning("trace start failed (%s)", e)
            self.handler = None
        return self

    def config(self, **kw) -> dict:
        """Runnable config: attach the callback + session/tags for this case (one trace/case)."""
        cfg = dict(kw)
        if self.handler is not None:
            c = self.case
            cfg["callbacks"] = [self.handler]
            cfg["metadata"] = {
                "langfuse_session_id": c.patient_id,   # groups appeal/needs-info loops together
                "langfuse_tags": [f"plan:{c.plan_id}", f"cpt:{c.order.cpt}", f"role:{self.role}"],
            }
        return cfg

    def finish(self, final: dict, expected_label: str | None = None) -> None:
        if self.handler is None:
            return
        try:
            tid = getattr(self.handler, "last_trace_id", None)
            if not tid:
                return
            self._score(tid, final, expected_label)
            _client.flush()
        except Exception as e:
            log.warning("trace finish failed (%s)", e)

    def _score(self, tid, final, expected_label):
        c = self.case
        label = _agent_label(final)
        calls0, first0, failed0 = self._snap
        did_retry = (STATS.first_try_ok - first0) < (STATS.calls - calls0)
        had_failure = (STATS.failed - failed0) > 0
        trail = " ".join(final.get("audit_log", []))
        numeric = {
            "schema_first_try": 0 if (did_retry or had_failure) else 1,
            "hallucination_flag": 1 if "Hallucination guard" in trail else 0,
            "escalated": 1 if final.get("status") == "human_review" else 0,
            "approved": 1 if label == "APPROVED" else 0,
        }
        if expected_label is not None:
            numeric["decision_correct"] = 1 if label == expected_label else 0
        for name, value in numeric.items():
            self._push(tid, name, value)
        # Categorical scores drive the accuracy / fairness dashboard slices.
        for name, value in {"decision": label, "sex": c.sex,
                            "age_band": _age_band(c.age)}.items():
            self._push(tid, name, value, data_type="CATEGORICAL")

    def _push(self, tid, name, value, data_type=None):
        try:
            if data_type:
                _client.create_score(trace_id=tid, name=name, value=value, data_type=data_type)
            else:
                _client.create_score(trace_id=tid, name=name, value=value)
        except Exception:
            pass

    def __exit__(self, *exc):
        return False


def trace_case(case, actor_role: str = "clinician") -> _Tracer:
    return _Tracer(case, actor_role)
