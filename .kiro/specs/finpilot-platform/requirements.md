# Requirements Document

## Introduction

FinPilot AI is a multi-tenant B2B SaaS web application for AI-powered receivables, payment recovery, and cash flow management, targeting Indian MSMEs with INR as the primary currency. The Platform centralizes customer and invoice management, outstanding receivables monitoring, payment follow-up automation, payment recording and allocation, bank transaction reconciliation, cash inflow forecasting, and a read-only AI finance assistant into a single application with organization-based access control, audit trails, and notifications.

The repository already contains a partial implementation of Phase 2 (SaaS foundation) and Phase 3 (core financial records): a Django 5.2 + DRF backend with a `core` app implementing authentication, organizations, memberships with role checks, customers, invoices with draft/issued/void lifecycle and integer-paise totals, payments with atomic allocations, a receivables dashboard, invoice aging, and an audit trail; a React 19 + Vite + TypeScript frontend; and PostgreSQL configured via docker-compose. The remaining scope covers invoice import, collections automation, messaging providers, bank statement import, reconciliation, cash flow forecasting, the AI finance assistant, optional document extraction, subscriptions, platform administration, notifications, data export, and production readiness.

Core engineering principle: the financial ledger and calculations must be deterministic and verifiable. The AI_Assistant may assist with extraction, explanations, classification, and recommendations, but the AI_Assistant must not independently modify financial records or initiate consequential financial actions without the required authorization.

## Glossary

- **Platform**: The FinPilot AI web application comprising the API, Frontend, Background_Workers, and external provider integrations.
- **API**: The Django REST Framework backend that serves as the authoritative financial system and enforces all security, validation, and business rules server-side.
- **Frontend**: The React + TypeScript web interface served to users.
- **Organization**: A tenant business entity that owns customer, invoice, payment, and related financial records.
- **Membership**: The association of a User with an Organization carrying a role and an active status.
- **User**: An authenticated account that may belong to one or more Organizations through Memberships.
- **Customer**: A business entity recorded under an Organization that receives invoices and makes payments.
- **Invoice**: A financial record carrying subtotal, discount, tax, total, and a status that determines whether the Invoice participates in receivables and forecasts.
- **Invoice_Item**: A line item on an Invoice with description, quantity, unit price, and line total.
- **Payment**: A record of money received from a Customer.
- **Payment_Allocation**: An assignment of a portion of a Payment to an Invoice to reduce the Invoice outstanding balance.
- **Bank_Transaction**: A normalized row from an imported bank statement pending reconciliation.
- **Reconciliation_Match**: A suggestion linking a Bank_Transaction to an Invoice or Payment pending authorized confirmation.
- **Reminder_Policy**: A configurable rule defining when, how, and whether approval is required for reminders sent for eligible Invoices.
- **Reminder_Job**: A scheduled or proposed reminder instance for a specific Invoice under a Reminder_Policy.
- **Reminder_Template**: A reusable message template with validated placeholders for Invoice and Customer data.
- **Message_Log**: A record of a reminder message delivery lifecycle through a Messaging_Service.
- **Cash_Forecast**: A projection of expected receivable inflows for a defined period with documented assumptions.
- **AI_Assistant**: A read-only conversational interface that answers financial questions using authorized Organization data through server-controlled tools.
- **Extraction_Service**: An optional service that extracts candidate Invoice fields from uploaded documents for human review.
- **Notification**: An in-app or external alert about an operational event.
- **Audit_Log**: An append-only record of a security-sensitive or financially consequential action.
- **Subscription**: An Organization plan assignment with status and entitlement limits.
- **Import_Batch**: A record of a file import operation with processing status and row-level results.
- **Background_Worker**: An asynchronous task processor for reminders, imports, exports, forecasts, and messaging.
- **File_Storage**: Private object storage for uploaded files and generated exports with short-lived authorized download links.
- **Messaging_Service**: A provider abstraction layer for outbound email and business messaging delivery.
- **Auth_Service**: The component handling authentication, sessions, password reset, and account status.
- **Admin_Service**: Platform-level administration tools for managing Organizations, Users, and Subscription plan definitions.
- **Export_Service**: The component that generates authorized data exports asynchronously.
- **Validator**: The component that validates input data formats and business rules on the server.
- **Minor_Unit**: The smallest currency denomination (paise for INR), stored and processed as integer values for all monetary amounts.
- **Role**: A permission level assigned to a Membership: Platform administrator, Business owner, Finance manager, Accountant, Collections executive, or Viewer.
- **Authorized_User**: A User whose active Membership role grants the specific permission required for a given operation.

## Requirements

### Requirement 1: Authentication and Account Management

**User Story:** As a business user, I want secure account creation, login, logout, and password reset, so that only authenticated and authorized users access the Platform.

#### Acceptance Criteria

1. WHEN an unauthenticated request targets a protected endpoint, THE API SHALL return an authentication failure response.
2. WHEN a User whose account status is inactive or suspended attempts to sign in, THE Auth_Service SHALL block the sign-in attempt, return a failure response that does not reveal the account status, and log a security event to the Audit_Log.
3. WHEN a User requests a password reset, THE Auth_Service SHALL issue a single-use password reset token that is valid for no more than 60 minutes after issuance and deliver the token to the User's verified contact method through the configured channel.
4. WHEN a password reset token is expired or has already been used, THE Auth_Service SHALL reject the reset attempt with a failure response that does not reveal whether the token was valid, expired, or already used.
5. WHEN a User signs in or signs out, THE Auth_Service SHALL log a security event to the Audit_Log recording the User identity, event type, timestamp, and outcome.
6. WHILE a User holds the Business owner, Finance manager, or Platform administrator role and the User account is not enrolled in multi-factor authentication, THE Auth_Service SHALL require multi-factor authentication enrollment before granting access.
7. WHEN an authenticated User attempts to access a resource scoped to an Organization for which the User has no active Membership, THE API SHALL return an authorization failure response.
8. THE API SHALL enforce all authentication and authorization checks server-side independently of the Frontend.
9. WHEN a User submits an account creation request, THE Auth_Service SHALL validate the email format, enforce email uniqueness across all accounts, require that the password contains at least 8 characters and at least one uppercase letter, one lowercase letter, one digit, and one symbol, and create the account.
10. WHEN a User submits sign-in credentials that do not match an existing account, THE Auth_Service SHALL reject the sign-in attempt, log the failed attempt to the Audit_Log, and return a failure response that does not reveal whether the submitted email corresponds to an existing account.
11. WHILE a User session has been inactive for longer than 30 minutes, THE API SHALL require re-authentication before granting further access.

### Requirement 2: Organization Onboarding and Management

**User Story:** As a business owner, I want to create and configure my business organization, so that my team can collaborate within an isolated tenant.

#### Acceptance Criteria

1. WHEN an authenticated User creates an Organization with all required fields, THE API SHALL create an initial active Membership assigning that User the Business owner role for the new Organization.
2. THE API SHALL generate an internal identifier for each Organization that is unique across all Organizations in the Platform.
3. WHEN an Authorized_User updates Organization legal name, trading name, business email, contact phone number, country, default currency, or timezone, THE API SHALL persist the changes and record the User identity, timestamp, Organization identifier, and each changed field with before and after values in the Audit_Log.
4. WHERE the Organization timezone is configured, THE API SHALL evaluate dates, due dates, and reminder schedules using that configured timezone.
5. THE API SHALL store for each Organization a default currency, country, timezone, legal name, trading name, business email, and contact phone number, with each text field not exceeding 255 characters.
6. THE initial deployment SHALL support Organizations registered in India with INR as the default currency and Asia/Kolkata as the default timezone.
7. IF an authenticated User submits Organization creation data with missing required fields or invalid field formats, THEN THE API SHALL reject the creation and return validation errors identifying each invalid field.
8. IF the Organization timezone is not configured, THEN THE API SHALL evaluate dates, due dates, and reminder schedules using Asia/Kolkata as the default timezone.

### Requirement 3: Customer Management

**User Story:** As a finance team member, I want to create, search, update, and deactivate customers, so that I can maintain an accurate customer register.

#### Acceptance Criteria

1. WHEN an Authorized_User creates a Customer, THE API SHALL scope the Customer to the active Organization.
2. IF a Customer record is submitted with an invalid email, phone, or GSTIN format, THEN THE Validator SHALL reject the submission with an error indicating which field is invalid.
3. WHEN a newly submitted Customer matches an existing Customer in the same Organization by exact GSTIN, exact email, exact phone, or case-insensitive name, THE API SHALL return a warning identifying the potential duplicate without blocking the creation.
4. WHEN an Authorized_User deactivates a Customer, THE API SHALL set the Customer active flag to false and preserve all related Invoice and Payment records.
5. WHEN an Invoice or Payment references a Customer, THE API SHALL prevent permanent deletion of that Customer.
6. WHEN a User requests the customer list, THE API SHALL return only Customers belonging to the active Organization with support for filtering by name using a case-insensitive partial match and by status (active or inactive).
7. THE API SHALL restrict Customer create, update, and deactivate operations to Authorized_Users with an active Membership role of Business owner, Finance manager, or Accountant.
8. THE API SHALL treat the Customer name as a required field and email, phone, and GSTIN as optional identifiers for Customer creation.

### Requirement 4: Invoice Management

**User Story:** As a finance team member, I want to create and manage invoices with server-calculated totals, so that outstanding balances are accurate and verifiable.

#### Acceptance Criteria

1. WHEN an Invoice is created, THE API SHALL calculate the Invoice total as the subtotal minus the discount plus the tax, where the subtotal, discount, and tax are each non-negative integer Minor_Units, using integer Minor_Unit arithmetic throughout.
2. WHEN an Invoice is submitted with a discount greater than the subtotal, THE Validator SHALL reject the Invoice.
3. THE API SHALL store all monetary amounts as integer Minor_Units and SHALL never use binary floating-point arithmetic for authoritative financial calculations.
4. WHEN a User requests an Invoice, THE API SHALL derive the displayed status as one of Draft, Issued, Partially paid, Paid, Overdue, or Void, where Void and Draft are stored lifecycle states evaluated first and Issued, Partially paid, Paid, and Overdue are derived for issued Invoices from the outstanding balance, valid Payment_Allocations, and due date.
5. WHILE an Invoice has the status Void, THE API SHALL exclude the Invoice from outstanding receivables and forecasts.
6. WHILE an Invoice has the status Draft, THE API SHALL exclude the Invoice from receivables and forecasts.
7. WHEN an issued Invoice has at least one valid Payment_Allocation, an outstanding balance greater than zero, and a due date that is not earlier than the configured Organization reporting date, THE API SHALL derive the displayed status as Partially paid.
8. WHEN an issued Invoice has an outstanding balance of zero, THE API SHALL derive the displayed status as Paid.
9. WHEN an issued Invoice has an outstanding balance greater than zero and a due date earlier than the configured Organization reporting date, THE API SHALL derive the displayed status as Overdue.
10. WHEN an Authorized_User attempts to change the Invoice total or status of an Invoice that has existing Payment_Allocations, THE API SHALL require a correction or reversal authorized by a Finance manager or Business owner before applying the change.
11. WHEN an Invoice has one or more Payment_Allocations, THE API SHALL prevent deletion of the Invoice.
12. THE API SHALL enforce uniqueness of Invoice numbers within the active Organization, such that no two Invoices belonging to the same Organization share the same Invoice number.
13. WHEN an Invoice references a Customer outside the active Organization, THE Validator SHALL reject the Invoice.
14. WHEN an Invoice specifies a currency that differs from the Organization default currency, THE API SHALL reject the Invoice and return an error indicating that the Invoice currency must match the Organization default currency.
15. THE API SHALL calculate the outstanding balance for each Invoice as the Invoice total minus the sum of valid Payment_Allocation amounts, where a valid Payment_Allocation targets the same Invoice, belongs to the same Organization, and has an amount that does not exceed the Invoice outstanding balance, and the calculated outstanding balance SHALL never be less than zero.
16. WHEN an issued Invoice has no valid Payment_Allocations, an outstanding balance greater than zero, and a due date that is not earlier than the configured Organization reporting date, THE API SHALL derive the displayed status as Issued.

### Requirement 5: Invoice Import

**User Story:** As a finance team member, I want to import invoices from CSV and XLSX files, so that I can onboard many invoices efficiently without manual entry.

#### Acceptance Criteria

1. WHEN an Authorized_User downloads the invoice import template, THE API SHALL provide a downloadable sample file in CSV and XLSX format containing column headers matching the required import fields and at least one example row with valid sample data.
2. WHEN an import file is uploaded, THE Validator SHALL validate that the file type is CSV or XLSX, that the file size does not exceed 10 megabytes, that the file contains all required columns, and that each row contains valid date formats, valid currencies, valid amounts, and valid customer references within the active Organization.
3. WHEN an import file is uploaded, THE API SHALL create an Import_Batch record with a unique batch identifier and a processing status reflecting one of the following stages: pending, validating, previewing, committed, or failed.
4. WHEN the API parses imported rows, THE API SHALL present a preview of all parsed rows with a per-row validation status of valid, error, or duplicate-flagged, before committing any financial records.
5. WHEN an imported row contains validation errors, THE API SHALL report row-level errors identifying the row number, the field name, and the nature of the validation failure.
6. WHEN an imported row contains an Invoice number matching an existing issued Invoice within the same Organization, THE API SHALL identify the row as a potential duplicate and flag it in the preview.
7. WHEN an Authorized_User confirms the import, THE API SHALL commit only rows that have no validation errors and that the Authorized_User has selected for import, and SHALL return an import summary containing counts of created, rejected, skipped, and flagged rows.
8. WHEN a file is re-uploaded that produces a batch identifier matching an existing Import_Batch, THE API SHALL return the existing Import_Batch results without creating duplicate Invoices.
9. THE API SHALL require explicit User confirmation before importing any financial records.
10. THE API SHALL calculate each imported Invoice total from validated line items, discounts, and taxes using integer Minor_Unit arithmetic.
11. WHEN the calculated Invoice total differs from the imported Invoice total by any non-zero amount in integer Minor_Units, THE API SHALL flag the row with a discrepancy error in the preview.
12. IF an import file passes type and size validation but cannot be parsed into rows, contains no data rows, or is missing required columns, THEN THE API SHALL reject the file with a file-level error and record the failure status in the Import_Batch.

### Requirement 6: Payment Recording and Allocation

**User Story:** As a finance team member, I want to record payments and allocate them across invoices, so that outstanding balances reflect received money accurately.

#### Acceptance Criteria

1. WHEN an Authorized_User records a Payment, THE API SHALL create the Payment scoped to the active Organization and linked to a Customer belonging to that Organization.
2. WHEN a Payment includes Payment_Allocations, THE API SHALL validate, using integer Minor_Unit arithmetic, that the sum of Payment_Allocation amounts is less than or equal to the Payment amount.
3. WHEN a Payment_Allocation targets an Invoice, THE Validator SHALL verify that the Invoice has the status Issued or Partially paid, belongs to the same Customer as the Payment, and belongs to the same Organization as the Payment.
4. IF a Payment_Allocation amount, in integer Minor_Units, exceeds the current Invoice outstanding balance, THEN THE Validator SHALL reject the Payment_Allocation.
5. WHEN a Payment includes one or more Payment_Allocations, THE API SHALL persist the Payment and all of its Payment_Allocations atomically, such that no Payment or Payment_Allocation is persisted if any allocation fails validation.
6. WHEN a Payment is created, THE API SHALL record the event in the Audit_Log.
7. WHEN a submitted Payment reference exactly matches an existing Payment reference for the same Customer and Organization, THE API SHALL return a non-blocking duplicate warning.
8. WHILE the sum of a Payment's Payment_Allocation amounts is less than the Payment amount, THE API SHALL return the unallocated remainder, calculated in integer Minor_Units as the Payment amount minus the sum of Payment_Allocation amounts, as a value distinct from the allocated amount.
9. WHEN an Authorized_User corrects or reverses a Payment_Allocation, THE API SHALL retain the original Payment_Allocation record unchanged and record the correction or reversal in the Audit_Log.
10. THE API SHALL prevent deletion of Payment and Payment_Allocation records.
11. IF a Payment specifies a currency that differs from the Organization default currency, THEN THE Validator SHALL reject the Payment with an error indicating the currency mismatch.
12. WHEN a duplicate Payment is submitted through an API retry and matches an existing Payment in Customer, amount, currency, payment date, and reference, THE API SHALL prevent creation of a second Payment with identical financial effect through idempotency controls.
13. WHEN a Payment_Allocation is created, corrected, or reversed, THE API SHALL recalculate the outstanding balance for each affected Invoice using integer Minor_Unit arithmetic.
14. IF a Payment is recorded with an amount that is not a positive integer Minor_Unit value, THEN THE Validator SHALL reject the Payment.
15. IF a Payment_Allocation is recorded with an amount that is not a positive integer Minor_Unit value, THEN THE Validator SHALL reject the Payment_Allocation.

### Requirement 7: Receivables Dashboard

**User Story:** As a business owner, I want to see my organization's receivables position at a glance, so that I can understand outstanding, overdue, and collected amounts.

#### Acceptance Criteria

1. WHEN an Authorized_User opens the receivables dashboard, THE API SHALL return a dashboard summary containing total outstanding, total overdue, amount due on the configured Organization reporting date, amount due within 1 to 7 calendar days after the reporting date, amount collected within the selected reporting period, count of overdue Invoices, count of Customers with outstanding balances, the 10 Customers with the highest overdue amounts ranked in descending order, and the 20 most recent Payment records received within the last 30 days.
2. WHEN the API calculates dashboard totals, THE API SHALL derive each total so that it reconciles exactly with the corresponding sum computed from issued Invoice records and their valid Payment_Allocations for the active Organization.
3. WHILE an Invoice has the status Draft or Void, THE API SHALL exclude the Invoice from all receivables totals.
4. WHEN an Authorized_User applies date-range or Customer filters, THE API SHALL return totals scoped to the selected filters.
5. WHEN an Authorized_User selects a dashboard metric, THE API SHALL return the underlying Invoice and Payment records that compose that metric, scoped to the same filters applied to the dashboard.
6. WHEN no Invoices match the selected filters or no outstanding Invoices exist for the active Organization, THE Frontend SHALL display an empty state.
7. THE Frontend SHALL display the reporting currency and the active reporting period on the dashboard.
8. WHEN the receivables dashboard displays any projected or forecast receivable amounts, THE Frontend SHALL present those amounts as projected receipts distinct from actual collected receipts.
9. IF no reporting period is selected on the receivables dashboard, THEN THE API SHALL compute the amount collected over the default reporting period of the current calendar month in the configured Organization timezone.

### Requirement 8: Invoice Aging Reports

**User Story:** As a finance manager, I want to see how long invoices have been overdue, so that I can prioritize collection efforts.

#### Acceptance Criteria

1. WHEN an Authorized_User requests an aging report, THE API SHALL include only Invoices that have an outstanding balance greater than zero Minor_Units and have the status Issued, Partially paid, or Overdue.
2. WHEN the API assigns an Invoice to an aging bucket, THE API SHALL assign each qualifying Invoice to exactly one of the following buckets: Not yet due (due date is on or after the reporting date), 1 to 30 days overdue, 31 to 60 days overdue, 61 to 90 days overdue, or more than 90 days overdue.
3. WHEN the API computes the days-overdue value for a bucket assignment, THE API SHALL calculate it as the reporting date minus Invoice due date expressed as whole calendar days using the Organization configured timezone, where a due date equal to the reporting date yields zero and is assigned to the Not yet due bucket.
4. WHEN an Authorized_User requests an aging report without specifying a reporting date, THE API SHALL use the current calendar date in the Organization configured timezone as the reporting date.
5. WHEN an Authorized_User requests an aging report and specifies a reporting date, THE API SHALL use the supplied date as the reporting date for all bucket calculations in that report.
6. WHILE an Invoice has the status Draft or Void, THE API SHALL exclude the Invoice from all aging report calculations and bucket totals.
7. WHEN an Authorized_User applies Customer, due date range, or status filters to an aging report request, THE API SHALL return only Invoices matching all selected filters.
8. WHEN an Authorized_User selects a bucket in the aging report, THE API SHALL return the Invoice number, Customer name, Invoice date, due date, outstanding balance in Minor_Units, and days overdue for each Invoice in that bucket.
9. WHEN an Authorized_User exports an aging report, THE Export_Service SHALL generate the report in the format selected by the Authorized_User (CSV or XLSX) and SHALL record the reporting date used for bucket calculations as a field in the exported file.
10. IF the Export_Service cannot generate the aging report export within 60 seconds, THEN THE Export_Service SHALL return an error response indicating the failure and SHALL not deliver a partial export file.

### Requirement 9: Reminder Policies

**User Story:** As a finance manager, I want to configure reminder policies, so that the Platform can identify eligible invoices and propose or send reminders according to my rules.

#### Acceptance Criteria

1. WHEN an Authorized_User creates a Reminder_Policy, THE API SHALL store the policy name, applicable Invoice statuses, trigger offset in days relative to the due date (in the range −365 to +365, where negative values mean before and positive values mean after), channel, Reminder_Template, schedule with timezone, approval mode, maximum reminder frequency in days, maximum attempt count, quiet hours start and end times, customer-specific exclusions, and enabled state.
2. WHEN a Reminder_Policy is created, THE API SHALL set the automatic sending mode to disabled by default.
3. WHEN an Authorized_User enables automatic sending for a Reminder_Policy, THE API SHALL require the Authorized_User to submit an explicit confirmation action before activating automatic mode.
4. IF an Authorized_User does not submit the required confirmation action, THEN THE API SHALL leave the Reminder_Policy automatic sending mode in the disabled state.
5. WHEN a Reminder_Policy targets a Customer whose contact destination for the configured channel is absent, malformed, or blocked, THE API SHALL block reminders to that Customer for that policy and record the block reason.
6. WHEN an Authorized_User records a reminder opt-out for a Customer, THE API SHALL set the Customer opt-out flag to true and record the change in the Audit_Log.
7. WHILE a Customer has the opt-out flag set to true, THE API SHALL exclude that Customer from all Reminder_Policy evaluation.
8. WHILE an Invoice has the status Draft, Paid, or Void, THE API SHALL exclude the Invoice from Reminder_Policy evaluation.
9. WHEN an Authorized_User modifies a Reminder_Policy, THE API SHALL record the change in the Audit_Log.
10. WHEN the Reminder_Scheduler evaluates eligible Invoices, THE API SHALL prevent creation of a duplicate Reminder_Job where a Reminder_Job with the same Reminder_Policy identifier, Invoice identifier, and scheduled trigger date already exists in a pending or sent state.

### Requirement 10: Reminder Approval and Automatic Sending

**User Story:** As a finance manager, I want to review proposed reminders before they are sent or let the Platform send them automatically with safety checks, so that reminders go to the right customers at the right time.

#### Acceptance Criteria

1. WHEN the Reminder_Scheduler identifies eligible Invoices in approval-required mode, THE API SHALL create proposed Reminder_Jobs for Authorized_User review.
2. WHEN an Authorized_User reviews a proposed Reminder_Job, THE API SHALL display the Customer, Invoice, amount, due date, channel, and message content.
3. WHEN an Authorized_User approves a proposed Reminder_Job, THE API SHALL dispatch the reminder through the configured Messaging_Service and record the result with the provider reference in the Message_Log.
4. WHEN the Reminder_Scheduler identifies eligible Invoices in automatic mode, THE API SHALL create a Reminder_Job with an idempotency key.
5. WHEN the Background_Worker dispatches an automatic Reminder_Job, THE Background_Worker SHALL perform a final eligibility check immediately before sending.
6. WHEN the final eligibility check before dispatch finds that the Invoice is paid, void, or has a zero outstanding balance, THE Background_Worker SHALL block the reminder and record the reason.
7. WHEN the final eligibility check before dispatch finds that the Customer contact is invalid, THE Background_Worker SHALL block the reminder and record the reason.
8. WHEN the final eligibility check before dispatch finds that the Reminder_Policy is disabled, THE Background_Worker SHALL block the reminder and record the reason.
9. WHEN a Reminder_Job for the same scheduled occurrence has already been sent, THE Background_Worker SHALL block the duplicate reminder.
10. WHEN the message amount in a Reminder_Job does not reflect the latest outstanding balance, THE Background_Worker SHALL block the reminder and record the reason.
11. WHEN an Authorized_User rejects a proposed Reminder_Job, THE API SHALL mark the Reminder_Job as rejected and record the rejection in the Audit_Log.
12. WHEN the Reminder_Scheduler schedules the next eligible reminder, THE API SHALL compute the next eligible reminder time respecting the maximum frequency limit.

### Requirement 11: Messaging Channels and Delivery Logs

**User Story:** As a finance manager, I want reminders delivered through email and approved messaging providers with delivery tracking, so that I know whether each reminder reached the customer.

#### Acceptance Criteria

1. THE Messaging_Service SHALL abstract all outbound message delivery behind a provider interface so that Email and additional approved business messaging providers can be added without changing the calling code.
2. IF a second messaging channel is selected and all required provider credentials are present and valid, THEN THE Messaging_Service SHALL enable that channel for outbound delivery.
3. WHEN the Messaging_Service submits a message to a provider, THE Messaging_Service SHALL create a Message_Log entry immediately with status `queued` and record the provider-assigned message identifier once the provider accepts the message.
4. THE Message_Log SHALL track the delivery lifecycle of each message through exactly the following states: `queued`, `sent`, `delivered`, `failed`, `cancelled`, and `unknown`.
5. WHEN a provider returns a retriable error response for a submitted message, THE Background_Worker SHALL retry delivery using exponential backoff starting at 30 seconds, doubling on each attempt, with a maximum delay of 1800 seconds and a maximum of 5 total attempts.
6. WHEN all retry attempts for a message are exhausted without a successful provider acceptance, THE Background_Worker SHALL set the Message_Log status to `failed` and SHALL create a Notification for the Authorized_User responsible for the Reminder_Job.
7. WHEN a provider returns a non-retriable error response for a submitted message, THE Background_Worker SHALL set the Message_Log status to `failed` immediately and SHALL not schedule further retry attempts.
8. WHEN a provider webhook delivers a delivery status update, THE API SHALL verify the webhook signature using the provider-supplied signing secret before processing and SHALL reject any webhook event whose timestamp is more than 300 seconds older than the current server time.
9. WHEN a provider webhook delivers a delivery status update that passes signature verification, THE API SHALL update the corresponding Message_Log entry to the provider-reported state.
10. WHEN a provider acknowledges only that a message was accepted for delivery, THE Messaging_Service SHALL record the Message_Log status as `sent` and SHALL not advance the status to `delivered`.
11. WHEN a Reminder_Job is dispatched, THE Message_Log SHALL record the Organization identifier, Invoice identifier, Customer identifier, channel, Reminder_Template identifier, initial status, dispatch timestamp, and provider error description if the provider returns an error.
12. WHEN an Authorized_User approves a reminder message before dispatch, THE Message_Log SHALL record the approver identity and the approval timestamp.
13. WHEN an Authorized_User edits a reminder message before dispatch, THE Message_Log SHALL record the editor identity, the edit timestamp, and the fields that were changed.
14. IF the Messaging_Service cannot retrieve the provider credentials required to submit a message, THEN THE Messaging_Service SHALL abort the send attempt, set the Message_Log status to `failed`, and record the credential access failure reason in the Message_Log.
15. THE API SHALL store provider credentials exclusively in a secret store or environment configuration and SHALL never persist credentials in source control or in the application database.

### Requirement 12: Reminder Templates

**User Story:** As a finance manager, I want to create and manage message templates with placeholders, so that reminders are consistent and personalized.

#### Acceptance Criteria

1. WHEN an Authorized_User creates a Reminder_Template, THE API SHALL support placeholders for Customer name, Invoice number, Invoice date, due date, outstanding amount, payment reference instructions, and business contact information.
2. WHEN a Reminder_Template is saved, THE Validator SHALL validate each placeholder token in the template body and subject against the supported placeholder set.
3. IF a Reminder_Template contains one or more unsupported placeholder tokens, THEN THE Validator SHALL reject the save and return an error identifying each unsupported placeholder token by name.
4. WHEN a Reminder_Template is saved, THE Validator SHALL enforce that the template body and subject length comply with the length and format constraints of the configured channel.
5. IF a Reminder_Template body or subject exceeds the channel length or format constraint at save time, THEN THE Validator SHALL reject the save and return an error indicating the violated constraint and the configured limit.
6. WHEN user-provided values are substituted into a Reminder_Template at render time, THE API SHALL apply channel-appropriate escaping to each substituted value to prevent content injection for the target delivery channel.
7. WHEN a Reminder_Template is rendered for dispatch and a supported placeholder token cannot be resolved to a value because the required data is absent, THE Background_Worker SHALL block the message from being sent and record the unresolvable placeholder token name in the Message_Log.
8. WHEN an Authorized_User previews a Reminder_Template, THE Frontend SHALL render the template using representative static fixture data for all placeholder tokens and SHALL not use live Customer or Invoice records.
9. WHEN an Authorized_User saves a change to a Reminder_Template that is referenced by at least one active Reminder_Policy, and the change modifies the template body, the template subject, or the set of placeholder tokens used, THE API SHALL create a pending revision and require an Authorized_User with the role of Business owner or Finance manager to approve the revision before the change takes effect.
10. WHEN an Authorized_User modifies a Reminder_Template, THE API SHALL record a version entry capturing the previous body, previous subject, the identity of the User who made the change, and the timestamp of the change.
11. THE API SHALL retain Reminder_Template version entries for a minimum of 90 days.

### Requirement 13: Bank Statement Import

**User Story:** As an accountant, I want to import bank statement files, so that I can match imported transactions against outstanding invoices.

#### Acceptance Criteria

1. WHEN an Authorized_User uploads a bank statement file, THE Validator SHALL accept only files in CSV or XLSX format not exceeding 10 MB and SHALL reject any file that does not conform to either accepted format with an error indicating the reason for rejection.
2. WHEN an uploaded file passes format validation, THE API SHALL create an Import_Batch record with a unique batch identifier and an initial processing status of pending.
3. WHEN the API parses an uploaded bank statement file, THE API SHALL present a preview of the mapped rows to the Authorized_User before writing any Bank_Transaction record to the staging table.
4. WHEN an Authorized_User reviews the column mapping, THE API SHALL require the Authorized_User to confirm or correct the mapping of the mandatory columns transaction date, description, debit amount, credit amount, and account identifier before processing any row.
5. WHEN an Authorized_User confirms the column mapping and preview, THE API SHALL normalize each row by converting debit and credit amounts to integer Minor_Units, converting transaction date and value date to ISO 8601 UTC, and storing transaction reference, account identifier, description, and currency as parsed from the source file.
6. WHEN the API detects a probable duplicate Bank_Transaction within the same Organization, defined as a row with matching account identifier, transaction date, amount in Minor_Units, and transaction reference, THE API SHALL flag the row as a probable duplicate and require explicit Authorized_User confirmation before storing that row.
7. WHEN a Bank_Transaction row is stored after Authorized_User confirmation, THE API SHALL place the transaction in a staging table separate from confirmed Payment records and SHALL keep it in the staging table until a Reconciliation_Match for that transaction is confirmed by an Authorized_User.
8. WHEN an import file is processed, THE API SHALL record the file-processing status and row-level errors with specific field-level detail in the Import_Batch record.
9. THE API SHALL store each uploaded bank statement file in File_Storage and SHALL restrict access to Authorized_Users of the owning Organization only.
10. THE API SHALL never request or store bank login credentials, multi-factor authentication codes, one-time passwords, or security answers.

### Requirement 14: Payment Reconciliation

**User Story:** As an accountant, I want the Platform to suggest matches between bank transactions and invoices or payments, so that I can confirm accurate reconciliations.

#### Acceptance Criteria

1. WHEN the Reconciliation_Service matches Bank_Transactions, THE Reconciliation_Service SHALL run deterministic matching rules first using exact payment reference, transaction reference, Customer identity, Invoice number in narration, exact or near-exact amount, and transaction date.
2. WHEN deterministic matching produces no exact match, THE Reconciliation_Service SHALL generate fuzzy match suggestions only and SHALL display an uncertainty indicator with matching evidence.
3. WHEN the Reconciliation_Service presents a Reconciliation_Match, THE API SHALL display the match evidence and confidence indicator.
4. WHEN an Authorized_User confirms a Reconciliation_Match, THE API SHALL create a confirmed Payment_Allocation through an audited process.
5. WHEN a Reconciliation_Match is uncertain, THE API SHALL not create a confirmed Payment_Allocation without explicit Authorized_User confirmation.
6. WHEN a Bank_Transaction settles multiple Invoices, THE Reconciliation_Service SHALL support one Bank_Transaction linked to multiple Invoices.
7. WHEN a Bank_Transaction is partially settled, THE Reconciliation_Service SHALL support partial settlement amounts.
8. WHEN a Bank_Transaction has already been allocated up to its available amount, THE API SHALL prevent further allocation beyond the available amount.
9. WHEN an Authorized_User confirms or rejects a Reconciliation_Match, THE API SHALL record the reviewer identity and timestamp in the Audit_Log.
10. WHEN a Reconciliation_Match is confirmed or rejected, THE API SHALL preserve the original imported Bank_Transaction and the full reconciliation history.

### Requirement 15: Cash Inflow Forecasting

**User Story:** As a business owner, I want to forecast expected cash inflows, so that I can plan for upcoming receivables.

#### Acceptance Criteria

1. WHEN an Authorized_User requests a Cash_Forecast, THE Forecast_Service SHALL calculate expected receivable inflows for the forecast period selected by the Authorized_User from 7 days, 30 days, or 60 days.
2. WHILE an Invoice has the status Void, Draft, or Paid, THE Forecast_Service SHALL exclude the Invoice from the forecast.
3. WHEN the Forecast_Service assigns an Invoice balance to a forecast period, THE Forecast_Service SHALL use the Invoice due date adjusted by the payment timing assumption selected from the following options: due-date (no adjustment), historical-delay (adjustment derived from confirmed payment records), or custom-day-offset (a positive or negative integer offset in days supplied by the Authorized_User).
4. WHEN the Forecast_Service applies historical-delay as the payment timing assumption, THE Forecast_Service SHALL base the adjustment only on confirmed paid Invoices for the same Organization that have a recorded payment date, and SHALL require at least 10 such Invoices within the preceding 12 months before applying the adjustment.
5. WHEN the Forecast_Service generates a Cash_Forecast, THE Forecast_Service SHALL calculate three scenarios: conservative (75th-percentile historical payment delay or +14 days if insufficient history), base (mean historical payment delay or 0-day offset if insufficient history), and optimistic (25th-percentile historical payment delay or −7 days if insufficient history), each with explicitly documented assumptions.
6. WHEN an Invoice is created, updated to a status of Void, Paid, or Issued, or when a Payment_Allocation affecting an Invoice is created, modified, or reversed, THE Forecast_Service SHALL recalculate the affected Cash_Forecast.
7. WHEN the Forecast_Service generates a Cash_Forecast, THE Forecast_Service SHALL store the generation timestamp, the identifiers and count of qualifying Invoices used as input, and the assumptions applied to each scenario.
8. WHEN fewer than 10 confirmed paid Invoices with recorded payment dates exist within the preceding 12 months for the active Organization, THE Forecast_Service SHALL mark the Cash_Forecast as having insufficient historical data and SHALL indicate which scenario assumptions fell back to rule-based values.
9. WHEN the Forecast_Service assigns an expected payment date to an Invoice, THE Forecast_Service SHALL base the date on the due date and the selected timing assumption and SHALL not invent a precise date outside of a defined rule.
10. IF the Forecast_Service cannot determine an expected payment date for an Invoice using any defined rule, THEN THE Forecast_Service SHALL exclude the Invoice from the forecast and record the exclusion with the Invoice identifier and the reason.
11. THE Frontend SHALL display each forecast scenario amount as a projected inflow and SHALL display the forecast period and the documented assumptions for each scenario.
12. WHEN an Authorized_User inspects a Cash_Forecast, THE API SHALL return the Invoice number, Customer name, outstanding balance in Minor_Units, due date, and assigned forecast date for each contributing Invoice.
13. THE Frontend SHALL display a notice that the forecast covers expected cash inflows only and excludes bank balances, expenses, payroll, taxes, and other outflows.

### Requirement 16: AI Finance Assistant

**User Story:** As a business owner, I want to ask financial questions in natural language, so that I can understand my receivables position without building reports manually.

#### Acceptance Criteria

1. WHEN an Authorized_User submits a question to the AI_Assistant, THE AI_Assistant SHALL retrieve data exclusively through authenticated server-controlled tools that enforce Organization and role permissions before returning data to the language model.
2. IF a server-controlled tool call fails an Organization or role permission check, THEN THE AI_Assistant SHALL return a response indicating that the requested data is not accessible and SHALL not fabricate or substitute data.
3. WHEN the AI_Assistant derives monetary amounts, outstanding balances, totals, or record counts, THE AI_Assistant SHALL take those values directly from the results returned by API tool calls and SHALL not compute those values using language model inference.
4. WHEN the AI_Assistant returns an answer, THE AI_Assistant SHALL include the dates, amounts, periods, and Invoice references on which the answer is based and SHALL state when the basis of the answer cannot be determined from available data.
5. WHEN data is incomplete or insufficient to answer a question, THE AI_Assistant SHALL state that the data is incomplete or insufficient.
6. WHEN the AI_Assistant presents an estimate, THE AI_Assistant SHALL distinguish the estimate from confirmed facts.
7. THE AI_Assistant SHALL be read-only in the initial release and SHALL not execute payments, change ledger records, approve reminders, or modify permissions.
8. WHEN the AI_Assistant processes imported Invoice text, Customer notes, or transaction descriptions, THE AI_Assistant SHALL treat the content as untrusted input and SHALL not render, follow, or propagate any instruction embedded within that content.
9. THE AI_Assistant SHALL not expose system prompts, internal tool definitions, secrets, or records belonging to other Organizations in any response.
10. WHEN the AI_Assistant processes a request, THE API SHALL log the Organization identifier, User identifier, session identifier, timestamp, tool calls invoked, and response status, and SHALL not include question text or answer content in the minimum log record.
11. IF a server-controlled tool call returns records belonging to an Organization other than the requesting User's Organization, THEN THE AI_Assistant SHALL discard those records and SHALL not include them in the response.
12. WHEN the AI model or a required data tool is unavailable, THE AI_Assistant SHALL return a response indicating that the service is unavailable and SHALL not fabricate an answer.

### Requirement 17: AI-Assisted Document Extraction

**User Story:** As a finance team member, I want to upload invoice documents and have fields extracted for review, so that I can reduce manual data entry.

#### Acceptance Criteria

1. WHERE AI-assisted document extraction is enabled and core Invoice and Payment workflows are not delayed by its inclusion, THE Extraction_Service SHALL accept uploaded Invoice documents in PDF, PNG, or JPEG format with a maximum file size of 10 MB per document and SHALL extract candidate Customer name, Invoice number, Invoice date, due date, subtotal, tax amount, total amount, and line items from each document.
2. WHEN the Extraction_Service produces an extraction result, THE Extraction_Service SHALL validate each extracted field against the Invoice schema, checking that dates are valid calendar dates, that all monetary amounts are positive numeric values expressible as integer Minor_Units, and that required fields are present.
3. WHEN the Extraction_Service assigns a confidence indicator below the service-defined acceptance threshold to an extracted field, or when a required field is absent, or when two extracted fields carry contradictory values for the same attribute, THE Extraction_Service SHALL mark each affected field with a flag indicating the reason (low confidence, missing, or conflicting) and SHALL not pre-populate that field in the review form without explicit Authorized_User correction.
4. WHEN the Extraction_Service completes processing an uploaded document, THE Frontend SHALL display all extracted fields alongside the source document reference in an editable review form, visually distinguishing flagged fields from accepted fields, before any financial record is created or updated.
5. WHEN an Authorized_User submits the extraction review form, THE API SHALL require an explicit confirmation action from the Authorized_User and SHALL not create or update any Invoice record until that confirmation is received.
6. WHEN an extraction result is stored, THE API SHALL link the source document to the extraction result in File_Storage under the same access controls that apply to Invoice documents, and SHALL not expose the source document to Users outside the active Organization.
7. THE API SHALL never derive an authoritative Invoice amount from an AI-extracted value alone and SHALL treat every AI-extracted monetary amount as a candidate value that requires Authorized_User confirmation before the value is persisted to the financial ledger.
8. IF the Extraction_Service fails to process an uploaded document or returns no extractable fields, THEN THE API SHALL return an error response indicating that extraction was unsuccessful and SHALL preserve the uploaded document in File_Storage without creating any partial Invoice record.

### Requirement 18: Notifications

**User Story:** As a user, I want to be notified about important operational events, so that I can take timely action on reminders, imports, and account changes.

#### Acceptance Criteria

1. WHEN a Reminder_Job awaits approval, THE API SHALL create a Notification for each active Membership holder with a Business owner or Finance manager role in the Organization.
2. WHEN a reminder delivery fails, THE API SHALL create a Notification for the User who initiated the associated Reminder_Job or Reminder_Policy.
3. WHEN an Import_Batch completes or fails, THE API SHALL create a Notification for the User who submitted the import file.
4. WHEN a Reconciliation_Match requires review, THE API SHALL create a Notification for each active Membership holder with a Business owner, Finance manager, or Accountant role in the Organization.
5. WHEN a Cash_Forecast generation fails, THE API SHALL create a Notification for the User who requested the Cash_Forecast.
6. WHEN a Subscription or Organization account status changes, THE API SHALL create a Notification for each active Membership holder with a Business owner role in the Organization.
7. WHEN a security event is one of the following — sign-in from a previously unseen device or location, five or more consecutive failed sign-in attempts, password reset completion, Membership role change, or Membership deactivation — THE API SHALL create a Notification for the User whose account or Membership was affected.
8. WHEN the API evaluates whether to create a Notification, THE API SHALL treat a Notification as a duplicate if a Notification with the same event type, entity identifier, and Organization identifier already exists in an unresolved state, and THE API SHALL not create the duplicate Notification.
9. WHEN an Authorized_User enables or disables a specific notification type in the notification preferences, THE API SHALL persist the preference scoped to that User and Organization combination.
10. IF a User has disabled a notification type in the notification preferences, THEN THE API SHALL skip creating a Notification of that type for that User.
11. WHEN the API creates a Notification, THE Platform SHALL deliver the Notification to the in-app Notification center for the recipient User.
12. THE API SHALL store each Notification with a read status initialized to unread at creation time.
13. WHEN a User marks a Notification as read, THE API SHALL update the read status of that Notification to read for that User.
14. WHEN the API generates the subject line or push preview text for an email or push Notification, THE API SHALL restrict the content to the event type, entity type, and date, and SHALL exclude invoice amounts, outstanding balances, customer names, and payment references from the subject line and push preview text.

### Requirement 19: Audit Logs

**User Story:** As a compliance officer, I want a searchable audit trail of security-sensitive and financially consequential actions, so that accountability is maintained.

#### Acceptance Criteria

1. WHEN a login or security event occurs, THE API SHALL record the event in the Audit_Log.
2. WHEN an Organization Membership change occurs, THE API SHALL record the change in the Audit_Log.
3. WHEN an Invoice is created or edited, THE API SHALL record the action in the Audit_Log.
4. WHEN a Payment or Payment_Allocation is created, corrected, or reversed, THE API SHALL record the action in the Audit_Log.
5. WHEN a Reminder_Policy is changed, THE API SHALL record the change in the Audit_Log.
6. WHEN a Reminder_Job is approved, rejected, or sent, THE API SHALL record the action in the Audit_Log.
7. WHEN a Reconciliation_Match is confirmed or rejected, THE API SHALL record the action in the Audit_Log.
8. WHEN a permission change occurs, THE API SHALL record the change in the Audit_Log.
9. WHEN a data export is generated, THE API SHALL record the export in the Audit_Log.
10. WHEN a Subscription change occurs, THE API SHALL record the change in the Audit_Log.
11. WHEN a Platform administrator support access event occurs, THE API SHALL record the event in the Audit_Log including the administrator identity, the Organization accessed, the access scope, and the start and end timestamps.
12. WHEN the API creates an Audit_Log entry, THE API SHALL include the event identifier, Organization identifier, actor identifier, action, entity type, entity identifier, timestamp, change summary, and request identifier, and SHALL include a reason when the actor provides one.
13. IF any User or system process attempts to update or delete an existing Audit_Log entry, THEN THE API SHALL reject the modification.
14. THE API SHALL never log credentials, passwords, authentication tokens, card numbers, or bank account numbers in the Audit_Log.
15. WHEN an Authorized_User requests audit records, THE API SHALL enforce permission-controlled access to the Audit_Log and SHALL return only records scoped to the active Organization.
16. WHEN the API generates an Audit_Log entry for a financially consequential operation, THE API SHALL create the entry within the same database transaction as the business operation so that the Audit_Log entry and the business record are committed atomically.

### Requirement 20: Subscription and Plan Controls

**User Story:** As a platform administrator, I want to manage subscription tiers and enforce usage limits, so that organizations use features within their plan entitlements.

#### Acceptance Criteria

1. THE Admin_Service SHALL store plan definitions and entitlements for the plans Starter, Growth, Business, and Enterprise in a central configuration table that is readable at runtime without a code deployment.
2. WHEN an Organization subscribes to a plan, THE API SHALL create a Subscription record with a status of one of the following: trial, active, past-due, cancelled, or expired.
3. WHEN an Organization holds an active Subscription, THE API SHALL enforce the configured limits for User count, Invoice count, outbound message volume per calendar month, and AI_Assistant requests per calendar month.
4. WHEN an Organization reaches a configured limit, THE API SHALL block the operation that would exceed the limit and return an error indicating the limit type and the current plan.
5. WHEN an Authorized_User views the subscription screen, THE Frontend SHALL display the current Subscription status, the plan name, the current usage for each configured limit, and the billing event history.
6. THE Admin_Service SHALL read all plan limits from the central configuration table and SHALL not hardcode any commercial limit in application code.
7. WHEN online billing is enabled and the billing provider delivers a webhook event, THE API SHALL verify the webhook signature and process the event idempotently, such that processing the same event identifier a second time does not change the Subscription state.
8. THE API SHALL keep the payment-gateway integration behind an abstraction layer so that changing the billing provider does not require changes outside the billing integration module.

### Requirement 21: Platform Administration

**User Story:** As a platform administrator, I want to manage organizations, users, and system health, so that I can operate the Platform reliably.

#### Acceptance Criteria

1. WHEN a Platform administrator views the admin console, THE Admin_Service SHALL display Organization and User account status for all Organizations on the Platform.
2. WHEN a Platform administrator modifies plan definitions or limits, THE Admin_Service SHALL persist the changes and record the modification in the Audit_Log with the administrator identity and a summary of each changed value.
3. WHEN a Platform administrator suspends an Organization or User account, THE API SHALL set the account status to suspended and record the action in the Audit_Log with the administrator identity and reason.
4. WHEN a Platform administrator reactivates a suspended Organization or User account, THE API SHALL set the account status to active and record the action in the Audit_Log with the administrator identity.
5. WHEN a Platform administrator inspects job failures, THE Admin_Service SHALL display the Background_Worker job identifier, status, failure reason, retry count, and last failure timestamp.
6. WHEN a Platform administrator requires support access to an Organization's data, THE API SHALL require explicit authorization, restrict the access scope to read-only, limit the access duration to a maximum of 24 hours, and record the access event in the Audit_Log with the administrator identity, the Organization identifier, the authorized scope, and the start and end timestamps.
7. THE Admin_Service SHALL not grant a Platform administrator access to an Organization's financial data by default; access requires the explicit authorization process described in criterion 6.

### Requirement 22: Data Export and Archival

**User Story:** As a finance manager, I want to export financial data and reports, so that I can share them externally and maintain records.

#### Acceptance Criteria

1. WHEN an Authorized_User requests a data export, THE Export_Service SHALL generate the export for the selected data type from the following set: Invoices, Payments, Customers, receivables reports, reminder logs, or reconciliation results.
2. WHEN the Export_Service generates an export, THE API SHALL apply the same Organization scoping and permission checks to the export as to the corresponding data view.
3. WHEN an export request will produce more than 1000 rows, THE Export_Service SHALL process the export asynchronously through a Background_Worker and notify the requesting User when the export is ready.
4. WHEN an export is ready, THE API SHALL provide a download link that is valid for no more than 60 minutes and requires authentication to access.
5. WHEN any export is generated, THE API SHALL record the export in the Audit_Log with the Authorized_User identity, the data type exported, the row count, the Organization identifier, and the timestamp.
6. WHEN an Organization account is closed, THE API SHALL never delete Payment or Payment_Allocation records for that Organization, and SHALL retain all financial records for the retention period defined in the Organization data retention policy.

### Requirement 23: Multi-Tenant Isolation

**User Story:** As a security engineer, I want every tenant-owned record scoped to its Organization, so that cross-organization data access is impossible.

#### Acceptance Criteria

1. WHEN the API processes any tenant-owned resource, THE API SHALL derive the active Organization from the authenticated User's active Membership in the server session and SHALL not rely on an Organization identifier supplied by the client as the sole source of authorization.
2. WHEN the API receives a request with a client-supplied Organization identifier that differs from the Organization derived from the authenticated User's active Membership, THE API SHALL reject the request.
3. WHEN a Background_Worker job is enqueued, THE Background_Worker SHALL persist the Organization identifier in the job metadata at enqueue time and SHALL validate the Organization identifier against the Organization table before beginning processing.
4. WHEN a request targets a resource whose Organization identifier does not match the Organization derived from the authenticated User's active Membership, THE API SHALL return an authorization failure response.
5. WHEN the API creates a foreign key reference between tenant-owned entities, THE API SHALL enforce the reference at the database schema level where the data model supports it to prevent cross-Organization references.

### Requirement 24: Financial Accuracy and Determinism

**User Story:** As a financial auditor, I want all money calculations to be deterministic and verifiable, so that reports and balances always reconcile.

#### Acceptance Criteria

1. THE API SHALL store all authoritative monetary amounts as integer Minor_Units and SHALL never use binary floating-point types for authoritative financial amounts.
2. WHEN the API performs any Invoice total calculation, Payment_Allocation, outstanding balance update, or other balance-affecting operation, THE API SHALL execute the entire operation within a single database transaction that commits all changes or rolls back all changes atomically.
3. THE API SHALL apply a single documented rounding policy consistently across all reports, dashboards, exports, and AI_Assistant queries, and SHALL store the policy in a documented location accessible to the development team.
4. WHEN the API corrects a consequential financial record, THE API SHALL create a correction or reversal record preserving the original values and SHALL not overwrite the original financial history.
5. WHEN the API receives a duplicate webhook event or a retried background task, THE API SHALL use an idempotency key to detect the duplicate and SHALL not apply the financial effect a second time.
6. WHEN an Invoice has an outstanding balance of zero, THE API SHALL not include the Invoice in outstanding receivables totals.
7. WHEN the API sends a reminder for an Invoice, THE API SHALL not change the Invoice status to Paid, since sending a reminder does not constitute a Payment record.
8. WHEN all reports calculate financial totals, THE reports SHALL derive those totals using the same trusted financial calculation functions and the same rounding policy.
9. WHEN the AI_Assistant returns financial values, THE AI_Assistant SHALL present only values obtained from authoritative API tool call results and SHALL not override or adjust those values using language model reasoning.

### Requirement 25: Security and Input Validation

**User Story:** As a security engineer, I want all inputs validated and authorized server-side, so that the Platform resists common attacks.

#### Acceptance Criteria

1. WHILE the Platform runs in production, THE Platform SHALL reject HTTP requests and redirect clients to the equivalent HTTPS URL.
2. WHEN a User submits a password, THE Auth_Service SHALL store the password using an adaptive password hashing algorithm from the bcrypt, Argon2, or scrypt family.
3. WHEN the API receives any input, THE Validator SHALL validate the input for format, type, length, and allowed values server-side before processing.
4. WHEN the API processes any request, THE API SHALL authorize the request against the authenticated User's active Membership role before executing the requested operation.
5. WHEN an upload is received, THE API SHALL verify that the file type is in the configured allow-list, that the file size does not exceed 10 MB, and SHALL scan the file content using an anti-malware or file-type verification mechanism before storing it.
6. WHEN the API stores uploaded files, THE API SHALL store them in private File_Storage and SHALL generate download links that expire after no more than 15 minutes.
7. WHEN the Platform runs in any environment, THE Platform SHALL not write credentials, authentication tokens, session identifiers, personally identifiable information, or financial record values to development or application logs.
8. WHEN a release is being prepared, THE Platform SHALL run dependency and vulnerability checks and SHALL block the release if any dependency has an unresolved critical or high severity vulnerability.
9. WHEN the API handles cross-site requests, THE API SHALL enforce CSRF protection for all state-changing operations.

### Requirement 26: Performance

**User Story:** As a user, I want the Platform to respond quickly, so that I can work efficiently.

#### Acceptance Criteria

1. WHEN an Authorized_User performs a common API read, THE API SHALL respond within 500 milliseconds at the 95th percentile under agreed pilot load, excluding external provider latency.
2. WHEN an Authorized_User opens the receivables dashboard, THE API SHALL respond within 2000 milliseconds at the 95th percentile for the agreed pilot dataset.
3. WHEN an Authorized_User performs a routine record write, THE API SHALL respond within 1000 milliseconds at the 95th percentile, excluding external provider processing time.
4. WHEN an import or bulk operation is requested, THE Background_Worker SHALL process the operation asynchronously and SHALL expose a status endpoint that returns the current processing progress as a percentage or row count.
5. WHEN the API returns a list endpoint response, THE API SHALL paginate the results with a configurable page size and return the total record count, the current page number, and a link to the next page when one exists.
6. WHEN an import or export generates results exceeding 10000 rows, THE API SHALL not process the operation in a single synchronous request but SHALL delegate processing to a Background_Worker.

### Requirement 27: Background Worker Reliability

**User Story:** As a platform operator, I want background jobs to have traceable status and failure reasons, so that I can monitor and troubleshoot automation.

#### Acceptance Criteria

1. WHEN a Background_Worker processes a job, THE Background_Worker SHALL update the job record with the current status from the following set: pending, in_progress, completed, failed, or cancelled, and SHALL record a failure reason when the status is set to failed.
2. WHEN a Background_Worker job fails, THE Background_Worker SHALL record the failure reason, the exception type, and the retry count in the job record.
3. WHEN an external provider call fails during Background_Worker processing, THE Background_Worker SHALL not modify any financial record and SHALL preserve the job state so the operation can be retried safely or resolved through manual intervention.
4. WHEN the Background_Worker processes a reminder dispatch, messaging delivery, Cash_Forecast calculation, file import, or data export, THE Background_Worker SHALL execute the processing asynchronously and SHALL not block the API response.
5. WHEN a Background_Worker job is retried, THE Background_Worker SHALL verify the idempotency key before applying any state change to ensure that the financial effect of the job is not applied more than once.

### Requirement 28: API Design and Documentation

**User Story:** As a developer, I want a versioned, documented REST API, so that I can integrate with the Platform reliably.

#### Acceptance Criteria

1. THE API SHALL expose all endpoints under the versioned base path `/api/v1/`.
2. WHEN the API returns an error, THE API SHALL return an appropriate HTTP status code and a structured error response body containing an error code, a human-readable message, and field-level details for validation errors.
3. THE API SHALL validate all input server-side and SHALL never include internal stack traces, secrets, or sensitive data in API responses.
4. THE API SHALL generate OpenAPI documentation for all endpoints, keeping the documentation synchronized with each API change.
5. WHEN a User requests a list endpoint, THE API SHALL support pagination using page number and page size parameters, and SHALL support filtering and sorting only through a defined set of validated fields.
6. WHEN the API performs a financial write operation or a provider-triggering operation, THE API SHALL accept and enforce an idempotency key so that retrying the same request with the same key does not duplicate the financial or provider effect.
