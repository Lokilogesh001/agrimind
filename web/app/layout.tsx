import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = { title: 'AgriMind — Observable Crop Advisory', description: 'Multi-agent crop advisory with auditable decisions.' };
export default function RootLayout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
