"""Web search tools backed by Tavily or SerpAPI."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from langchain_core.tools import tool

from app.config import settings

_TIMEOUT_SECONDS = 15
_MAX_RESULTS = 10
_MAX_AMAZON_PRODUCTS = 5
_AMAZON_DOMAIN_PATTERN = re.compile(r"^amazon\.[a-z]{2,3}(?:\.[a-z]{2})?$")
_PHONE_ACCESSORY_TERMS = (
    "case",
    "cover",
    "screen protector",
    "charger",
    "charging cable",
    "phone holder",
    "mount",
    "earbuds",
)
_NON_PHONE_DEVICE_TERMS = ("watch", "buds", "tablet", "tab", "ipad", "headphones")
_PHONE_QUERY_PATTERN = re.compile(
    r"\b(?:phones?|smartphones?|iphones?|mobile phones?|handsets?)\b",
    re.IGNORECASE,
)
_LAPTOP_ACCESSORY_TERMS = (
    "bag",
    "backpack",
    "case",
    "cover",
    "sleeve",
    "charger",
    "charging cable",
    "dock",
    "docking station",
    "stand",
    "cooling pad",
    "screen protector",
)
_PHONE_PRODUCT_PATTERN = re.compile(r"\b(?:phones?|smartphones?|iphones?|handsets?)\b", re.IGNORECASE)
_PHONE_VARIANT_TERMS = {"air", "mini", "plus", "pro", "ultra", "max"}
_KNOWN_PHONE_BRANDS = (
    "samsung",
    "google",
    "oneplus",
    "xiaomi",
    "redmi",
    "poco",
    "motorola",
    "oppo",
    "vivo",
    "realme",
    "nothing",
    "huawei",
    "honor",
    "sony",
    "asus",
    "tecno",
    "infinix",
    "zte",
)
_PHONE_QUERY_STOP_WORDS = {
    "a", "an", "and", "apple", "best", "compare", "comparison", "for", "iphone",
    "latest", "mobile", "new", "or", "phone", "phones", "smartphone", "smartphones",
    "the", "top",
}
_LAPTOP_QUERY_PATTERN = re.compile(r"\b(?:laptops?|notebooks?|macbooks?|chromebooks?)\b", re.IGNORECASE)
_LAPTOP_PRODUCT_PATTERN = re.compile(r"\b(?:laptops?|notebooks?|macbooks?|chromebooks?)\b", re.IGNORECASE)
_PHONE_SPECIFIC_QUERY_PATTERN = re.compile(
    r"\b(?:phone|phones|smartphone|smartphones|iphone|iphones|mobile|mobiles|handset|handsets|"
    r"best|top|new|latest|compare|comparison|under|below|less|than|with|and|or|the|a|an)\b",
    re.IGNORECASE,
)
_AMAZON_CURRENCIES = {
    "amazon.in": ("INR", "en-IN"),
    "amazon.com": ("USD", "en-US"),
    "amazon.co.uk": ("GBP", "en-GB"),
}


def _is_phone_query(query: str) -> bool:
    if any(re.search(rf"\b{re.escape(term)}\b", query, re.IGNORECASE) for term in _PHONE_ACCESSORY_TERMS):
        return False
    return bool(_PHONE_QUERY_PATTERN.search(query))


def _is_phone_product(title: str) -> bool:
    normalized = title.casefold()
    if any(term in normalized for term in _PHONE_ACCESSORY_TERMS):
        return False
    if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in _NON_PHONE_DEVICE_TERMS):
        return False
    return bool(_PHONE_PRODUCT_PATTERN.search(title) or _phone_brand(title))


def _is_laptop_query(query: str) -> bool:
    if any(re.search(rf"\b{re.escape(term)}\b", query, re.IGNORECASE) for term in _LAPTOP_ACCESSORY_TERMS):
        return False
    return bool(_LAPTOP_QUERY_PATTERN.search(query))


def _is_laptop_product(title: str) -> bool:
    if any(re.search(rf"\b{re.escape(term)}\b", title, re.IGNORECASE) for term in _LAPTOP_ACCESSORY_TERMS):
        return False
    return bool(_LAPTOP_PRODUCT_PATTERN.search(title))


def _has_specific_phone_query(query: str) -> bool:
    remaining = _PHONE_SPECIFIC_QUERY_PATTERN.sub(" ", query)
    return bool(re.search(r"[a-z0-9]", remaining, re.IGNORECASE))


def _matches_requested_phone_model(query: str, title: str) -> bool:
    requested_brand = _phone_brand(query)
    if requested_brand and _phone_brand(title) != requested_brand:
        return False

    requested_iphone_model = re.search(r"\biphone\s*(\d{1,2})\b", query, re.IGNORECASE)
    if requested_iphone_model:
        result_iphone_model = re.search(r"\biphone\s*(\d{1,2})\b", title, re.IGNORECASE)
        if not result_iphone_model or result_iphone_model.group(1) != requested_iphone_model.group(1):
            return False

    query_terms = {
        term.casefold()
        for term in re.findall(r"[a-z]+|\d+", query, re.IGNORECASE)
        if term.casefold() not in _PHONE_QUERY_STOP_WORDS
    }
    required_terms = {
        term for term in query_terms
        if term.isdigit() or term in _PHONE_VARIANT_TERMS
    }
    title_terms = {
        term.casefold() for term in re.findall(r"[a-z]+|\d+", title, re.IGNORECASE)
    }
    return not required_terms or required_terms.issubset(title_terms)


def _phone_brand(value: Any) -> str:
    normalized = str(value or "").casefold()
    if "iphone" in normalized or "apple" in normalized:
        return "apple"
    for brand in _KNOWN_PHONE_BRANDS:
        if brand in normalized:
            return "xiaomi" if brand == "redmi" else brand
    return ""


def _amazon_search_results(query: str, amazon_domain: str) -> list[dict[str, Any]]:
    params = urlencode(
        {
            "engine": "amazon",
            "k": query,
            "amazon_domain": amazon_domain,
            "api_key": settings.serpapi_api_key,
        }
    )
    payload = _request_json(f"https://serpapi.com/search.json?{params}")
    if payload.get("error"):
        raise RuntimeError(f"SerpAPI Amazon search failed: {str(payload['error'])[:200]}")
    results = payload.get("organic_results", [])
    if not isinstance(results, list):
        raise RuntimeError("SerpAPI returned an unexpected Amazon search-results format.")
    return [item for item in results if isinstance(item, dict)]


def format_search_sources(results: list[dict[str, str]]) -> str:
    """Format valid provider result URLs as a user-visible source list."""
    sources: list[str] = []
    seen_urls: set[str] = set()
    for result in results:
        url = result.get("url", "").strip()
        parsed_url = urlsplit(url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc or url in seen_urls:
            continue

        title = " ".join(result.get("title", "").split()) or parsed_url.netloc
        sources.append(f"- {title}: {url}")
        seen_urls.add(url)

    return f"\n\nSources:\n" + "\n".join(sources) if sources else ""


def _request_json(url: str, *, body: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send a bounded-time JSON request and return an object response."""
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    request = Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise RuntimeError(f"Web search provider returned HTTP {exc.code}.") from None
    except (URLError, TimeoutError):
        raise RuntimeError("Could not connect to the web search provider.") from None
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RuntimeError("Web search provider returned an invalid JSON response.") from None

    if not isinstance(payload, dict):
        raise RuntimeError("Web search provider returned an unexpected response.")
    return payload


def _tavily_search(query: str, max_results: int) -> list[dict[str, str]]:
    if not settings.tavily_api_key:
        raise ValueError("TAVILY_API_KEY is required when WEB_SEARCH_PROVIDER=tavily.")

    payload = _request_json(
        "https://api.tavily.com/search",
        body={
            "api_key": settings.tavily_api_key,
            "query": query,
            "search_depth": "basic",
            "topic": "general",
            "max_results": max_results,
            "include_answer": False,
        },
    )
    if payload.get("error"):
        raise RuntimeError(f"Tavily search failed: {str(payload['error'])[:200]}")
    results = payload.get("results", [])
    if not isinstance(results, list):
        raise RuntimeError("Tavily returned an unexpected search-results format.")

    return [
        {
            "title": str(item.get("title", "")),
            "url": str(item.get("url", "")),
            "snippet": str(item.get("content", "")),
            "source": "Tavily",
        }
        for item in results[:max_results]
        if isinstance(item, dict)
    ]


def _serpapi_search(query: str, max_results: int) -> list[dict[str, str]]:
    if not settings.serpapi_api_key:
        raise ValueError("SERPAPI_KEY (or SERPAPI_API_KEY) is required when WEB_SEARCH_PROVIDER=serpapi.")

    params = urlencode(
        {
            "engine": "google",
            "q": query,
            "api_key": settings.serpapi_api_key,
            "num": max_results,
        }
    )
    payload = _request_json(f"https://serpapi.com/search.json?{params}")
    if payload.get("error"):
        raise RuntimeError(f"SerpAPI search failed: {str(payload['error'])[:200]}")
    results = payload.get("organic_results", [])
    if not isinstance(results, list):
        raise RuntimeError("SerpAPI returned an unexpected search-results format.")

    return [
        {
            "title": str(item.get("title", "")),
            "url": str(item.get("link", "")),
            "snippet": str(item.get("snippet", "")),
            "source": "SerpAPI",
        }
        for item in results[:max_results]
        if isinstance(item, dict)
    ]


def _safe_amazon_url(value: Any, amazon_domain: str) -> str | None:
    """Return only HTTPS Amazon product URLs for the requested marketplace."""
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or not (host == amazon_domain or host.endswith(f".{amazon_domain}"))
    ):
        return None
    return parsed.geturl()


def _safe_amazon_image(value: Any) -> str | None:
    """Allow known Amazon image hosts only."""
    if not isinstance(value, str):
        return None
    parsed = urlsplit(value.strip())
    host = (parsed.hostname or "").lower()
    if (
        parsed.scheme != "https"
        or parsed.username
        or parsed.password
        or not (host.endswith(".media-amazon.com") or host.endswith(".ssl-images-amazon.com"))
    ):
        return None
    return parsed.geturl()


def _amazon_product_details(asin: str, amazon_domain: str) -> dict[str, Any]:
    if not settings.serpapi_api_key:
        raise ValueError("SERPAPI_KEY (or SERPAPI_API_KEY) is required for Amazon product search.")
    params = urlencode(
        {
            "engine": "amazon_product",
            "asin": asin,
            "amazon_domain": amazon_domain,
            "api_key": settings.serpapi_api_key,
        }
    )
    payload = _request_json(f"https://serpapi.com/search.json?{params}")
    if payload.get("error"):
        raise RuntimeError(f"SerpAPI Amazon product lookup failed: {str(payload['error'])[:200]}")
    product = payload.get("product_results", {})
    if not isinstance(product, dict):
        raise RuntimeError("SerpAPI returned an unexpected Amazon product format.")
    return product


def _normalize_amazon_product(result: dict[str, Any], details: dict[str, Any], amazon_domain: str) -> dict[str, Any] | None:
    asin = result.get("asin")
    detail_asin = details.get("asin")
    if isinstance(asin, str) and isinstance(detail_asin, str) and asin.upper() != detail_asin.upper():
        raise RuntimeError("SerpAPI returned Amazon product details for a different ASIN.")
    title = details.get("title") or result.get("title")
    link = _safe_amazon_url(
        details.get("link_clean") or details.get("link") or result.get("link_clean") or result.get("link"),
        amazon_domain,
    )
    if not isinstance(asin, str) or not isinstance(title, str) or not link:
        return None

    images: list[str] = []
    raw_thumbnails = details.get("thumbnails")
    if not isinstance(raw_thumbnails, list):
        raw_thumbnails = []
    for raw_image in [details.get("thumbnail"), result.get("thumbnail"), *raw_thumbnails]:
        image = _safe_amazon_image(raw_image)
        if image and image not in images:
            images.append(image)

    variants: list[dict[str, Any]] = []
    raw_variants = details.get("variants", [])
    if isinstance(raw_variants, list):
        for variant_group in raw_variants:
            if not isinstance(variant_group, dict):
                continue
            items = variant_group.get("items", [])
            if not isinstance(items, list):
                continue
            names = [
                str(item["name"]).strip()
                for item in items[:12]
                if isinstance(item, dict) and isinstance(item.get("name"), str) and item["name"].strip()
            ]
            if names:
                variants.append({"name": str(variant_group.get("title") or "Options"), "items": names})

    variant_combinations = details.get("variant_combinations", [])
    if not variants and isinstance(variant_combinations, list):
        combinations = []
        for combination in variant_combinations[:12]:
            dimensions = combination.get("dimensions") if isinstance(combination, dict) else None
            if isinstance(dimensions, dict):
                label = " · ".join(
                    f"{str(key).replace('_', ' ').title()}: {value}"
                    for key, value in dimensions.items()
                    if isinstance(value, (str, int, float))
                )
                if label:
                    combinations.append(label)
        if combinations:
            variants.append({"name": "Available variants", "items": combinations})

    return {
        "asin": asin,
        "title": title.strip(),
        "url": link,
        "images": images,
        "price": details.get("price") or result.get("price"),
        "extracted_price": details.get("extracted_price") or result.get("extracted_price"),
        "currency": _AMAZON_CURRENCIES.get(amazon_domain, (None, None))[0],
        "currency_locale": _AMAZON_CURRENCIES.get(amazon_domain, (None, None))[1],
        "rating": details.get("rating") or result.get("rating"),
        "reviews": details.get("reviews") or result.get("reviews"),
        "brand": details.get("brand"),
        "description": details.get("description"),
        "stock": details.get("stock"),
        "delivery": (
            details.get("delivery")
            or result.get("delivery")
            or []
        ),
        "variants": variants,
        "options_summary": result.get("options"),
        "source": "Amazon via SerpAPI",
    }


@tool
def amazon_product_search(
    query: str,
    amazon_domain: str = "amazon.in",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Return live Amazon API listings and details for the selected marketplace."""
    clean_query = (query or "").strip()
    domain = (amazon_domain or "").strip().lower()
    if not clean_query:
        raise ValueError("Amazon product search query cannot be empty.")
    if not _AMAZON_DOMAIN_PATTERN.fullmatch(domain):
        raise ValueError("amazon_domain must be a marketplace domain such as amazon.com or amazon.in.")
    if not 1 <= max_results <= _MAX_AMAZON_PRODUCTS:
        raise ValueError(f"max_results must be between 1 and {_MAX_AMAZON_PRODUCTS}.")
    if not settings.serpapi_api_key:
        raise ValueError("SERPAPI_KEY (or SERPAPI_API_KEY) is required for Amazon product search.")

    results = _amazon_search_results(clean_query, domain)
    products: list[dict[str, Any]] = []
    seen_asins: set[str] = set()
    detail_errors: list[str] = []
    is_phone_query = _is_phone_query(clean_query)
    is_laptop_query = _is_laptop_query(clean_query)

    def load_product(result: dict[str, Any], result_type: str) -> dict[str, Any] | None:
        result_title = result.get("title")
        if is_phone_query and (not isinstance(result_title, str) or not _is_phone_product(result_title)):
            return None
        if (
            is_phone_query
            and result_type == "requested"
            and isinstance(result_title, str)
            and not _matches_requested_phone_model(clean_query, result_title)
        ):
            return None
        if is_laptop_query and (not isinstance(result_title, str) or not _is_laptop_product(result_title)):
            return None
        asin = result.get("asin")
        if not isinstance(asin, str) or not re.fullmatch(r"[A-Z0-9]{10}", asin):
            return None
        if asin.upper() in seen_asins:
            return None
        try:
            details = _amazon_product_details(asin, domain)
        except RuntimeError as exc:
            detail_errors.append(str(exc))
            return None
        product = _normalize_amazon_product(result, details, domain)
        if product and is_phone_query and not _is_phone_product(product["title"]):
            return None
        if (
            product
            and is_phone_query
            and result_type == "requested"
            and not _matches_requested_phone_model(clean_query, product["title"])
        ):
            return None
        if product and is_laptop_query and not _is_laptop_product(product["title"]):
            return None
        if product:
            product["result_type"] = result_type
            seen_asins.add(asin.upper())
        return product

    if is_phone_query and _has_specific_phone_query(clean_query):
        requested_product = None
        for result in results:
            product = load_product(result, "requested")
            if product:
                requested_product = product
                break

        if requested_product:
            products.append(requested_product)

        if len(products) < max_results:
            alternative_results = _amazon_search_results(
                f"best smartphone alternatives to {clean_query}",
                domain,
            )
            requested_brand = _phone_brand(clean_query) or _phone_brand(
                (requested_product or {}).get("brand")
            )
            seen_brands: set[str] = {requested_brand} if requested_brand else set()
            for result in alternative_results:
                title = result.get("title")
                if not isinstance(title, str) or not _is_phone_product(title):
                    continue
                result_brand = _phone_brand(result.get("brand") or title)
                if not result_brand or result_brand == requested_brand or result_brand in seen_brands:
                    continue
                product = load_product(result, "alternative")
                if not product:
                    continue
                brand = _phone_brand(product.get("brand") or product["title"])
                if not brand or brand == requested_brand or brand in seen_brands:
                    continue
                products.append(product)
                seen_brands.add(brand)
                if len(products) >= max_results:
                    break
    else:
        for result in results:
            product = load_product(result, "requested")
            if product:
                products.append(product)
            if len(products) >= max_results:
                break

    if not products and detail_errors:
        raise RuntimeError(
            f"SerpAPI returned Amazon listings, but product details could not be loaded: {detail_errors[0]}"
        )

    return products


@tool
def web_search(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """Search the public web for current product information, comparisons, or trends; returns title, URL, snippet, and provider for each result."""
    clean_query = (query or "").strip()
    if not clean_query:
        raise ValueError("Search query cannot be empty.")
    if not 1 <= max_results <= _MAX_RESULTS:
        raise ValueError(f"max_results must be between 1 and {_MAX_RESULTS}.")

    provider = settings.web_search_provider
    if provider == "auto":
        if settings.tavily_api_key:
            provider = "tavily"
        elif settings.serpapi_api_key:
            provider = "serpapi"
        else:
            raise ValueError(
                "Web search is not configured. Set TAVILY_API_KEY or SERPAPI_KEY in backend/.env."
            )

    if provider == "tavily":
        return _tavily_search(clean_query, max_results)
    if provider == "serpapi":
        return _serpapi_search(clean_query, max_results)
    raise ValueError("WEB_SEARCH_PROVIDER must be auto, tavily, or serpapi.")
