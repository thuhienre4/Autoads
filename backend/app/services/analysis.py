from app.services.sample_data import KEYWORDS, SEARCH_TERMS, daily_metrics


NEGATIVE_PATTERNS = {
    "free": "Nguoi dung tim mien phi, kho co y dinh mua",
    "torrent": "Lien quan den noi dung download/torrent",
    "job": "Y dinh tuyen dung, khong phu hop quang cao ban hang",
    "career": "Y dinh nghe nghiep/tuyen dung",
    "tutorial": "Y dinh hoc cach lam, intent thap",
    "download": "Y dinh tai ve, rui ro khong lien quan",
    "crack": "Y dinh vi pham ban quyen, can loai tru",
}


def dashboard_summary(days: int = 30) -> dict:
    rows = daily_metrics(days)
    clicks = sum(row["clicks"] for row in rows)
    impressions = sum(row["impressions"] for row in rows)
    cost = sum(row["cost"] for row in rows)
    conversions = sum(row["conversions"] for row in rows)
    value = sum(row["conversion_value"] for row in rows)
    return {
        "clicks": clicks,
        "impressions": impressions,
        "cost": round(cost, 2),
        "conversions": round(conversions, 2),
        "conversion_rate": round(conversions / clicks * 100, 2) if clicks else 0,
        "roas": round(value / cost, 2) if cost else 0,
        "avg_cpc": round(cost / clicks, 2) if clicks else 0,
        "avg_ctr": round(clicks / impressions * 100, 2) if impressions else 0,
    }


def classify_keywords() -> dict:
    waste = []
    growth = []
    for keyword in KEYWORDS:
        item = {**keyword}
        if keyword["cost"] >= 900000 and keyword["conversions"] <= 1:
            item.update(
                {
                    "label": "Dang dot ngan sach",
                    "recommendations": ["Pause Keyword", "Giam Bid", "Chuyen Match Type sang Exact/Phrase"],
                    "priority": "high",
                }
            )
            waste.append(item)
        if keyword["ctr"] >= 8 and keyword["conversions"] >= 20 and keyword["roas"] >= 6:
            item.update(
                {
                    "label": "Keyword tang truong",
                    "recommendations": ["Tang Bid", "Tang Ngan Sach", "Tao Ad Group Rieng"],
                    "priority": "high",
                }
            )
            growth.append(item)
    return {"waste": waste, "growth": growth}


def classify_search_terms() -> dict:
    new_keywords = []
    negatives = []
    for term in SEARCH_TERMS:
        lowered = term["search_term"].lower()
        negative_reason = next((reason for pattern, reason in NEGATIVE_PATTERNS.items() if pattern in lowered), None)
        if negative_reason:
            negatives.append(
                {
                    **term,
                    "intent": "Irrelevant / Low commercial intent",
                    "action": "Them vao Negative Keywords",
                    "reason": negative_reason,
                }
            )
            continue

        commercial = any(token in lowered for token in ["best", "pricing", "service", "software", "agency"])
        long_tail = len(lowered.split()) >= 4
        if commercial or long_tail or term["conversions"] > 0:
            new_keywords.append(
                {
                    **term,
                    "intent": "Buyer intent" if term["conversions"] > 0 else "Commercial long-tail",
                    "action": "Them vao Campaign hoac Ad Group phu hop",
                    "reason": "CTR/conversion intent tot va co cau truc long-tail",
                }
            )
    return {"new_keywords": new_keywords, "negative_keywords": negatives}


def generate_recommendations() -> list[dict]:
    insights = classify_keywords()
    search_terms = classify_search_terms()
    rows = []
    row_id = 1
    for keyword in insights["waste"]:
        rows.append(
            {
                "id": row_id,
                "type": "PAUSE_KEYWORD",
                "title": f"Tam dung keyword: {keyword['keyword_text']}",
                "description": f"Cost {keyword['cost']:,.0f} VND nhung conversion bang {keyword['conversions']}.",
                "priority": "high",
                "estimated_impact": "Giam CPC lang phi va tai phan bo ngan sach sang keyword co ROAS cao.",
                "status": "pending",
            }
        )
        row_id += 1
    for keyword in insights["growth"]:
        rows.append(
            {
                "id": row_id,
                "type": "INCREASE_BID",
                "title": f"Mo rong keyword tang truong: {keyword['keyword_text']}",
                "description": f"CTR {keyword['ctr']}%, conversion {keyword['conversions']} va ROAS {keyword['roas']}.",
                "priority": "high",
                "estimated_impact": "Tang clicks va conversions voi rui ro CPC hop ly.",
                "status": "pending",
            }
        )
        row_id += 1
    for term in search_terms["negative_keywords"][:3]:
        rows.append(
            {
                "id": row_id,
                "type": "ADD_NEGATIVE",
                "title": f"Them negative: {term['search_term']}",
                "description": term["reason"],
                "priority": "medium",
                "estimated_impact": "Giam impression va click khong co y dinh mua.",
                "status": "pending",
            }
        )
        row_id += 1
    rows.append(
        {
            "id": row_id,
            "type": "CREATE_AD",
            "title": "Tao quang cao moi cho ad group co CTR giam",
            "description": "Thu nghiem headline co CTA truc tiep va noi bat loi ich chinh.",
            "priority": "medium",
            "estimated_impact": "Tang CTR va Quality Score neu message match landing page.",
            "status": "pending",
        }
    )
    return rows
