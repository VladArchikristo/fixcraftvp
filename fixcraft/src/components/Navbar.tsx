"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="nav-glass fixed top-0 left-0 right-0 z-50">
      <div className="max-w-7xl mx-auto px-6 sm:px-8 h-24 flex items-center justify-between">
        {/* Logo - Fixed overlapping */}
        <Link href="/" className="flex items-center gap-1 group flex-shrink-0">
          <span className="logo-fix text-3xl sm:text-4xl font-extrabold tracking-tight text-[#1B2A52]" style={{ fontFamily: 'var(--font-playfair)', lineHeight: '1' }}>Fix</span>
          <span className="logo-craft text-3xl sm:text-4xl font-extrabold tracking-tight text-[#B8922A]" style={{ fontFamily: 'var(--font-playfair)', lineHeight: '1' }}>Craft</span>
          <span className="logo-vp text-xl sm:text-2xl font-bold tracking-wide text-[#B8922A] ml-1" style={{ fontFamily: 'var(--font-playfair)', lineHeight: '1' }}>VP</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden lg:flex items-center gap-8 flex-shrink-0">
          <Link href="/" className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-xs font-bold uppercase tracking-widest">Home</Link>
          <Link href="/gallery" className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-xs font-bold uppercase tracking-widest">Gallery</Link>
          <Link href="/contact" className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-xs font-bold uppercase tracking-widest">Contact</Link>
          <Link href="/contact" className="btn-primary text-xs flex-shrink-0">
            Get a Quote
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          className="lg:hidden text-[#1B2A52] hover:text-[#B8922A] transition-colors p-2 flex-shrink-0"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="w-7 h-7" /> : <Menu className="w-7 h-7" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {open && (
        <div className="lg:hidden bg-[#FAF7F2] border-t border-[#E8E0D5] px-6 pb-8 pt-4">
          <div className="flex flex-col gap-6">
            <Link href="/" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-xs font-bold uppercase tracking-widest">Home</Link>
            <Link href="/gallery" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-xs font-bold uppercase tracking-widest">Gallery</Link>
            <Link href="/contact" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-xs font-bold uppercase tracking-widest">Contact</Link>
            <Link href="/contact" onClick={() => setOpen(false)} className="btn-primary text-xs text-center">
              Get a Quote
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
