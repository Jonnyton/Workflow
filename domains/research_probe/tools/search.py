"""Mock research search tool for the probe domain.

This is a deterministic stub that returns simulated search results.
In production, this would integrate with real search backends (vector DB,
web search API, document corpus, etc.).
"""

from __future__ import annotations

from typing import Any


class ResearchSearchTool:
    """Mock research search tool.

    Implements the DomainTool protocol with a deterministic mock backend
    for testing the research workflow without external dependencies.
    """

    name = "research_search"
    description = "Search for documents and sources relevant to a research query"

    def __call__(self, query: str, max_results: int = 5) -> list[dict[str, Any]]:
        """Execute a mock research search.

        Args:
            query: The research query or topic.
            max_results: Maximum number of results to return (default 5).

        Returns:
            List of mock source documents, each with id, title, url, and summary.
        """
        # Mock database of research sources
        mock_sources = {
            "machine learning": [
                {
                    "id": "src_001",
                    "title": "Deep Learning Fundamentals",
                    "url": "https://example.com/dl-fundamentals",
                    "summary": "Core concepts in deep neural networks and training",
                    "relevance": 0.95,
                },
                {
                    "id": "src_002",
                    "title": "Transformer Architecture",
                    "url": "https://example.com/transformers",
                    "summary": "Attention mechanisms and the transformer model",
                    "relevance": 0.92,
                },
                {
                    "id": "src_003",
                    "title": "LLM Fine-tuning Strategies",
                    "url": "https://example.com/llm-finetuning",
                    "summary": "Techniques for adapting large models to domains",
                    "relevance": 0.88,
                },
            ],
            "agent workflows": [
                {
                    "id": "src_004",
                    "title": "Agentic AI Patterns",
                    "url": "https://example.com/agentic-patterns",
                    "summary": "Design patterns for autonomous agent systems",
                    "relevance": 0.96,
                },
                {
                    "id": "src_005",
                    "title": "Tool-Use in LLMs",
                    "url": "https://example.com/tool-use",
                    "summary": "How language models invoke external tools",
                    "relevance": 0.91,
                },
            ],
            "knowledge graphs": [
                {
                    "id": "src_006",
                    "title": "Graph Neural Networks",
                    "url": "https://example.com/gnns",
                    "summary": "Learning on structured graph data",
                    "relevance": 0.89,
                },
                {
                    "id": "src_007",
                    "title": "Knowledge Representation",
                    "url": "https://example.com/kg-repr",
                    "summary": "Representing facts and relationships as graphs",
                    "relevance": 0.85,
                },
            ],
        }

        # Return matching sources or a default set
        normalized_query = query.lower()
        results = []

        for key, sources in mock_sources.items():
            if key in normalized_query or any(word in key for word in normalized_query.split()):
                results.extend(sources)

        # If no exact match, return default sources
        if not results:
            results = mock_sources["machine learning"]

        # Sort by relevance and limit to max_results
        results = sorted(results, key=lambda x: x["relevance"], reverse=True)
        return results[:max_results]


# Module-level instance
research_search = ResearchSearchTool()
