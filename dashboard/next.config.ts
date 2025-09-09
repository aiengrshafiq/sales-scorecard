import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  output: 'export',
   images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'i.pravatar.cc',
      },
      // This is a common hostname for Pipedrive user icons.
      // You may need to add others if Pipedrive uses different domains.
      {
        protocol: 'https',
        hostname: 'pipedrive-backend.s3.amazonaws.com',
      },
    ],
  },
};

export default nextConfig;
