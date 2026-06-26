/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**.autoscout24.com' },
      { protocol: 'https', hostname: '**.mobile.de' },
      { protocol: 'https', hostname: '**.polovniautomobili.com' },
    ],
  },
}

module.exports = nextConfig
