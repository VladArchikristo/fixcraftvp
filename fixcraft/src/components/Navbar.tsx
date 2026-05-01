"use client";

import Link from "next/link";
import { useState } from "react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="fixed top-0 left-0 right-0 z-50 bg-gray-950/80 backdrop-blur-md border-b border-white/10">
      <div className="max-w-6xl mx-auto px-4 h-16 flex items-center justify-between">
        <Link href="/" className="text-xl font-bold tracking-tight">
          FixCraft<span className="text-amber-400">VP</span>
        </Link>

        {/* Desktop */}
        <div className="hidden md:flex items-center gap-8 text-sm font-medium">
          <Link href="/" className="text-gray-300 hover:text-white transition-colors">Home</Link>
          <Link href="/gallery" className="text-gray-300 hover:text-white transition-colors">Gallery</Link>
          <Link href="/contact" className="text-gray-300 hover:text-white transition-colors">Contact</Link>
          <a
            href="tel:7865660753"
            className="bg-amber-400 text-gray-950 px-4 py-2 rounded-full font-semibold hover:bg-amber-300 transition-colors"
          >
            (786) 566-0753
          </a>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-gray-300 hover:text-white"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-gray-950 border-t border-white/10 px-4 pb-4 flex flex-col gap-4 text-sm font-medium">
          <Link href="/" onClick={() => setOpen(false)} className="text-gray-300 hover:text-white pt-4">Home</Link>
          <Link href="/gallery" onClick={() => setOpen(false)} className="text-gray-300 hover:text-white">Gallery</Link>
          <Link href="/contact" onClick={() => setOpen(false)} className="text-gray-300 hover:text-white">Contact</Link>
          <a href="tel:7865660753" className="bg-amber-400 text-gray-950 px-4 py-2 rounded-full font-semibold text-center">
            (786) 566-0753
          </a>
        </div>
      )}
    </nav>
  );
}
