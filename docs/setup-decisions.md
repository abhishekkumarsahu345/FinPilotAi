# Product decisions still needed

The project can continue without these decisions for the local core. They are required before enabling the related production features.

| Area | Initial assumption | Needed before release |
|---|---|---|
| Invoice tax | User-entered subtotal, discount, and tax total | Supported line-item GST rates, tax components, rounding and invoice issuance rules |
| Invoice source | Track invoices created in this app | Whether the app issues legal invoices or tracks externally issued invoices |
| Invoice import | Deferred | Sample CSV/XLSX files and column mapping expectations |
| Bank import | Deferred | Bank/export format samples and file limits |
| Reminders | Approval-first; provider disabled | Email provider and sender domain; approved business messaging account only if needed |
| Forecast | Deferred | Payment history availability and agreed assumptions |
| AI | Deferred, read-only | Approved provider, data processing terms, budget, and allowed query scope |
| Hosting | Local PostgreSQL configuration | Cloud, deployment region, budget, backup and retention requirements |
| Subscription | Plan model not activated | Initial plans, limits, and billing provider |
| Privacy | Organization-scoped data | Retention, deletion, export, and support-access policy |

Provider credentials must be supplied as deployment secrets/environment variables when a provider is selected. Do not paste production secrets into source files or commit `.env`.
