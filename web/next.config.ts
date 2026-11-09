import type { NextConfig } from "next";

const apiOrigin = process.env.RTC_API_ORIGIN ?? "http://127.0.0.1:8000";

const config: NextConfig = {
  distDir: process.env.RTC_NEXT_DIST_DIR ?? '.next',
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: apiOrigin + "/:path*" }];
  },
};

export default config;
