"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="nav-glass fixed top-0 left-0 right-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-0 group">
          <span className="logo-fix logo-text">Fix</span>
          <span className="logo-craft logo-text">Craft</span>
          <span className="logo-vp logo-text">VP</span>
        </Link>

        {/* Desktop Navigation */}
        <div className="hidden md:flex items-center gap-12">
          <Link href="/" className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-sm font-bold uppercase tracking-widest">Home</Link>
          <Link href="/gallery" className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-sm font-bold uppercase tracking-widest">Gallery</Link>
          <Link href="/contact" className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-sm font-bold uppercase tracking-widest">Contact</Link>
          <Link href="/contact" className="btn-primary text-sm">
            Get a Quote
          </Link>
        </div>

        {/* Mobile Menu Button */}
        <button
          className="md:hidden text-[#1B2A52] hover:text-[#B8922A] transition-colors p-2"
          onClick={() => setOpen(!open)}
          aria-label="Toggle menu"
        >
          {open ? <X className="w-7 h-7" /> : <Menu className="w-7 h-7" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {open && (
        <div className="md:hidden bg-[#FAF7F2] border-t border-[#E8E0D5] px-6 pb-8 pt-4">
          <div className="flex flex-col gap-8">
            <Link href="/" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-sm font-bold uppercase tracking-widest">Home</Link>
            <Link href="/gallery" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-sm font-bold uppercase tracking-widest">Gallery</Link>
            <Link href="/contact" onClick={() => setOpen(false)} className="text-[#5A6B7C] hover:text-[#1B2A52] transition-colors text-sm font-bold uppercase tracking-widest">Contact</Link>
            <Link href="/contact" onClick={() => setOpen(false)} className="btn-primary text-sm text-center">
              Get a Quote
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}
