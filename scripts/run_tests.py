"""Run unit/integration tests with local credentials shadowed and external I/O blocked."""
from __future__ import annotations

import ipaddress
import os
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.update({key: "" for key in (
    "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SENTRY_DSN",
    "GROQ_API_KEY", "OPENAI_API_KEY", "POLLINATIONS_TOKEN",
    "AGNES_API_KEY", "CLOUDFLARE_IMAGE_API_KEY", "CLOUDFLARE_IMAGE_URL",
)})
os.environ["CERTIFICATE_REGISTRY_MODE"] = "manual"
os.environ["LOG_LEVEL"] = "CRITICAL"


original_connect = socket.socket.connect


def local_connect(sock, address):
    if isinstance(address, tuple):
        try:
            local = ipaddress.ip_address(address[0]).is_loopback
        except ValueError:
            local = address[0] == "localhost"
        if not local:
            raise OSError("External network access is disabled in the test runner")
    return original_connect(sock, address)


if __name__ == "__main__":
    names = sys.argv[1:] or ["test_app", "test_evidence_binding", "test_visual_content", "test_image_modes", "test_claim_evaluation", "test_project_actions"]
    with patch.object(socket.socket, "connect", local_connect):
        suite = unittest.defaultTestLoader.loadTestsFromNames(names)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
