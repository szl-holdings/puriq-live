/* PURIQ signed-price inspection. Fixed same-origin read API; no trading actions. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const text = (id, value) => { $(id).textContent = value; };
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const label = value => typeof value === 'string' ? value : 'UNAVAILABLE';
  let expiryTimer = null;
  let expiresAt = null;

  function decision(value, state) {
    text('decision', value);
    $('decision').dataset.state = state;
  }

  function reasons(items) {
    $('reasons').replaceChildren();
    items.forEach(value => {
      const item = document.createElement('li');
      item.textContent = value;
      $('reasons').append(item);
    });
  }

  function reset() {
    clearTimeout(expiryTimer);
    expiryTimer = null;
    expiresAt = null;
    decision('NOT OBSERVED', 'idle');
    text('observation-heading', $('symbol').value + ' / USD');
    ['price', 'authenticity', 'freshness', 'sources'].forEach(id => text(id, '—'));
    text('price-note', 'A price appears only when the full record passes the review policy.');
    text('checked', 'No check completed.');
    text('scope', 'No signature checked.');
    text('source-time', 'No authenticated event time.');
    text('receipt-hash', 'UNAVAILABLE');
    text('key-source', 'UNAVAILABLE');
    text('key-trust', 'No keyring retrieved.');
    text('receipt', 'No receipt available.');
    text('provider', 'No provider data available.');
    text('provider-warning', 'No provider data available.');
    $('provider-warning').classList.remove('warning');
    $('status').classList.remove('warning');
    reasons(['No observation to evaluate.']);
  }

  function expireObservation() {
    if (expiresAt === null || performance.now() < expiresAt) return;
    clearTimeout(expiryTimer);
    expiryTimer = null;
    expiresAt = null;
    decision('REPORTED · ABSTAIN', 'abstain');
    text('price', '—');
    text('price-note', 'The review window expired. Refresh for a new observation.');
    text('freshness', 'Expired');
    text('status', 'ABSTAIN — the checked observation has expired. Refresh to inspect a new public sample.');
    $('status').classList.add('warning');
    reasons(['OBSERVATION_EXPIRED — the displayed check exceeded the freshness window. The receipt preserves the original check.']);
  }

  function render(body, symbol, requestStartedAt) {
    if (!object(body) || !object(body.verification) || !object(body.receipt) ||
        !object(body.provider_print) || body.symbol !== symbol ||
        !['REVIEW', 'ABSTAIN'].includes(body.status) || body.truth_label !== 'REPORTED' ||
        body.trading_enabled !== false) {
      throw new Error('Invalid observation response');
    }
    const verification = body.verification;
    const provider = body.provider_print;
    const receipt = body.receipt;
    const authenticated = verification.core_valid === true && verification.record_valid === true &&
      verification.verification_scope === 'full-record';
    const priceValid = typeof body.price_text === 'string' && /^\d+(?:\.\d+)?$/.test(body.price_text);
    const eventTime = typeof provider.at === 'string' ? Date.parse(provider.at) : NaN;
    const maxAge = object(receipt.policy) ? receipt.policy.max_age_seconds : NaN;
    const remaining = typeof maxAge === 'number' && maxAge > 0 && Number.isFinite(maxAge) &&
      typeof receipt.observed_at === 'number' && Number.isFinite(receipt.observed_at) && Number.isFinite(eventTime)
      ? maxAge * 1000 - (receipt.observed_at * 1000 - eventTime) - (performance.now() - requestStartedAt) : NaN;
    const review = body.status === 'REVIEW' && authenticated && verification.fresh === true && priceValid && remaining > 0;
    const decisionReasons = Array.isArray(body.decision_reasons)
      ? body.decision_reasons.filter(value => typeof value === 'string') : [];

    decision(review ? 'REPORTED · REVIEW' : 'REPORTED · ABSTAIN', review ? 'review' : 'abstain');
    text('price', review ? body.price_text : '—');
    text('price-note', review
      ? 'Authenticated reported price at the time of this check. For review only.'
      : 'Price withheld. This observation does not meet the full-record review policy.');
    text('authenticity', authenticated ? 'Full record' : verification.core_valid === true ? 'Price only' : 'Not verified');
    text('scope', authenticated ? 'Core price and record signatures valid against the provider keyring.'
      : verification.core_valid === true ? 'Core signature valid; record metadata is not authenticated.'
      : 'Provider data have not passed signature verification.');
    text('freshness', authenticated ? (verification.fresh === true
      ? remaining <= 0 ? 'Expired' : 'Fresh at check' : 'Not fresh') : 'Not established');
    text('source-time', authenticated && typeof provider.at === 'string' ? 'Event time: ' + provider.at
      : authenticated && typeof provider.at === 'number' ? 'Provider event time: ' + provider.at
      : 'No authenticated event time.');
    text('sources', authenticated && Number.isInteger(provider.sources) && provider.sources >= 0
      ? String(provider.sources) : '—');
    if (typeof receipt.observed_at === 'number' && Number.isFinite(receipt.observed_at)) {
      const checked = new Date(receipt.observed_at * 1000);
      if (Number.isFinite(checked.getTime())) text('checked', 'Checked ' + checked.toISOString().replace('.000Z', ' UTC'));
    }
    text('receipt-hash', label(receipt.receipt_id));
    text('key-source', label(receipt.key_source_url));
    text('key-trust', label(receipt.key_trust));
    text('receipt', JSON.stringify(receipt, null, 2));
    text('provider', JSON.stringify(provider, null, 2));
    text('provider-warning', authenticated
      ? 'Signature-authenticated provider claims. Market accuracy and source independence are not verified.'
      : 'UNTRUSTED PROVIDER DATA — the full record is not authenticated. Values here are diagnostic claims only.');
    $('provider-warning').classList.toggle('warning', !authenticated);
    if (review) {
      reasons(['The observation passed the configured review policy. Market accuracy and source independence remain unverified.']);
    } else {
      reasons(decisionReasons.length ? decisionReasons : [remaining <= 0
        ? 'OBSERVATION_EXPIRED — the reported check exceeded its freshness window.'
        : 'Full-record review requirements were not satisfied.']);
    }
    text('status', review
      ? 'REVIEW — reported observation passed the review policy at check time. Trading remains disabled.'
      : 'ABSTAIN — reported observation withheld from review. Inspect the decision reasons and receipt.');
    $('status').classList.toggle('warning', !review);
    if (review) {
      expiresAt = performance.now() + remaining;
      // One local expiry, never a fetch loop. Use server/event time and a monotonic
      // elapsed clock so client wall-clock skew cannot keep a price eligible.
      expiryTimer = setTimeout(expireObservation, Math.ceil(remaining) + 1);
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) expireObservation();
  });

  $('symbol').addEventListener('change', () => {
    reset();
    text('status', 'NOT OBSERVED — refresh to inspect a signed public sample for ' + $('symbol').value + '.');
  });

  $('controls').addEventListener('submit', async event => {
    event.preventDefault();
    const symbol = $('symbol').value;
    reset();
    $('refresh').disabled = true;
    $('symbol').disabled = true;
    $('controls').setAttribute('aria-busy', 'true');
    text('status', 'Checking the public provider record and keyring…');
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 25000);
    try {
      const query = new URLSearchParams({symbol});
      // Deduct the entire request round trip conservatively, including time
      // before response headers arrive, so delivery delay cannot extend freshness.
      const requestStartedAt = performance.now();
      const response = await fetch('/api/puriq/v1/signed-price?' + query, {
        method: 'GET', headers: {Accept: 'application/json'}, cache: 'no-store', signal: controller.signal
      });
      if (!response.ok) throw new Error('Observation unavailable');
      render(await response.json(), symbol, requestStartedAt);
    } catch (_) {
      reset();
      decision('UNAVAILABLE', 'unavailable');
      text('price-note', 'No usable observation. Refresh to try the public source again.');
      text('status', 'UNAVAILABLE — the public source, keyring, or verification response could not be checked.');
      $('status').classList.add('warning');
      reasons(['No valid observation received. No price is displayed.']);
    } finally {
      clearTimeout(timeout);
      $('refresh').disabled = false;
      $('symbol').disabled = false;
      $('controls').removeAttribute('aria-busy');
    }
  });
})();
