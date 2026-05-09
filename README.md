# Visa-filter Simplify

A Chrome extension for international students applying to US jobs. Uses public USCIS visa-filing data to flag job postings from employers unlikely to sponsor, before you spend an hour on the application.

Also autofills work-authorization questions with sponsor-friendly framing to avoid triggering ATS auto-reject filters, and tracks your application pipeline with visa-aware analytics.

Generic tools like Simplify don't solve this — international students are ~5% of their audience, so the hard problem (which companies will actually consider you) stays unsolved.

## Structure

- `client/` — the Chrome extension
- `backend/` — API server that communicates with the database

## Data

Employer sponsorship likelihood is derived from public USCIS H-1B filing data.
