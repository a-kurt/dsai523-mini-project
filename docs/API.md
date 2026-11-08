# Movie Court API

Base path: `/api`. The browser uses same-origin JSON requests and an HttpOnly
session cookie. Do not put authentication secrets or invitation tokens in URLs.
All errors are JSON objects such as `{"error":"Please sign in."}`.

## Authentication and CSRF

Call `GET /api/auth/me` first. It returns:

```json
{"user": null, "csrf_token": "session-specific-value"}
```

Send that value as `X-CSRF-Token` on **every** POST, PATCH, and DELETE request,
including registration and login. Keep the session cookie. Call `/api/auth/me`
again after signing in because authentication renews session/CSRF state.
Do not store secrets or raw invitation tokens in local storage.

| Method and path | JSON request | Success |
| --- | --- | --- |
| GET `/auth/me` | None | 200: `user` and `csrf_token` |
| POST `/auth/register` | `{"username":"juror_one","password":"a-long-private-password"}` | 201: `user`; signed in |
| POST `/auth/login` | `{"username":"juror_one","password":"a-long-private-password"}` | 200: `user`; signed in |
| POST `/auth/logout` | None | 204; session ends |

User objects contain `id` and `username`, never a password or password hash.
Usernames are 3–32 lowercase letters, numbers, or underscores. Passwords are
12–128 characters. Use a unique, long password. Login errors do not reveal whether an account exists.

## Movie search

`GET /api/movies/search?q=Shrek` returns 200:

```json
{"movies":[{"id":809,"title":"Shrek 2","release_date":"2004-05-19","overview":"Movie summary from TMDB.","poster_path":"/example.jpg"}]}
```

The example illustrates the format, not a recorded live API result. The backend
calls TMDB with its server-side Read Access Token and request timeout. It never
sends that token to the browser. Movie creation also fetches movie details from
TMDB instead of trusting a client-supplied movie title.

## Cases

| Method and path | Request | Who can use it |
| --- | --- | --- |
| GET `/cases` | None | Signed-in user; returns only their member cases |
| POST `/cases` | `{"movie_id":809,"title":"The sequel trial","charge":"Shrek 2 is the greatest sequel ever."}` | Signed-in user; becomes judge; 201 |
| GET `/cases/1` | None | Case members |
| PATCH `/cases/1` | `{"title":"A new title","charge":"A revised charge"}` | Judge during debate |
| DELETE `/cases/1` | None | Judge; 204 |

List response: `{"cases":[...]}`. Create/update response: `{"case":{...}}`.
A case contains `id`, `title`, `charge`, `phase`, `movie`, and `created_at`.
Titles are 1–120 characters and charges are 1–1000 characters.
Movie fields are `id`, `title`, `release_date`, `overview`, and `poster_path`.

The case detail response contains:

- `case`: the case fields above.
- `members`: `user_id`, `username`, and role for each member.
- `arguments`: each argument's `id`, `user_id`, `username`, `role`, `body`, and `created_at`.
- `my_role`: `judge`, `prosecutor`, `defender`, or `juror`.
- `my_vote`: your choice or null.
- `verdict`: null until close; then `guilty`, `not_guilty`, `total`, and `result`.

A verdict result is `guilty`, `not_guilty`, or `tie`. The response never includes
other jurors' individual votes. Totals stay hidden while voting is open.

## Invitations

| Method and path | Request | Result |
| --- | --- | --- |
| POST `/cases/1/invites` | `{"role":"juror"}` | Judge creates token; 201: `token`, `expires_at` |
| DELETE `/cases/1/invites` | None | Judge revokes unused case invites; 204 |
| POST `/invites/redeem` | `{"token":"the-private-invitation"}` | Signed-in user joins; 201: `case_id`, `role` |

Allowed invitation roles: `prosecutor`, `defender`, `juror`. The judge cannot
invite another judge. There is one prosecutor and one defender; jurors can be
multiple. Existing members cannot join the same case again under another role.
Only the initial response contains the raw random token. Share it privately.
Tokens expire after `INVITE_TTL_SECONDS` (default 3600), are stored only as
SHA-256 hashes, and are consumed atomically. Used, revoked, and expired tokens
cannot grant access. Membership stays after an invitation expires.

## Arguments and votes

| Method and path | Request | Who/when |
| --- | --- | --- |
| POST `/cases/1/arguments` | `{"body":"The soundtrack makes the case."}` | Prosecutor or defender during debate; 201 |
| PATCH `/cases/1/arguments/2` | `{"body":"My revised argument."}` | Argument's author during debate |
| DELETE `/cases/1/arguments/2` | None | Argument's author during debate; 204 |
| POST `/cases/1/phase` | `{"phase":"voting"}` | Judge, debate → voting |
| POST `/cases/1/votes` | `{"choice":"guilty"}` | Juror during voting, exactly once; 201 |
| POST `/cases/1/phase` | `{"phase":"closed"}` | Judge, voting → closed |

Create/update argument responses contain `argument`; phase changes contain
`case`. A vote response contains a confirmation `message`.
Vote choices are `guilty` (the charge is true) and `not_guilty` (the charge is
false). Ballots are final. A judge or advocate cannot vote.

The judge needs both advocates and at least one juror to start voting, and at
least one vote to close it. The judge may close while other jurors have not
voted; those jurors abstain. The judge should tell everyone before closing.
Phases only move forward. There is no reopening,
editing arguments during voting, or deleting a ballot after seeing results.

## Status codes

- **200:** a successful read or update.
- **201:** a user, case, invite, membership, argument, or vote was created.
- **204:** a successful delete/logout, with no response body.
- **400:** invalid/missing fields or malformed JSON.
- **401:** sign-in is needed or login credentials are incorrect.
- **403:** CSRF or role check failed.
- **404:** resource missing or unavailable to this user.
- **409:** duplicate action or invalid case state, such as voting twice.
- **429:** a request rate limit was reached, where configured.
- **502/503:** external API unavailable or missing server configuration.

See the actual tests for exact edge-case behavior. API errors must not expose
stack traces, SQL credentials, session keys, or the TMDB token.
