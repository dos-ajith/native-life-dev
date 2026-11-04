# Roles and Permissions

Native Life has exactly six roles. `scripts/seed.py` (`ROLE_DEFINITIONS`) is the
source of truth for their names and permissions; the slugs and canonical order
live in `app/core/permissions.py` (`RoleSlug`, `CANONICAL_ROLE_SLUGS`).

## Roles

| # | Slug | Name | Who | Selectable in the app | Verification |
|---|---|---|---|---|---|
| 1 | `super-admin` | Super Admin | Full backend administration | No | — |
| 2 | `native-admin` | Native Admin | Backend staff managing promoters | No | — |
| 3 | `individual-user` | Individual User | Default for every registration | Yes | Not required |
| 4 | `promoter` | Promoter | Figma card "Promoter" | Yes | Required |
| 5 | `club-community` | Club / Community | Figma card "Club / Community" | Yes | Required |
| 6 | `business-service-provider` | Business / Service Provider | Figma card "Business / Service Provider" | Yes | Required |

The two combined Figma cards are one role each. Nothing in the backend treats
clubs differently from communities, or businesses differently from service
providers, so splitting them would only create duplicate roles.

## How roles combine

- Every regular account starts with `individual-user`. After selecting a
  Promoter, Club / Community or Business / Service Provider role the account
  holds both while verification is pending; when an admin approves the request,
  `individual-user` is removed and the verified role is the only one left.
  Switching roles or going back to Individual User re-adds the base role.
- `GET /api/v1/account-roles` lists only the four selectable roles. Super Admin
  and Native Admin can never be selected or requested through user-facing APIs.
- Selecting a role records the assignment immediately, but its permissions
  apply only once an admin approves it. Verification is tracked on that
  assignment (`user_has_roles.verified_at`) and never carries over to a newly
  selected role. While it is pending, the account holds only the permissions of
  `individual-user`, and `GET /auth/me` lists only approved roles in `roles`;
  the pending selection is reported in `account_role`.
- Admin accounts cannot select account roles.

## Permission matrix

SA = Super Admin, NA = Native Admin, IU = Individual User, PR = Promoter,
CC = Club / Community, BS = Business / Service Provider. Super Admin is also
granted every permission in code (`authorization_service._role_grants`), so it
keeps full access even if a new permission is added before the seeder runs.

| Permission | SA | NA | IU | PR | CC | BS |
|---|---|---|---|---|---|---|
| `user.view` | ✓ | ✓ |  |  |  |  |
| `user.create` | ✓ |  |  |  |  |  |
| `user.update` | ✓ |  |  |  |  |  |
| `user.delete` | ✓ |  |  |  |  |  |
| `role.view` | ✓ |  |  |  |  |  |
| `role.create` | ✓ |  |  |  |  |  |
| `role.update` | ✓ |  |  |  |  |  |
| `role.delete` | ✓ |  |  |  |  |  |
| `permission.view` | ✓ |  |  |  |  |  |
| `permission.create` | ✓ |  |  |  |  |  |
| `permission.update` | ✓ |  |  |  |  |  |
| `permission.delete` | ✓ |  |  |  |  |  |
| `page.view` | ✓ |  |  |  |  |  |
| `page.read` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `page.create` | ✓ |  |  |  |  |  |
| `page.update` | ✓ |  |  |  |  |  |
| `page.delete` | ✓ |  |  |  |  |  |
| `setting.view` | ✓ |  |  |  |  |  |
| `setting.create` | ✓ |  |  |  |  |  |
| `setting.update` | ✓ |  |  |  |  |  |
| `setting.delete` | ✓ |  |  |  |  |  |
| `geography.import` | ✓ |  |  |  |  |  |
| `post.view` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `post.create` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `post.create_any` | ✓ | ✓ |  |  |  |  |
| `post.view_any` | ✓ | ✓ |  |  |  |  |
| `post.update_any` | ✓ |  |  |  |  |  |
| `post.delete_any` | ✓ |  |  |  |  |  |
| `post.block` | ✓ | ✓ |  |  |  |  |
| `post.like` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `post.comment` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `post.share` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `post.save` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `comment.delete_any` | ✓ |  |  |  |  |  |
| `category.suggest` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `category.view_pending` | ✓ |  |  |  |  |  |
| `category.approve` | ✓ |  |  |  |  |  |
| `category.reject` | ✓ |  |  |  |  |  |
| `category.create` | ✓ |  |  |  |  |  |
| `category.update` | ✓ |  |  |  |  |  |
| `category.delete` | ✓ |  |  |  |  |  |
| `community.create` |  |  |  |  | ✓ |  |
| `community.view_pending` | ✓ | ✓ |  |  |  |  |
| `community.approve` | ✓ | ✓ |  |  |  |  |
| `community.reject` | ✓ | ✓ |  |  |  |  |
| `business.create` | ✓ |  |  |  |  | ✓ |
| `business.search` | ✓ |  |  | ✓ |  |  |
| `business.view_any` | ✓ |  |  |  |  |  |
| `business.update_any` | ✓ |  |  |  |  |  |
| `business.delete_any` | ✓ |  |  |  |  |  |
| `business.escalate` | ✓ | ✓ |  |  |  |  |
| `business.create_any` | ✓ | ✓ |  |  |  |  |
| `deal.create` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `deal.view_any` | ✓ |  |  |  |  |  |
| `role_upgrade_request.create` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `role_upgrade_request.view_own` | ✓ |  | ✓ | ✓ | ✓ | ✓ |
| `role_upgrade_request.view_any` | ✓ |  |  |  |  |  |
| `role_upgrade_request.review_promoter` | ✓ | ✓ |  |  |  |  |
| `role_upgrade_request.approve` | ✓ |  |  |  |  |  |
| `role_upgrade_request.reject` | ✓ |  |  |  |  |  |

## Ownership

Permissions decide *what* a role may do; ownership decides *which records*.
Posts, comments, businesses (and their images and documents) can only be
changed by their owner unless the caller holds the matching `*_any`
permission, which only Super Admin has.

## Deal acceptance

Who may accept or decline a submitted deal is not a permission. It is the
`deal_accepting_roles` setting (a JSON array of one role slug, seeded as
`["promoter"]`), and only roles with a verification workflow (promoter,
club-community, business-service-provider) can be configured. An accepting user
must hold that role with completed verification (`user_has_roles.verified_at`),
be active, have the deal's village as their primary native place, not be the
deal's creator, and hold an open invitation for it — rechecked on every accept
or decline. Creating deals (`deal.create`) is independent of this setting.

## Verification review

- Super Admin (`role_upgrade_request.view_any` / `approve` / `reject`) reviews
  every verification request.
- Native Admin (`role_upgrade_request.review_promoter`) lists, opens, approves
  and rejects **Promoter** requests only; other requests return 404 for it.
  It is notified only about Promoter requests.
- Nobody can review their own request.

## Privilege-escalation guards

These are enforced in the service layer, independently of permissions, so a
misconfigured role still cannot escalate:

- Only a Super Admin can grant or remove `super-admin` or `native-admin`
  (`UserService._ensure_can_change_roles`).
- Only a Super Admin can update, re-image, delete or change the roles of a
  Super Admin account (`UserService._ensure_can_modify`).
- Only a Super Admin can change an admin role's details or permissions
  (`RoleService._ensure_can_change`).
- The six built-in roles cannot be deleted.

## Migrating from the legacy roles

Migration `5c5c2fb4090a_consolidate_final_role_model` maps the old roles:

| Legacy slug | Becomes | Notes |
|---|---|---|
| `public-user` | `individual-user` | Same row, so every assignment is kept |
| `business-profile` | `business-service-provider` | Same row; assignments and verification kept |
| `service-provider` | `business-service-provider` | Merged; existing verification kept |
| `club` | `club-community` | Same row (or merged) |
| `community` | `club-community` | Merged; a duplicate pending request is cancelled |
| `public-authority` | retired | Holders get `individual-user` unless they hold an admin role; pending requests cancelled |
| `delivery-team-member` | retired | Same as `public-authority` |

Request history is never deleted: `role_upgrade_requests.requested_role_id`
is set to `NULL` (and the request shown without a role) when its role is
retired. The downgrade refuses to run while such rows exist, and it does not
recreate retired or merged roles.

After `alembic upgrade head`, run `python -m scripts.seed` so each role's
permissions match this document (for example, to strip Native Admin's former
full access).
