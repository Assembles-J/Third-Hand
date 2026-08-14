def test_main_aliases_application_after_governance_install():
    import app.main as main
    from app import application

    assert main is application
    assert main.app is application.app
    assert main.paper_trading_symbols.__module__ == "app.paper_runtime_integration"
    assert main.run_paper_trading_cycle.__module__ == "app.paper_runtime_integration"
