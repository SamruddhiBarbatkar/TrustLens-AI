# Security Rules

- Use environment variables for secrets and never commit `.env` files.
- Enforce authentication and owner filtering for every private resource.
- Validate uploads, enforce size limits, generate safe filenames, and prevent path traversal.
- Use secure password hashing, JWT validation, CORS allow-lists, and user-safe errors.
- Never return stack traces, serve model files, or trust client-supplied ownership fields.
