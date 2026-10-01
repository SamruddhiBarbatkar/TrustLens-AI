# MongoDB Skill

## Implementation standards

- Configure connection lifecycle through environment-backed settings and fail safely when unavailable.
- Define document shapes in schemas; serialize ObjectIds safely at API boundaries.
- Create a unique normalized-email index and indexes for owner/timestamp queries.
- Include authenticated owner ID in every private query and mutation.
- Store password hashes only; never store credentials, tokens, or client-trusted owner IDs.
- Use bounded queries, stable sort order, pagination where lists can grow, and explicit error handling.

## Verification

Test connection failure behavior, duplicate users, index creation, owner isolation, pagination, and serialization.
