/** @type {import('next').NextConfig} */
const nextConfig = {
  // Strict mode u razvoju montira komponentu dvaput -> dva EventSource-a -> agent bi se pokrenuo dvaput
  // (i platio dvaput). Zato je iskljucen.
  reactStrictMode: false,
  devIndicators: false,   // Next-ov indikator u uglu prekriva odgovor u demu
};

export default nextConfig;
