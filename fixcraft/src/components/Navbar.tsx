"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="nav-glass fixed top-0 left-0 right-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 h-18 sm:h-20 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-0 group">
          <span className="logo-fix text-2xl sm:text-3xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-playfair)' }}>Fix</span>
          <span className="logo-craft text-2xl sm:text-3xl font-bold tracking-tight" style={{ fontFamily: 'var(--font-playfair)' }}>Craft</span>
          <span className="logo-craft text-lg sm:text-xl font-normal tracking-wide ml-0.5" style={{ fontFamily: 'var(--font-playfair)' }}>VP</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-10">
          <Link href="/" className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors text-xs font-semibold uppercase tracking-widest">Home</Link>
          <Link href="/gallery" className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors text-xs font-semibold uppercase tracking-widest">Gallery</Link>
          <Link href="/contact" className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors text-xs font-semibold uppercase tracking-widest">Contact</Link>
          <Link href="/contact" className="btn-primary text-xs">
            Get a Quote
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          className="md:hidden text-[#1e3a5f] hover:text-[#8B6A45] transition-colors p-2"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {open && (
        <div className="md:hidden bg-[#FAF7F2] border-t border-[#E8E0D5] px-6 pb-8">
          <div className="flex flex-col gap-6 pt-6">
            <Link href="/" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors text-xs font-semibold uppercase tracking-widest">Home</Link>
            <Link href="/gallery" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors text-xs font-semibold uppercase tracking-widest">Gallery</Link>
            <Link href="/contact" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1e3a5f] transition-colors text-xs font-semibold uppercase tracking-widest">Contact</Link>
            <Link href="/contact" onClick={() => setOpen(false)} className="btn-primary text-xs text-center">
              Get a Quote
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
