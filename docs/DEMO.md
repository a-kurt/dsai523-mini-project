# Demonstration and course checklist

Movie Court argues about movies, not people. Use fictional case text and test
accounts. Never show password hashes, API tokens, database passwords, student
IDs in public source, or private contact information.

## Live demonstration

Prepare at least four accounts in separate browser profiles: judge, prosecutor,
defender, and juror. A fifth account is useful to show blocked outsider access.
Use a real deployed GCP service and a real TMDB token for the final recording.
Automated tests use mocks and do not replace the external REST demonstration.

1. Search TMDB for a movie, for example *Shrek 2*. Show its returned metadata.
2. Create a case: **“Shrek 2 is the greatest sequel ever.”** Point out that a
   guilty verdict means the charge is true, not that the movie is bad.
3. Edit the case title/charge to demonstrate update. Create and delete a separate
   disposable case to demonstrate delete without losing the main demo.
4. Create a prosecutor invite, a defender invite, and a juror invite. Each friend
   signs in and redeems their own token. Show that a used token is refused.
5. Generate an extra invite, revoke it, and show that it no longer works.
   Show expiry with a short TTL in a separate development instance or the
   automated expiry test. Do not alter production clocks or claim an unrun check.
6. Both advocates post arguments. Edit/delete a disposable argument. The other
   advocate must not be able to edit it. The outsider must not read the case.
7. The judge starts voting. The juror submits a ballot. Show that a second vote
   fails, that the judge cannot vote, and that totals are still hidden.
8. The judge closes the case. Show the totals and verdict. Explain tie handling.
9. Show rows in Cloud SQL and demonstrate persistence across a fresh Cloud Run
   revision or restart. Keep credentials/hashes outside the recording.
10. Show HTTPS and Secure/HttpOnly cookies. Explain password hashing, server-side
    role checks, CSRF protection, and hashed single-use invitation tokens.

Use the browser interface for the story. Use API tests or a prepared REST client
for negative cases that the interface intentionally does not offer. Do not imply
that hiding a button is the permission check; the API must reject the request.

## Rubric map

| Requirement | Points in detailed guide | Evidence |
| --- | --- | --- |
| REST CRUD and suitable HTTP responses | 20 | Case and argument create/read/update/delete, API reference, functional tests |
| External REST service | 20 | Real server-side TMDB search/details, failure handling |
| External cloud database | 20 | Cloud SQL connection, persisted rows after new app revision |
| Documented code and README | 10 | Module descriptions, README, API/deployment/demo docs |
| Option 2 security | Up to 30 | HTTPS, hashed password authentication, user accounts and access management |

The guidelines contain older 10/15 wording as well as the detailed 100-point
breakdown. This plan uses the detailed breakdown; ask the instructor about any
conflict. Custom tokens are not a separately named automatic bonus in the
attached guide. If the instructor gave additional directions, keep that
clarification with the team. Do not promise full marks from feature names alone.

Cloud database role policies are a fourth possible security item, but are not
claimed as an implemented bonus here. A dedicated app database user is good
practice; it does not by itself prove per-user database row policies.

## Suggested video outline (14 minutes total)

| Time | Presenter | Content |
| --- | --- | --- |
| 0:00–0:45 | All | Project name, group number, names and student IDs; what Movie Court does |
| 0:45–3:15 | Member 1 | User flow, TMDB integration, real search and case creation |
| 3:15–5:45 | Member 2 | REST CRUD, role permissions, request/status examples |
| 5:45–9:00 | Member 3 | Docker, GCP architecture, Cloud SQL persistence |
| 9:00–13:30 | Member 4 | HTTPS, password hashes, custom invite tokens, voting and negative checks |
| 13:30–14:00 | All | Verdict reveal and limitations |

These are presentation roles, not a claim about who wrote which code. Every
member must appear, explain their actual contribution, and understand it.
Use your real full names and IDs only in the required presentation materials.
The booklet allows at most 15 minutes in total.

## Before submitting

- Confirm the team has exactly four members and the correct group number.
- Review all code and understand the architecture; do not present unverified claims.
- Confirm the GitHub repository is public and has no credentials or student IDs.
- Fill in actual results and remaining limitations in VALIDATION.md.
- Record a live demonstration with every member appearing and speaking.
- Upload to YouTube; it satisfies both documents' platform wording.
- Test the repository/video links from an account without special access.
- Submit only those links on Moodle by **7 December 2026, 23:59**, per the booklet.
  Confirm the course timezone and any later instructor announcements.
