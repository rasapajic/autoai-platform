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

let navigationTools
try {
  const ts = require('typescript')
  const source = readFileSync(new URL('../src/lib/search-navigation.ts', import.meta.url), 'utf8')
  const { outputText } = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } })
  navigationTools = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString('base64')}`)
} catch (error) {
  if (error.code !== 'MODULE_NOT_FOUND' || Number(process.versions.node.split('.')[0]) < 24) throw error
  navigationTools = await import('../src/lib/search-navigation.ts')
}

test('return from a listing retains exact model, all filters, sorting, AI text and page seven', () => {
  const initial = new URLSearchParams('make=Jaguar&model=F-Pace&model_exact=true&country=DE&min_price=8000&max_price=10000&min_year=2015&max_year=2023&max_km=150000&fuel_type=diesel&price_rating=good&sort_by=price_asc&page=7&transmission=automatic&body_type=suv')
  const filters = navigationTools.searchFiltersFromParams(initial)
  const url = navigationTools.searchUrl(filters, 'Jaguar do 10000€')
  const href = navigationTools.listingHref('listing-123', url)
  const returnTo = new URL(href, 'https://app.test').searchParams.get('returnTo')
  const back = navigationTools.resolveReturnUrl(returnTo, '', 'https://app.test', href, '/search')
  const restored = new URL(navigationTools.restoreSearchHref(back), 'https://app.test')
  assert.deepEqual(navigationTools.searchFiltersFromParams(restored.searchParams), filters)
  assert.equal(restored.searchParams.get('q'), 'Jaguar do 10000€')
  assert.equal(restored.searchParams.get('restore'), '1')
  assert.equal(filters.page, 7)
})

test('search URL parsing keeps zero values, exact-match state and valid page defaults', () => {
  for (const page of ['', '-1', '0', '1.5', 'NaN', 'Infinity', '9007199254740992']) {
    assert.equal(navigationTools.searchFiltersFromParams(new URLSearchParams({ page })).page, 1)
  }
  const url = navigationTools.searchUrl({ make: 'Citroën & DS', model: 'C_4%', model_exact: true, min_price: 0, page: 3 }, '', '/')
  const parsed = navigationTools.searchFiltersFromParams(new URL(url, 'https://app.test').searchParams)
  assert.equal(parsed.make, 'Citroën & DS')
  assert.equal(parsed.model, 'C_4%')
  assert.equal(parsed.model_exact, true)
  assert.equal(parsed.min_price, '0')
  assert.equal(parsed.page, 3)
  assert.equal(navigationTools.searchUrl({ page: 1, sort_by: 'date', model_exact: false }), '/search')
})

test('back targets use the actual previous internal page and retain a safe new-tab fallback', () => {
  const origin = 'https://app.test'
  assert.equal(navigationTools.resolveReturnUrl('/search?page=7', origin+'/favorites', origin, '/listing/123', '/search'), '/favorites')
  assert.equal(navigationTools.resolveReturnUrl('/search?page=7', origin+'/listing/previous', origin, '/listing/123', '/search'), '/listing/previous')
  assert.equal(navigationTools.resolveReturnUrl('/search?page=7', 'https://external.test/', origin, '/listing/123', '/search'), '/search?page=7')
  assert.equal(navigationTools.resolveReturnUrl('/search?page=7', origin+'/listing/123', origin, '/listing/123', '/search'), '/search?page=7')
  assert.equal(navigationTools.resolveReturnUrl('/search?page=7', origin+'/', origin, '/listing/123', '/search'), '/search?page=7')
  assert.equal(navigationTools.resolveReturnUrl(null, '', origin, '/listing/123', null), '/search')
  assert.equal(navigationTools.restoreSearchHref('/favorites'), '/favorites')
})

test('return targets reject external, script, authentication, API and disguised redirect paths', () => {
  for (const path of ['https://evil.test', '//evil.test', '/\\evil.test', 'javascript:alert(1)', '/login', '/api/v1/users/logout', '/%2f%2fevil.test', '/search\n?x=1']) {
    assert.equal(navigationTools.safeReturnUrl(path), null, path)
  }
})

test('return snapshots keep list position and independent filter scroll per search context', () => {
  const values = new Map()
  const storage = { getItem: k => values.get(k) || null, setItem: (k,v) => values.set(k,v) }
  const snapshot = { url: '/search?country=DE&page=7', y: 1350, filterY: 220, modelY: 80, otherMakesOpen: true, mobileFiltersOpen: false, listingId: 'car-7', listingOffset: 140 }
  navigationTools.rememberSearch(storage, snapshot)
  navigationTools.rememberSearch(storage, { ...snapshot, url: '/search?country=AT&page=2', y: 300, filterY: 0 })
  assert.deepEqual(navigationTools.savedSearch(storage, snapshot.url), snapshot)
  assert.equal(navigationTools.restoredScrollY(snapshot, 0, 1630), 1490)
  assert.equal(navigationTools.restoredScrollY(snapshot, 0), 1350)
  assert.equal(navigationTools.restoredScrollY(snapshot, 0, 50), 0)
})

test('disabled or corrupt session storage does not prevent a return through the URL', () => {
  const blocked = { getItem: () => { throw Error('blocked') }, setItem: () => { throw Error('full') } }
  const snapshot = { url: '/search?page=7', y: 1350, filterY: 220, modelY: 0, otherMakesOpen: false, mobileFiltersOpen: false }
  assert.doesNotThrow(() => navigationTools.rememberSearch(blocked, snapshot))
  assert.equal(navigationTools.savedSearch(blocked, snapshot.url), null)
  let value = 'invalid-json'
  const corrupt = { getItem: () => value, setItem: (k,v) => { if (k === 'autoai_search_snapshots') value = v } }
  assert.equal(navigationTools.savedSearch(corrupt, snapshot.url), null)
  navigationTools.rememberSearch(corrupt, snapshot)
  assert.deepEqual(navigationTools.savedSearch(corrupt, snapshot.url), snapshot)
})

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
