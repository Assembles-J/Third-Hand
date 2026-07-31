from app.relative_strength import RelativeStrengthService


def test_relative_strength_requests_benchmark_configuration_before_calling_upstream():
    result = RelativeStrengthService().assess([], None, None)
    assert result["status"] == "not_configured"
