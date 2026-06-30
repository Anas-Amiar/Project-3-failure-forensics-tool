"""
Sample documents to run through the pipeline. Several are deliberately
written to break a specific step -- without real failures, there's nothing
for the forensics tool to actually find.
"""

SAMPLE_DOCUMENTS = [
    {
        "doc_id": "doc_001",
        "label": "clean_contract",
        "text": """The parties to this agreement are John Smith and Sarah Lee, entered
        into on January 15, 2024. The parties hereby agree to the terms and conditions
        outlined below regarding the provision of consulting services.""",
    },
    {
        "doc_id": "doc_002",
        "label": "clean_invoice",
        "text": """Invoice #4471. Bill to: Acme Corp. Amount due: $4,250.00.
        Payment is due within 30 days of receipt.""",
    },
    {
        "doc_id": "doc_003",
        "label": "clean_report",
        "text": """Quarterly Report: Summary of results. Our analysis shows a 12%
        increase in customer retention. Key findings indicate that onboarding
        improvements were the primary driver.""",
    },
    {
        "doc_id": "doc_004",
        "label": "clean_correspondence",
        "text": """Dear team, following up on our meeting yesterday. Best regards,
        Maria Garcia.""",
    },
    {
        "doc_id": "doc_005",
        "label": "broken_contract_no_dates",
        "text": """The parties to this agreement are Robert Chen and the Acme
        Corporation. The parties hereby agree to the terms and conditions
        outlined below.""",
        # FAILURE MODE: no date anywhere in the text -> extraction confidence drops,
        # summary falls back to "an unspecified date"
    },
    {
        "doc_id": "doc_006",
        "label": "broken_invoice_mixed_currency",
        "text": """Invoice #9981. Bill to: Global Imports Ltd. Amount due: $1,200.00,
        converted from an original charge of €1,050.00. Payment terms: net 30.""",
        # FAILURE MODE: two different currency symbols -> extraction confidence drops,
        # the picked "amounts[0]" may be the wrong figure
    },
    {
        "doc_id": "doc_007",
        "label": "broken_ambiguous_category",
        "text": """Dear Mr. Anderson, please find attached the invoice for services
        rendered. Amount due: $800.00. Best regards, the billing team.""",
        # FAILURE MODE: contains both correspondence keywords (Dear, regards) and
        # invoice keywords (invoice, amount due, bill) -> low-confidence classification
    },
    {
        "doc_id": "doc_008",
        "label": "broken_empty_content",
        "text": """ok.""",
        # FAILURE MODE: near-empty document -> nothing extractable, everything falls
        # back to "unknown"/"unspecified"
    },
]
