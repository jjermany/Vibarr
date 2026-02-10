/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = process.env.INTERNAL_API_URL || 'http://127.0.0.1:8000'
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/health',
        destination: `${backendUrl}/health`,
      },
      {
        source: '/health/:path*',
        destination: `${backendUrl}/health/:path*`,
      },
      {
        source: '/docs',
        destination: `${backendUrl}/docs`,
      },
      {
        source: '/openapi.json',
        destination: `${backendUrl}/openapi.json`,
      },
    ]
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'i.scdn.co',
        pathname: '/image/**',
      },
      {
        protocol: 'https',
        hostname: 'lastfm.freetls.fastly.net',
        pathname: '/i/**',
      },
      {
        protocol: 'https',
        hostname: 'www.theaudiodb.com',
        pathname: '/images/**',
      },
      {
        protocol: 'https',
        hostname: 'coverartarchive.org',
        pathname: '/**',
      },
    ],
  },
}

module.exports = nextConfig
