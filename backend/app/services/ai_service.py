from html.parser import HTMLParser
from collections import Counter
import re
from urllib.parse import unquote, urlparse

from app.core.config import settings
from app.schemas.ads import AdGenerationRequest, LandingPageAuditRequest, SearchCampaignOptimizationRequest
from app.services.analysis import classify_keywords, classify_search_terms, dashboard_summary
from app.services.page_reader import fetch_static_page, render_page
from app.services.sample_data import CAMPAIGNS, KEYWORDS, SEARCH_TERMS, daily_metrics


GOOGLE_ADS_EXPERT_OPTIMIZATION_PROMPT = """
You are a senior Google Ads expert with 10+ years of Search Ads optimization experience.
Analyze Google Ads campaign data and return automated optimization recommendations to:
1. Reduce wasted spend from inefficient keywords, search terms, ad groups, or campaigns.
2. Improve CTR, conversion rate, and Quality Score through keyword intent, ad copy, and landing page alignment.
3. Optimize CPA, ROAS, and budget allocation based on actual performance.
4. Recommend keywords to keep, increase bid, decrease bid, pause, or convert to exact match.
5. Recommend negative keywords from search terms with low purchase intent.
6. Generate English Search Ads campaign content based on the landing page URL.
7. Ensure every new campaign is created PAUSED for review before going live.
Return JSON with: summary, wasted_spend_findings, growth_opportunities, negative_keywords,
bid_adjustments, campaign_actions, landing_page_alignment, generated_search_ads,
priority_score, expected_impact.
""".strip()


class LandingPageHTMLParser(HTMLParser):
    SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "nav", "header", "footer", "aside", "form", "dialog"}
    VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
    NOISE_MARKERS = {
        "breadcrumb", "cookie", "consent", "drawer", "footer", "header", "menu", "modal",
        "navbar", "navigation", "newsletter", "popup", "sidebar", "social-share", "sticky-bar",
    }

    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_description = ""
        self.headings = []
        self.h1s = []
        self.body_parts = []
        self.main_body_parts = []
        self._title_parts = []
        self._title_depth = 0
        self._captures = []
        self.action_parts = []
        self._main_depth = 0
        self._skip_stack = []

    @classmethod
    def _is_noise_container(cls, attrs_dict: dict[str, str]) -> bool:
        identity = " ".join([attrs_dict.get("id", ""), attrs_dict.get("class", ""), attrs_dict.get("role", "")]).casefold()
        tokens = set(re.findall(r"[a-z0-9_-]+", identity))
        return any(marker in identity or marker in tokens for marker in cls.NOISE_MARKERS)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        tag = tag.lower()
        attrs_dict = {key.lower(): value or "" for key, value in attrs}
        if self._skip_stack:
            if tag not in self.VOID_TAGS:
                self._skip_stack.append(tag)
            return
        if tag in self.SKIP_TAGS or self._is_noise_container(attrs_dict):
            if tag not in self.VOID_TAGS:
                self._skip_stack.append(tag)
            return
        if tag in {"main", "article"}:
            self._main_depth += 1
        if tag == "title":
            self._title_depth += 1
            return
        if tag == "meta":
            meta_key = (attrs_dict.get("name") or attrs_dict.get("property") or "").casefold()
            content = attrs_dict.get("content", "").strip()
            if meta_key in {"description", "og:description", "twitter:description"} and content and not self.meta_description:
                self.meta_description = content
            if meta_key in {"og:title", "twitter:title"} and content and not self.title:
                self.title = content
            return
        if tag in {"h1", "h2", "h3", "p", "li", "a", "button"}:
            self._captures.append({"tag": tag, "parts": [], "in_main": self._main_depth > 0})

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if self._skip_stack:
            if tag in self._skip_stack:
                while self._skip_stack:
                    skipped_tag = self._skip_stack.pop()
                    if skipped_tag == tag:
                        break
            return
        if tag == "title" and self._title_depth:
            self._title_depth -= 1
            return
        if tag in {"h1", "h2", "h3", "p", "li", "a", "button"}:
            for index in range(len(self._captures) - 1, -1, -1):
                capture = self._captures[index]
                if capture["tag"] != tag:
                    continue
                self._captures.pop(index)
                text = " ".join(capture["parts"]).strip()
                if text:
                    if tag.startswith("h") and text not in self.headings:
                        self.headings.append(text)
                    if tag == "h1" and text not in self.h1s:
                        self.h1s.append(text)
                    if tag in {"a", "button"}:
                        self.action_parts.append(text)
                    self.body_parts.append(text)
                    if capture["in_main"]:
                        self.main_body_parts.append(text)
                break
        if tag in {"main", "article"} and self._main_depth:
            self._main_depth -= 1

    def handle_data(self, data: str):
        text = " ".join(data.split())
        if not text or self._skip_stack:
            return
        if self._title_depth:
            self._title_parts.append(text)
        for capture in self._captures:
            capture["parts"].append(text)

    def summary(self) -> dict:
        if self._title_parts:
            self.title = " ".join(self._title_parts)
        preferred_parts = self.main_body_parts if len(" ".join(self.main_body_parts)) >= 120 else self.body_parts
        preferred_parts = [
            item for item in _dedupe_text(preferred_parts)
            if len(item.split()) >= 2 and not _looks_like_page_chrome(item)
        ]
        body_text = " ".join(preferred_parts)
        signals = _extract_commercial_signals(preferred_parts, self.action_parts)
        word_count = len(re.findall(r"[^\W_]+", body_text, flags=re.UNICODE))
        confidence = min(
            100,
            (15 if self.title else 0)
            + (10 if self.meta_description else 0)
            + (15 if self.headings else 0)
            + (30 if word_count >= 150 else round(word_count / 150 * 30))
            + (20 if self.main_body_parts else 0)
            + (10 if any(signals.values()) else 0),
        )
        return {
            "title": _limit(self.title, 120),
            "meta_description": _limit(self.meta_description, 180),
            "headings": _dedupe_text(self.headings)[:8],
            "h1s": _dedupe_text(self.h1s)[:3],
            "content_phrases": [_limit(item, 140) for item in preferred_parts[:16]],
            "body_excerpt": _limit(body_text, 2400),
            "word_count": word_count,
            "extraction_confidence": confidence,
            **signals,
        }


def _looks_like_page_chrome(value: str) -> bool:
    normalized = " ".join(value.casefold().split())
    chrome_phrases = {
        "accept all", "accept cookies", "cookie settings", "privacy policy", "terms of service",
        "skip to content", "sign in", "log in", "all rights reserved", "do not sell",
    }
    return normalized in chrome_phrases or (
        len(normalized.split()) <= 5
        and any(phrase in normalized for phrase in chrome_phrases)
    )


def _extract_commercial_signals(content_parts: list[str], action_parts: list[str]) -> dict:
    cta_pattern = re.compile(
        r"\b(get|start|buy|shop|book|request|contact|download|register|sign up|try|learn|"
        r"explore|discover|view|see|compare|join|subscribe|mua|đăng ký|bắt đầu|xem|"
        r"khám phá|liên hệ|nhận|dùng thử|tải)\b",
        re.IGNORECASE,
    )
    offer_pattern = re.compile(
        r"(%\s*(off|discount)|[$€£₫]\s?\d|free\s+(?:\d+[- ]day\s+)?(trial|shipping|demo)|"
        r"money[- ]back|guarantee|save\s+\d|discount|special offer|pricing|"
        r"giảm\s*\d|miễn phí|dùng thử|hoàn tiền|ưu đãi|bảo hành)",
        re.IGNORECASE,
    )
    trust_pattern = re.compile(
        r"\b(trusted|verified|certified|secure|award|reviews?|ratings?|customers?|clients?|"
        r"money[- ]back|guarantee|support|years? experience|chứng nhận|xác minh|an toàn|"
        r"đánh giá|khách hàng|bảo đảm|hoàn tiền|hỗ trợ|năm kinh nghiệm)\b",
        re.IGNORECASE,
    )
    actions = [
        item for item in _dedupe_text(action_parts)
        if 1 <= len(item.split()) <= 8 and len(item) <= 70 and cta_pattern.search(item)
    ]
    offers = [item for item in _dedupe_text(content_parts) if len(item) <= 180 and offer_pattern.search(item)]
    trust = [item for item in _dedupe_text(content_parts) if len(item) <= 180 and trust_pattern.search(item)]
    return {
        "detected_ctas": actions[:6],
        "detected_offers": offers[:6],
        "detected_trust_signals": trust[:6],
    }


def _dedupe_text(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        value = " ".join(item.split()).strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def _limit(text: str, max_length: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_length:
        return text
    shortened = text[: max_length + 1].rsplit(" ", 1)[0].rstrip(" ,;:-&/+")
    return shortened if len(shortened) >= max_length * 0.6 else text[:max_length].rstrip()


def _title_from_url(url: str) -> str:
    path = unquote(urlparse(url).path).strip("/")
    if not path:
        return ""
    last = path.split("/")[-1].replace("-", " ").replace("_", " ")
    return " ".join(word.capitalize() for word in last.split()[:4])


def _page_identity(url: str, page_context: dict) -> str:
    title = re.split(r"[|–—:]", page_context.get("title", ""), maxsplit=1)[0].strip()
    if title:
        return _limit(title, 60)
    headings = page_context.get("headings", [])
    if headings:
        return _limit(headings[0], 60)
    path_title = _title_from_url(url)
    if path_title:
        return path_title
    hostname = urlparse(url).hostname or "Landing Page"
    return hostname.removeprefix("www.").split(".")[0].replace("-", " ").title()


def _unique_limited(items: list[str], max_length: int, limit: int) -> list[str]:
    seen = set()
    results = []
    for item in items:
        value = _limit(item, max_length)
        key = value.lower()
        if value and key not in seen:
            seen.add(key)
            results.append(value)
        if len(results) == limit:
            break
    return results


SEO_STOPWORDS = {
    "about", "after", "also", "and", "are", "best", "but", "can", "for", "from", "get",
    "has", "have", "how", "into", "its", "more", "not", "our", "page", "that", "the", "their",
    "this", "through", "today", "use", "using", "was", "were", "what", "when", "where", "which",
    "with", "your", "cua", "cho", "cac", "duoc", "khong", "mot", "nhung", "the", "trong", "voi",
}


def _normalize_match(value: str) -> str:
    return " ".join(re.sub(r"[^\w]+", " ", value.casefold(), flags=re.UNICODE).split())


def _title_phrase(value: str) -> str:
    value = " ".join(value.split()).strip(" |,.;:-")
    return " ".join(word.capitalize() if word.islower() else word for word in value.split())


def _sanitize_ad_capitalization(value: str) -> str:
    """Remove coupon-code-like tokens and normalize editorial all-caps words."""
    value = " ".join(value.split()).strip()
    if re.search(r"\b[A-Z]{2,}\d{1,}[A-Z0-9]*\b", value):
        return ""
    return re.sub(
        r"\b[A-Z]{2,}\b",
        lambda match: match.group(0).capitalize(),
        value,
    )


def _fit_headline(value: str) -> str:
    value = _title_phrase(value)
    if len(value) <= 30:
        return value
    fitted = []
    for word in value.split():
        candidate = " ".join([*fitted, word])
        if len(candidate) > 30:
            break
        fitted.append(word)
    while fitted and fitted[-1].casefold() in {"&", "and", "or", "for", "with", "of", "the"}:
        fitted.pop()
    return " ".join(fitted) or value[:30].rstrip()


def _headline_phrase_variants(phrase: str) -> list[str]:
    words = _title_phrase(phrase).split()
    if len(words) < 2:
        return []
    prefix = _fit_headline(" ".join(words))
    suffix_words = []
    for word in reversed(words):
        candidate = " ".join([word, *reversed(suffix_words)])
        if len(candidate) > 30:
            break
        suffix_words.append(word)
    suffix_parts = list(reversed(suffix_words))
    while suffix_parts and suffix_parts[0].casefold().strip(",") in {"&", "and", "or", "for", "with"}:
        suffix_parts.pop(0)
    suffix = " ".join(suffix_parts).replace(", And ", " And ").strip(" ,.;:-")
    incomplete_prefix = prefix.casefold().endswith(
        (" happy", " professional", " professional-grade", " fast", " easy", " built", " designed")
    )
    return _unique_limited(["" if incomplete_prefix else prefix, suffix], 30, 2)


def _headline_facts(page_context: dict) -> list[str]:
    """Return short, attributable phrases from the page in priority order."""
    title = re.split(r"\s+[|\-\u2013\u2014]\s+|[|:]", page_context.get("title", ""), maxsplit=1)[0].strip()
    phrases = [title, *page_context.get("headings", [])]
    meta = page_context.get("meta_description", "")
    if meta:
        phrases.extend(re.split(r"[.;]|\s+[\u2013\u2014]\s+", meta))
    phrases.extend(
        phrase for phrase in page_context.get("content_phrases", [])[:8]
        if 2 <= len(phrase.split()) <= 8 and len(phrase) <= 60
    )
    result = []
    for phrase in phrases:
        phrase = re.sub(r"\s+", " ", phrase).strip(" |,.;:-")
        if len(phrase.split()) < 2:
            continue
        result.extend(_headline_phrase_variants(phrase))
    return _unique_limited(result, 30, 12)


def _keyword_supported_by_page(keyword: str, page_context: dict) -> bool:
    page_text = _normalize_match(" ".join([
        page_context.get("title", ""),
        page_context.get("meta_description", ""),
        *page_context.get("headings", []),
        page_context.get("body_excerpt", ""),
    ]))
    keyword_tokens = [
        token for token in _normalize_match(keyword).split()
        if token not in SEO_STOPWORDS
    ]
    if not keyword_tokens or not page_text:
        return False
    page_tokens = set(page_text.split())
    return all(token in page_tokens for token in keyword_tokens)


def _build_aligned_headlines(
    *,
    product: str,
    page_title_theme: str,
    page_context: dict,
    keywords: list[str],
    offer: str,
    cta: str,
    trust: str,
    is_vietnamese: bool,
) -> tuple[list[str], dict]:
    page_facts = _headline_facts(page_context)
    if len(product) <= 18:
        page_facts = [
            _fit_headline(f"{fact} {product}")
            if len(fact.split()) <= 3 and _normalize_match(product) not in _normalize_match(fact)
            else fact
            for fact in page_facts
        ]
    supported_keywords = [keyword for keyword in keywords if _keyword_supported_by_page(keyword, page_context)]
    unsupported_keywords = [keyword for keyword in keywords if keyword not in supported_keywords]
    headline_keywords = [keyword for keyword in supported_keywords if len(keyword.split()) >= 2]
    fallback_keywords = [keyword for keyword in unsupported_keywords if len(keyword.split()) >= 2]
    factual_candidates = [
        *page_facts,
        *[_fit_headline(keyword) for keyword in headline_keywords[:5]],
        _fit_headline(product),
        _fit_headline(page_title_theme),
        _fit_headline(offer),
        _fit_headline(trust),
    ]
    if is_vietnamese:
        action_candidates = [
            f"Khám Phá {product}", f"Xem {product}", f"{cta} Ngay",
            f"Xem Tính Năng {product}", f"Tìm Hiểu {page_title_theme}",
            f"Khám Phá Thêm Về {product}", f"Chi Tiết {product}",
            f"Vì Sao Chọn {product}",
        ]
    else:
        action_candidates = [
            f"Explore {product}", f"See {product}", f"{cta} Today",
            f"See {product} Features", f"Learn About {page_title_theme}",
            f"Discover {product}", f"{product} Details", f"Why Choose {product}",
        ]
    fact_action_candidates = []
    for fact in page_facts[:6]:
        if is_vietnamese:
            fact_action_candidates.extend([f"Xem {fact}", f"Tìm Hiểu {fact}"])
        else:
            fact_action_candidates.extend([f"See {fact}", f"About {fact}"])
    keyword_action_candidates = []
    for keyword in headline_keywords[:4]:
        if is_vietnamese:
            keyword_action_candidates.extend([f"Xem {keyword}", f"Tìm Hiểu {keyword}"])
        else:
            keyword_action_candidates.extend([f"See {keyword}", f"About {keyword}"])
    candidates = [
        *factual_candidates,
        *action_candidates,
        *fact_action_candidates,
        *keyword_action_candidates,
    ]
    if len(_unique_limited(candidates, 30, 15)) < 15:
        candidates.extend(_fit_headline(keyword) for keyword in fallback_keywords)
    headlines = _unique_limited(
        [
            fitted
            for item in candidates
            if len((fitted := _sanitize_ad_capitalization(_fit_headline(item))).split()) >= 2
        ],
        30,
        15,
    )
    headline_keys = {item.casefold() for item in headlines}
    return headlines, {
        "page_facts_used": [fact for fact in page_facts if fact.casefold() in headline_keys],
        "page_supported_keywords": supported_keywords,
        "unsupported_keywords": unsupported_keywords,
        "fallback_keyword_headlines_used": any(
            _fit_headline(keyword).casefold() in headline_keys for keyword in fallback_keywords
        ),
    }


def _as_complete_sentence(value: str) -> str:
    value = " ".join(value.split()).strip(" ,.;:-")
    if not value or len(value) > 89:
        return ""
    value = value[0].upper() + value[1:]
    return f"{value}."


def _description_facts(product: str, page_title_theme: str, page_context: dict) -> list[str]:
    sources = [
        page_context.get("meta_description", ""),
        *page_context.get("headings", []),
        *page_context.get("content_phrases", [])[:8],
    ]
    facts = []
    for source in sources:
        for sentence in re.split(r"[.!?;]+", source):
            sentence = " ".join(sentence.split()).strip(" ,.;:-")
            if len(sentence.split()) < 2:
                continue
            complete = _as_complete_sentence(sentence)
            if complete:
                facts.append(complete)
                continue
            parts = re.split(r"\s+for\s+", sentence, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2:
                subject, details = parts
                facts.extend([
                    _as_complete_sentence(subject),
                    _as_complete_sentence(f"{details} with {product}"),
                ])
    short_claims = [fact for fact in facts if len(fact.split()) <= 4]
    expanded_facts = [
        _as_complete_sentence(f"{fact.rstrip('.')} {page_title_theme}")
        for fact in short_claims
    ]
    return _unique_limited(
        [
            sanitized
            for fact in [*facts, *expanded_facts]
            if fact and len(fact.split()) >= 4
            and (sanitized := _sanitize_ad_capitalization(fact))
        ],
        90,
        10,
    )


def _build_aligned_descriptions(
    *,
    product: str,
    page_title_theme: str,
    page_context: dict,
    audience: str,
    offer: str,
    cta: str,
    trust: str,
) -> tuple[list[str], dict]:
    page_facts = _description_facts(product, page_title_theme, page_context)
    explicit_facts = [
        _sanitize_ad_capitalization(sentence)
        for value in [offer, trust]
        if value.strip() and (sentence := _as_complete_sentence(value))
    ]
    neutral_candidates = [
        _as_complete_sentence(f"{page_title_theme} - {cta}"),
        _as_complete_sentence(f"Explore {product} features and details - {cta}"),
    ]
    if audience and audience != "customers looking for this solution":
        neutral_candidates.append(_as_complete_sentence(f"{product} for {audience} - {cta}"))
    descriptions = _unique_limited(
        [
            sanitized
            for item in [*page_facts, *explicit_facts, *neutral_candidates]
            if item and (sanitized := _sanitize_ad_capitalization(item))
        ],
        90,
        4,
    )
    return descriptions, {
        "page_facts_used": [fact for fact in page_facts if fact in descriptions],
        "used_request_offer": bool(offer and any(offer.casefold() in item.casefold() for item in descriptions)),
        "used_request_trust": bool(trust and any(trust.casefold() in item.casefold() for item in descriptions)),
    }


def _sentence(parts: list[str], max_length: int = 90) -> str:
    clean = [" ".join(str(part).split()).strip(" .") for part in parts if str(part or "").strip()]
    text = ". ".join(clean)
    if text and not text.endswith((".", "!", "?")):
        text += "."
    text = _limit(text, max_length)
    if text and not text.endswith((".", "!", "?")) and len(text) < max_length:
        text += "."
    return text


def _compact_keyword(value: str, max_length: int = 30) -> str:
    words = [
        word.casefold()
        for word in re.findall(r"[^\W_]+", value, flags=re.UNICODE)
        if word.casefold() not in SEO_STOPWORDS
    ]
    result = []
    for word in words:
        candidate = " ".join([*result, word])
        if len(candidate) > max_length:
            continue
        result.append(word)
    return " ".join(result)


def _extract_page_keywords(product: str, page_context: dict, limit: int = 8) -> list[str]:
    text = " ".join(
        [
            product,
            page_context.get("title", ""),
            page_context.get("meta_description", ""),
            " ".join(page_context.get("headings", [])),
            page_context.get("body_excerpt", ""),
        ]
    )
    words = [
        word.casefold()
        for word in re.findall(r"[^\W\d_]{3,}", text, flags=re.UNICODE)
        if word.casefold() not in SEO_STOPWORDS
    ]
    frequent = [word for word, _ in Counter(words).most_common(limit * 2)]
    page_phrases = [
        _compact_keyword(product),
        _compact_keyword(re.split(r"[|–—:]", page_context.get("title", ""), maxsplit=1)[0]),
        *[_compact_keyword(heading) for heading in page_context.get("headings", [])[:3]],
    ]
    return _unique_limited([*page_phrases, *frequent], 40, limit)


def _infer_search_intent(keywords: list[str]) -> str:
    text = " ".join(keywords).casefold()
    if any(token in text for token in ["buy", "price", "pricing", "discount", "order", "book", "hire", "mua", "gia", "đăng ký"]):
        return "transactional"
    if any(token in text for token in ["best", "top", "review", "compare", "vs", "service", "software", "tốt nhất", "so sánh"]):
        return "commercial"
    if any(token in text for token in ["how", "what", "why", "guide", "tutorial", "cách", "là gì", "hướng dẫn"]):
        return "informational"
    return "commercial"


def _coverage(keywords: list[str], assets: list[str]) -> tuple[int, list[str]]:
    haystack = _normalize_match(" ".join(assets))
    matched = [keyword for keyword in keywords if _normalize_match(keyword) in haystack]
    percentage = round(len(matched) / max(len(keywords), 1) * 100)
    return percentage, matched


def _build_seo_analysis(
    keywords: list[str],
    headlines: list[str],
    descriptions: list[str],
    page_context: dict,
    cta: str,
    offer: str,
    intent: str,
) -> dict:
    headline_coverage, headline_matches = _coverage(keywords, headlines)
    description_coverage, description_matches = _coverage(keywords, descriptions)
    title = page_context.get("title", "")
    meta_description = page_context.get("meta_description", "")
    headings = page_context.get("headings", [])
    h1s = page_context.get("h1s") or headings[:1]
    body_excerpt = page_context.get("body_excerpt", "")
    word_count = page_context.get("word_count") or len(re.findall(r"[^\W_]+", body_excerpt, flags=re.UNICODE))
    extraction_confidence = page_context.get("extraction_confidence")
    if extraction_confidence is None:
        extraction_confidence = 70 if page_context.get("fetched") else 0
    page_assets = [
        title,
        meta_description,
        *headings,
        body_excerpt,
    ]
    page_coverage, page_matches = _coverage(keywords, page_assets)
    primary = keywords[0] if keywords else ""
    normalized_primary = _normalize_match(primary)
    primary_in_title = bool(normalized_primary and normalized_primary in _normalize_match(title))
    primary_in_h1 = bool(normalized_primary and normalized_primary in _normalize_match(" ".join(h1s)))
    primary_in_meta = bool(normalized_primary and normalized_primary in _normalize_match(meta_description))
    primary_in_headlines = bool(primary and _normalize_match(primary) in _normalize_match(" ".join(headlines)))
    cta_present = _normalize_match(cta) in _normalize_match(" ".join(descriptions))
    offer_present = bool(offer and _normalize_match(offer) in _normalize_match(" ".join(descriptions)))
    rsa_limits_valid = (
        3 <= len(headlines) <= 15
        and 2 <= len(descriptions) <= 4
        and all(len(item) <= 30 for item in headlines)
        and all(len(item) <= 90 for item in descriptions)
    )

    landing_page_score = round(
        (10 if page_context.get("fetched") else 0)
        + (10 if title else 0)
        + (5 if 30 <= len(title) <= 65 else 0)
        + (10 if meta_description else 0)
        + (5 if 110 <= len(meta_description) <= 165 else 0)
        + (10 if h1s else 0)
        + min(word_count / 300, 1) * 10
        + (10 if primary_in_title else 0)
        + (10 if primary_in_h1 else 0)
        + (5 if primary_in_meta else 0)
        + (5 if page_context.get("detected_ctas") else 0)
        + (5 if page_context.get("detected_trust_signals") else 0)
        + min(max(extraction_confidence, 0), 100) * 0.05
    )
    keyword_alignment_score = round(
        page_coverage * 0.45
        + headline_coverage * 0.35
        + description_coverage * 0.20
    )
    rsa_quality_score = round(
        (20 if len(headlines) >= 10 else len(headlines) / 10 * 20)
        + (15 if len(descriptions) >= 4 else len(descriptions) / 4 * 15)
        + (20 if rsa_limits_valid else 0)
        + (20 if primary_in_headlines else 0)
        + headline_coverage * 0.15
        + description_coverage * 0.10
    )
    conversion_readiness_score = round(
        (35 if cta_present else 0)
        + (25 if offer_present else 0)
        + (20 if page_context.get("detected_ctas") else 0)
        + (20 if page_context.get("detected_trust_signals") else 0)
    )
    score = round(
        landing_page_score * 0.40
        + keyword_alignment_score * 0.25
        + rsa_quality_score * 0.25
        + conversion_readiness_score * 0.10
    )
    score = max(0, min(100, score))
    if not page_context.get("fetched"):
        score = min(score, 55)

    improvement_plan = []

    def add_improvement(priority: str, area: str, action: str, gain: int):
        improvement_plan.append({
            "priority": priority,
            "area": area,
            "action": action,
            "estimated_gain": gain,
        })

    if not page_context.get("fetched"):
        add_improvement("critical", "Crawlability", "Make the landing page publicly accessible and return indexable HTML.", 15)
    if not title:
        add_improvement("critical", "SEO title", f"Add a unique title containing “{primary}”.", 10)
    elif not 30 <= len(title) <= 65:
        add_improvement("medium", "SEO title", "Rewrite the title to approximately 30–65 characters.", 5)
    if primary and not primary_in_title:
        add_improvement("high", "SEO title", f"Use the exact primary theme “{primary}” naturally in the title.", 8)
    if not meta_description:
        add_improvement("high", "Meta description", "Add a benefit-led meta description with the primary theme and CTA.", 8)
    elif not 110 <= len(meta_description) <= 165:
        add_improvement("medium", "Meta description", "Keep the meta description around 110–165 characters.", 4)
    if primary and not primary_in_meta:
        add_improvement("medium", "Meta description", f"Include “{primary}” naturally in the meta description.", 4)
    if not h1s:
        add_improvement("critical", "Page heading", "Add one clear H1 that states the primary page topic.", 10)
    elif primary and not primary_in_h1:
        add_improvement("high", "Page heading", f"Align the H1 with “{primary}” without keyword stuffing.", 8)
    if word_count < 300:
        add_improvement("medium", "Content depth", f"Expand useful main content from {word_count} to at least 300 words.", 6)
    if not page_context.get("detected_ctas"):
        add_improvement("high", "Conversion", "Add one visible, action-oriented CTA above the fold.", 6)
    if not page_context.get("detected_trust_signals"):
        add_improvement("medium", "Trust", "Add verifiable reviews, customer proof, guarantees or support details.", 5)
    if not primary_in_headlines:
        add_improvement("high", "RSA headlines", "Keep the primary keyword intact in at least one RSA headline.", 7)
    if headline_coverage < 60:
        add_improvement("medium", "RSA coverage", "Use more supported secondary themes across distinct headlines.", 5)
    if page_coverage < 50:
        add_improvement("high", "Message match", "Align title, H1 and main copy with supported search themes.", 8)
    if not cta_present:
        add_improvement("medium", "RSA descriptions", "Include the primary CTA in at least one description.", 4)
    priority_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    improvement_plan.sort(key=lambda item: (priority_rank.get(item["priority"], 9), -item["estimated_gain"]))
    recommendations = [item["action"] for item in improvement_plan[:8]]
    if not recommendations:
        recommendations.append("Strong foundation. Continue testing RSA combinations and monitor search-term quality.")
    potential_score = min(100, score + sum(item["estimated_gain"] for item in improvement_plan[:5]))

    return {
        "score": score,
        "potential_score": potential_score,
        "grade": "Excellent" if score >= 85 else "Good" if score >= 70 else "Needs work" if score >= 50 else "Weak",
        "subscores": {
            "landing_page": min(100, landing_page_score),
            "keyword_alignment": min(100, keyword_alignment_score),
            "rsa_quality": min(100, rsa_quality_score),
            "conversion_readiness": min(100, conversion_readiness_score),
        },
        "primary_keyword": primary,
        "secondary_keywords": keywords[1:],
        "search_intent": intent,
        "headline_keyword_coverage": headline_coverage,
        "description_keyword_coverage": description_coverage,
        "landing_page_keyword_coverage": page_coverage,
        "matched_keywords": {
            "headlines": headline_matches,
            "descriptions": description_matches,
            "landing_page": page_matches,
        },
        "checks": [
            {"label": "Landing page fetched", "passed": bool(page_context.get("fetched"))},
            {"label": "SEO title length", "passed": 30 <= len(title) <= 65},
            {"label": "Meta description length", "passed": 110 <= len(meta_description) <= 165},
            {"label": "Primary keyword in title", "passed": primary_in_title},
            {"label": "Primary keyword in H1", "passed": primary_in_h1},
            {"label": "Primary keyword in headline", "passed": primary_in_headlines},
            {"label": "CTA in description", "passed": cta_present},
            {"label": "Offer in description", "passed": offer_present},
            {"label": "All RSA limits valid", "passed": rsa_limits_valid},
        ],
        "improvement_plan": improvement_plan,
        "recommendations": recommendations,
    }


def _fetch_landing_page_context(url: str) -> dict:
    empty = {
        "source_url": url,
        "fetched": False,
        "title": "",
        "meta_description": "",
        "headings": [],
        "h1s": [],
        "content_phrases": [],
        "body_excerpt": "",
        "word_count": 0,
        "extraction_confidence": 0,
        "detected_ctas": [],
        "detected_offers": [],
        "detected_trust_signals": [],
        "fetch_method": "",
        "browser_fallback_used": False,
        "http_error": "",
        "error": "",
    }
    static_page = fetch_static_page(url)
    static_summary = {}
    if static_page.html:
        parser = LandingPageHTMLParser()
        parser.feed(static_page.html)
        static_summary = parser.summary()

    def has_usable_content(summary: dict) -> bool:
        return bool(
            summary
            and (
                summary.get("word_count", 0) >= 10
                or summary.get("headings")
                or summary.get("title")
                or summary.get("meta_description")
            )
        )

    needs_browser = (
        not static_page.html
        or static_summary.get("word_count", 0) < settings.PAGE_READER_MIN_WORDS
        or static_summary.get("extraction_confidence", 0) < settings.PAGE_READER_MIN_CONFIDENCE
    )
    if not needs_browser:
        return {
            **empty,
            **static_summary,
            "fetched": True,
            "final_url": static_page.final_url,
            "fetch_method": "http",
        }

    rendered_page = render_page(static_page.final_url or url)
    if rendered_page.html:
        parser = LandingPageHTMLParser()
        parser.feed(rendered_page.html)
        rendered_summary = parser.summary()
        # Keep the most useful extraction if browser rendering did not improve it.
        if (
            has_usable_content(rendered_summary)
            and (
                not has_usable_content(static_summary)
                or rendered_summary.get("extraction_confidence", 0)
                >= static_summary.get("extraction_confidence", 0)
            )
        ):
            return {
                **empty,
                **rendered_summary,
                "fetched": True,
                "final_url": rendered_page.final_url,
                "fetch_method": "playwright",
                "browser_fallback_used": True,
                "http_error": static_page.error,
            }

    if has_usable_content(static_summary):
        return {
            **empty,
            **static_summary,
            "fetched": True,
            "final_url": static_page.final_url,
            "fetch_method": "http",
            "browser_fallback_used": True,
            "error": rendered_page.error,
        }
    empty["http_error"] = static_page.error
    empty["browser_fallback_used"] = True
    empty["error"] = rendered_page.error or static_page.error
    return empty


def generate_google_ads_copy(payload: AdGenerationRequest) -> dict:
    landing_page_url = str(payload.landing_page_url)
    page_context = _fetch_landing_page_context(landing_page_url)
    page_product = _page_identity(landing_page_url, page_context)
    product = (payload.product_name or "").strip() or page_product
    audience = (payload.target_audience or "").strip() or "customers looking for this solution"
    page_topic = page_context.get("title") or (page_context.get("headings") or [page_product])[0]

    language = (payload.language or "English").strip() or "English"
    tone = (payload.tone or "Professional").strip() or "Professional"
    is_vietnamese = language.casefold().startswith(("vi", "tiếng việt", "vietnam"))
    message = (
        (payload.landing_page_message or "").strip()
        or page_context["meta_description"]
        or page_context["body_excerpt"]
        or f"Explore {product} for {audience}."
    )
    detected_offers = page_context.get("detected_offers") or []
    detected_ctas = page_context.get("detected_ctas") or []
    detected_trust = page_context.get("detected_trust_signals") or []
    offer = (payload.primary_offer or "").strip() or (
        _limit(min(detected_offers, key=len), 85) if detected_offers else ""
    )
    cta = (payload.primary_cta or "").strip() or (
        _limit(min(detected_ctas, key=len), 30) if detected_ctas else "Learn More"
    )
    trust = (payload.trust_signals or "").strip() or (
        _limit(min(detected_trust, key=len), 85) if detected_trust else ""
    )
    keywords = _unique_limited(
        [keyword.strip().casefold() for keyword in payload.target_keywords if keyword.strip()],
        40,
        10,
    )
    if not keywords:
        keywords = _extract_page_keywords(product, page_context)

    primary_keyword = keywords[0]
    intent = _infer_search_intent(keywords)
    page_title_theme = re.split(r"[|–—:]", page_topic)[0].strip() or product
    if is_vietnamese:
        descriptions = [
            _sentence([f"{_title_phrase(primary_keyword)} dành cho {audience}", f"{cta} ngay hôm nay"]),
            _sentence([offer, f"{_title_phrase(keywords[1] if len(keywords) > 1 else primary_keyword)} phù hợp với {product}", cta]),
            _sentence([_title_phrase(keywords[2] if len(keywords) > 2 else primary_keyword), trust, "Xem tính năng và lợi ích"]),
            _sentence([message, f"{_title_phrase(primary_keyword)} khớp nội dung landing page", cta]),
        ]
        default_ctas = [cta, "Bắt Đầu Ngay", "Xem Bảng Giá", "Nhận Tư Vấn", "Khám Phá Ngay"]
    else:
        descriptions = [
            _sentence([f"{_title_phrase(primary_keyword)} for {audience}", f"{cta} today"]),
            _sentence([offer, f"{_title_phrase(keywords[1] if len(keywords) > 1 else primary_keyword)} aligned with {product}", cta]),
            _sentence([_title_phrase(keywords[2] if len(keywords) > 2 else primary_keyword), trust, "Explore features and benefits"]),
            _sentence([message, f"{_title_phrase(primary_keyword)} matched to this landing page", cta]),
        ]
        default_ctas = [cta, "Get Started", "See Pricing", "Book A Demo", "Explore Features"]

    headlines, headline_alignment = _build_aligned_headlines(
        product=product,
        page_title_theme=page_title_theme,
        page_context=page_context,
        keywords=keywords,
        offer=offer,
        cta=cta,
        trust=trust,
        is_vietnamese=is_vietnamese,
    )
    descriptions, description_alignment = _build_aligned_descriptions(
        product=product,
        page_title_theme=page_title_theme,
        page_context=page_context,
        audience=audience,
        offer=offer,
        cta=cta,
        trust=trust,
    )
    seo_analysis = _build_seo_analysis(
        keywords=keywords,
        headlines=headlines,
        descriptions=descriptions,
        page_context=page_context,
        cta=cta,
        offer=offer,
        intent=intent,
    )
    return {
        "headlines": headlines,
        "descriptions": descriptions,
        "cta_suggestions": _unique_limited(default_ctas, 30, 5),
        "seo_analysis": seo_analysis,
        "landing_page_alignment": {
            "content_source": "landing_page" if page_context.get("fetched") else "request_fallback",
            "page_topic": page_topic,
            "message_used": message,
            "offer_used": offer,
            "trust_used": trust,
            "keywords_used": keywords,
            "language": language,
            "tone": tone,
            "search_intent": intent,
            "seo_score": seo_analysis["score"],
            "headline_alignment": headline_alignment,
            "description_alignment": description_alignment,
            "page_context": page_context,
        },
    }


def _keyword_action(keyword: dict) -> str:
    if keyword.get("cost", 0) >= 900000 and keyword.get("conversions", 0) <= 1:
        return "pause_or_decrease_bid"
    if keyword.get("ctr", 0) >= 8 and keyword.get("conversions", 0) >= 20 and keyword.get("roas", 0) >= 6:
        return "increase_bid_and_scale"
    if keyword.get("match_type", "").upper() != "EXACT":
        return "convert_to_exact_match"
    return "keep_monitoring"


def generate_search_campaign_optimization(payload: SearchCampaignOptimizationRequest) -> dict:
    keywords = payload.keywords or KEYWORDS
    search_terms = payload.search_terms or SEARCH_TERMS
    performance = payload.daily_performance or daily_metrics(30)
    campaigns = payload.campaigns or CAMPAIGNS

    total_cost = sum(row.get("cost", 0) for row in performance)
    total_clicks = sum(row.get("clicks", 0) for row in performance)
    total_impressions = sum(row.get("impressions", 0) for row in performance)
    total_conversions = sum(row.get("conversions", 0) for row in performance)
    total_value = sum(row.get("conversion_value", 0) for row in performance)
    summary = {
        **dashboard_summary(30),
        "campaign_name": payload.campaign_name or (campaigns[0]["name"] if campaigns else "Search Campaign"),
        "analyzed_campaigns": len(campaigns),
        "analyzed_keywords": len(keywords),
        "analyzed_search_terms": len(search_terms),
        "cost": round(total_cost, 2),
        "clicks": total_clicks,
        "impressions": total_impressions,
        "conversions": round(total_conversions, 2),
        "ctr": round(total_clicks / total_impressions * 100, 2) if total_impressions else 0,
        "cpa": round(total_cost / total_conversions, 2) if total_conversions else 0,
        "roas": round(total_value / total_cost, 2) if total_cost else 0,
    }

    classified_keywords = classify_keywords()
    classified_terms = classify_search_terms()
    wasted_keywords = payload.keywords and [
        item for item in keywords if item.get("cost", 0) >= 900000 and item.get("conversions", 0) <= 1
    ] or classified_keywords["waste"]
    growth_keywords = payload.keywords and [
        item for item in keywords if item.get("ctr", 0) >= 8 and item.get("conversions", 0) >= 20 and item.get("roas", 0) >= 6
    ] or classified_keywords["growth"]

    negative_terms = payload.search_terms and [
        item for item in search_terms if item.get("conversions", 0) <= 0 and item.get("cost", 0) >= 100000
    ] or classified_terms["negative_keywords"]

    generated_ads = None
    landing_page_alignment = {
        "status": "not_provided",
        "recommendation": "Add a landing_page_url to generate English RSA content and validate message match.",
    }
    if payload.landing_page_url:
        generated_ads = generate_google_ads_copy(
            AdGenerationRequest(
                product_name=payload.product_name,
                website=payload.landing_page_url,
                landing_page_url=payload.landing_page_url,
                language=payload.language or "English",
                target_audience=payload.target_audience,
                target_keywords=payload.target_keywords,
            )
        )
        landing_page_alignment = generated_ads["landing_page_alignment"]

    wasted_spend = sum(item.get("cost", 0) for item in wasted_keywords)
    priority_score = min(100, int((wasted_spend / max(total_cost, 1)) * 70) + len(negative_terms) * 5 + len(growth_keywords) * 5)

    return {
        "summary": summary,
        "wasted_spend_findings": [
            {
                "keyword": item.get("keyword_text") or item.get("keyword") or item.get("search_term"),
                "cost": item.get("cost", 0),
                "conversions": item.get("conversions", 0),
                "roas": item.get("roas", 0),
                "recommended_action": "pause keyword, decrease bid, or isolate before spending more",
                "reason": "High cost with weak or zero conversion output.",
            }
            for item in wasted_keywords
        ],
        "growth_opportunities": [
            {
                "keyword": item.get("keyword_text") or item.get("keyword"),
                "ctr": item.get("ctr", 0),
                "conversions": item.get("conversions", 0),
                "roas": item.get("roas", 0),
                "recommended_action": "increase manual CPC bid and consider a dedicated exact-match ad group",
            }
            for item in growth_keywords
        ],
        "negative_keywords": [
            {
                "search_term": item.get("search_term"),
                "match_type": "PHRASE",
                "reason": item.get("reason") or "Spend with no conversion or weak commercial intent.",
            }
            for item in negative_terms
        ],
        "bid_adjustments": [
            {
                "keyword": item.get("keyword_text") or item.get("keyword"),
                "current_match_type": item.get("match_type", "UNKNOWN"),
                "action": _keyword_action(item),
                "recommended_match_type": "EXACT",
            }
            for item in keywords
        ],
        "campaign_actions": [
            {
                "action": "create_or_update_search_campaign",
                "status": "PAUSED",
                "bidding_strategy": "MANUAL_CPC",
                "keyword_match_type": "EXACT",
                "safety_note": "New campaigns must stay PAUSED until reviewed in Google Ads.",
            },
            {
                "action": "reallocate_budget",
                "from": "wasted keywords/ad groups",
                "to": "high CTR, high conversion, high ROAS exact-match themes",
            },
        ],
        "landing_page_alignment": landing_page_alignment,
        "generated_search_ads": generated_ads and {
            "language": payload.language or "English",
            "headlines": generated_ads["headlines"],
            "descriptions": generated_ads["descriptions"],
            "cta_suggestions": generated_ads["cta_suggestions"],
        },
        "priority_score": priority_score,
        "expected_impact": {
            "wasted_spend_to_review": round(wasted_spend, 2),
            "primary_metric": "CPA and ROAS",
            "summary": "Prioritize cutting non-converting spend, adding negative keywords, moving strong intent terms to exact match, and launching PAUSED English RSA drafts aligned to the landing page.",
        },
        "expert_prompt": GOOGLE_ADS_EXPERT_OPTIMIZATION_PROMPT,
    }


def audit_landing_page(payload: LandingPageAuditRequest) -> dict:
    url = str(payload.url)
    https_bonus = url.startswith("https://")
    return {
        "url": payload.url,
        "seo_score": 82 if https_bonus else 70,
        "ux_score": 78,
        "conversion_score": 74,
        "mobile_score": 80,
        "findings": [
            "Thong diep chinh can khop chat hon voi keyword/ad copy.",
            "CTA nen xuat hien trong vung first viewport va lap lai sau cac block noi dung.",
            "Can co bang chung xa hoi: logo khach hang, review, case study hoac so lieu.",
        ],
        "recommendations": [
            "Toi uu title/meta theo buyer intent va tu khoa chinh.",
            "Rut gon form, giam truong nhap lieu khong can thiet.",
            "Nen anh, bat cache va kiem tra Core Web Vitals tren mobile.",
            "Them section so sanh loi ich/chi phi de tang conversion intent.",
        ],
    }


def predict_conversion(ctr: float, cpc: float, device: str, audience: str, hour: int, day: int) -> dict:
    score = 0.36 + min(ctr, 20) * 0.018 - min(cpc / 100000, 1.5) * 0.08
    if device.lower() in {"desktop", "tablet"}:
        score += 0.08
    if any(token in audience.lower() for token in ["remarketing", "in-market", "buyer"]):
        score += 0.16
    if 8 <= hour <= 18:
        score += 0.07
    if day in {1, 2, 3, 4}:
        score += 0.05
    probability = max(0.05, min(0.95, score))
    if probability >= 0.72:
        recommendation = "Tang Bid"
    elif probability >= 0.45:
        recommendation = "Giu nguyen"
    else:
        recommendation = "Giam Bid"
    return {
        "conversion_probability": round(probability * 100, 2),
        "recommendation": recommendation,
        "rationale": "Du doan dua tren CTR, CPC, device, audience va khung gio co kha nang mua.",
    }


def find_ad_angles(niche_or_product: str, target_audience: str) -> dict:
    product = niche_or_product.strip()
    audience = target_audience.strip()
    angles = [
        {
            "angle": "Fear / Risk",
            "hook": f"{audience} co the dang mat ngan sach vi thong diep quang cao khong dung intent.",
            "sample_headline": f"Dung Lang Phi Ngan Sach {product}"[:30],
            "sample_description": f"Phat hien diem ro ri trong funnel {product} va sua truoc khi tang ngan sach."[:90],
        },
        {
            "angle": "Curiosity",
            "hook": f"Mot thay doi nho trong copy co the lam {audience} click nhieu hon.",
            "sample_headline": f"Bi Mat Tang CTR {product}"[:30],
            "sample_description": f"Kham pha goc quang cao moi giup {product} noi bat hon trong ket qua tim kiem."[:90],
        },
        {
            "angle": "Social Proof",
            "hook": f"{audience} tin nhanh hon khi thay bang chung va ket qua that.",
            "sample_headline": f"{product} Duoc Tin Dung"[:30],
            "sample_description": f"Them trust signal, case study va loi ich ro rang de tang conversion tu traffic hien co."[:90],
        },
        {
            "angle": "Urgency",
            "hook": f"Quyet dinh cham co the lam {audience} bo lo traffic dang co CPC tot.",
            "sample_headline": f"Toi Uu {product} Hom Nay"[:30],
            "sample_description": f"Nhan de xuat nhanh de tang click, giam CPC va uu tien keyword co kha nang chuyen doi."[:90],
        },
    ]
    return {"angles": angles}
