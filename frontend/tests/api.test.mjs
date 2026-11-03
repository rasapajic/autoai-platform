import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

process.env.NEXT_PUBLIC_API_URL = 'https://api.example.test/api/v1'
const require = createRequire(import.meta.url)
let api
try {
  const ts = require('typescript')
  const source = readFileSync(new URL('../src/lib/api.ts', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  })
  api = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
} catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND' || Number(process.versions.node.split('.')[0]) < 24) throw error
  api = await import('../src/lib/api.ts')
}

const original = { fetch: globalThis.fetch, window: globalThis.window, localStorage: globalThis.localStorage }
let stored, calls, redirects
beforeEach(() => {
  stored = new Map([['autoai_token', 'current-session'], ['autoai_email', 'user@example.test'], ['autoai_name', 'User']])
  calls = []
  redirects = []
  globalThis.localStorage = { getItem: key => stored.get(key) ?? null, removeItem: key => stored.delete(key) }
  globalThis.window = { location: { replace: url => redirects.push(url) } }
  globalThis.fetch = async (url, options) => {
    calls.push({ url, options })
    return new Response(JSON.stringify([]), { status: 200 })
  }
})
afterEach(() => {
  for (const [key, value] of Object.entries(original)) {
    if (value === undefined) delete globalThis[key]
    else globalThis[key] = value
  }
})

test('makes, models, inbox and alerts carry the current session', async () => {
  await api.getMakes(1)
  await api.getModels('Alfa Romeo & DS')
  await api.getInboxStats()
  await api.getAlerts()
  assert.deepEqual(calls.map(call => call.url), [
    'https://api.example.test/api/v1/search/makes?min_count=1',
    'https://api.example.test/api/v1/search/models?make=Alfa%20Romeo%20%26%20DS',
    'https://api.example.test/api/v1/inbox/conversations/stats/summary',
    'https://api.example.test/api/v1/alerts/',
  ])
  for (const { options } of calls) assert.equal(new Headers(options.headers).get('Authorization'), 'Bearer current-session')
  stored.set('autoai_token', 'renewed-session')
  await api.getMakes()
  assert.equal(new Headers(calls.at(-1).options.headers).get('Authorization'), 'Bearer renewed-session')
})

test('POST requests keep authentication and their JSON body', async () => {
  await api.parseSearch('Golf dizel')
  await api.createAlert({ name: 'Golf', frequency: 'daily' })
  for (const { options } of calls) {
    assert.equal(options.method, 'POST')
    assert.equal(new Headers(options.headers).get('Authorization'), 'Bearer current-session')
    assert.equal(new Headers(options.headers).get('Content-Type'), 'application/json')
  }
  assert.deepEqual(JSON.parse(calls[0].options.body), { text: 'Golf dizel' })
  assert.deepEqual(JSON.parse(calls[1].options.body), { name: 'Golf', frequency: 'daily' })
})

test('expired sessions are removed and redirected instead of returning an empty catalog', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Prijava je istekla' }), { status: 401 })
  await assert.rejects(api.getMakes(), error => error.detail === 'Prijava je istekla')
  assert.equal(stored.size, 0)
  assert.deepEqual(redirects, ['/login'])
})

test('non-JSON 401 still clears the expired session', async () => {
  globalThis.fetch = async () => new Response('Unauthorized', { status: 401 })
  await assert.rejects(api.getModels('BMW'))
  assert.equal(stored.size, 0)
  assert.deepEqual(redirects, ['/login'])
})

test('failed login keeps the user on the login form', async () => {
  globalThis.fetch = async () => new Response(JSON.stringify({ detail: 'Pogrešna lozinka' }), { status: 401 })
  await assert.rejects(api.login({ email: 'user@example.test', password: 'wrong' }))
  assert.deepEqual(redirects, [])
})

test('server and network errors reject without erasing a valid session', async () => {
  globalThis.fetch = async () => new Response('Unavailable', { status: 503 })
  await assert.rejects(api.searchListings({}))
  globalThis.fetch = async () => { throw new TypeError('Network unavailable') }
  await assert.rejects(api.getMakes())
  assert.equal(stored.get('autoai_token'), 'current-session')
  assert.deepEqual(redirects, [])
})

test('missing sessions never send a fabricated bearer token', async () => {
  stored.clear()
  await api.getMakes()
  assert.equal(new Headers(calls[0].options.headers).get('Authorization'), null)
})

let modelTools
try {
  const ts = require('typescript')
  const source = readFileSync(new URL('../src/lib/model-options.ts', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
  modelTools = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
} catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND' || Number(process.versions.node.split('.')[0]) < 24) throw error
  modelTools = await import('../src/lib/model-options.ts')
}

test('model overview groups case variants, sorts names and retains numeric models', () => {
  const rows = modelTools.prepareModelOptions([
    { model: 'XF', count: 4 }, { model: 'F-Pace', count: 3 }, { model: 'f-pace', count: 2 },
    { model: '208', count: 8 }, { model: '', count: 5 }, { model: 'XJ', count: -1 },
  ])
  assert.deepEqual(rows, [{ model: '208', count: 8 }, { model: 'F-Pace', count: 5 }, { model: 'XF', count: 4 }])
  assert.throws(() => modelTools.prepareModelOptions({ error: 'Unavailable' }))
})

test('switching or removing a make clears the prior model and resets pagination', () => {
  const selected = { make: 'Jaguar', model: 'F', model_exact: true, page: 4, max_price: '20000' }
  for (const make of ['BMW', '']) {
    assert.deepEqual(modelTools.changeListingFilter(selected, 'make', make), { ...selected, make, model: '', model_exact: false, page: 1 })
  }
})

test('model selection is exact and survives other filter and page changes', () => {
  const initial = { make: 'Jaguar', model: '', model_exact: false, page: 4, max_price: '' }
  const selected = modelTools.changeListingFilter(initial, 'model', 'F')
  assert.equal(selected.model_exact, true)
  assert.equal(selected.page, 1)
  assert.equal(modelTools.changeListingFilter(selected, 'max_price', '15000').model, 'F')
  assert.equal(modelTools.changeListingFilter(selected, 'page', 2).model_exact, true)
  assert.equal(modelTools.changeListingFilter(selected, 'model', '').model_exact, false)
})

test('AI parsing keeps its partial search behavior and cannot retain another make model', () => {
  const selected = { make: 'Jaguar', model: 'F', model_exact: true, page: 3, max_price: '' }
  assert.equal(modelTools.mergeParsedFilters(selected, { make: 'BMW' }).model, '')
  assert.equal(modelTools.mergeParsedFilters(selected, { model: 'XF' }).model_exact, false)
  assert.equal(modelTools.mergeParsedFilters(selected, { max_price: '15000' }).model_exact, true)
  const partial = modelTools.mergeParsedFilters(selected, { model: 'F' })
  assert.equal(modelTools.changeListingFilter(partial, 'model', 'F').model_exact, true)
})

test('country selection combines with existing filters and all countries removes the restriction', async () => {
  const previous = { make: 'Jaguar', model: 'F-Pace', model_exact: true, country: '', max_price: '20000', page: 4 }
  for (const country of ['AT', 'BE', 'NL', 'IT', 'DE']) {
    const selected = modelTools.changeListingFilter(previous, 'country', country)
    assert.deepEqual(selected, { ...previous, country, page: 1 })
    await api.searchListings(selected)
    const params = new URL(calls.at(-1).url).searchParams
    assert.equal(params.get('country'), country)
    assert.equal(params.get('make'), 'Jaguar')
    assert.equal(params.get('model'), 'F-Pace')
    assert.equal(params.get('model_exact'), 'true')
    assert.equal(params.get('max_price'), '20000')
    assert.equal(params.get('page'), '1')
    const cleared = modelTools.changeListingFilter({ ...selected, page: 3 }, 'country', '')
    await api.searchListings(cleared)
    assert.equal(new URL(calls.at(-1).url).searchParams.has('country'), false)
    assert.equal(cleared.model_exact, true)
    assert.equal(cleared.page, 1)
  }
})

let recommendationTools
try {
  const ts = require('typescript')
  const source = readFileSync(new URL('../src/lib/listing-recommendation.ts', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
  recommendationTools = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
} catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND' || Number(process.versions.node.split('.')[0]) < 24) throw error
  recommendationTools = await import('../src/lib/listing-recommendation.ts')
}

const priceRecommendation = {
  status: 'consider', title: 'Vredi kontaktirati prodavca', reason: 'Cena je 10% ispod medijane 10 sličnih oglasa.',
  next_step: 'Zatraži VIN i pregled.', confidence: 'limited', cautions: ['Stanje zahteva proveru.'],
  comparison: { available: true, sample_size: 10, reference_price: 20000, delta_pct: -10, freshness_days: 7, reason: 'Uporediva vozila.' },
}

test('recommendation retains its concrete reason and never treats an AI score as buying evidence', () => {
  const result = recommendationTools.resolveRecommendation({ recommendation: priceRecommendation })
  assert.deepEqual(result, priceRecommendation)
  const unknown = recommendationTools.resolveRecommendation({ ai_score: 100, price_estimated: 30000, price_delta_pct: -50 })
  assert.equal(unknown.status, 'verify')
  assert.equal(unknown.confidence, 'insufficient')
  assert.match(unknown.reason, /Nema dovoljno podataka/)
})

test('critical and warning VIN mismatches override an attractive price and include the actual conflict', () => {
  for (const [severity, status] of [['critical', 'avoid'], ['warning', 'verify']]) {
    const result = recommendationTools.resolveRecommendation({ recommendation: priceRecommendation }, {
      mismatches: [{ severity, field: 'Gorivo', message: 'VIN navodi dizel, oglas benzin.' }],
    })
    assert.equal(result.status, status)
    assert.match(result.reason, /VIN navodi dizel, oglas benzin/)
    assert.equal(result.comparison.sample_size, 10)
    assert.match(result.next_step, /pre bilo kakve uplate/)
  }
})

test('high safety risk prevents a positive recommendation and VIN decode alone does not upgrade one', () => {
  const result = recommendationTools.resolveRecommendation({ recommendation: priceRecommendation }, null, {
    risk_level: 'high', red_flags: ['Sumnjiv način plaćanja'],
  })
  assert.equal(result.status, 'verify')
  assert.match(result.reason, /Sumnjiv način plaćanja/)
  assert.equal(recommendationTools.resolveRecommendation({}, { success: true, match_status: 'ok' }).status, 'verify')
  const avoided = { ...priceRecommendation, status: 'avoid', title: 'Preskoči po ovoj ceni' }
  assert.equal(recommendationTools.resolveRecommendation({ recommendation: avoided }, { match_status: 'ok' }).status, 'avoid')
})

let dateTools
try {
  const ts = require('typescript')
  const source = readFileSync(new URL('../src/lib/listing-dates.ts', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
  dateTools = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
} catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND' || Number(process.versions.node.split('.')[0]) < 24) throw error
  dateTools = await import('../src/lib/listing-dates.ts')
}

test('source date display preserves date-only precision without inventing midnight', () => {
  assert.equal(dateTools.formatListingDate('2025-11-01', 'date'), '1.11.2025.')
  assert.equal(dateTools.formatListingDate('2025-02-30', 'date'), 'Nije dostupno')
  assert.equal(dateTools.formatListingDate(undefined), 'Nije dostupno')
  assert.equal(dateTools.formatListingDate('2025-11-01T12:00:00'), 'Nije dostupno')
})

test('timestamp display uses Vienna winter and summer time independently of browser timezone', () => {
  assert.match(dateTools.formatListingDate('2025-11-01T12:00:00Z'), /13:00/)
  assert.match(dateTools.formatListingDate('2025-07-01T12:00:00Z'), /14:00/)
})
