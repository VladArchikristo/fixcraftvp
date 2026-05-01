import Link from "next/link";
import Navbar from "@/components/Navbar";
import { Armchair, Monitor, Library, Paintbrush, Droplets, Home, Phone, Calendar, Sparkles } from "lucide-react";

const services = [
  {
    icon: <Armchair className="w-9 h-9" strokeWidth={1.5} />,
    title: "Furniture Assembly",
    desc: "IKEA, Pottery Barn, Wayfair, Costco — any brand, assembled with precision and care.",
    price: "$65/hr",
  },
  {
    icon: <Monitor className="w-9 h-9" strokeWidth={1.5} />,
    title: "TV Mounting",
    desc: "Any wall type — drywall, concrete, brick. Hidden cable management included.",
    price: "$99 flat",
  },
  {
    icon: <Library className="w-9 h-9" strokeWidth={1.5} />,
    title: "Shelves & Organizers",
    desc: "Floating shelves, garage systems, closet organizers — perfectly level and secure.",
    price: "$65/hr",
  },
  {
    icon: <Paintbrush className="w-9 h-9" strokeWidth={1.5} />,
    title: "Drywall & Painting",
    desc: "Hole repairs, texture matching, full wall painting. Professional, crisp finishes.",
    price: "$65/hr",
  },
  {
    icon: <Droplets className="w-9 h-9" strokeWidth={1.5} />,
    title: "Plumbing Fixtures",
    desc: "Faucet installation, garbage disposal replacement. Clean work, no leaks guaranteed.",
    price: "$100 flat",
  },
  {
    icon: <Home className="w-9 h-9" strokeWidth={1.5} />,
    title: "General Handyman",
    desc: "Doors, locks, fixtures, repairs. If it's broken, we'll fix it right.",
    price: "$65/hr",
  },
];

const pricing = [
  { service: "Furniture Assembly (IKEA, Wayfair, Pottery Barn)", price: "$65/hr" },
  { service: "TV Mounting — standard (up to 55\")", price: "$99 flat" },
  { service: "TV Mounting + cable concealment", price: "$149 flat" },
  { service: "Floating Shelves & Closet Systems", price: "$65/hr" },
  { service: "Drywall Repair & Patch", price: "$65/hr" },
  { service: "Garbage Disposal Replacement", price: "$125 flat" },
  { service: "Faucet Replacement (bathroom/kitchen)", price: "$125 flat" },
  { service: "Wall Painting (per room)", price: "Quote on site" },
];

const features = [
  {
    icon: <Calendar className="w-5 h-5" />,
    title: "Same-Day Booking",
    desc: "Available today or tomorrow",
  },
  {
    icon: <Sparkles className="w-5 h-5" />,
    title: "Precision Work",
    desc: "Attention to every detail",
  },
  {
    icon: <Phone className="w-5 h-5" />,
    title: "Licensed & Insured",
    desc: "Fully covered for peace of mind",
  },
];

export default function HomePage() {
  return (
    <>
      <Navbar />

      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-center justify-center overflow-hidden hero-section px-4">
        <div className="absolute inset-0 bg-gradient-to-br from-[#E8DCC8]/30 via-transparent to-[#D4C4A8]/20" />
        <div className="absolute top-0 right-0 w-2/3 h-2/3 bg-gradient-to-bl from-[#F5EFE6]/40 to-transparent blur-3xl" />
        
        <div className="relative z-10 text-center max-w-5xl mx-auto pt-20">
          <div className="inline-flex items-center gap-2 bg-white/60 backdrop-blur-md px-4 py-2 rounded-full border border-[#E8E0D5] mb-6">
            <Sparkles className="w-4 h-4 text-[#A67C52]" />
            <span className="text-[#A67C52] text-xs font-medium uppercase tracking-widest">Charlotte, NC — Ballantyne Area</span>
          </div>
          
          <h1 className="text-5xl sm:text-6xl md:text-7xl lg:text-8xl font-bold leading-[1.05] mb-6 tracking-tight">
            Your Home,
            <span className="block text-[#A67C52]">Done Right</span>
          </h1>
          
          <p className="text-lg sm:text-xl text-[#6B6560] mb-10 max-w-2xl mx-auto leading-relaxed">
            Professional furniture assembly, TV mounting, and handyman services for 
            homeowners who expect perfection. Licensed, insured, and detail-obsessed.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/contact" className="btn-primary inline-flex items-center justify-center gap-2">
              Book a Service
            </Link>
            <a href="tel:+19802016705" className="btn-secondary inline-flex items-center justify-center gap-2">
              <Phone className="w-4 h-4" />
              (980) 201-6705
            </a>
          </div>

          {/* Features */}
          <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-6 max-w-3xl mx-auto">
            {features.map((f, i) => (
              <div key={i} className="flex flex-col items-center text-center">
                <div className="text-[#A67C52] mb-2">{f.icon}</div>
                <h3 className="text-sm font-semibold text-[#2C1B0F] mb-1">{f.title}</h3>
                <p className="text-xs text-[#8B8580]">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* Services */}
      <section className="py-24 px-4 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-[#A67C52] text-xs font-semibold uppercase tracking-widest mb-3">What We Do</p>
            <h2 className="text-4xl md:text-5xl font-bold text-[#2C1B0F] mb-5 tracking-tight">
              Premium Handyman Services
            </h2>
            <p className="text-lg text-[#6B6560] max-w-xl mx-auto">
              Every job, big or small, gets our full attention. Done right, the first time.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {services.map((s, i) => (
              <div key={i} className="card-premium group">
                <div className="icon-box mb-5 group-hover:scale-105 transition-transform duration-300">
                  {s.icon}
                </div>
                <h3 className="text-xl font-semibold mb-3 text-[#2C1B0F] tracking-tight">{s.title}</h3>
                <p className="text-[#6B6560] text-sm leading-relaxed mb-4">{s.desc}</p>
                <span className="inline-block px-3 py-1.5 bg-[#FAF7F2] rounded-md text-[#A67C52] text-xs font-semibold tracking-wide">
                  {s.price}
                </span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-24 px-4 bg-gradient-to-br from-[#FAF7F2] via-[#F5EFE6] to-[#FAF7F2]">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-[#A67C52] text-xs font-semibold uppercase tracking-widest mb-3">Transparent Pricing</p>
            <h2 className="text-4xl md:text-5xl font-bold text-[#2C1B0F] mb-5 tracking-tight">
              No Surprises, Ever
            </h2>
            <p className="text-lg text-[#6B6560]">
              Flat rates where possible. Hourly for custom jobs. Quote provided upfront.
            </p>
          </div>

          <div className="card shadow-premium">
            {pricing.map((p, i) => (
              <div
                key={i}
                className={`flex items-center justify-between px-6 py-4 ${
                  i < pricing.length - 1 ? "border-b border-[#E8E0D5]" : ""
                }`}
              >
                <span className="text-[#2C1B0F] font-medium text-base">{p.service}</span>
                <span className="text-[#A67C52] font-bold text-base whitespace-nowrap ml-4">{p.price}</span>
              </div>
            ))}
          </div>
          <p className="text-center text-[#8B8580] text-sm mt-6">
            * Minimum 1-hour charge for hourly services. Free estimates for large projects.
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4 bg-gradient-to-br from-[#2C1B0F] via-[#3D2514] to-[#2C1B0F] text-center">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-5 tracking-tight">
            Ready to Get Started?
          </h2>
          <p className="text-[#D4C4A8] text-lg mb-10 max-w-xl mx-auto leading-relaxed">
            Book online in 60 seconds or call us. Same-day and next-day appointments available.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/contact" className="btn-primary bg-white text-[#2C1B0F] hover:bg-[#F5EFE6] shadow-white/20">
              Book a Service
            </Link>
            <Link href="tel:+19802016705" className="btn-secondary border-white/30 text-white hover:bg-white/10">
              Call Now
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#FAF7F2] border-t border-[#E8E0D5] py-12 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <p className="text-[#2C1B0F] font-semibold mb-2">FixCraft VP</p>
          <p className="text-[#6B6560] text-sm mb-4">Professional Handyman Services in Charlotte, NC</p>
          <p className="text-[#8B8580] text-xs">
            © 2026 FixCraft VP — Ballantyne Area & Surrounding Communities
          </p>
        </div>
      </footer>
    </>
  );
}
