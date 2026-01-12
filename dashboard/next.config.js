/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Allow connections to backend API
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/:path*',
      },
    ]
  },
}

module.exports = nextConfig
