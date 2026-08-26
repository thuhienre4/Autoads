from datetime import date, timedelta


def daily_metrics(days: int = 30):
    today = date.today()
    rows = []
    for index in range(days):
        day = today - timedelta(days=days - index - 1)
        clicks = 420 + index * 9 + (index % 5) * 28
        impressions = 9200 + index * 130 + (index % 3) * 500
        cost = round(1750000 + index * 41000 + (index % 4) * 120000, 2)
        conversions = round(22 + index * 0.55 + (index % 4) * 2.3, 2)
        value = round(conversions * 530000, 2)
        rows.append(
            {
                "date": day,
                "clicks": clicks,
                "impressions": impressions,
                "cost": cost,
                "conversions": conversions,
                "conversion_value": value,
                "roas": round(value / cost, 2),
            }
        )
    return rows


CAMPAIGNS = [
    {
        "id": 1,
        "name": "Search - SaaS Backup - VN",
        "status": "ENABLED",
        "budget_amount": 9000000,
        "clicks": 8420,
        "impressions": 182400,
        "cost": 35650000,
        "conversions": 392,
        "conversion_value": 221800000,
        "roas": 6.22,
    },
    {
        "id": 2,
        "name": "Brand - Data Recovery",
        "status": "ENABLED",
        "budget_amount": 3500000,
        "clicks": 3150,
        "impressions": 42800,
        "cost": 7850000,
        "conversions": 214,
        "conversion_value": 126300000,
        "roas": 16.09,
    },
    {
        "id": 3,
        "name": "Competitor - Cloud Backup",
        "status": "LIMITED",
        "budget_amount": 5000000,
        "clicks": 1940,
        "impressions": 66200,
        "cost": 12890000,
        "conversions": 38,
        "conversion_value": 19400000,
        "roas": 1.51,
    },
]

KEYWORDS = [
    {
        "id": 101,
        "keyword_text": "wordpress backup",
        "match_type": "PHRASE",
        "cost": 2500000,
        "clicks": 612,
        "conversions": 0,
        "ctr": 4.8,
        "cpc": 4085,
        "roas": 0,
    },
    {
        "id": 102,
        "keyword_text": "website backup service",
        "match_type": "EXACT",
        "cost": 1480000,
        "clicks": 438,
        "conversions": 41,
        "ctr": 8.9,
        "cpc": 3379,
        "roas": 9.7,
    },
    {
        "id": 103,
        "keyword_text": "free mysql backup",
        "match_type": "BROAD",
        "cost": 930000,
        "clicks": 354,
        "conversions": 1,
        "ctr": 5.2,
        "cpc": 2627,
        "roas": 0.6,
    },
    {
        "id": 104,
        "keyword_text": "enterprise cloud backup pricing",
        "match_type": "PHRASE",
        "cost": 860000,
        "clicks": 226,
        "conversions": 33,
        "ctr": 11.4,
        "cpc": 3805,
        "roas": 14.2,
    },
]

SEARCH_TERMS = [
    {"search_term": "best wordpress backup plugin for agency", "clicks": 82, "cost": 244000, "conversions": 9},
    {"search_term": "wordpress backup tutorial free", "clicks": 91, "cost": 188000, "conversions": 0},
    {"search_term": "cloud backup software pricing", "clicks": 77, "cost": 229000, "conversions": 11},
    {"search_term": "backup software crack download", "clicks": 39, "cost": 94000, "conversions": 0},
    {"search_term": "data backup jobs remote", "clicks": 26, "cost": 61000, "conversions": 0},
]
