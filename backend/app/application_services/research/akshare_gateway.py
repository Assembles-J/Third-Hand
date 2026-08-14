"""Bridge allowlisted AKShare research interfaces into ResearchDataGateway."""
from __future__ import annotations

from typing import Callable, Mapping, Any

from app.domain.research.data_gateway import ProviderFetchResult, ResearchDataRequest, canonical_hash
from app.time_utils import beijing_now


class AkshareGatewayFetcher:
    """Callable provider adapter accepted by ``ResearchDataGateway``.

    Generic Registry calls cannot reliably infer the economic data's true
    reporting date from arbitrary schemas, so ``as_of`` defaults to retrieval
    time and the detail records that semantic explicitly. Specific Company
    adapters may provide stronger point-in-time semantics later.
    """

    def __init__(
        self,
        *,
        executor,
        interface_name: str,
        argument_builder: Callable[[ResearchDataRequest, tuple[str, ...], object | None], Mapping[str, Any]],
    ) -> None:
        self.executor = executor
        self.interface_name = str(interface_name)
        self.argument_builder = argument_builder

    def __call__(self, request: ResearchDataRequest, missing_coverage: tuple[str, ...], previous_snapshot):
        arguments = dict(self.argument_builder(request, missing_coverage, previous_snapshot))
        result = self.executor.execute(self.interface_name, arguments)
        now = beijing_now().isoformat()
        coverage = request.required_coverage_keys or missing_coverage
        return ProviderFetchResult(
            provider="akshare_registry",
            payload=result,
            as_of=now,
            available_at=now,
            source_reference=f"akshare:{self.interface_name}",
            coverage_keys=tuple(coverage),
            detail={
                "interface_name": self.interface_name,
                "arguments_hash": canonical_hash(arguments),
                "as_of_semantics": "retrieval_time_fallback",
                "usage_scope": "RESEARCH_ONLY",
            },
        )
