"""Tests for configured web search providers and Sales tool execution."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from langchain_core.messages import AIMessage

from app import main as main_module
from app.agents import coordinator, recommendation, sales
from app.config import get_settings
from app.data.taxonomy import product_subcategory
from app.ml.recommender import infer_product_category, infer_product_subcategory
from app.main import AmazonSearchRequest, amazon_search_endpoint
from app.tools import web_search as web_search_module


class WebSearchTests(unittest.TestCase):
    def test_settings_accept_serpapi_key_alias(self) -> None:
        with patch.dict(os.environ, {"SERPAPI_KEY": "test-serpapi-key"}, clear=True):
            configured = get_settings()
        self.assertEqual(configured.serpapi_api_key, "test-serpapi-key")

    def test_auto_prefers_tavily_when_both_providers_are_configured(self) -> None:
        with (
            patch.object(
                web_search_module,
                "settings",
                Mock(
                    web_search_provider="auto",
                    tavily_api_key="test-tavily-key",
                    serpapi_api_key="test-serpapi-key",
                ),
            ),
            patch.object(
                web_search_module,
                "_tavily_search",
                return_value=[{"title": "Result", "url": "https://example.com", "snippet": "", "source": "Tavily"}],
            ) as tavily,
            patch.object(web_search_module, "_serpapi_search") as serpapi,
        ):
            results = web_search_module.web_search.invoke({"query": "wireless headphones"})

        tavily.assert_called_once_with("wireless headphones", 5)
        serpapi.assert_not_called()
        self.assertEqual(results[0]["source"], "Tavily")

    def test_serpapi_request_uses_configured_key_and_normalizes_results(self) -> None:
        with (
            patch.object(
                web_search_module,
                "settings",
                Mock(serpapi_api_key="test-serpapi-key"),
            ),
            patch.object(
                web_search_module,
                "_request_json",
                return_value={
                    "organic_results": [
                        {
                            "title": "Headphones",
                            "link": "https://example.com/headphones",
                            "snippet": "A product review",
                        }
                    ]
                },
            ) as request_json,
        ):
            results = web_search_module._serpapi_search("headphones", 3)

        request_url = request_json.call_args.args[0]
        query_params = parse_qs(urlparse(request_url).query)
        self.assertEqual(query_params["api_key"], ["test-serpapi-key"])
        self.assertEqual(query_params["q"], ["headphones"])
        self.assertEqual(results[0]["url"], "https://example.com/headphones")
        self.assertEqual(results[0]["source"], "SerpAPI")

    def test_amazon_search_returns_safe_details_variants_and_images(self) -> None:
        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(
                web_search_module,
                "_request_json",
                side_effect=[
                    {
                        "organic_results": [
                            {
                                "asin": "B012345678",
                                "title": "Wireless Headphones",
                                "link_clean": "https://www.amazon.com/dp/B012345678/",
                                "thumbnail": "https://m.media-amazon.com/images/main.jpg",
                                "options": "3 colors",
                            }
                        ]
                    },
                    {
                        "product_results": {
                            "asin": "B012345678",
                            "title": "Wireless Headphones",
                            "link_clean": "https://www.amazon.com/dp/B012345678/",
                            "thumbnails": ["https://m.media-amazon.com/images/blue.jpg"],
                            "price": "$799.00",
                            "rating": 4.7,
                            "reviews": 1200,
                            "description": "Product details",
                            "variants": [
                                {
                                    "title": "Color",
                                    "items": [
                                        {"name": "Black"},
                                        {"name": "Blue"},
                                    ],
                                }
                            ],
                        }
                    },
                ],
            ) as request_json,
        ):
            products = web_search_module.amazon_product_search.invoke(
                {"query": "wireless headphones", "amazon_domain": "amazon.com", "max_results": 3}
            )

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0]["asin"], "B012345678")
        self.assertEqual(products[0]["variants"], [{"name": "Color", "items": ["Black", "Blue"]}])
        self.assertEqual(
            products[0]["images"],
            [
                "https://m.media-amazon.com/images/main.jpg",
                "https://m.media-amazon.com/images/blue.jpg",
            ],
        )
        self.assertEqual(products[0]["price"], "$799.00")
        self.assertEqual(products[0]["currency"], "USD")
        self.assertEqual(products[0]["currency_locale"], "en-US")
        self.assertEqual(len(request_json.call_args_list), 2)
        search_params = parse_qs(urlparse(request_json.call_args_list[0].args[0]).query)
        self.assertEqual(search_params["engine"], ["amazon"])
        self.assertEqual(search_params["k"], ["wireless headphones"])
        self.assertEqual(search_params["amazon_domain"], ["amazon.com"])
        detail_params = parse_qs(urlparse(request_json.call_args_list[1].args[0]).query)
        self.assertEqual(detail_params["engine"], ["amazon_product"])
        self.assertEqual(detail_params["asin"], ["B012345678"])
        self.assertEqual(search_params["api_key"], ["test-serpapi-key"])

    def test_amazon_product_search_defaults_to_india_and_returns_inr(self) -> None:
        result = {
            "asin": "B012345678",
            "title": "Phone India",
            "link_clean": "https://www.amazon.in/dp/B012345678/",
        }

        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(web_search_module, "_amazon_search_results", return_value=[result]) as search,
            patch.object(
                web_search_module,
                "_amazon_product_details",
                return_value={
                    "asin": "B012345678",
                    "title": "Phone India",
                    "link_clean": "https://www.amazon.in/dp/B012345678/",
                    "price": "₹49,999",
                    "extracted_price": 49999,
                },
            ) as details,
        ):
            products = web_search_module.amazon_product_search.invoke({"query": "phone"})

        search.assert_called_once_with("phone", "amazon.in")
        details.assert_called_once_with("B012345678", "amazon.in")
        self.assertEqual(products[0]["price"], "₹49,999")
        self.assertEqual(products[0]["currency"], "INR")
        self.assertEqual(products[0]["currency_locale"], "en-IN")

    def test_laptop_search_filters_out_phones_and_accessories(self) -> None:
        results = [
            {
                "asin": "LAPTOP0001",
                "title": "ASUS Vivobook 15 Laptop",
                "link_clean": "https://www.amazon.in/dp/LAPTOP0001/",
            },
            {
                "asin": "BAG0000001",
                "title": "Laptop Bag for ASUS Vivobook",
                "link_clean": "https://www.amazon.in/dp/BAG0000001/",
            },
            {
                "asin": "PHONE00001",
                "title": "Samsung Galaxy S25 Smartphone",
                "link_clean": "https://www.amazon.in/dp/PHONE00001/",
            },
            {
                "asin": "MACBOOK001",
                "title": "Apple MacBook Air Laptop",
                "link_clean": "https://www.amazon.in/dp/MACBOOK001/",
            },
        ]

        def product_details(asin: str, amazon_domain: str):
            result = next(item for item in results if item["asin"] == asin)
            return {
                "asin": asin,
                "title": result["title"],
                "link_clean": result["link_clean"],
                "price": "₹99,999",
                "extracted_price": 99999,
            }

        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(web_search_module, "_amazon_search_results", return_value=results),
            patch.object(
                web_search_module,
                "_amazon_product_details",
                side_effect=product_details,
            ) as details,
        ):
            products = web_search_module.amazon_product_search.invoke(
                {"query": "laptops", "amazon_domain": "amazon.in", "max_results": 5}
            )

        self.assertEqual([item["asin"] for item in products], ["LAPTOP0001", "MACBOOK001"])
        self.assertEqual(details.call_count, 2)
        self.assertTrue(all(web_search_module._is_laptop_product(item["title"]) for item in products))

    def test_phone_search_filters_out_laptops_and_phone_accessories(self) -> None:
        results = [
            {
                "asin": "PHONE00001",
                "title": "Samsung Galaxy S25 Smartphone",
                "link_clean": "https://www.amazon.in/dp/PHONE00001/",
            },
            {
                "asin": "CASE000001",
                "title": "iPhone 17 Protective Case",
                "link_clean": "https://www.amazon.in/dp/CASE000001/",
            },
            {
                "asin": "LAPTOP0001",
                "title": "Dell XPS 15 Laptop",
                "link_clean": "https://www.amazon.in/dp/LAPTOP0001/",
            },
        ]

        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(web_search_module, "_amazon_search_results", return_value=results),
            patch.object(
                web_search_module,
                "_amazon_product_details",
                side_effect=lambda asin, amazon_domain: {
                    **next(item for item in results if item["asin"] == asin),
                    "price": "₹50,000",
                },
            ) as details,
        ):
            products = web_search_module.amazon_product_search.invoke(
                {"query": "phones", "amazon_domain": "amazon.in", "max_results": 5}
            )

        self.assertEqual([item["asin"] for item in products], ["PHONE00001"])
        details.assert_called_once()

    def test_specific_phone_search_uses_dynamic_amazon_brands_for_alternatives(self) -> None:
        exact_results = [
            {
                "asin": "APPLE00002",
                "title": "Apple iPhone 16 Smartphone",
                "link_clean": "https://www.amazon.com/dp/APPLE00002/",
            },
            {
                "asin": "APPLE00001",
                "title": "Apple iPhone 17 Smartphone",
                "link_clean": "https://www.amazon.com/dp/APPLE00001/",
            }
        ]
        alternative_results = [
            {
                "asin": "SAMSUNG001",
                "title": "Samsung Galaxy S25 Smartphone",
                "link_clean": "https://www.amazon.com/dp/SAMSUNG001/",
            },
            {
                "asin": "SAMSUNG002",
                "title": "Samsung Galaxy S24 Smartphone",
                "link_clean": "https://www.amazon.com/dp/SAMSUNG002/",
            },
            {
                "asin": "GOOGLE0001",
                "title": "Google Pixel 10 Smartphone",
                "link_clean": "https://www.amazon.com/dp/GOOGLE0001/",
            },
            {
                "asin": "APPLE00002",
                "title": "Apple iPhone 16 Smartphone",
                "link_clean": "https://www.amazon.com/dp/APPLE00002/",
            },
            {
                "asin": "CASE000001",
                "title": "Phone case for Samsung Galaxy S25",
                "link_clean": "https://www.amazon.com/dp/CASE000001/",
            },
        ]

        all_results = exact_results + alternative_results
        brands = {
            "APPLE00001": "Apple",
            "SAMSUNG001": "Samsung",
            "SAMSUNG002": "Samsung",
            "GOOGLE0001": "Google",
            "APPLE00002": "Apple",
            "CASE000001": "Samsung",
        }

        def product_details(asin: str, amazon_domain: str):
            result = next(item for item in all_results if item["asin"] == asin)
            return {
                "asin": asin,
                "title": result["title"],
                "link_clean": f"https://www.amazon.com/dp/{asin}/",
                "brand": brands[asin],
            }

        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(
                web_search_module,
                "_amazon_search_results",
                side_effect=[exact_results, alternative_results],
            ) as search,
            patch.object(
                web_search_module,
                "_amazon_product_details",
                side_effect=product_details,
            ) as details,
        ):
            products = web_search_module.amazon_product_search.invoke(
                {"query": "iphone 17", "amazon_domain": "amazon.com", "max_results": 5}
            )

        self.assertEqual([item["asin"] for item in products], ["APPLE00001", "SAMSUNG001", "GOOGLE0001"])
        self.assertEqual([item["result_type"] for item in products], ["requested", "alternative", "alternative"])
        self.assertEqual([item["brand"] for item in products], ["Apple", "Samsung", "Google"])
        self.assertEqual(search.call_args_list[0].args, ("iphone 17", "amazon.com"))
        self.assertEqual(
            search.call_args_list[1].args,
            ("best smartphone alternatives to iphone 17", "amazon.com"),
        )
        self.assertEqual(details.call_count, 3)

    def test_iphone_search_excludes_other_generations_and_unknown_brands(self) -> None:
        exact_results = [
            {
                "asin": "APPLE00016",
                "title": "Apple iPhone 16 128 GB Smartphone with A18 Chip",
                "link_clean": "https://www.amazon.in/dp/APPLE00016/",
            },
            {
                "asin": "APPLE00017",
                "title": "Apple iPhone 17 Smartphone",
                "link_clean": "https://www.amazon.in/dp/APPLE00017/",
            },
            {
                "asin": "OTHER00018",
                "title": "Android 18 Smartphone",
                "link_clean": "https://www.amazon.in/dp/OTHER00018/",
            },
        ]
        alternative_results = [
            {
                "asin": "GENERIC001",
                "title": "Pro 14 Mini 4G Smartphone",
                "link_clean": "https://www.amazon.in/dp/GENERIC001/",
            },
            {
                "asin": "APPLE00016",
                "title": "Apple iPhone 16 Smartphone",
                "link_clean": "https://www.amazon.in/dp/APPLE00016/",
            },
            {
                "asin": "SAMSUNG001",
                "title": "Samsung Galaxy S25",
                "link_clean": "https://www.amazon.in/dp/SAMSUNG001/",
            },
            {
                "asin": "GOOGLE0001",
                "title": "Google Pixel 10 Smartphone",
                "link_clean": "https://www.amazon.in/dp/GOOGLE0001/",
            },
        ]
        all_results = exact_results + alternative_results
        brands = {
            "APPLE00016": "Apple",
            "APPLE00017": "Apple",
            "OTHER00018": "Unbranded",
            "GENERIC001": "Pro",
            "SAMSUNG001": "Samsung",
            "GOOGLE0001": "Google",
        }

        def product_details(asin: str, amazon_domain: str):
            item = next(result for result in all_results if result["asin"] == asin)
            return {
                "asin": asin,
                "title": item["title"],
                "link_clean": item["link_clean"],
                "brand": brands[asin],
            }

        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(
                web_search_module,
                "_amazon_search_results",
                side_effect=[exact_results, alternative_results],
            ),
            patch.object(
                web_search_module,
                "_amazon_product_details",
                side_effect=product_details,
            ),
        ):
            products = web_search_module.amazon_product_search.invoke(
                {"query": "iPhone 18", "amazon_domain": "amazon.in", "max_results": 5}
            )

        self.assertEqual([item["asin"] for item in products], ["SAMSUNG001", "GOOGLE0001"])
        self.assertEqual([item["result_type"] for item in products], ["alternative", "alternative"])
        self.assertNotIn("Apple", [item["brand"] for item in products])

    def test_amazon_search_continues_after_one_product_details_failure(self) -> None:
        results = [
            {
                "asin": "BADDET0001",
                "title": "Wireless Headphones",
                "link_clean": "https://www.amazon.in/dp/BADDET0001/",
            },
            {
                "asin": "GOODDET001",
                "title": "Bluetooth Headphones",
                "link_clean": "https://www.amazon.in/dp/GOODDET001/",
            },
        ]

        with (
            patch.object(web_search_module, "settings", Mock(serpapi_api_key="test-serpapi-key")),
            patch.object(web_search_module, "_amazon_search_results", return_value=results),
            patch.object(
                web_search_module,
                "_amazon_product_details",
                side_effect=[
                    RuntimeError("temporary details lookup failure"),
                    {
                        "asin": "GOODDET001",
                        "title": "Bluetooth Headphones",
                        "link_clean": "https://www.amazon.in/dp/GOODDET001/",
                    },
                ],
            ),
        ):
            products = web_search_module.amazon_product_search.invoke(
                {"query": "headphones", "amazon_domain": "amazon.in", "max_results": 2}
            )

        self.assertEqual([product["asin"] for product in products], ["GOODDET001"])

    def test_coordinator_routes_confirmation_of_web_search_offer_as_recommendation(self) -> None:
        state = {
            "messages": [
                {"role": "user", "content": "How are you doing, suggest me good phones"},
                {
                    "role": "assistant",
                    "content": (
                        "Would you like me to look up the latest public recommendations "
                        "using a web search? Let me know and I'll fetch them."
                    ),
                },
                {"role": "user", "content": "yes"},
            ]
        }

        with patch.object(coordinator, "coordinate") as classify:
            result = coordinator.coordinator_node(state)

        classify.assert_not_called()
        self.assertEqual(result["intent"], "recommendation")
        self.assertEqual(result["plan"][0]["agent"], "recommendation")
        self.assertIn("suggest me good phones", result["plan"][0]["instruction"])

    def test_recommendation_continues_after_confirmation_with_web_results(self) -> None:
        web_search_tool = Mock()
        web_search_tool.invoke.return_value = [
            {
                "title": "Current phone recommendations",
                "url": "https://example.com/phones",
                "snippet": "Recent iPhone and Android models compared.",
                "source": "Tavily",
            }
        ]
        state = {
            "user_id": "u123",
            "messages": [
                {"role": "user", "content": "How are you doing, suggest me good phones"},
                {
                    "role": "assistant",
                    "content": (
                        "Would you like me to look up public recommendations using a web search? "
                        "Let me know and I'll fetch them."
                    ),
                },
                {"role": "user", "content": "yes"},
            ],
            "agent_outputs": {},
        }

        with patch.dict(recommendation._TOOLS_BY_NAME, {"web_search": web_search_tool}):
            result = recommendation.recommendation_node(state)

        web_search_tool.invoke.assert_called_once_with(
            {
                "query": "current public recommendations for smartphones suggest me good phones",
                "max_results": 5,
            }
        )
        message = result["agent_outputs"]["recommendation"]["message"]
        self.assertIn("Current phone recommendations", message)
        self.assertIn("https://example.com/phones", message)
        self.assertIn("external results", message)

    def test_specific_phone_search_filters_out_non_matching_models(self) -> None:
        self.assertTrue(
            web_search_module._matches_requested_phone_model(
                "iPhone 17 Pro Max",
                "Apple iPhone 17 Pro Max Smartphone",
            )
        )
        self.assertFalse(
            web_search_module._matches_requested_phone_model(
                "iPhone 17",
                "Apple iPhone 16 Smartphone",
            )
        )
        self.assertFalse(
            web_search_module._matches_requested_phone_model(
                "iPhone 17 Pro",
                "Apple iPhone 17 Smartphone",
            )
        )
        self.assertFalse(
            web_search_module._matches_requested_phone_model(
                "iPhone 18",
                "Apple iPhone 16 128 GB Smartphone with A18 Chip",
            )
        )

    def test_amazon_search_rejects_invalid_marketplace(self) -> None:
        with self.assertRaisesRegex(ValueError, "marketplace domain"):
            web_search_module.amazon_product_search.invoke(
                {"query": "iphone17", "amazon_domain": "not-amazon.example"}
            )

    def test_phone_query_detection_uses_category_terms_not_model_names(self) -> None:
        self.assertTrue(web_search_module._is_phone_query("smartphones"))
        self.assertTrue(web_search_module._is_phone_query("mobile phone"))
        self.assertFalse(web_search_module._is_phone_query("smartwatch"))
        self.assertFalse(web_search_module._is_phone_query("iPhone 17 case"))

    def test_amazon_search_endpoint_returns_product_cards(self) -> None:
        expected_products = [{"asin": "B012345678", "title": "Phone 17"}]
        with patch.object(
            main_module,
            "amazon_product_search",
            Mock(invoke=Mock(return_value=expected_products)),
        ) as search:
            result = amazon_search_endpoint(
                AmazonSearchRequest(query="iPhone 17", amazon_domain="amazon.in", max_results=2)
            )

        search.invoke.assert_called_once_with(
            {"query": "iPhone 17", "amazon_domain": "amazon.in", "max_results": 2}
        )
        self.assertEqual(result["products"], expected_products)
        self.assertEqual(result["amazon_domain"], "amazon.in")

    def test_source_formatter_includes_only_unique_http_links(self) -> None:
        formatted = web_search_module.format_search_sources(
            [
                {"title": "Running guide", "url": "https://example.com/guide"},
                {"title": "Duplicate", "url": "https://example.com/guide"},
                {"title": "Unsafe", "url": "javascript:alert(1)"},
            ]
        )

        self.assertIn("Running guide: https://example.com/guide", formatted)
        self.assertEqual(formatted.count("https://example.com/guide"), 1)
        self.assertNotIn("javascript:", formatted)

    def test_product_category_inference_recognizes_catalog_product_types(self) -> None:
        self.assertEqual(infer_product_category("which running shoes are best?"), "Footwear")
        self.assertEqual(infer_product_category("recommend wireless headphones"), "Audio")
        self.assertEqual(infer_product_subcategory("recommend running shoes"), "Running Shoes")
        self.assertEqual(infer_product_subcategory("recommend headphones"), "Headphones")
        self.assertIsNone(infer_product_category("recommend some products"))

    def test_generated_product_subcategory_matches_its_product_type(self) -> None:
        self.assertEqual(
            product_subcategory("Nike Lightweight Mesh Running Shoes", "Sneakers"),
            "Running Shoes",
        )
        self.assertEqual(
            product_subcategory("Adidas Classic Casual Canvas Sneakers", "Training Shoes"),
            "Sneakers",
        )

    def test_sales_agent_executes_follow_up_tool_calls(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "current running shoe trends"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        final = AIMessage(content="Here are current running shoe trends.")

        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])
                self.bound_tools = []

            def bind_tools(self, tools):
                self.bound_tools = tools
                return self

            def invoke(self, messages):
                return next(self.responses)

        model = FakeModel()
        web_search_tool = Mock()
        web_search_tool.invoke.return_value = [
            {
                "title": "Running trends",
                "url": "https://example.com/trends",
                "snippet": "Current trends",
                "source": "Tavily",
            }
        ]
        state = {
            "messages": [{"role": "user", "content": "Search online for current running shoe trends"}],
            "agent_outputs": {},
        }

        with (
            patch.object(sales, "get_llm", return_value=model),
            patch.dict(sales._TOOLS_BY_NAME, {"web_search": web_search_tool}),
        ):
            result = sales.sales_node(state)

        bound_tool_names = {bound_tool.name for bound_tool in model.bound_tools}
        self.assertEqual(
            bound_tool_names,
            {"search_products", "rag_search", "web_search", "amazon_product_search"},
        )
        web_search_tool.invoke.assert_called_once_with({"query": "current running shoe trends"})
        self.assertEqual(
            result["agent_outputs"]["sales"]["message"],
            "Here are current running shoe trends.\n\nSources:\n- Running trends: https://example.com/trends",
        )

    def test_sales_agent_returns_amazon_products_for_frontend(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "amazon_product_search",
                    "args": {"query": "iphone 17"},
                    "id": "call-amazon-1",
                    "type": "tool_call",
                }
            ],
        )
        final = AIMessage(content="Here are Amazon listings for the iPhone 17.")

        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return next(self.responses)

        amazon_tool = Mock()
        product = {
            "asin": "B012345678",
            "title": "Phone 17",
            "url": "https://www.amazon.com/dp/B012345678/",
            "images": ["https://m.media-amazon.com/images/main.jpg"],
            "variants": [{"name": "Color", "items": ["Blue"]}],
        }
        amazon_tool.invoke.return_value = [product]
        with (
            patch.object(sales, "get_llm", return_value=FakeModel()),
            patch.dict(sales._TOOLS_BY_NAME, {"amazon_product_search": amazon_tool}),
        ):
            result = sales.sales_node(
                {
                    "messages": [{"role": "user", "content": "Search Amazon for iPhone 17"}],
                    "agent_outputs": {},
                }
            )

        amazon_tool.invoke.assert_called_once_with({"query": "iphone 17"})
        self.assertEqual(result["agent_outputs"]["sales"]["amazon_products"], [product])

    def test_sales_product_search_automatically_combines_catalog_and_amazon(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_products",
                    "args": {"query": "iphone 18"},
                    "id": "call-catalog-1",
                    "type": "tool_call",
                }
            ],
        )
        final = AIMessage(content="I found Apple iPhone 18 in the AURA catalog.")

        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return next(self.responses)

        catalog_tool = Mock()
        catalog_tool.invoke.return_value = [
            {
                "id": "P001",
                "name": "Apple iPhone 18",
                "brand": "Apple",
            }
        ]
        amazon_tool = Mock()
        amazon_tool.invoke.return_value = [
            {
                "asin": "B012345678",
                "title": "Apple iPhone 18",
                "result_type": "requested",
            }
        ]

        with (
            patch.object(sales, "get_llm", return_value=FakeModel()),
            patch.object(sales, "settings", Mock(serpapi_api_key="test-key")),
            patch.dict(
                sales._TOOLS_BY_NAME,
                {
                    "search_products": catalog_tool,
                    "amazon_product_search": amazon_tool,
                },
            ),
        ):
            result = sales.sales_node(
                {
                    "messages": [{"role": "user", "content": "Find iPhone 18"}],
                    "agent_outputs": {},
                }
            )

        catalog_tool.invoke.assert_called_once_with({"query": "iphone 18"})
        amazon_tool.invoke.assert_called_once_with(
            {
                "query": "Apple iPhone 18",
                "amazon_domain": "amazon.in",
                "max_results": 3,
            }
        )
        output = result["agent_outputs"]["sales"]
        self.assertEqual(output["cited_products"], [{"id": "P001", "name": "Apple iPhone 18", "brand": "Apple"}])
        self.assertEqual(output["amazon_products"][0]["asin"], "B012345678")
        self.assertEqual(output["amazon_products"][0]["aura_recommendation"], "Apple iPhone 18")
        self.assertIn("for the catalog options above", output["message"])

    def test_amazon_cards_are_searched_and_filtered_per_catalog_recommendation(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_products",
                    "args": {"query": "running shoes"},
                    "id": "call-shoes-1",
                    "type": "tool_call",
                }
            ],
        )
        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return next(self.responses)

        recommendations = [
            {"id": "P011", "name": "Nike Lightweight Mesh Running Shoes", "brand": "Nike", "subcategory": "Running Shoes"},
            {"id": "P012", "name": "Adidas Lightweight Mesh Running Shoes", "brand": "Adidas", "subcategory": "Running Shoes"},
            {"id": "P013", "name": "Puma Lightweight Mesh Running Shoes", "brand": "Puma", "subcategory": "Running Shoes"},
        ]
        final = AIMessage(
            content="Here are the recommended options: "
            + "; ".join(item["name"] for item in recommendations)
            + "."
        )
        catalog_tool = Mock()
        catalog_tool.invoke.return_value = recommendations
        amazon_tool = Mock()
        amazon_tool.invoke.side_effect = [
                [
                    {
                        "asin": "NIKE000001",
                        "title": "Nike Men's Running Shoes",
                        "brand": "Nike",
                        "result_type": "requested",
                    },
                    {
                        "asin": "OTHER00001",
                        "title": "Campus Men's Running Shoes",
                        "brand": "Campus",
                        "result_type": "requested",
                    },
                ],
                [
                    {
                        "asin": "ADIDAS0001",
                        "title": "Adidas Men's Running Shoes",
                        "brand": "Adidas",
                        "result_type": "requested",
                    }
                ],
                [
                    {
                        "asin": "PUMA000001",
                        "title": "Puma Men's Running Shoes",
                        "brand": "Puma",
                        "result_type": "requested",
                    }
                ],
            ]

        with (
            patch.object(sales, "get_llm", return_value=FakeModel()),
            patch.object(sales, "settings", Mock(serpapi_api_key="test-key")),
            patch.dict(
                sales._TOOLS_BY_NAME,
                {"search_products": catalog_tool, "amazon_product_search": amazon_tool},
            ),
        ):
            result = sales.sales_node(
                {
                    "messages": [{"role": "user", "content": "Show me running shoes"}],
                    "agent_outputs": {},
                }
            )

        self.assertEqual(
            [call.kwargs.get("query") or call.args[0]["query"] for call in amazon_tool.invoke.call_args_list],
            [f"{item['brand']} Running Shoes" for item in recommendations],
        )
        self.assertEqual(
            [call.kwargs.get("max_results") or call.args[0]["max_results"] for call in amazon_tool.invoke.call_args_list],
            [3, 3, 3],
        )
        self.assertEqual(
            [item["asin"] for item in result["agent_outputs"]["sales"]["amazon_products"]],
            ["NIKE000001", "ADIDAS0001", "PUMA000001"],
        )
        self.assertNotIn(
            "OTHER00001",
            [item["asin"] for item in result["agent_outputs"]["sales"]["amazon_products"]],
        )
        self.assertEqual(
            [
                item["aura_recommendation"]
                for item in result["agent_outputs"]["sales"]["amazon_products"]
            ],
            [item["name"] for item in recommendations],
        )

    def test_amazon_recommendation_match_requires_brand_and_relevant_terms(self) -> None:
        recommendation_item = {
            "name": "Nike Lightweight Mesh Running Shoes",
            "brand": "Nike",
            "subcategory": "Running Shoes",
        }
        self.assertTrue(
            sales._amazon_result_matches_recommendation(
                {"title": "Nike Mens V5 RNR Sneakers", "brand": None},
                recommendation_item,
            )
        )
        self.assertTrue(
            sales._amazon_result_matches_recommendation(
                {"title": "Nike Men's Running Shoes"},
                recommendation_item,
            )
        )
        self.assertFalse(
            sales._amazon_result_matches_recommendation(
                {"title": "Campus Men's Running Shoes"},
                recommendation_item,
            )
        )
        self.assertFalse(
            sales._amazon_result_matches_recommendation(
                {"title": "Nike Air Max"},
                recommendation_item,
            )
        )
        self.assertEqual(
            sales._amazon_recommendation_query(recommendation_item),
            "Nike Running Shoes",
        )

    def test_sales_product_search_keeps_catalog_working_without_amazon_key(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "search_products",
                    "args": {"query": "headphones"},
                    "id": "call-catalog-2",
                    "type": "tool_call",
                }
            ],
        )
        final = AIMessage(content="Here are headphones from our catalog.")

        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                return next(self.responses)

        catalog_tool = Mock()
        catalog_tool.invoke.return_value = [{"id": "P002", "name": "AURA headphones"}]
        amazon_tool = Mock()

        with (
            patch.object(sales, "get_llm", return_value=FakeModel()),
            patch.object(sales, "settings", Mock(serpapi_api_key=None)),
            patch.dict(
                sales._TOOLS_BY_NAME,
                {
                    "search_products": catalog_tool,
                    "amazon_product_search": amazon_tool,
                },
            ),
        ):
            result = sales.sales_node(
                {
                    "messages": [{"role": "user", "content": "Find headphones"}],
                    "agent_outputs": {},
                }
            )

        amazon_tool.invoke.assert_not_called()
        output = result["agent_outputs"]["sales"]
        self.assertEqual(output["cited_products"], [{"id": "P002", "name": "AURA headphones"}])
        self.assertEqual(output["amazon_products"], [])
        self.assertNotIn("Amazon search", output["message"])

    def test_recommendation_agent_executes_web_search_tool_call(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "web_search",
                    "args": {"query": "current running shoe recommendations"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        final = AIMessage(content="Here are current online running shoe recommendations.")

        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])
                self.bound_tools = []

            def bind_tools(self, tools):
                self.bound_tools = tools
                return self

            def invoke(self, messages):
                return next(self.responses)

        model = FakeModel()
        web_search_tool = Mock()
        web_search_tool.invoke.return_value = [
            {
                "title": "Running recommendations",
                "url": "https://example.com/running",
                "snippet": "Current recommendations",
                "source": "Tavily",
            }
        ]
        state = {
            "user_id": "u123",
            "messages": [
                {
                    "role": "user",
                    "content": "Search the web for current running shoe recommendations",
                }
            ],
            "agent_outputs": {},
        }

        with (
            patch.object(recommendation, "get_llm", return_value=model),
            patch.dict(recommendation._TOOLS_BY_NAME, {"web_search": web_search_tool}),
        ):
            result = recommendation.recommendation_node(state)

        bound_tool_names = {bound_tool.name for bound_tool in model.bound_tools}
        self.assertEqual(bound_tool_names, {"get_recommendations", "web_search"})
        web_search_tool.invoke.assert_called_once_with(
            {"query": "current running shoe recommendations"}
        )
        self.assertIn("Running recommendations: https://example.com/running", result["agent_outputs"]["recommendation"]["message"])
        self.assertEqual(
            result["agent_outputs"]["recommendation"]["message"],
            "Here are current online running shoe recommendations."
            "\n\nSources:\n- Running recommendations: https://example.com/running",
        )

    def test_recommendation_agent_forces_follow_up_to_requested_category(self) -> None:
        first = AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "get_recommendations",
                    "args": {"user_id": "wrong-user", "k": 4, "category": "Audio"},
                    "id": "call-1",
                    "type": "tool_call",
                }
            ],
        )
        final = AIMessage(content="The best shoe is the highest-rated footwear option.")

        class FakeModel:
            def __init__(self) -> None:
                self.responses = iter([first, final])
                self.last_messages = None

            def bind_tools(self, tools):
                return self

            def invoke(self, messages):
                self.last_messages = messages
                return next(self.responses)

        model = FakeModel()
        recommendations_tool = Mock()
        recommendations_tool.invoke.return_value = [
            {
                "product_id": "P031",
                "name": "Nike Lightweight Mesh Running Shoes",
                "category": "Footwear",
                "subcategory": "Running Shoes",
                "price": 1399,
                "rating_avg": 4.6,
                "score": 3.1,
                "description": "Breathable mesh shoes for daily running.",
                "why": "Highly rated in Footwear",
            }
        ]
        state = {
            "user_id": "u123",
            "messages": [
                {"role": "user", "content": "Recommend running shoes"},
                {"role": "assistant", "content": "Here are running shoe options."},
                {"role": "user", "content": "Which one is the best among them?"},
            ],
            "agent_outputs": {},
        }

        with (
            patch.object(recommendation, "get_llm", return_value=model),
            patch.dict(
                recommendation._TOOLS_BY_NAME,
                {"get_recommendations": recommendations_tool},
            ),
        ):
            result = recommendation.recommendation_node(state)

        recommendations_tool.invoke.assert_called_once_with(
            {
                "user_id": "u123",
                "k": 12,
                "category": "Footwear",
                "subcategory": "Running Shoes",
            }
        )
        self.assertIn("Recommend running shoes", model.last_messages[1].content)
        self.assertIn("Requested catalog category: Footwear", model.last_messages[1].content)
        self.assertIn("Requested product type: Running Shoes", model.last_messages[1].content)
        self.assertIn(
            "Best-rated Footwear option: Nike Lightweight Mesh Running Shoes",
            result["agent_outputs"]["recommendation"]["message"],
        )
        self.assertIn("Breathable mesh shoes for daily running.", result["agent_outputs"]["recommendation"]["message"])

    def test_category_recommendations_are_formatted_from_catalog_data(self) -> None:
        message = recommendation._category_recommendation_message(
            [
                {
                    "name": "Nike Lightweight Mesh Running Shoes",
                    "category": "Footwear",
                    "subcategory": "Running Shoes",
                    "price": 1399,
                    "rating_avg": 4.6,
                    "description": "Breathable shoes with a cushioned sole.",
                    "why": "Matches your interest",
                }
            ],
            "Footwear",
        )

        self.assertIn("Running Shoes", message)
        self.assertIn("₹1,399", message)
        self.assertIn("4.6★", message)
        self.assertIn("Breathable shoes with a cushioned sole.", message)
        self.assertNotIn("**", message)


if __name__ == "__main__":
    unittest.main()
