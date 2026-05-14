import { NextRequest, NextResponse } from 'next/server'

const LANG_MAP: Record<string, string> = {
  DE: 'German', AT: 'German', CH: 'German',
  FR: 'French', IT: 'Italian', NL: 'Dutch',
  BE: 'Dutch', ES: 'Spanish', DK: 'Danish',
  SE: 'Swedish', NO: 'Norwegian', PL: 'Polish',
  RS: 'Serbian', HR: 'Croatian', BA: 'Bosnian',
}

export async function POST(req: NextRequest) {
  const { country, make, model, year, price, questions, custom_text } = await req.json()

  const lang = LANG_MAP[country] || 'German'
  const allQ = [...(questions || []), ...(custom_text?.trim() ? [custom_text] : [])]

  if (allQ.length === 0) {
    return NextResponse.json({ error: 'No questions provided' }, { status: 400 })
  }

  const prompt = `You are helping a Balkan car buyer write a professional inquiry to a European car seller.

Car listing details:
- Vehicle: ${year || ''} ${make || ''} ${model || ''}
- Listed price: ${price ? `${Number(price).toLocaleString()} EUR` : 'not specified'}
- Seller country: ${country}

The buyer wants to ask (written in their local Balkan language):
${allQ.map(q => `- ${q}`).join('\n')}

Write a professional, polite, and natural-sounding inquiry email/message in ${lang}.
Requirements:
- Start with an appropriate greeting
- Ask all the buyer's questions naturally and professionally
- Keep it concise (under 150 words)
- End with a polite closing and signature placeholder
- Sound like a genuine, educated buyer — not robotic
- Do NOT mention AI, translation, or that the message was generated
- Do NOT add extra commentary — output ONLY the message itself`

  try {
    const res = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': process.env.ANTHROPIC_API_KEY || '',
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: 'claude-haiku-4-5-20251001',
        max_tokens: 600,
        messages: [{ role: 'user', content: prompt }],
      }),
    })

    if (!res.ok) throw new Error(`API error: ${res.status}`)

    const data = await res.json()
    const message = data.content?.[0]?.text || ''
    return NextResponse.json({ message, language: lang })

  } catch (err) {
    console.error('Contact message error:', err)
    return NextResponse.json({ error: 'Failed to generate message' }, { status: 500 })
  }
}
