# Technical Specification: Todo Sharing

## 1. Overview & Objective
- **Feature Summary**: Allows users to share their individual todo items with other registered users, granting them either read-only (viewer) or edit (editor) access.
- **Problem Statement**: Users currently manage todos in isolation. To foster collaboration, users need a way to securely grant and revoke access to specific tasks without exposing their entire list.
- **Target Audience / Roles**:
  - **Owner**: The user who originally created the todo. Has full control, including deleting the todo, editing it, sharing it, and revoking access.
  - **Viewer**: A user who has been granted read-only access to a shared todo.
  - **Editor**: A user who has been granted edit access. Can modify the title, description, and completion status of the shared todo.

## 2. User Stories & Acceptance Criteria

### User Story 1: Share a Todo
- **As an** Owner
- **I want to** share my todo with another registered user by their email address and assign them a specific role (Viewer or Editor)
- **So that** we can collaborate or they can track my progress.
- **Acceptance Criteria**:
  - [ ] The system validates that the target email belongs to a registered user.
  - [ ] The system prevents an owner from sharing a todo with themselves.
  - [ ] The system prevents creating a duplicate share (if user already has access, it updates the role instead).
  - [ ] The target user immediately gains access with the specified role.

### User Story 2: View Shared Todos
- **As a** Viewer or Editor
- **I want to** see the todos shared with me in my todo list or a dedicated "Shared with me" view
- **So that** I know what tasks I am collaborating on.
- **Acceptance Criteria**:
  - [ ] The API returns shared todos alongside or separated from owned todos.
  - [ ] The UI clearly indicates which todos are shared and the role the user has.

### User Story 3: Edit a Shared Todo
- **As an** Editor
- **I want to** modify the title, description, or completion status of a shared todo
- **So that** I can contribute to the task.
- **Acceptance Criteria**:
  - [ ] The system allows updates to `title`, `description`, and `completed` fields.
  - [ ] The system denies requests to delete the todo (only the owner can delete).
  - [ ] The system denies requests to share the todo further (only the owner can share).

### User Story 4: Revoke Access
- **As an** Owner
- **I want to** revoke a user's access to my shared todo
- **So that** they can no longer view or edit it.
- **Acceptance Criteria**:
  - [ ] The owner can successfully remove a user's access.
  - [ ] The revoked user's access is immediately terminated (cache invalidated instantly).
  - [ ] If the revoked user attempts a concurrent update, the system rejects it with a 403 Forbidden error.

## 3. Scope
- **In-Scope**:
  - Sharing individual todos via email.
  - Two permission levels: `viewer` and `editor`.
  - Fetching, updating, and revoking shared todos.
  - Real-time (immediate) cache invalidation upon access changes.
- **Out-of-Scope**:
  - Sharing an entire list/workspace (only per-todo sharing is supported in this iteration).
  - Real-time WebSockets/SSE updates to the UI when a todo is modified by another user.
  - Email notifications for invitations.
  - Public link sharing (must be authenticated users).

## 4. Database Design

### New Table: `todo_shares`
| Column | Type | Constraints | Description |
|---|---|---|---|
| `todo_id` | `UUID` | PK, FK (`todos.id`) `ON DELETE CASCADE` | The shared todo. |
| `user_id` | `UUID` | PK, FK (`users.id`) `ON DELETE CASCADE` | The user receiving access. |
| `role` | `VARCHAR(20)` | `NOT NULL`, `CHECK (role IN ('viewer', 'editor'))` | The access level granted. |
| `created_at` | `TIMESTAMPTZ` | `NOT NULL`, Default: `NOW()` | Audit timestamp. |

### Constraints & Indexes
- **Primary Key**: Composite `(todo_id, user_id)` implicitly enforces uniqueness, preventing duplicate invites.
- **Foreign Keys**: Both `todo_id` and `user_id` use `ON DELETE CASCADE` so that if a user or a todo is deleted, the share records are automatically cleaned up without leaving orphaned rows.
- **Indexes**:
  - `todo_shares(user_id)`: To quickly fetch all todos shared with a specific user.
  - `todo_shares(todo_id)`: To quickly list all users who have access to a specific todo (for the owner).

## 5. API Contracts & Endpoints

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/todos/{todo_id}/share` | Share a todo with a user by email | Yes (Owner only) |
| `PUT` | `/api/v1/todos/{todo_id}/share/{user_id}` | Update an existing share role | Yes (Owner only) |
| `DELETE`| `/api/v1/todos/{todo_id}/share/{user_id}` | Revoke access from a user | Yes (Owner only) |
| `GET` | `/api/v1/todos/{todo_id}/share` | List all users a todo is shared with | Yes (Owner only) |
| `GET` | `/api/v1/todos/shared` | List all todos shared with the current user | Yes |

### Request & Response Examples

**`POST /api/v1/todos/{todo_id}/share`**
- **Request Body**:
  ```json
  {
    "email": "collaborator@example.com",
    "role": "editor"
  }
  ```
- **Responses**:
  - `201 Created`: Successfully shared.
  - `400 Bad Request`: Cannot share with yourself.
  - `403 Forbidden`: Requester is not the owner of the todo.
  - `404 Not Found`: User with given email does not exist, or Todo not found.
  - `409 Conflict`: Todo is already shared with this user (suggests using `PUT` instead).

**`PUT /api/v1/todos/{todo_id}` (Existing Update Endpoint)**
- Now checks authorization against both `todos` and `todo_shares` tables.
- **Responses**:
  - `200 OK`: Updated successfully.
  - `403 Forbidden`: Requester is a `viewer` or has no access.

## 6. Business Logic & Security Considerations

### Authorization & Permission Matrix
| Action | Owner | Editor | Viewer | No Access |
|---|---|---|---|---|
| Read Todo | ✅ | ✅ | ✅ | ❌ |
| Update Title/Desc/Status | ✅ | ✅ | ❌ | ❌ |
| Delete Todo | ✅ | ❌ | ❌ | ❌ |
| Share/Revoke Access | ✅ | ❌ | ❌ | ❌ |

### Edge Cases & Race Conditions
- **Self-Sharing**: The API layer must strictly validate `target_user.id != current_user.id` before inserting into `todo_shares`.
- **Duplicate Invites**: The composite Primary Key `(todo_id, user_id)` naturally prevents database-level duplication. The API should catch the `IntegrityError` and return a `409 Conflict` (or perform an `UPSERT` depending on UX requirements).
- **Concurrent Updates & Revocations**:
  - If the Owner revokes User B's access exactly when User B sends a `PUT` request to update the todo, the database transaction isolation and row-level locks must ensure that User B's authorization check happens *after* the revocation is committed, resulting in a `403 Forbidden`.

## 7. Caching & Invalidation Strategy

Currently, caching is scoped by user (`todos:{user_id}:*`). With shared todos, caching becomes more complex because a single todo's state affects multiple users' lists.

### Cache Key Structure
- Shared list cache: `todos:shared:{user_id}:*`
- Individual Todo Cache: `todo:{todo_id}` (Moving to entity-based caching is recommended to avoid syncing multiple user lists).

### Invalidation Triggers
- **Owner revokes access**: Immediately invalidate `todos:shared:{revoked_user_id}:*`.
- **Owner updates todo**: Invalidate the owner's list cache `todos:{owner_id}:*` and the individual `todo:{todo_id}` cache. (If collaborators fetch shared lists via the `todos:shared:*` endpoint, those must also be invalidated or they must rely on the individual entity cache).
- **Editor updates todo**: Invalidate the editor's `todos:shared:{editor_id}:*`, the owner's `todos:{owner_id}:*`, and all other collaborators' lists. Due to the high fan-out of cache invalidation, migrating to Hash sets or entity-level caching in Redis is highly recommended before implementing this feature.
