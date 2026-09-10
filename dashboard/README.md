# ForgeSense Local Monitor

The dashboard is a local read-only engineering monitor for the pre-hardware reference system. It is served by `tools/run_dashboard.py` and consumes only the documented `/api/v1/*` monitoring endpoints.

Run from the repository root:

```bash
make dashboard
```

Default bind address is `127.0.0.1:8765`. The UI intentionally has no actuator or recovery controls.
