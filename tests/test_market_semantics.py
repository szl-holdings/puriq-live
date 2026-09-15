"""No shifted labels, fabricated zeroes, or time-window substitution."""
import pytest
import httpx
from puriq_market import normalize_polymarket, PuriqClient, SourceUnavailable, _bounded_get_json


def row(**overrides):
    data = dict(outcomes=['Yes', 'No'], outcomePrices=['0.6', '0.4'], active=True, closed=False)
    data.update(overrides)
    return normalize_polymarket([data], limit=1)['markets'][0]


@pytest.mark.parametrize('invalid', ['bad', None, True, -0.1, 1.1, float('nan'), float('inf')])
def test_invalid_price_does_not_shift_onto_yes(invalid):
    value = row(outcomePrices=[invalid, '0.4'])
    assert value['yes_probability'] is None
    assert value['outcomes'][0]['probability'] is None
    assert value['outcomes'][1]['probability'] == .4


def test_reversed_yes_no_uses_label_not_position():
    assert row(outcomes=['No', 'Yes'], outcomePrices=[.4, .6])['yes_probability'] == .6


@pytest.mark.parametrize('outcomes', [['A', 'B'], ['Yes', 'Yes'], ['Yes'], ['Yes', 'No', 'Other']])
def test_never_infers_yes_on_unknown_or_mismatched_schema(outcomes):
    assert row(outcomes=outcomes)['yes_probability'] is None


def test_zero_24h_volume_is_not_lifetime_volume():
    assert row(volume24hr=0, volume=123456)['volume_24h'] == 0
    missing = row(volume=123456)
    assert missing['volume_24h'] is None
    assert missing['volume_lifetime'] == 123456


def test_crossed_book_is_not_zero_spread():
    observed = row(bestBid=.8, bestAsk=.2, liquidityNum=100, volume24hr=100)
    assert observed['spread'] is None
    assert observed['liquidity_quality']['score'] is None
    assert 'CROSSED_BOOK' in observed['data_quality_flags']


def test_missing_aggregates_are_unknown_not_zero():
    empty = normalize_polymarket([], limit=1)
    assert empty['volume_24h_total'] is None
    assert empty['liquidity_total'] is None
    assert empty['volume_24h_observed_rows'] == 0


def test_negative_or_boolean_liquidity_and_string_active_not_admitted():
    assert row(liquidityNum=-1)['liquidity'] is None
    assert row(liquidityNum=True)['liquidity'] is None
    assert row(active='false')['active'] is False


def test_coinbase_wrong_pair_is_rejected():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={'data':{'base':'ETH','currency':'USD','amount':'1'}}))
    with pytest.raises(SourceUnavailable, match='pair'):
        PuriqClient(transport).coinbase('BTC', 'USD')


def test_unexpected_port_is_not_an_allowed_destination():
    with pytest.raises(SourceUnavailable):
        _bounded_get_json('https://api.coinbase.com:444/v2/prices/BTC-USD/spot', max_bytes=100)


def test_ui_nulls_and_unobserved_sources_are_not_painted_green():
    from app import HTML_TEMPLATE
    assert "if(value===null||value===undefined||value==='')return 'UNAVAILABLE'" in HTML_TEMPLATE
    assert "receipts[id]&&observations[id]" in HTML_TEMPLATE


@pytest.mark.parametrize("invalid", [10 ** 1000, 1e308, -1, True])
def test_invalid_volume_domain_stays_unavailable(invalid):
    value = row(volume24hr=invalid)
    assert value["volume_24h"] is None


def test_all_missing_or_zero_summary_preserves_coverage():
    missing = normalize_polymarket([{"outcomes": ["Yes", "No"], "outcomePrices": [.5, .5]}], limit=1)
    zero = normalize_polymarket([{"outcomes": ["Yes", "No"], "outcomePrices": [.5, .5], "volume24hr": 0}], limit=1)
    assert missing["volume_24h_total"] is None and missing["volume_24h_observed_rows"] == 0
    assert zero["volume_24h_total"] == 0 and zero["volume_24h_observed_rows"] == 1
