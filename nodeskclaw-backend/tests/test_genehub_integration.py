"""Tests for Registry Adapter layer, Aggregator, and legacy converter."""

from __future__ import annotations

import pytest

from app.services.genehub_converter import (
    extract_paginated_items,
    genehub_gene_to_local,
    genehub_genome_to_local,
    genehub_tags_to_local,
)
from app.services.registry_adapter import (
    RegistrySearchResult,
    RegistrySkillDetail,
    RegistrySkillItem,
)


# ═══════════════════════════════════════════════════
#  genehub_converter unit tests (legacy, deprecated)
# ═══════════════════════════════════════════════════


class TestGenehubGeneToLocal:
    def test_basic_mapping(self):
        gene = {
            "id": "uuid-from-genehub",
            "name": "Test Gene",
            "slug": "test-gene",
            "version": "1.0.0",
            "description": "A test gene",
            "short_description": "test",
            "category": "skill",
            "tags": ["test", "demo"],
            "source": "official",
            "icon": "brain",
            "install_count": 42,
            "avg_rating": 4.5,
            "effectiveness_score": 3.8,
            "is_published": True,
            "review_status": "approved",
            "manifest": {"skill": {"name": "test-gene", "content": "test content"}},
            "dependencies": [],
            "synergies": ["other-gene"],
            "created_at": "2026-03-01T00:00:00Z",
            "updated_at": "2026-03-01T12:00:00Z",
        }
        result = genehub_gene_to_local(gene)
        assert result["name"] == "Test Gene"
        assert result["slug"] == "test-gene"
        assert result["tags"] == ["test", "demo"]
        assert result["install_count"] == 42
        assert result["avg_rating"] == 4.5
        assert result["is_published"] is True
        assert result["manifest"]["skill"]["name"] == "test-gene"

    def test_local_cache_supplements_uuid(self):
        gene = {"slug": "test-gene", "name": "Test"}
        cache = {"id": "local-uuid-123", "org_id": "org-456", "created_by": "user-789"}
        result = genehub_gene_to_local(gene, cache)
        assert result["id"] == "local-uuid-123"
        assert result["org_id"] == "org-456"
        assert result["created_by"] == "user-789"

    def test_missing_fields_default_gracefully(self):
        gene = {"slug": "minimal-gene"}
        result = genehub_gene_to_local(gene)
        assert result["slug"] == "minimal-gene"
        assert result["name"] == ""
        assert result["tags"] == []
        assert result["install_count"] == 0
        assert result["avg_rating"] == 0
        assert result["is_published"] is True


class TestGenehubGenomeToLocal:
    def test_basic_mapping(self):
        genome = {
            "id": "genome-id",
            "name": "Starter Pack",
            "slug": "starter-pack",
            "description": "A starter genome",
            "genes": [
                {"slug": "gene-a", "version": "1.0.0"},
                {"slug": "gene-b", "version": "2.0.0"},
            ],
            "install_count": 10,
        }
        result = genehub_genome_to_local(genome)
        assert result["name"] == "Starter Pack"
        assert result["slug"] == "starter-pack"
        assert result["gene_slugs"] == ["gene-a", "gene-b"]
        assert result["install_count"] == 10


class TestExtractPaginatedItems:
    def test_genehub_format(self):
        body = {
            "code": 0,
            "data": {
                "items": [{"slug": "a"}, {"slug": "b"}],
                "total": 42,
                "page": 1,
                "page_size": 20,
            },
        }
        items, total = extract_paginated_items(body)
        assert len(items) == 2
        assert total == 42

    def test_empty_response(self):
        body = {"code": 0, "data": {}}
        items, total = extract_paginated_items(body)
        assert items == []
        assert total == 0

    def test_flat_array_fallback(self):
        body = {"code": 0, "data": [{"slug": "x"}]}
        items, total = extract_paginated_items(body)
        assert len(items) == 1
        assert total == 1


class TestGenehubTagsToLocal:
    def test_conversion(self):
        tags = [{"tag": "ai", "count": 10}, {"tag": "coding", "count": 5}]
        result = genehub_tags_to_local(tags)
        assert len(result) == 2
        assert result[0]["tag"] == "ai"
        assert result[0]["count"] == 10


# ═══════════════════════════════════════════════════
#  Legacy genehub_client tests (module-level functions)
# ═══════════════════════════════════════════════════


class TestGenehubClientDisabled:
    """When GENEHUB_REGISTRY_URL is empty, all calls should return None."""

    @pytest.fixture(autouse=True)
    def _patch_settings(self, monkeypatch):
        monkeypatch.setattr("app.services.genehub_client.settings.GENEHUB_REGISTRY_URL", "")

    @pytest.mark.asyncio
    async def test_list_genes_returns_none(self):
        from app.services import genehub_client

        result = await genehub_client.list_genes()
        assert result is None

    @pytest.mark.asyncio
    async def test_get_gene_returns_none(self):
        from app.services import genehub_client

        result = await genehub_client.get_gene("any-slug")
        assert result is None

    @pytest.mark.asyncio
    async def test_report_install_returns_false(self):
        from app.services import genehub_client

        result = await genehub_client.report_install("any-slug")
        assert result is False


# ═══════════════════════════════════════════════════
#  GeneHubAdapter tests
# ═══════════════════════════════════════════════════


class TestGeneHubAdapterMapping:
    def test_gene_to_item_mapping(self):
        from app.services.genehub_client import GeneHubAdapter

        adapter = GeneHubAdapter(
            registry_id="deskhub", registry_name="DeskHub",
            base_url="https://skills.deskclaw.me",
        )
        raw = {
            "slug": "test-gene",
            "name": "Test Gene",
            "version": "1.0.0",
            "tags": ["ai"],
            "install_count": 10,
            "source": "official",
        }
        item = adapter._gene_to_item(raw)
        assert item.slug == "test-gene"
        assert item.name == "Test Gene"
        assert item.source_registry == "deskhub"
        assert item.source_registry_name == "DeskHub"
        assert item.install_count == 10
        assert item.tags == ["ai"]


# ═══════════════════════════════════════════════════
#  ClawHubAdapter stub tests
# ═══════════════════════════════════════════════════


class TestClawHubAdapterStub:
    @pytest.mark.asyncio
    async def test_all_methods_return_none_or_false(self):
        from app.services.clawhub_adapter import ClawHubAdapter

        adapter = ClawHubAdapter()
        assert await adapter.search_skills() is None
        assert await adapter.get_skill("any") is None
        assert await adapter.get_manifest("any") is None
        assert await adapter.get_featured() is None
        assert await adapter.get_tags() is None
        assert await adapter.get_synergies("any") is None
        assert await adapter.publish_skill({}) is None
        assert await adapter.report_install("any") is False
        assert await adapter.report_effectiveness("any", "metric", 1.0) is False


# ═══════════════════════════════════════════════════
#  RegistryAggregator tests
# ═══════════════════════════════════════════════════


class _MockAdapter:
    """Minimal mock adapter for testing aggregator merge logic."""

    def __init__(self, registry_id: str, items: list[RegistrySkillItem]):
        self.registry_id = registry_id
        self.registry_name = registry_id
        self.base_url = None
        self._items = items

    async def search_skills(self, **kwargs) -> RegistrySearchResult:
        return RegistrySearchResult(items=self._items, total=len(self._items))

    async def get_skill(self, slug: str) -> RegistrySkillDetail | None:
        for item in self._items:
            if item.slug == slug:
                return RegistrySkillDetail(**item.model_dump())
        return None

    async def get_manifest(self, slug: str, version=None) -> dict | None:
        for item in self._items:
            if item.slug == slug:
                return item.manifest
        return None

    async def get_featured(self, limit: int = 10) -> list[RegistrySkillItem]:
        return self._items[:limit]

    async def get_tags(self) -> list[dict]:
        return [{"tag": "mock", "count": 1}]

    async def get_synergies(self, slug: str) -> list[dict] | None:
        return None

    async def publish_skill(self, manifest: dict) -> dict | None:
        return None

    async def report_install(self, slug: str) -> bool:
        return True

    async def report_effectiveness(self, slug: str, metric_type: str, value: float) -> bool:
        return True

    async def close(self) -> None:
        pass


def _make_item(slug: str, registry_id: str, install_count: int = 0) -> RegistrySkillItem:
    return RegistrySkillItem(
        slug=slug,
        name=slug,
        source_registry=registry_id,
        source_registry_name=registry_id,
        install_count=install_count,
    )


class TestRegistryAggregator:
    @pytest.mark.asyncio
    async def test_search_merges_multiple_adapters(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [_make_item("gene-a", "local"), _make_item("gene-b", "local")])
        external = _MockAdapter("deskhub", [_make_item("gene-b", "deskhub"), _make_item("gene-c", "deskhub")])
        agg = RegistryAggregator([local, external])

        result = await agg.search()
        slugs = [item.slug for item in result.items]
        assert "gene-a" in slugs
        assert "gene-b" in slugs
        assert "gene-c" in slugs
        assert len(result.items) == 3

        gene_b = next(item for item in result.items if item.slug == "gene-b")
        assert gene_b.source_registry == "local"

    @pytest.mark.asyncio
    async def test_search_handles_adapter_failure(self):
        from app.services.registry_aggregator import RegistryAggregator

        class FailingAdapter(_MockAdapter):
            async def search_skills(self, **kwargs):
                raise RuntimeError("network error")

        local = _MockAdapter("local", [_make_item("gene-a", "local")])
        failing = FailingAdapter("deskhub", [])
        agg = RegistryAggregator([local, failing])

        result = await agg.search()
        assert len(result.items) == 1
        assert result.items[0].slug == "gene-a"

    @pytest.mark.asyncio
    async def test_get_skill_priority(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [_make_item("gene-x", "local")])
        external = _MockAdapter("deskhub", [_make_item("gene-x", "deskhub")])
        agg = RegistryAggregator([local, external])

        detail = await agg.get_skill("gene-x")
        assert detail is not None
        assert detail.source_registry == "local"

    @pytest.mark.asyncio
    async def test_get_featured_dedupes_and_sorts(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [_make_item("gene-a", "local", install_count=5)])
        external = _MockAdapter("deskhub", [_make_item("gene-b", "deskhub", install_count=10)])
        agg = RegistryAggregator([local, external])

        featured = await agg.get_featured(limit=10)
        assert len(featured) == 2
        assert featured[0].slug == "gene-b"

    @pytest.mark.asyncio
    async def test_publish_routes_to_correct_adapter(self):
        from app.services.registry_aggregator import RegistryAggregator

        local = _MockAdapter("local", [])
        external = _MockAdapter("deskhub", [])
        agg = RegistryAggregator([local, external])

        result = await agg.publish_to("deskhub", {"slug": "test"})
        assert result is None

        result = await agg.publish_to("unknown", {"slug": "test"})
        assert result is None

    @pytest.mark.asyncio
    async def test_module_level_api(self):
        from app.services import registry_aggregator

        local = _MockAdapter("local", [_make_item("gene-a", "local")])
        registry_aggregator.init([local])

        agg = registry_aggregator.get_aggregator()
        assert agg is not None

        result = await agg.search()
        assert len(result.items) == 1

        await registry_aggregator.close()

        with pytest.raises(RuntimeError):
            registry_aggregator.get_aggregator()
