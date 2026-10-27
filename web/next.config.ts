import type { NextConfig } from 'next';

const envOrigins = process.env.ALLOWED_DEV_ORIGINS
  ? process.env.ALLOWED_DEV_ORIGINS.split(',').map((s) => s.trim())
  : [];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  allowedDevOrigins: Array.from(new Set(['10.241.255.20', ...envOrigins].filter(Boolean))),
};

export default nextConfig;

