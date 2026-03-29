# Users and Permissions

TinySignage uses role-based access control (RBAC) to manage who can do what. The first admin account is created during the setup wizard.

---

## Roles

| Role | Level | What they can do |
|------|-------|-----------------|
| **Admin** | 3 | Everything: manage users, devices, overrides, tokens, backup, plus all editor and viewer actions |
| **Editor** | 2 | Manage content: assets, playlists, schedules, tags, layouts |
| **Viewer** | 1 | Read-only CMS access: browse media, view playlists, view devices and schedules |
| **Device** | 0 | Player polling and heartbeat only (not a human user role) |

Roles are hierarchical: an admin can do everything an editor can do, and an editor can do everything a viewer can do.

### Permission matrix

| Action | Admin | Editor | Viewer |
|--------|-------|--------|--------|
| View media, playlists, devices | Yes | Yes | Yes |
| Upload/edit/delete media | Yes | Yes | No |
| Create/edit/delete playlists | Yes | Yes | No |
| Create/edit/delete schedules | Yes | Yes | No |
| Create/edit/delete layouts | Yes | Yes | No |
| Manage tags | Yes | Yes | No |
| Create/edit/delete devices | Yes | No | No |
| Manage device groups | Yes | No | No |
| Create/cancel emergency overrides | Yes | No | No |
| Manage users | Yes | No | No |
| Create/revoke API tokens | Yes | No | No |
| Export/import backups | Yes | No | No |
| View audit log | Yes | No | No |
| View system logs | Yes | No | No |

---

## Creating users

Admins can create new users from the **Users** page in the CMS.

Each user has:
- **Username** -- unique, used for login
- **Display name** -- optional, shown in the UI
- **Role** -- admin, editor, or viewer
- **Password** -- set at creation, can be changed later

Users can be deactivated without deleting them. Deactivated users cannot log in but their audit history is preserved.

---

## Login and logout

Users log in at `/cms` (redirected to `/login` if not authenticated). Login uses username and password, and returns a session token.

The session token:
- Has a `ts_` prefix followed by 48 hex characters
- Is stored in the browser's `localStorage` as `tinysignage_token`
- Expires after 30 days
- Is sent as an `Authorization: Bearer <token>` header on every API request

Logging out invalidates the session token immediately.

---

## API tokens

Admins can create long-lived API tokens for programmatic access. API tokens work the same as session tokens but do not expire unless explicitly given an expiry date.

### Creating a token

Go to the CMS, navigate to token management (admin-only), and create a new token. Specify:
- **Name** -- describes the token's purpose
- **Role** -- permission level for this token
- **Expiry** -- optional expiration date

The plaintext token is shown only once at creation. Copy it immediately -- it cannot be retrieved later.

### Token format

All tokens (session and API) use the same format:
- Prefix: `ts_` + 48 hex characters (24 random bytes)
- Stored as SHA-256 hash in the database (the plaintext is never stored)

### Revoking tokens

Admins can revoke any token from the token management page. Revoked tokens are immediately invalid.

---

## Session management

Expired sessions are pruned automatically on each login. If you need to revoke all sessions for a user, an admin can revoke their tokens from the token management page.

---

## First-boot admin creation

The setup wizard at `/setup` creates the first admin account. This is the only way to create a user without authentication. After setup completes, a marker file (`db/.setup_done`) is written, and the setup endpoint redirects to `/cms`.

To re-run the setup wizard (e.g., if you need to reset everything), delete `db/.setup_done` and restart the application.

---

## See also

- [Configuration](configuration.md) -- CORS and server settings
- [Devices](devices.md) -- Device tokens and pairing
- [API Reference](api-reference.md) -- Auth, user, and token endpoints
- [Backup and Restore](backup-and-restore.md) -- Admin-only backup operations
