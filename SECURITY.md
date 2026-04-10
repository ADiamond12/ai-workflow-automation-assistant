# Security Policy

## Scope

This project is currently maintained as a portfolio application and local demo system.
Treat it as a development-stage codebase, not as a hosted multi-tenant service.

## Supported Use

- local development
- portfolio demos
- interview walkthroughs
- controlled testing with synthetic or non-sensitive data

## Reporting A Vulnerability

If you find a security issue:

1. Do not open a public issue with exploit details.
2. Report the issue privately to the maintainer.
3. Include reproduction steps, affected files, impact, and suggested remediation if possible.

## Security Expectations

- do not commit secrets, tokens, or real customer data
- prefer the mock provider for demos unless a live provider is explicitly needed
- keep destructive integrations out of scope unless they are reviewed and documented
- validate structured AI output before using it in workflow decisions
- do not treat the current CI baseline as proof of production readiness
