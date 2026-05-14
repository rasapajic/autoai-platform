import { NextRequest, NextResponse } from 'next/server'

const CLAUDE = 'claude-haiku-4-5-20251001'
const API    = 'https://api.anthropic.com/v1/messages'

async function callClaude(prompt: string, maxTokens = 800): Promise<string> {
  const res = await fetch(API, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': process.env.ANTHROPIC_API_KEY || '',
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: CLAUDE, max_tokens: maxTokens,
      messages: [{ role: 'user', content: prompt }],
    }),
  })
  const data = await res.json()
  return data.content?.[0]?.text || ''
}

function parseJSON(raw: string): any {
  try {
    return JSON.parse(raw.replace(/```json|```/g, '').trim())
  } catch { return {} }
}

export async function POST(req: NextRequest) {
  const { url, text } = await req.json()

  let content = text || ''

  // ── Try to fetch URL ──────────────────────────────────────
  if (url && !text) {
    try {
      const res = await fetch(url, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36',
          'Accept': 'text/html,application/xhtml+xml',
          'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
        },
        signal: AbortSignal.timeout(12000),
      })
      const html = await res.text()
      content = html
        .replace(/<script[\s\S]*?<\/script>/gi, '')
        .replace(/<style[\s\S]*?<\/style>/gi, '')
        .replace(/<[^>]+>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 9000)
    } catch {
      return NextResponse.json({
        success: false,
        error: 'fetch_failed',
        message: 'Ne mogu da pristupim oglasu. Kopiraj i nalepi tekst oglasa ispod.',
      })
    }
  }

  if (!content.trim()) {
    return NextResponse.json({ success: false, error: 'no_content', message: 'Nema sadržaja za analizu.' })
  }

  // ── Step 1: Extract structured listing data ───────────────
  const extractPrompt = `Extract car listing data from this content.
${url ? `Source URL: ${url}` : 'Source: manual paste'}

Content:
${content.slice(0, 7000)}

Return ONLY valid JSON (no markdown, no backticks, no extra text):
{
  "title": "full listing title",
  "make": "brand name or null",
  "model": "model name or null",
  "year": 2020,
  "price": 15000,
  "currency": "EUR",
  "mileage": 85000,
  "fuel_type": "diesel",
  "transmission": "automatic",
  "engine_power_kw": 110,
  "body_type": "sedan",
  "color": "black",
  "country": "DE",
  "city": "München",
  "description": "brief description max 200 chars",
  "source_site": "autoscout24"
}`

  const listing = parseJSON(await callClaude(extractPrompt, 900))

  if (!listing.make && !listing.title) {
    return NextResponse.json({
      success: false,
      error: 'parse_failed',
      message: 'Ne mogu da prepoznam oglas. Pokušaj da nalepljuješ tekst oglasa.',
    })
  }

  // ── Step 2: AI Analysis ───────────────────────────────────
  const analyzePrompt = `Analyze this European car listing for a buyer in Serbia/Balkans planning to import it.

Vehicle: ${listing.year || '?'} ${listing.make || '?'} ${listing.model || '?'}
Price: ${listing.price || '?'} ${listing.currency || 'EUR'}
Mileage: ${listing.mileage || '?'} km
Fuel: ${listing.fuel_type || '?'}
Transmission: ${listing.transmission || '?'}
Country: ${listing.country || '?'}
${listing.description ? `Description: ${listing.description}` : ''}

Consider: Serbian import taxes (5% customs + 20% VAT), transport costs (~420 EUR), registration (~280 EUR).

Return ONLY valid JSON:
{
  "price_rating": "great",
  "price_delta_pct": -8.5,
  "market_price_estimate": 16500,
  "buying_insight": "Kratka preporuka na srpskom max 65 znakova",
  "risk_flags": ["rizik 1 na srpskom ako postoji"],
  "safe_signals": ["pozitivan signal 1 na srpskom ako postoji"],
  "recommendation": "KUPI",
  "notes": "2-3 rečenice o ovom autu za srpsko tržište na srpskom jeziku"
}

price_rating must be one of: great, good, fair, high, overpriced
recommendation must be one of: KUPI, RAZMATRAJ, IZBEGNI`

  const analysis = parseJSON(await callClaude(analyzePrompt, 700))

  return NextResponse.json({ success: true, url, listing, analysis })
}
