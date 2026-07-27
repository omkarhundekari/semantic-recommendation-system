# ADR: Trust, Tenancy, Identity, and Erasure Boundaries

## Status

Accepted

## Context

Solvyn is intended to become a multi-user, multi-workspace learning and execution platform with:

- evidence-grounded project recommendations
- interactive execution roadmaps
- learner progression and achievements
- GitHub verification
- Build Passports and shareable accomplishments
- individual, team, mentor, and institutional use
- free, premium, and enterprise plans
- large research and repository corpora
- web and future mobile clients

The current trusted-store subsystem provides deterministic SQLite readiness, migration provenance, receipt-chain validation, and recovery assessment.

These guarantees are intentionally stronger than ordinary application storage validation, but they must not be allowed to define or constrain future identity, tenancy, privacy, or product architecture incorrectly.

This ADR defines the boundaries between:

- database-level trust
- workspace-level evidence integrity
- identity and authorization
- immutable evidence
- erasable user data
- storage-engine-specific implementation
- future monetization and usage metering

## Architectural philosophy

The purpose of this ADR is to preserve future architectural freedom without implementing future product complexity today.

The system should reserve clean extension points while avoiding speculative infrastructure or premature abstractions.

## Decision 1: Database trust and workspace evidence trust are separate domains

The existing trusted receipt chain is scoped to the database store.

It establishes database-level guarantees such as:

- schema and migration provenance
- receipt lineage
- deterministic recovery state
- corruption detection
- readiness validation
- store-level consistency

It does not establish workspace-level evidence authenticity or ownership.

Workspace evidence integrity will be implemented as a separate future subsystem scoped to stable product identities such as:

- workspace_id
- project_id
- roadmap_snapshot_id
- execution_event_id
- evidence identity
- verification identity

The receipt chain must not be extended into a per-workspace authorization or evidence-integrity mechanism.

### Revisit trigger

Design workspace-scoped integrity when externally sourced execution evidence, public Build Passports, mentor verification, or enterprise audit exports become product requirements.

## Decision 2: Workspace is the tenancy boundary

Product data is scoped primarily by workspace_id.

The architecture must not assume that one workspace belongs permanently to one user.

A workspace may later support:

- multiple members
- mentor access
- teams
- organizations
- institutions
- transferred control
- service accounts
- system actors

Authorization will eventually be derived from workspace membership and policy, not from an owner_id field embedded across domain tables.

## Decision 3: Attribution and authorization are separate

The identity model will distinguish:

- principal_id: the actor performing an operation
- created_by_principal_id: the actor responsible for creating a resource, where attribution matters
- workspace_id: the tenant boundary
- membership and role records: the future authorization boundary

A `principal_id` must be a randomly generated opaque identifier. It must never be derived from an email address, provider account ID, username, or other personal identifier.

A principal may represent:

- a human user
- a service account
- a system actor
- an integration
- an automated verifier

A universal owner_id column will not be introduced because it would incorrectly conflate attribution, control, tenancy, and authorization.

### Revisit trigger

Implement principals, memberships, and authorization before real multi-user access, OAuth login, shared workspaces, mentor access, or institution-managed workspaces are enabled.

## Decision 4: Immutable evidence must exclude erasable personal data

Immutable execution and evidence records should contain only the minimum stable facts required for integrity and auditability.

Permitted immutable fields may include:

- opaque principal identifiers
- workspace and project identifiers
- event identifiers
- event type
- verification outcome
- source provider type
- internal resource references
- content hashes for sufficiently high-entropy content
- timestamps
- deterministic fingerprints
- non-sensitive execution facts

Directly erasable or sensitive data must live outside immutable evidence records.

Examples include:

- names
- email addresses
- OAuth identities
- access tokens
- refresh tokens
- repository credentials
- private project descriptions
- resumes
- private prompts
- raw user-authored text
- sensitive profile information

## Decision 5: External resource references may contain personal data

External URLs and identifiers are not automatically non-personal.

For example, a GitHub repository URL may contain a username.

Immutable evidence should prefer opaque internal resource IDs whose external identifiers are resolved through a deletable integration or resource store.

Where external identifiers must persist, that persistence must be explicitly documented and justified.

### Revisit trigger

Finalize resource-reference retention rules before importing real user repositories or enabling deletion requests.

## Decision 6: Content hashes are not automatically anonymized

A hash of a low-entropy value such as an email address, username, or name may be reversible through enumeration or dictionary attacks.

Hashes used in immutable evidence should represent sufficiently high-entropy content such as:

- source files
- repositories
- documents
- structured evidence payloads
- canonical execution artifacts

Hashes must not be treated as anonymization for personal identifiers.

Personal identifiers should remain in deletable storage or use a separately justified keyed construction.

## Decision 7: Erasure preserves opaque historical structure

When a principal is deleted or anonymized:

- personal profile data may be deleted
- OAuth identities and credentials must be deleted
- private user content may be deleted or crypto-shredded
- immutable evidence may retain an opaque principal_id
- the principal ID must no longer resolve to identifiable profile data

This preserves historical evidence structure without preserving directly identifying information.

The persistence of opaque identifiers must be documented as part of the erasure policy.

### Revisit trigger

Complete the formal erasure workflow before production user registration or external repository ingestion.

## Decision 8: Trust orchestration depends on capabilities, not SQLite primitives

Higher-level recovery and trust services must depend on product guarantees rather than direct PRAGMA calls.

The service boundary should expose capabilities such as:

- assess storage readiness
- assess recovery state
- build a deterministic snapshot fingerprint
- execute within a consistent read snapshot

SQLite-specific implementation may internally use:

- explicit read transactions
- PRAGMA user_version
- PRAGMA integrity_check
- PRAGMA foreign_key_check
- SQLite journal and WAL semantics

Future storage adapters may implement the same guarantees using their native transaction and consistency mechanisms.

SQLite-specific behavior is confined behind the capability boundary and tested against the current behavioral contract. Full engine independence remains an architectural assertion until a second storage adapter is implemented and both adapters pass the shared contract suite.

The abstraction must not claim that SQLite and PostgreSQL expose equivalent low-level concepts.

Adapter-specific diagnostic values may be exposed as diagnostics, but they must not become required inputs to engine-neutral fingerprinting or recovery identity.

## Decision 9: Snapshot fingerprints must have an explicit guarantee

A snapshot fingerprint used for recovery or audit must be:

- deterministic
- comparable across processes
- comparable across time
- derived only from authoritative assessed state
- changed whenever the assessed state changes
- unchanged when the assessed state is semantically identical
- independent of connection-local tokens such as PRAGMA data_version

The fingerprint contract must be validated through shared adapter-level tests.

## Decision 10: Usage-producing operations require centralized service boundaries

The system does not yet require subscriptions, quotas, or billing enforcement.

However, operations that may later be monetized must flow through instrumentable service boundaries.

Examples include:

- project recommendation generation
- roadmap generation
- research retrieval
- code evaluation
- GitHub verification
- Build Passport generation
- premium export
- AI-assisted refinement

Future usage events should support:

- usage_event_id
- idempotency_key
- principal_id
- workspace_id
- operation_type
- provider
- model
- input units
- output units
- duration
- status
- estimated cost
- occurred_at

Usage-event idempotency is required to prevent retry-driven double counting and billing disputes.

## Decision 11: Current trust ceiling

The current receipt system provides corruption evidence and deterministic lineage validation.

Unsigned hashes do not provide an adversarial tamper-proof boundary against an actor with full database write access.

The product must not market the current system as cryptographically tamper-proof.

### Revisit trigger

Add signed receipts or external anchoring when:

- enterprise audit guarantees require it
- adversarial database write access enters the threat model
- external attestations become a product requirement
- compliance or contractual commitments require non-repudiation

## Decision 12: Recovery service sequencing

The trusted recovery service will be completed as the final deep trusted-store milestone for the current phase.

Its purpose is to:

- acquire one authoritative read snapshot
- assess readiness
- assess deterministic recovery state
- produce an auditable typed result
- avoid TOCTOU races
- remain reusable by future CLI, operator, API, and support tooling

After this milestone, engineering focus will shift to:

1. principal and external identity design
2. authentication
3. workspace membership
4. authorization
5. interactive roadmap experience
6. learner progress and proof capture
7. one narrow monetizable workflow

Proof capture must be reviewed against the workspace-evidence-integrity revisit triggers before it produces portable, public, passport-level, or enterprise-verifiable claims.

Further trust-subsystem expansion is postponed unless triggered by a production incident, operational requirement, compliance requirement, or enterprise security commitment.

## Intentionally postponed

### Workspace evidence integrity

Postponed until externally verifiable execution evidence, Build Passports, public sharing, or enterprise audit exports require it.

### Signed receipts

Postponed until adversarial tampering or enterprise non-repudiation becomes part of the threat model.

### PostgreSQL adapter

Postponed until concurrency, operational scale, deployment architecture, or production workload makes SQLite unsuitable.

The capability contract must remain storage-engine independent even while only SQLite is implemented.

### Subscription and billing infrastructure

Postponed until one narrow paid workflow has been validated.

Service boundaries and usage-event semantics should be preserved before billing enforcement exists.

### Full organization and role model

Postponed until shared workspaces, mentors, teams, institutions, or enterprise customers require it.

The system must not make single-owner assumptions before then.

## Consequences

### Positive

- avoids incorrect owner semantics
- preserves multi-user and team evolution
- protects future erasure capability
- prevents SQLite details from leaking into orchestration
- separates migration trust from workspace evidence trust
- preserves future monetization and metering paths
- limits further overinvestment in the trust subsystem

### Negative

- identity and privacy architecture must be completed before real users
- immutable event payloads require stricter review
- external resource references require indirection or retention policy
- future adapters must satisfy a strong shared capability contract
- some previously convenient direct storage access may need refactoring

## Validation requirements

Before accepting the recovery service:

- readiness and recovery must run inside one caller-owned read transaction
- the service must not commit, roll back, or close caller-owned resources unexpectedly
- no connection-local data_version value may be used as durable snapshot identity
- snapshot fingerprinting must be deterministic
- unreadable or unverifiable states must fail closed
- SQLite-specific logic must remain inside the SQLite adapter boundary
- the service must be read-only
- tests must cover transaction ownership, error paths, fingerprint stability, fingerprint change, WAL behavior, and compatibility with existing readiness behavior

## Final decision

Proceed with one final trusted recovery service milestone after this ADR is accepted.

Then stop deepening the trust subsystem and move product development toward identity, authorization, interactive learning, proof capture, and monetizable user value.
