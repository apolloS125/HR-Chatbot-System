import { loadEnvConfig } from "@next/env";
import type { NextConfig } from "next";

loadEnvConfig("..", process.env.NODE_ENV !== "production", console, true);

const nextConfig: NextConfig = {};

export default nextConfig;
