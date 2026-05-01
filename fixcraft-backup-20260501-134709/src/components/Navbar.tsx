"use client";

import Link from "next/link";
import { useState } from "react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
      <nav className="fixed top-0 left-0 right-0 z-50 bg-[#FAF7F2]/90 backdrop-blur-md border-b border-[#D4C4A8]/20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 sm:h-20 flex items-center justify-between">
        <Link href="/" className="text-[#2C1B0F] font-[family-name:var(--font-playfair)] text-2xl font-semibold tracking-tight">
          FixCraft<span className="text-[#A67C52]">VP</span>
        </Link>

        {/* Desktop */}
        <div className="hidden md:flex items-center gap-10 text-sm font-medium">
          <Link href="/" className="text-[#6B6560] hover:text-[#2C1B0F] transition-colors duration-300 uppercase tracking-[0.15em] text-xs">Home</Link>
          <Link href="/gallery" className="text-[#6B6560] hover:text-[#2C1B0F] transition-colors duration-300 uppercase tracking-[0.15em] text-xs">Gallery</Link>
          <Link href="/contact" className="text-[#6B6560] hover:text-[#2C1B0F] transition-colors duration-300 uppercase tracking-[0.15em] text-xs">Contact</Link>
          <Link href="/contact" className="bg-[#2C1B0F] text-[#FAF7F2] px-6 py-2 text-xs font-medium uppercase tracking-[0.15em] hover:bg-[#A67C52] transition-colors duration-300">
            Get a Quote
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-[#2C1B0F] hover:text-[#A67C52]"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {open ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {/* Mobile menu */}
      {open && (
        <div className="md:hidden bg-[#FAF7F2] border-t border-[#D4C4A8]/20 px-6 pb-8 flex flex-col gap-6 text-sm font-medium">
          <Link href="/" onClick={() => setOpen(false)} className="text-[#6B6560] hover:text-[#2C1B0F] transition-colors uppercase tracking-[0.15em] text-xs pt-6">Home</Link>
          <Link href="/gallery" onClick={() => setOpen(false)} className="text-[#6B6560] hover:text-[#2C1B0F] transition-colors uppercase tracking-[0.15em] text-xs">Gallery</Link>
          <Link href="/contact" onClick={() => setOpen(false)} className="text-[#6B6560] hover:text-[#2C1B0F] transition-colors uppercase tracking-[0.15em] text-xs">Contact</Link>
          <Link href="/contact" className="bg-[#2C1B0F] text-[#FAF7F2] px-6 py-3 text-xs font-medium uppercase tracking-[0.15em] text-center hover:bg-[#A67C52] transition-colors">
            Get a Quote
          </Link>
        </div>
      )}
    </nav>
  );
}
