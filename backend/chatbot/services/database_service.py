"""Read-only access to reference rows stored in the application database."""
import re

from django.conf import settings

from ..models import Conversation, DatabaseRecord, Document, Message

_QUESTION_WORDS = {
    "who", "what", "how", "why", "when", "where", "which", "the", "and", "for",
    "with", "from", "that", "this", "your", "about", "does", "did", "are", "was",
    "were", "have", "has", "can", "you", "please", "tell", "give", "show",
}

SAMPLE_RECORDS = [
    (
        "customers",
        "Acme Corp",
        "Customer Acme Corp, account A-1001, city Pune, plan Enterprise, "
        "contact priya.shah@acme.example, phone 020-4000-1100, "
        "outstanding balance INR 12500, status active.",
    ),
    (
        "customers",
        "Northwind Traders",
        "Customer Northwind Traders, account A-1002, city Mumbai, plan Standard, "
        "contact arun.mehta@northwind.example, phone 022-4000-2200, "
        "outstanding balance INR 4800, status active.",
    ),
    (
        "employees",
        "Rituranjan Gupta",
        "Employee id E-1042, name Rituranjan Gupta, department Engineering, "
        "title Senior Software Engineer, location Pune, email ritu@example.com, "
        "joined 2016-04-12, manager Anita Deshmukh.",
    ),
    (
        "products",
        "Home Loan",
        "Product Home Loan, sample desk State Bank, interest rate 8.35 percent per year, "
        "maximum tenure 30 years, processing fee 0.35 percent, maximum amount INR 7500000.",
    ),
    (
        "orders",
        "ORD-7781",
        "Order ORD-7781 for customer Acme Corp, item Home Loan processing, "
        "amount INR 25000, status approved, date 2026-03-14.",
    ),
    (
        "policies",
        "Office hours",
        "Office hours are 9:30 to 18:30 IST, Monday to Friday. "
        "Support email is support@example.com. Support phone is 020-4000-1000.",
    ),
    (
        "products",
        "Custom Web Application",
        "Lumina Software product Custom Web Application. One-time price INR 850000. "
        "Yearly maintenance is 15 percent, which is INR 127500. Includes design, "
        "development, and 3 months of support. This is not an AI product.",
    ),
    (
        "products",
        "Mobile App",
        "Lumina Software product Mobile App for Android and iOS. One-time price INR 1200000. "
        "Yearly maintenance price INR 180000. App store release is included.",
    ),
    (
        "products",
        "Cloud Support Retainer",
        "Lumina Software product Cloud Support Retainer. Price INR 45000 per month. "
        "Annual price INR 540000. Covers hosting monitoring, backups, and weekday support.",
    ),
    (
        "products",
        "AI Chatbot",
        "Lumina Software product AI Chatbot, an artificial intelligence product. "
        "Setup price INR 650000. Monthly hosting and model support price INR 35000. "
        "The chatbot answers from the customer's documents.",
    ),
    (
        "products",
        "Machine Learning Forecasting",
        "Lumina Software product Machine Learning Forecasting, an ML product. "
        "Project price INR 900000. Includes data preparation, model training, and a "
        "demand forecast dashboard. Yearly retraining price INR 150000.",
    ),
    (
        "products",
        "Computer Vision Inspection",
        "Lumina Software product Computer Vision Inspection, an AI and ML product. "
        "Project price INR 1100000. It detects defects on a production line. "
        "Camera kit price INR 180000 extra.",
    ),
    (
        "products",
        "AI and ML Consulting",
        "Lumina Software product AI and ML Consulting for artificial intelligence and "
        "machine learning. Price INR 8000 per hour. A 40 hour package price is INR 280000. "
        "Covers use-case selection, model review, and a delivery plan.",
    ),
    (
        "products",
        "Analytics Dashboard",
        "Lumina Software product Analytics Dashboard. Price INR 550000. Connects sales "
        "and finance data. Optional artificial intelligence insight add-on price INR 120000.",
    ),
    (
        "products",
        "AI and ML price list",
        "Lumina Software AI and ML price list. AI Chatbot setup INR 650000 plus INR 35000 "
        "per month. Machine Learning Forecasting INR 900000, yearly retraining INR 150000. "
        "Computer Vision Inspection INR 1100000, camera kit INR 180000. AI and ML Consulting "
        "INR 8000 per hour, or INR 280000 for 40 hours. Analytics Dashboard AI add-on INR 120000.",
    ),
    (
        "sales",
        "SO-2401",
        "Lumina Software sale SO-2401 to customer Acme Corp. Product AI Chatbot. "
        "Setup price INR 650000. Monthly fee INR 35000. Status won. Date 2026-01-18. "
        "Sales lead Anita Deshmukh. City Pune.",
    ),
    (
        "sales",
        "SO-2408",
        "Lumina Software sale SO-2408 to customer Northwind Traders. Product Machine "
        "Learning Forecasting. Price INR 900000. Status won. Date 2026-02-02. "
        "Sales lead Rohan Kulkarni. City Mumbai.",
    ),
    (
        "sales",
        "SO-2415",
        "Lumina Software proposal SO-2415 to customer Pinnacle Retail. Product Computer "
        "Vision Inspection. Quoted price INR 1100000 plus camera kit INR 180000, "
        "total quoted INR 1280000. Status proposal, not closed. Date 2026-02-20. "
        "Sales lead Anita Deshmukh. City Bengaluru.",
    ),
    (
        "sales",
        "SO-2422",
        "Lumina Software sale SO-2422 to customer Metro Hospitals. Products AI Chatbot "
        "setup INR 650000 and AI and ML Consulting 40 hour package INR 280000. "
        "Total price INR 930000. Status won. Date 2026-03-09. Sales lead Neha Iyer. "
        "City Hyderabad.",
    ),
    (
        "sales",
        "SO-2430",
        "Lumina Software sale SO-2430 to customer CityBank. Product Custom Web Application. "
        "Price INR 850000. Status won. Date 2026-04-21. Sales lead Rohan Kulkarni. "
        "City Mumbai. This sale is not artificial intelligence.",
    ),
    (
        "sales",
        "SO-2444",
        "Lumina Software sale SO-2444 to customer Horizon Logistics. Product AI and ML "
        "Consulting, 40 hour package. Price INR 280000. Status won. Date 2026-05-12. "
        "Sales lead Neha Iyer. City Pune.",
    ),
    (
        "sales",
        "SO-2451",
        "Lumina Software sale SO-2451 to customer BlueLeaf Retail. Products Computer Vision "
        "Inspection INR 1100000 and AI Chatbot setup INR 650000. Total price INR 1750000. "
        "Status won. Date 2026-06-30. Sales lead Anita Deshmukh. City Pune.",
    ),
    (
        "sales",
        "SO-2460",
        "Lumina Software sale SO-2460 to customer Acme Corp. Product Cloud Support Retainer "
        "for the AI Chatbot. Price INR 45000 per month. Annual price INR 540000. "
        "Status won. Start date 2026-07-01. Sales lead Rohan Kulkarni.",
    ),
    (
        "sales",
        "Lumina Software sales summary",
        "Lumina Software Pvt Ltd closed sales total INR 5900000. Closed artificial "
        "intelligence and machine learning sales total INR 5050000. Closed non-AI sales "
        "total INR 850000, which is the CityBank Custom Web Application. Open proposal "
        "SO-2415 is quoted at INR 1280000 and is not included in closed sales. Closed AI "
        "and ML orders: SO-2401 INR 650000, SO-2408 INR 900000, SO-2422 INR 930000, "
        "SO-2444 INR 280000, SO-2451 INR 1750000, SO-2460 annual INR 540000.",
    ),
]


def user_data_summary(user):
    return {
        "conversations": Conversation.objects.filter(owner=user).count(),
        "messages": Message.objects.filter(conversation__owner=user).count(),
        "documents": Document.objects.filter(owner=user).count(),
        "ready_documents": Document.objects.filter(
            owner=user, status=Document.STATUS_READY
        ).count(),
        "database_records": DatabaseRecord.objects.count(),
    }


def ensure_sample_records():
    """Insert any sample rows whose title is not already stored."""
    existing = set(DatabaseRecord.objects.values_list("title", flat=True))
    missing = [
        DatabaseRecord(category=category, title=title, content=content)
        for category, title, content in SAMPLE_RECORDS
        if title not in existing
    ]
    if not missing:
        return 0
    DatabaseRecord.objects.bulk_create(missing)
    return len(missing)


def search_database(query: str, limit=None):
    ensure_sample_records()
    limit = limit or settings.DATABASE_CONTEXT_LIMIT
    records = list(DatabaseRecord.objects.all())
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", (query or "").lower())
        if len(word) > 2 and word not in _QUESTION_WORDS
    ]

    def score(record):
        text = f"{record.category} {record.title} {record.content}".lower()
        if not words:
            return 0
        return sum(1 for word in words if word in text)

    ranked = sorted(records, key=score, reverse=True)
    matched = [record for record in ranked if score(record) > 0]
    chosen = matched or ranked
    results = []
    for record in chosen[:limit]:
        results.append(
            {
                "id": str(record.id),
                "category": record.category,
                "title": record.title,
                "content": record.content,
                "score": score(record),
            }
        )
    return results
