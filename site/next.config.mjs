/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // DEV ONLY: `next dev` cannot run the Python functions in api/. When testing locally, we run a
  // small stdlib shim (scripts/dev_api.py) on :8787 and proxy /api/* to it. In production this
  // returns [] so Vercel serves the real serverless functions untouched.
  async rewrites() {
    if (process.env.NODE_ENV === "production") return [];
    return [{ source: "/api/:path*", destination: "http://127.0.0.1:8787/api/:path*" }];
  },
};

export default nextConfig;
