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
      {
        protocol: 'https',
        hostname: 'e-cdns-images.dzcdn.net',
        pathname: '/images/**',
      },
      {
        protocol: 'https',
        hostname: 'cdns-images.dzcdn.net',
        pathname: '/images/**',
      },

      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
        pathname: '/**',
      },
      {
        protocol: 'https',
        hostname: 'i.ytimg.com',
        pathname: '/**',
      },
      {
        protocol: 'http',
        hostname: 'i.scdn.co',
        pathname: '/image/**',
      },
      {
        protocol: 'http',
        hostname: 'lastfm.freetls.fastly.net',
        pathname: '/i/**',
      },
      {
        protocol: 'http',
        hostname: 'www.theaudiodb.com',
        pathname: '/images/**',
      },
      {
        protocol: 'http',
        hostname: 'coverartarchive.org',
        pathname: '/**',
      },
      {
        protocol: 'http',
        hostname: 'e-cdns-images.dzcdn.net',
        pathname: '/images/**',
      },
      {
        protocol: 'http',
        hostname: 'cdns-images.dzcdn.net',
        pathname: '/images/**',
      },
    ],
  },
}

module.exports = nextConfig
