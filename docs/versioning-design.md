# Knowledge content versioning

## Storage and visibility

Governed rows remain the single live record for each content item. Editing approved or published content creates a `ContentRevision` with a generic reference to the item, its `base_version`, author, JSON payload, status, and timestamp. The current row and its unique-key relationships stay untouched while the revision is pending. A revision is eligible to apply only while its base version still matches the live row; stale submissions must be reviewed against current content and resubmitted as a fresh revision.

Never-published items remain editable in place as drafts. Their version does not advance during draft edits. Existing content is served from the governed row, so pending proposals cannot leak to diagnosis or public endpoints.

## Review and apply

The workflow service owns all status changes. Mechanics can draft, create revisions, and submit only their own content. Reviewers and admins can start review, approve, return, reject, and publish. Self-approval is denied by default; `ALLOW_SELF_APPROVAL` is an explicit development override and defaults to false.

Every creation or workflow transition writes a `ContentReview` event with a JSON snapshot, actor, status, version, and comment. Approving a normal draft updates its state, clears `is_dummy`, and records `approved_by`. Approving a revision applies its payload inside one database transaction, increments the live version once, sets approval metadata, and records the resulting content snapshot. Publishing is a separate reviewer action and audit event. Versions never decrease.

Cause revisions carry parent fields and complete replacement sets for symptom links, self-checks, and costs. Apply validates and replaces these nested rows atomically; uniqueness or validation failures roll back the parent and all children. A cause snapshot includes the related content so its history is reconstructable.

## Concurrency and compatibility

Multiple revisions may be retained for discussion. `base_version` prevents a revision based on old live content from overwriting a newer approval. Unique constraints remain on the live tables because proposals are JSON and create no competing rows. This preserves existing reader queries and production visibility rules while meeting FR-31/FR-34 and workflow section 7.3; version history and reviewer attribution support the audit requirement.
