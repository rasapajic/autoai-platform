import { NextRequest, NextResponse } from 'next/server'

const BACKEND = 'https://autoai-platform-production.up.railway.app/api/v1'

export async function POST(request: NextRequest) {
  try {
    const body = await request.text()
    const auth = request.headers.get('authorization') || request.headers.get('Authorization') || ''

    const res = await fetch(`${BACKEND}/inbox/conversations/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': auth,
      },
      body,
    })

    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (e) {
    console.error('[Inbox Proxy POST] error:', e)
    return NextResponse.json({ error: 'Proxy error' }, { status: 500 })
  }
}

export async function GET(request: NextRequest) {
  try {
    const auth = request.headers.get('authorization') || request.headers.get('Authorization') || ''

    const res = await fetch(`${BACKEND}/inbox/conversations/`, {
      headers: { 'Authorization': auth },
    })

    const text = await res.text()

    try {
      const data = JSON.parse(text)
      return NextResponse.json(data, { status: res.status })
    } catch {
      return new NextResponse(text, { status: res.status })
    }
  } catch (e) {
    console.error('[Inbox Proxy GET] error:', e)
    return NextResponse.json({ error: 'Proxy error' }, { status: 500 })
  }
}
