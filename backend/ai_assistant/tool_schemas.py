"""
OpenAI function calling schemas for AI assistant tools.
Each schema describes a tool's parameters and usage for the LLM.
"""

TOOL_SCHEMAS = [
    # =============================================================================
    # PRIMARY TOOL: query_data (use this for most questions)
    # =============================================================================
    {
        "type": "function",
        "function": {
            "name": "query_data",
            "description": """General-purpose query tool for flexible data retrieval. This is the PRIMARY tool for:
- Counts: "how many X", "number of X", "count X"
- Lists: "show all X", "list X", "give me X"
- Filters: "X where Y", "X with Y", "X that Y"
- Aggregations: "total X", "average X", "sum of X", "max/min X"
- Grouping: "X by customer", "X per month", "X grouped by Y"
- Top N: "top 10 X", "highest X", "largest X"

Entities: customers (persons/people/clients/parties), invoices (bills), payments, payment_allocations

Examples:
- Count customers: entity="customers", aggregates={"count":{"count":"*"}}
- List active customers: entity="customers", fields=["name","email"], filters={"active":{"eq":true}}
- Overdue invoices: entity="invoices", filters={"status":{"eq":"issued"},"due_date":{"lt":"today"}}
- Top customers: entity="invoices", group_by="customer__name", aggregates={"total":{"sum":"total_minor"}}, order_by=["-total"], limit=10
- Payments last month: entity="payments", filters={"payment_date":{"gte":"today-30","lte":"today"}}

Use this INSTEAD of search_customers for counts and lists.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "entity": {
                        "type": "string",
                        "enum": ["customers", "invoices", "payments", "payment_allocations"],
                        "description": "Entity to query. customers=persons/people/clients/parties, invoices=bills"
                    },
                    "fields": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Fields to return. Use get_schema_help to see available fields. Related fields use double underscore (e.g., customer__name). Omit for defaults."
                    },
                    "filters": {
                        "type": "object",
                        "description": """Filters as {field: {operator: value}}. Operators: eq, ne, gt, gte, lt, lte, contains, startswith, in, isnull. 
Examples: {"active":{"eq":true}}, {"due_date":{"lt":"today"}}, {"name":{"contains":"Acme"}}, {"status":{"in":["issued","draft"]}}. 
Special values: "today", "now", "today-7" (7 days ago), "today+30" (30 days from now).""",
                        "additionalProperties": True
                    },
                    "group_by": {
                        "type": "string",
                        "description": "Field to group by. Use with aggregates for grouped stats. Examples: customer__name, invoice_date__month, status"
                    },
                    "aggregates": {
                        "type": "object",
                        "description": """Aggregates as {result_name: {function: field}}. Functions: count, sum, avg, min, max. 
Examples: {"count":{"count":"*"}}, {"total":{"sum":"total_minor"}}, {"average":{"avg":"amount_minor"}}, {"latest":{"max":"payment_date"}}""",
                        "additionalProperties": {
                            "type": "object",
                            "properties": {
                                "count": {"type": "string"},
                                "sum": {"type": "string"},
                                "avg": {"type": "string"},
                                "min": {"type": "string"},
                                "max": {"type": "string"}
                            }
                        }
                    },
                    "order_by": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Sort fields. Prefix with - for descending. Examples: ['name'], ['-total_minor'], ['-payment_date']"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max rows to return (default 100, max 200)",
                        "default": 100
                    }
                },
                "required": ["entity"]
            }
        }
    },
    
    # =============================================================================
    # HELPER TOOL: get_schema_help
    # =============================================================================
    {
        "type": "function",
        "function": {
            "name": "get_schema_help",
            "description": "Get available entities, fields, operators, and special values for query_data. Call this if you're unsure what fields are available or how to construct a query.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    
    # =============================================================================
    # SPECIALIZED TOOLS (use when query_data is not appropriate)
    # =============================================================================
    {
        "type": "function",
        "function": {
            "name": "get_receivables_summary",
            "description": "Get high-level overview of outstanding receivables. Use when user asks about total amounts owed, overdue totals, or upcoming payments. Returns outstanding_minor, overdue_minor, due_next_7_days_minor.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_top_overdue_customers",
            "description": "Get customers with highest overdue balances. Use when user asks 'who owes the most?', 'top overdue customers', or wants to prioritize collections. Returns list sorted by overdue amount.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Maximum customers to return (default 10, max 20)",
                        "default": 10
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoices_due_range",
            "description": "Get invoices due within a date range. Use when user asks about upcoming due dates, invoices due this week/month, or payment schedule. Returns invoices with due dates in range.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_from": {
                        "type": "integer",
                        "description": "Start of range in days from today (0 = today, negative = past)",
                        "default": 0
                    },
                    "days_to": {
                        "type": "integer",
                        "description": "End of range in days from today (7 = one week)",
                        "default": 7
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_late_paying_customers",
            "description": "Get customers with history of late payments. Use when user asks about slow payers, payment reliability, or risk assessment. Returns customers who consistently pay after due date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "min_invoices": {
                        "type": "integer",
                        "description": "Minimum late invoices to qualify (default 2)",
                        "default": 2
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_forecast_summary",
            "description": "Get expected cash inflows projection. Use when user asks about future collections, cash flow forecast, or expected receipts. Returns projection based on due dates and payment history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "period_days": {
                        "type": "integer",
                        "description": "Forecast period in days (default 30)",
                        "default": 30
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_details",
            "description": "Get complete customer profile with statistics. Use when user asks 'tell me about customer X', 'show details for customer Y', or wants comprehensive customer info. Returns contact details, payment terms, and financial statistics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name (exact match, case-insensitive). Use this when user provides a customer name."
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "Customer UUID. Use this when you have a customer ID from a previous tool call."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_invoices",
            "description": "Get all invoices for a specific customer. Use when user asks 'show invoices for customer X', 'what did X buy?', or wants invoice history for a customer. Returns list of invoices with amounts and balances.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name (exact match, case-insensitive)"
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "Customer UUID (alternative to name)"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["issued", "draft", "void"],
                        "description": "Filter by invoice status"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max invoices to return (default 20, max 100)",
                        "default": 20
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_customer_payments",
            "description": "Get payment history for a specific customer. Use when user asks 'when did X pay?', 'show payments from customer Y', or wants payment timeline. Returns payments with allocation details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "Customer name (exact match, case-insensitive)"
                    },
                    "customer_id": {
                        "type": "string",
                        "description": "Customer UUID (alternative to name)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max payments to return (default 20, max 100)",
                        "default": 20
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_invoice_details",
            "description": "Get complete details for a specific invoice. Use when user asks 'show invoice INV-001', 'details of invoice X', or wants line items and payment status. Returns full invoice with items and allocations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_number": {
                        "type": "string",
                        "description": "Invoice number (e.g., 'INV-001', 'INV-2024-001')"
                    }
                },
                "required": ["invoice_number"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_details",
            "description": "Get details for a specific payment. Use when user asks 'show payment abc-123' or wants payment allocation information. Returns payment with invoice allocations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_id": {
                        "type": "string",
                        "description": "Payment UUID"
                    }
                },
                "required": ["payment_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_customers",
            "description": "Search for customers by name (partial match). Use when user asks 'find customers named X', 'search for customer Y', 'list all customers', 'show all customers', 'how many customers', or wants to discover customer names. Returns matching customers with basic info. Pass empty string as query to get all customers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term (partial name match, case-insensitive). Use empty string '' to get all customers."
                    },
                    "active_only": {
                        "type": "boolean",
                        "description": "Only return active customers (default true)",
                        "default": True
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20, max 100)",
                        "default": 20
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_activity",
            "description": "Get recent financial activity across organization. Use when user asks 'what's new?', 'recent activity', 'latest transactions', or wants overview of recent changes. Returns recent invoices and/or payments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "activity_type": {
                        "type": "string",
                        "enum": ["all", "invoices", "payments"],
                        "description": "Type of activity to return",
                        "default": "all"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max items per type (default 20, max 50)",
                        "default": 20
                    }
                },
                "required": []
            }
        }
    }
]
