import { NextRequest, NextResponse } from 'next/server'

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://autoai-platform-production.up.railway.app/api/v1'

export async function POST(request: NextRequest) {
  const token = request.headers.get('Authorization')
  const body = await request.text()
  
  const res = await fetch(`${API_BASE}/inbox/conversations/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': token || '',
    },
    body,
  })
  
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}

export async function GET(request: NextRequest) {
  const token = request.headers.get('Authorization')
  
  const res = await fetch(`${API_BASE}/inbox/conversations/`, {
    headers: { 'Authorization': token || '' },
  })
  
  const data = await res.json()
  return NextResponse.json(data, { status: res.status })
}
