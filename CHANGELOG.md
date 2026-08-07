# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- WebSocket token authentication (HMAC-based)
- Heartbeat mechanism for connection health monitoring
- SQLite persistence layer for message and state storage
- Rate limiting (10 messages per 60 seconds per client)
- Message validation (max 2000 characters)
- Docker support with Dockerfile and docker-compose.yml
- Graceful shutdown handling for server and client connections
- HMAC timing-safe token comparison to prevent timing attacks
- Architecture documentation in README.md
- MIT License
