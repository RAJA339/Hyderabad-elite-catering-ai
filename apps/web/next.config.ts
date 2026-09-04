import type { NextConfig } from "next";

// `output: "standalone"` produces the self-contained server the Docker image needs, but it
// relocates the build output in a way Vercel's own pipeline cannot trace, failing with
// ENOENT on .next/next-server.js.nft.json. Vercel sets VERCEL=1, so skip it there.
const isVercel = Boolean(process.env.VERCEL);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  ...(isVercel ? {} : { output: "standalone" as const }),
};

export default nextConfig;
