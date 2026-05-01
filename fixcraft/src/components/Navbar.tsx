"use client";

import Link from "next/link";
import { useState } from "react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="nav-glass fixed top-0 left-0 right-0 z-50">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 h-16 sm:h-20 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-1">
          <span className="logo-fix text-2xl font-bold tracking-tight">Fix</span>
          <span className="logo-craft text-2xl font-bold tracking-tight">Craft VP</span>
        </Link>

        {/* Desktop */}
        <div className="hidden md:flex items-center gap-10 text-sm font-medium">
          <Link href="/" className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors duration-300 uppercase tracking-[0.15em] text-xs">Home</Link>
          <Link href="/gallery" className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors duration-300 uppercase tracking-[0.15em] text-xs">Gallery</Link>
          <Link href="/contact" className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors duration-300 uppercase tracking-[0.15em] text-xs">Contact</Link>
          <Link href="/contact" className="btn-primary text-xs px-6 py-2">
            Get a Quote
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden text-[#1e3a5f] hover:text-[#8B6A45]"
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
        <div className="md:hidden bg-[#FAF7F2] border-t border-[#E8E0D5] px-6 pb-8 flex flex-col gap-6 text-sm font-medium">
          <Link href="/" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors uppercase tracking-[0.15em] text-xs pt-6">Home</Link>
          <Link href="/gallery" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors uppercase tracking-[0.15em] text-xs">Gallery</Link>
          <Link href="/contact" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors uppercase tracking-[0.15em] text-xs">Contact</Link>
          <Link href="/contact" className="btn-primary text-xs px-6 py-3 text-center">
            Get a Quote
          </Link>
        </div>
      )}
    </nav>
  );
}
