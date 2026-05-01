import Link from "next/link";
import Navbar from "@/components/Navbar";
import { Armchair, Monitor, Library, Paintbrush, Droplets, Home } from "lucide-react";

const services = [
  {
    icon: <Armchair className="w-8 h-8" strokeWidth={1.2} />,
    title: "Furniture Assembly",
    desc: "IKEA, Pottery Barn, Wayfair, Costco — any brand, assembled with precision.",
    price: "$65/hr",
  },
  {
    icon: <Monitor className="w-8 h-8" strokeWidth={1.2} />,
    title: "TV Mounting",
    desc: "Any wall type — drywall, concrete, brick. Cable management included.",
    price: "$99 flat",
  },
  {
    icon: <Library className="w-8 h-8" strokeWidth={1.2} />,
    title: "Shelves & Organizers",
    desc: "Floating shelves, garage shelving, closet systems — clean & level.",
    price: "$65/hr",
  },
  {
    icon: <Paintbrush className="w-8 h-8" strokeWidth={1.2} />,
    title: "Drywall & Painting",
    desc: "Patchwork, texture matching, full wall paint. Crisp finishes.",
    price: "$65/hr",
  },
  {
    icon: <Droplets className="w-8 h-8" strokeWidth={1.2} />,
    title: "Plumbing Fixtures",
    desc: "Faucet & garbage disposal replacement. Quick, clean, leak-free.",
    price: "$100 flat",
  },
  {
    icon: <Home className="w-8 h-8" strokeWidth={1.2} />,
    title: "General Handyman",
    desc: "Doors, locks, fixtures, repairs — anything your home needs.",
    price: "$65/hr",
  },
];

const pricing = [
  { service: "Furniture Assembly (IKEA, Wayfair)", price: "$65/hr" },
  { service: "TV Mounting — standard", price: "$99 flat" },
  { service: "TV Mounting + cable management", price: "$149 flat" },
  { service: "Shelves & Closet Systems", price: "$65/hr" },
  { service: "Drywall Repair", price: "$65/hr" },
  { service: "Garbage Disposal Replacement", price: "$125 flat" },
  { service: "Faucet Replacement", price: "$125 flat" },
  { service: "Wall Painting (per room)", price: "Quote on site" },
];

export default function HomePage() {
  return (
    <>
      <Navbar />

      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-center justify-center bg-[#FAF7F2]">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-[#E8DCC8]/50 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_left,_var(--tw-gradient-stops))] from-[#D4C4A8]/30 via-transparent to-transparent" />

        <div className="relative z-10 text-center px-4 max-w-5xl mx-auto pt-20">
          <p className="text-[#A67C52] text-sm font-medium uppercase tracking-[0.25em] mb-6 font-[family-name:var(--font-cormorant)]">
            Charlotte, NC &amp; Surrounding Areas
          </p>
          <h1 className="font-[family-name:var(--font-playfair)] text-5xl md:text-7xl lg:text-8xl font-semibold leading-[1.1] mb-8 text-[#2C1B0F]">
            Your Home,
            <br />
            <span className="text-[#A67C52]">Done Right</span>
          </h1>
          <p className="text-lg md:text-xl text-[#6B6560] mb-12 max-w-2xl mx-auto leading-relaxed font-[family-name:var(--font-cormorant)]">
            Professional furniture assembly, TV mounting, and handyman services
            for homeowners who value precision.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/contact"
              className="bg-[#2C1B0F] text-[#FAF7F2] px-10 py-4 text-sm font-medium uppercase tracking-[0.15em] hover:bg-[#A67C52] transition-colors duration-300 shadow-xl shadow-[#2C1B0F]/10"
            >
              Book a Service
            </Link>
            <a
              href="tel:7865660753"
              className="border border-[#2C1B0F]/20 text-[#2C1B0F] px-10 py-4 text-sm font-medium uppercase tracking-[0.15em] hover:bg-[#F5EFE6] transition-colors duration-300"
            >
              (786) 566-0753
            </a>
          </div>
        </div>

        {/* Decorative line */}
        <div className="absolute bottom-12 left-1/2 -translate-x-1/2 flex flex-col items-center gap-3">
          <span className="text-[#A67C52] text-xs uppercase tracking-[0.3em]">Scroll</span>
          <div className="w-px h-12 bg-[#A67C52]/40" />
        </div>
      </section>

      {/* Services */}
      <section className="py-28 px-4 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-[#A67C52] text-sm uppercase tracking-[0.25em] mb-4 font-[family-name:var(--font-cormorant)]">What We Do</p>
            <h2 className="font-[family-name:var(--font-playfair)] text-4xl md:text-5xl font-semibold text-[#2C1B0F] mb-6">
              Services
            </h2>
            <p className="text-[#6B6560] text-lg font-[family-name:var(--font-cormorant)]">
              Fast, reliable, and done right the first time.
            </p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
            {services.map((s) => (
              <div
                key={s.title}
                className="group bg-[#FAF7F2] border border-[#D4C4A8]/30 p-8 hover:shadow-2xl hover:shadow-[#A67C52]/5 hover:border-[#A67C52]/20 transition-all duration-500"
              >
                <div className="text-[#A67C52] mb-6 group-hover:scale-110 transition-transform duration-300">
                  {s.icon}
                </div>
                <h3 className="font-[family-name:var(--font-playfair)] text-xl font-semibold mb-3 text-[#2C1B0F]">
                  {s.title}
                </h3>
                <p className="text-[#6B6560] text-sm leading-relaxed mb-5">
                  {s.desc}
                </p>
                <span className="text-[#A67C52] font-medium text-sm tracking-wide">{s.price}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-28 px-4 bg-[#FAF7F2]">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-[#A67C52] text-sm uppercase tracking-[0.25em] mb-4 font-[family-name:var(--font-cormorant)]">Pricing</p>
            <h2 className="font-[family-name:var(--font-playfair)] text-4xl md:text-5xl font-semibold text-[#2C1B0F] mb-6">
              Transparent Rates
            </h2>
            <p className="text-[#6B6560] text-lg font-[family-name:var(--font-cormorant)]">
              No surprises. Flat rates where possible.
            </p>
          </div>
          <div className="bg-white border border-[#D4C4A8]/30 shadow-sm">
            {pricing.map((p, i) => (
              <div
                key={p.service}
                className={`flex items-center justify-between px-8 py-5 ${
                  i < pricing.length - 1 ? "border-b border-[#D4C4A8]/20" : ""
                }`}
              >
                <span className="text-[#1A1918] font-medium">{p.service}</span>
                <span className="text-[#A67C52] font-semibold whitespace-nowrap ml-6">{p.price}</span>
              </div>
            ))}
          </div>
          <p className="text-center text-[#6B6560]/60 text-sm mt-6">
            * Minimum 1-hour charge for hourly services
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="py-28 px-4 bg-[#2C1B0F] text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="font-[family-name:var(--font-playfair)] text-4xl md:text-5xl font-semibold text-[#FAF7F2] mb-6">
            Ready to Get Started?
          </h2>
          <p className="text-[#D4C4A8] text-lg font-[family-name:var(--font-cormorant)] mb-12">
            Book online or call us. Same-day and next-day slots available.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/contact"
              className="bg-[#FAF7F2] text-[#2C1B0F] px-10 py-4 text-sm font-medium uppercase tracking-[0.15em] hover:bg-[#E8DCC8] transition-colors duration-300"
            >
              Book a Service
            </Link>
            <Link
              href="/gallery"
              className="border border-[#FAF7F2]/30 text-[#FAF7F2] px-10 py-4 text-sm font-medium uppercase tracking-[0.15em] hover:bg-[#FAF7F2]/10 transition-colors duration-300"
            >
              View Our Work
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#FAF7F2] border-t border-[#D4C4A8]/30 py-12 px-4">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row justify-between items-center gap-6">
          <p className="text-[#6B6560] text-sm">
            © 2026 FixCraft VP — Charlotte, NC
          </p>
          <a href="tel:7865660753" className="text-[#A67C52] font-medium hover:text-[#2C1B0F] transition-colors text-sm">
            (786) 566-0753
          </a>
        </div>
      </footer>
    </>
  );
}
