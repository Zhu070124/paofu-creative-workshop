# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in this project, please report it responsibly.

**Do not open a public issue.** Instead, send details to the project maintainer directly.

We aim to acknowledge reports within 48 hours and provide an initial assessment within 5 business days.

## Security Measures

### WebSocket Token Authentication

All WebSocket connections are authenticated using HMAC-based token verification. Tokens are compared using a timing-safe comparison function to prevent timing side-channel attacks.

### Message Validation

Incoming messages are validated and rejected if they exceed the maximum allowed length of 2000 characters. This prevents resource exhaustion from oversized payloads.

### Rate Limiting

Each client is limited to 10 messages per 60-second window. Clients exceeding this limit will have their connections throttled or terminated. This mitigates abuse and denial-of-service attempts.

### Heartbeat Cleanup

The server periodically sends heartbeat pings to all connected clients. Connections that fail to respond within the timeout window are automatically cleaned up, preventing resource leaks from stale or malicious connections.

### General Practices

- Dependencies are pinned in `requirements.txt` to ensure reproducible builds
- The Docker image is built from a minimal base to reduce attack surface
- The server supports graceful shutdown to ensure in-flight requests complete before termination
