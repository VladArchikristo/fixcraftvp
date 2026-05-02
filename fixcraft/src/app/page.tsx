import Link from "next/link";
import Navbar from "@/components/Navbar";

const services = [
  {
    icon: "🪑",
    title: "Furniture Assembly",
    desc: "IKEA, Pottery Barn, Wayfair, Costco — any brand, any complexity.",
    price: "From $65/hr",
  },
  {
    icon: "📺",
    title: "TV Mounting",
    desc: "Any wall type — drywall, concrete, brick. Cable management included.",
    price: "From $99",
  },
  {
    icon: "🔧",
    title: "Shelves & Organizers",
    desc: "Floating shelves, garage shelving, closet organizers.",
    price: "From $65/hr",
  },
  {
    icon: "🖌️",
    title: "Drywall & Painting",
    desc: "Holes, cracks, full walls. Clean results guaranteed.",
    price: "From $65/hr",
  },
  {
    icon: "🚿",
    title: "Plumbing Fixtures",
    desc: "Faucet & garbage disposal replacement. Quick & clean.",
    price: "From $100",
  },
  {
    icon: "🏠",
    title: "General Handyman",
    desc: "Anything your home needs — we handle it all.",
    price: "From $65/hr",
  },
];

const pricing = [
  { service: "Furniture Assembly (IKEA, Wayfair)", price: "$65/hr" },
  { service: "TV Mounting — standard", price: "$99 flat" },
  { service: "TV Mounting + cable management", price: "$149 flat" },
  { service: "Shelves & Organizers", price: "$65/hr" },
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
      <section className="relative min-h-screen flex items-center justify-center overflow-hidden">
        {/* Video background — add hero.mp4 to public/videos/ to enable */}
        {/* <video autoPlay muted loop playsInline
          className="absolute inset-0 w-full object-cover h-[110%]"
          src="/videos/hero.mp4" /> */}

        <div className="absolute inset-0 bg-gradient-to-br from-gray-900 via-gray-950 to-black" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-amber-900/20 via-transparent to-transparent" />
        <div className="absolute inset-0 bg-black/50" />
        <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-gray-950 to-transparent" />

        <div className="relative z-10 text-center px-4 max-w-4xl mx-auto fade-in-up">
          <p className="text-amber-400 text-sm font-semibold uppercase tracking-widest mb-4">
            Charlotte, NC &amp; Surrounding Areas
          </p>
          <h1 className="text-5xl md:text-7xl font-bold leading-tight mb-6">
            Your Home,{" "}
            <span className="text-amber-400">Done Right</span>
          </h1>
          <p className="text-xl text-gray-300 mb-10 max-w-2xl mx-auto">
            Professional furniture assembly, TV mounting, and handyman services.
            Same-day booking available.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/contact"
              className="bg-amber-400 text-gray-950 px-8 py-4 rounded-full text-lg font-bold hover:bg-amber-300 transition-all hover:scale-105 shadow-lg shadow-amber-400/20"
            >
              Book Now
            </Link>
            <a
              href="tel:7865660753"
              className="border border-white/30 text-white px-8 py-4 rounded-full text-lg font-medium hover:bg-white/10 transition-all"
            >
              (786) 566-0753
            </a>
          </div>
        </div>
      </section>

      {/* Services */}
      <section className="py-24 px-4 max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h2 className="text-4xl font-bold mb-4">What We Do</h2>
          <p className="text-gray-400 text-lg">Fast, reliable, and done right the first time.</p>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {services.map((s) => (
            <div
              key={s.title}
              className="bg-gray-900 rounded-2xl p-6 border border-white/10 hover:border-amber-400/40 transition-colors"
            >
              <div className="text-4xl mb-4">{s.icon}</div>
              <h3 className="text-xl font-semibold mb-2">{s.title}</h3>
              <p className="text-gray-400 text-sm mb-4">{s.desc}</p>
              <span className="text-amber-400 font-semibold text-sm">{s.price}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section className="py-24 px-4 bg-gray-900/50">
        <div className="max-w-3xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold mb-4">Transparent Pricing</h2>
            <p className="text-gray-400 text-lg">No surprises. Flat rates where possible.</p>
          </div>
          <div className="bg-gray-900 rounded-2xl border border-white/10 overflow-hidden">
            {pricing.map((p, i) => (
              <div
                key={p.service}
                className={`flex items-center justify-between px-6 py-4 ${
                  i < pricing.length - 1 ? "border-b border-white/10" : ""
                }`}
              >
                <span className="text-gray-300">{p.service}</span>
                <span className="text-amber-400 font-semibold whitespace-nowrap ml-4">{p.price}</span>
              </div>
            ))}
          </div>
          <p className="text-center text-gray-500 text-sm mt-4">
            * Minimum 1-hour charge for hourly services
          </p>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 px-4 text-center">
        <div className="max-w-2xl mx-auto">
          <h2 className="text-4xl font-bold mb-6">Ready to Get Started?</h2>
          <p className="text-gray-400 text-lg mb-10">
            Book online or call us. Same-day and next-day slots available.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link
              href="/contact"
              className="bg-amber-400 text-gray-950 px-8 py-4 rounded-full text-lg font-bold hover:bg-amber-300 transition-all hover:scale-105"
            >
              Book a Service
            </Link>
            <Link
              href="/gallery"
              className="border border-white/30 text-white px-8 py-4 rounded-full text-lg font-medium hover:bg-white/10 transition-all"
            >
              View Our Work
            </Link>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/10 py-8 px-4 text-center text-gray-500 text-sm">
        <p>
          © 2026 FixCraft VP — Charlotte, NC ·{" "}
          <a href="tel:7865660753" className="hover:text-white transition-colors">
            (786) 566-0753
          </a>
        </p>
      </footer>
    </>
  );
}
