def test_runtime_exposes_v2_research_local_first_gateway():
    import app.main as runtime

    assert hasattr(runtime, "research_data_repository_v2")
    assert hasattr(runtime, "research_data_gateway_v2")
    assert runtime.research_data_gateway_v2.repository is runtime.research_data_repository_v2
