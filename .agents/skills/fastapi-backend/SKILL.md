# FastAPI Backend Skill

## Before implementation

Read core/security/structure rules and the active task. Define request/response schemas and authorization requirements before routes.

## Build standards

- Use versioned routers, Pydantic schemas, dependency injection, and focused services.
- Validate all external input at the boundary; keep route handlers thin.
- Centralize expected error responses and log technical detail server-side only.
- Use authenticated dependencies and owner-scoped queries for private resources.
- Load configuration from environment-backed settings; never hardcode secrets.
- Make model/file failures explicit, controlled API states rather than fake results.

## Verification

Test success, validation, authentication, authorization, and failure paths through the API.
