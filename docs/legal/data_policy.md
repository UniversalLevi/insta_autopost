# Data Policy

**Effective date:** [Auto-filled from project]  
**Service:** InstaForge – Instagram Automation Platform  
**Version:** v1

## 1. Scope

This policy describes how InstaForge collects, uses, retains, and deletes data, in line with GDPR and DPDP principles.

## 2. Data Categories

| Category            | Examples                           | Purpose                    |
|---------------------|------------------------------------|----------------------------|
| Account             | Email, password hash, role       | Authentication, access     |
| Session             | Token, expiry                      | Session management         |
| Meta connection     | Page ID, IG ID, encrypted token   | Instagram API access       |
| Automation          | Flows, broadcasts, segments        | Service features           |
| Messages & logs     | DM logs, AI memory, audit logs    | Delivery, safety, compliance |
| Consents            | Terms, privacy, marketing, IP, ts | Legal basis, proof         |

## 3. Retention

- **Messages / DM logs:** 90 days, then auto-deleted (configurable).
- **Audit logs:** 1 year, then auto-deleted (configurable).
- **Tokens:** Deleted when you disconnect; backup metadata per backup policy.
- **Account data:** Until account deletion; then purged per your request (GDPR/DPDP).

## 4. Storage and Security

- Data stored in designated data directory; backups in backup directory.
- Tokens encrypted at rest (Fernet). No plaintext tokens in logs.
- Access controlled by user_id; admin actions logged.

## 5. Data Export (GDPR / DPDP)

You may request a copy of your data via the dashboard or API export. We provide a structured export of your account, consents, connected accounts metadata, and config (no decrypted tokens).

## 6. Data Deletion (Right to Erasure)

You may request deletion via the dashboard or API. We will:

- Delete or anonymize your account, sessions, consents, and automation data.
- Remove your connected Meta accounts and tokens.
- Purge your message logs and AI memory.
- Retain audit entries only where required by law (e.g. anonymized).

## 7. Third Parties

- **Meta/Facebook:** Required for Instagram API; subject to Meta's data terms.
- **OpenAI:** If you use AI features; subject to OpenAI's terms and our configuration (no training on your data by default).
- **Hosting/subprocessors:** Under data processing agreements where required.

## 8. Changes

We may update this policy. Material changes will be communicated; continued use constitutes acceptance.
