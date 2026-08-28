def test_main_aliases_application_after_governance_install():
    import app.main as main
    from app import application

    assert main is application
    assert main.app is application.app
    # The governed paper runtime remains the execution/policy owner. Adaptive
    # scheduling wraps full research cadence, then execution-only polling is the
    # final public cycle wrapper so frozen decisions can consume later cached
    # quotes without rerunning analysis.
    assert main.paper_trading_symbols.__module__ == "app.adaptive_paper_runtime"
    assert main.run_paper_trading_cycle.__module__ == "app.paper_execution_poll_runtime"
    assert callable(main.execute_due_paper_decisions)
    assert main.execute_due_paper_decisions.__module__ == "app.paper_runtime_integration"
