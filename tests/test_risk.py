from risk.limits import RiskManager, RiskConfig

def make_rm():
    return RiskManager(RiskConfig(
        max_position_pct=0.20, max_total_exposure_pct=1.0,
        stop_loss_pct=0.10, take_profit_pct=0.20))

def test_position_size():
    rm = make_rm()

    assert rm.position_size("AAPL", price=200, equity=100_000) == 100

def test_per_asset_cap_blocks_oversized():
    rm = make_rm()
    ok, _ = rm.check_new_order("AAPL", qty=150, price=200,
                               equity=100_000, current_exposure=0)
    assert ok is False

def test_at_cap_allowed():
    rm = make_rm()
    ok, _ = rm.check_new_order("AAPL", qty=100, price=200,
                               equity=100_000, current_exposure=0)
    assert ok is True

def test_total_exposure_cap():
    rm = make_rm()
    ok, _ = rm.check_new_order("MSFT", qty=100, price=200,
                               equity=100_000, current_exposure=90_000)
    assert ok is False

def test_stop_loss():
    rm = make_rm()
    exit_now, _ = rm.check_stops(entry_price=200, current_price=178)
    assert exit_now is True

def test_take_profit():
    rm = make_rm()
    exit_now, _ = rm.check_stops(entry_price=200, current_price=245)
    assert exit_now is True

def test_within_limits_holds():
    rm = make_rm()
    exit_now, _ = rm.check_stops(entry_price=200, current_price=205)
    assert exit_now is False
