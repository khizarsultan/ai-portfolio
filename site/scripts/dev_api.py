"""Local dev shim for the Vercel Python functions in api/*.py.

`next dev` does NOT execute the api/ Python functions — only `vercel dev` or a real deploy do.
This shim loads each api/*.py, maps /api/<name> to its `handler` class, and serves them on :8787
so `next dev` (with the dev-only rewrite in next.config.mjs) can proxy /api/* here.

Run from the site/ directory:  python3 scripts/dev_api.py
It uses only the deployed handlers' own code — no behavior changes. PA runs off the prerecorded
samples when NVIDIA_API_KEY is unset; the ML functions load their local joblib models.
"""
from __future__ import annotations
import glob
import importlib.util
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

API_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "api")
PORT = int(os.getenv("DEV_API_PORT", "8787"))

# Load every api/*.py and map its route to the module's `handler` class.
ROUTES: dict[str, type] = {}
for path in sorted(glob.glob(os.path.join(API_DIR, "*.py"))):
    stem = os.path.splitext(os.path.basename(path))[0]
    try:
        spec = importlib.util.spec_from_file_location(f"api_{stem.replace('-', '_')}", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        ROUTES[f"/api/{stem}"] = mod.handler
        print(f"  mounted /api/{stem}")
    except Exception as e:  # e.g. an ML model that won't unpickle locally — skip, keep the rest
        print(f"  SKIPPED /api/{stem}: {e}", file=sys.stderr)


class Dispatch(BaseHTTPRequestHandler):
    _target: type | None = None

    def _resolve(self) -> bool:
        route = self.path.split("?", 1)[0].rstrip("/") or self.path.split("?", 1)[0]
        self._target = ROUTES.get(route) or ROUTES.get(self.path.split("?", 1)[0])
        return self._target is not None

    def do_GET(self):
        if not self._resolve():
            return self.send_error(404, "no such function")
        self._target.do_GET(self)

    def do_POST(self):
        if not self._resolve():
            return self.send_error(404, "no such function")
        self._target.do_POST(self)

    def log_message(self, fmt, *args):
        print(f"  {self.command} {self.path} -> {args[1] if len(args) > 1 else ''}")

    def __getattr__(self, name):
        # Delegate helper methods (_send, predict, etc.) to the resolved handler class,
        # bound to THIS instance. Only fires for attributes Dispatch itself lacks.
        target = self.__dict__.get("_target")
        if target is not None and hasattr(target, name):
            attr = getattr(target, name)
            if callable(attr):
                return attr.__get__(self)
        raise AttributeError(name)


if __name__ == "__main__":
    print(f"dev api shim on http://127.0.0.1:{PORT}  ({len(ROUTES)} functions)")
    ThreadingHTTPServer(("127.0.0.1", PORT), Dispatch).serve_forever()
