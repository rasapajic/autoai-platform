import { NextRequest, NextResponse } from 'next/server'
const BACKEND = 'https://autoai-platform-production.up.railway.app/api/v1'
export async function POST(request: NextRequest) {
  try {
    const body = await request.text()
    const auth = request.headers.get('authorization') || request.headers.get('Authorization') || ''
    const res = await fetch(`${BACKEND}/inbox/analyze-reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': auth },
      body,
    })
    const data = await res.json()
    return NextResponse.json(data, { status: res.status })
  } catch (e) {
    return NextResponse.json({ error: 'Proxy error' }, { status: 500 })
  }
}
