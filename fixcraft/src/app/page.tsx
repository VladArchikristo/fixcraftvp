import Link from "next/link";
import Navbar from "@/components/Navbar";
import { 
  Armchair, Monitor, Library, Paintbrush, Droplets, Home,
  Phone, Calendar, Sparkles, Shield, Award, Clock, CheckCircle,
  Star, MapPin, ThumbsUp
} from "lucide-react";

const services = [
  {
    icon: <Armchair className="w-10 h-10" strokeWidth={1.5} />,
    title: "Furniture Assembly",
    desc: "IKEA, Pottery Barn, Wayfair, Costco — any brand, assembled with precision and care.",
    price: "$65/hr",
  },
  {
    icon: <Monitor className="w-10 h-10" strokeWidth={1.5} />,
    title: "TV Mounting",
    desc: "Any wall type — drywall, concrete, brick. Hidden cable management included.",
    price: "$99 flat",
  },
  {
    icon: <Library className="w-10 h-10" strokeWidth={1.5} />,
    title: "Shelves & Organizers",
    desc: "Floating shelves, garage systems, closet organizers — perfectly level and secure.",
    price: "$65/hr",
  },
  {
    icon: <Paintbrush className="w-10 h-10" strokeWidth={1.5} />,
    title: "Drywall & Painting",
    desc: "Hole repairs, texture matching, full wall painting. Professional, crisp finishes.",
    price: "$65/hr",
  },
  {
    icon: <Droplets className="w-10 h-10" strokeWidth={1.5} />,
    title: "Plumbing Fixtures",
    desc: "Faucet installation, garbage disposal replacement. Clean work, no leaks guaranteed.",
    price: "$100 flat",
  },
  {
    icon: <Home className="w-10 h-10" strokeWidth={1.5} />,
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

const trustBadges = [
  { icon: <Award className="w-6 h-6" />, title: "Licensed & Insured", desc: "Fully covered" },
  { icon: <Clock className="w-6 h-6" />, title: "Same-Day Service", desc: "Available today" },
  { icon: <Shield className="w-6 h-6" />, title: "Satisfaction Guaranteed", desc: "100% guarantee" },
  { icon: <ThumbsUp className="w-6 h-6" />, title: "5-Star Rated", desc: "Top rated on Google" },
];

const testimonials = [
  {
    stars: "★★★★★",
    text: "Absolutely fantastic service. They assembled my entire IKEA bedroom set in under 3 hours. Professional, clean, and precise.",
    author: "Jennifer M.",
    location: "Ballantyne"
  },
  {
    stars: "★★★★★",
    text: "Best handyman service in Charlotte. They mounted my 75\" TV perfectly and hid all the cables. Highly recommend!",
    author: "Robert K.",
    location: "SouthPark"
  },
  {
    stars: "★★★★★",
    text: "Quick, professional, and fair pricing. They fixed my leaky faucet and installed new shelves. Will definitely call again.",
    author: "Sarah T.",
    location: "Myers Park"
  },
];

const serviceAreas = [
  "Ballantyne", "SouthPark", "Myers Park", "Dilworth", "Plaza Midwood",
  "NoDa", "Uptown", "Elizabeth", "Cotswold", "Providence",
  "Huntersville", "Matthews", "Mint Hill", "Pineville", "Steele Creek"
];

export default function HomePage() {
  return (
    <>
      <Navbar />

      {/* Hero Section */}
      <section className="hero-section min-h-[95vh] flex items-center justify-center px-4 pt-20">
        <div className="relative z-10 text-center max-w-6xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-white/80 backdrop-blur-md px-5 py-2.5 rounded-full border border-[#D4C4A8]/40 mb-8 shadow-lg">
            <Sparkles className="w-4 h-4 text-[#8B6A45]" />
            <span className="text-[#8B6A45] text-xs font-bold uppercase tracking-widest">
              Charlotte's Premier Handyman Service
            </span>
          </div>
          
          <h1 className="mb-8">
            Your Home,
            <span className="block text-gradient-bronze">Done Right</span>
          </h1>
          
          <p className="text-lead max-w-2xl mx-auto mb-12 leading-relaxed">
            Professional furniture assembly, TV mounting, and handyman services for 
            discerning homeowners who expect excellence. Licensed, insured, and detail-obsessed.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-5 justify-center mb-16">
            <Link href="/contact" className="btn-primary inline-flex items-center justify-center gap-2">
              Book a Service
            </Link>
            <a href="tel:+19802016705" className="btn-secondary inline-flex items-center justify-center gap-2">
              <Phone className="w-4 h-4" />
              (980) 201-6705
            </a>
          </div>

          {/* Trust Badges */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto">
            {trustBadges.map((badge, i) => (
              <div key={i} className="trust-badge justify-center">
                <div className="text-[#8B6A45]">{badge.icon}</div>
                <div className="text-left">
                  <h3 className="text-sm font-bold text-[#1e3a5f]">{badge.title}</h3>
                  <p className="text-xs text-[#6B6560]">{badge.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <div className="section-divider" />

      {/* Services Section */}
      <section className="py-28 px-4 bg-white">
        <div className="max-w-6xl mx-auto">
          <div className="section-title">
            <span className="section-eyebrow">What We Do</span>
            <h2 className="section-headline">Premium Handyman Services</h2>
            <p className="section-subhead font-body">
              Every job, from the smallest repair to the largest project, receives our 
              full attention and expert craftsmanship.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {services.map((s, i) => (
              <div key={i} className="card-premium group">
                <div className="icon-box icon-box-lg mb-6 group-hover:scale-110 transition-transform duration-300">
                  {s.icon}
                </div>
                <h3 className="text-2xl font-display font-semibold mb-4 tracking-tight">{s.title}</h3>
                <p className="font-body text-lg text-[#6B6560] mb-6 leading-relaxed">{s.desc}</p>
                <span className="price-tag">{s.price}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Guarantee Section */}
      <section className="py-24 px-4 bg-gradient-beige">
        <div className="max-w-4xl mx-auto">
          <div className="guarantee-box">
            <div className="guarantee-icon">
              <CheckCircle className="w-8 h-8" />
            </div>
            <h2 className="text-3xl font-display font-bold mb-4">100% Satisfaction Guarantee</h2>
            <p className="font-body text-lg text-[#6B6560] mb-6">
              If you're not completely satisfied with our work, we'll make it right — 
              no questions asked. Your home deserves nothing less than perfection.
            </p>
            <div className="flex flex-wrap justify-center gap-3">
              <span className="area-tag">Licensed</span>
              <span className="area-tag">Insured</span>
              <span className="area-tag">Background Checked</span>
              <span className="area-tag">5-Star Rated</span>
            </div>
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section className="py-28 px-4 bg-white">
        <div className="max-w-3xl mx-auto">
          <div className="section-title">
            <span className="section-eyebrow">Transparent Pricing</span>
            <h2 className="section-headline">No Surprises, Ever</h2>
            <p className="section-subhead font-body">
              Honest, upfront pricing. Flat rates where possible. Free estimates for larger projects.
            </p>
          </div>

          <div className="card shadow-premium">
            {pricing.map((p, i) => (
              <div
                key={i}
                className={`flex items-center justify-between px-8 py-5 ${
                  i < pricing.length - 1 ? "border-b border-[#E8E0D5]/50" : ""
                }`}
              >
                <span className="text-[#1e3a5f] font-medium text-base font-display">{p.service}</span>
                <span className="text-[#8B6A45] font-bold text-lg whitespace-nowrap ml-4">{p.price}</span>
              </div>
            ))}
          </div>
          <p className="text-center text-[#9B9590] text-sm mt-6 font-sans">
            * Minimum 1-hour charge for hourly services. Free estimates for projects over $500.
          </p>
        </div>
      </section>

      {/* Testimonials Section */}
      <section className="py-28 px-4 bg-gradient-beige">
        <div className="max-w-6xl mx-auto">
          <div className="section-title">
            <span className="section-eyebrow">Testimonials</span>
            <h2 className="section-headline">What Our Clients Say</h2>
            <p className="section-subhead font-body">
              Don't take our word for it. Here's what Charlotte homeowners say about FixCraft VP.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {testimonials.map((t, i) => (
              <div key={i} className="testimonial-card">
                <div className="testimonial-stars">{t.stars}</div>
                <p className="font-body text-[#6B6560] text-lg mb-6 leading-relaxed italic">
                  "{t.text}"
                </p>
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-gradient-to-br from-[#8B6A45] to-[#6B5235] flex items-center justify-center text-white font-bold text-sm">
                    {t.author[0]}
                  </div>
                  <div>
                    <p className="text-sm font-bold text-[#1e3a5f]">{t.author}</p>
                    <div className="flex items-center gap-1 text-xs text-[#9B9590]">
                      <MapPin className="w-3 h-3" />
                      {t.location}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Service Areas */}
      <section className="py-20 px-4 bg-white border-t border-[#E8E0D5]/50">
        <div className="max-w-4xl mx-auto text-center">
          <p className="text-sm font-bold text-[#8B6A45] uppercase tracking-widest mb-6">Service Areas</p>
          <h3 className="text-2xl font-display font-bold mb-8">Proudly Serving Charlotte & Surrounding Areas</h3>
          <div className="flex flex-wrap justify-center">
            {serviceAreas.map((area, i) => (
              <span key={i} className="area-tag">{area}</span>
            ))}
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="section-dark py-28 px-4 text-center">
        <div className="max-w-3xl mx-auto">
          <h2 className="text-4xl md:text-5xl font-display font-bold text-white mb-6 tracking-tight">
            Ready to Get Started?
          </h2>
          <p className="text-lg text-[#D4C4A8] mb-10 font-body leading-relaxed max-w-xl mx-auto">
            Book online in 60 seconds or call us. Same-day and next-day appointments available 
            throughout Charlotte.
          </p>
          <div className="flex flex-col sm:flex-row gap-4 justify-center">
            <Link href="/contact" className="btn-primary bg-white text-[#1e3a5f] hover:bg-[#F5EFE6]">
              Book a Service
            </Link>
            <Link href="tel:+19802016705" className="btn-secondary border-white/40 text-white hover:bg-white/10">
              Call Now
            </Link>
          </div>
          <div className="mt-10 flex items-center justify-center gap-6 text-sm text-[#D4C4A8]/80 font-sans">
            <span className="flex items-center gap-2">
              <Phone className="w-4 h-4" />
              (980) 201-6705
            </span>
            <span>•</span>
            <span className="flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Same-Day Available
            </span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[#FAF7F2] border-t border-[#E8E0D5] py-16 px-4">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-10 mb-12">
            <div>
              <div className="flex items-center gap-1 mb-4">
                <span className="logo-fix text-xl font-bold">Fix</span>
                <span className="logo-craft text-xl font-bold">Craft VP</span>
              </div>
              <p className="text-[#6B6560] text-sm font-body leading-relaxed">
                Charlotte's most trusted handyman service. Professional, licensed, and insured.
              </p>
            </div>
            <div>
              <h4 className="text-sm font-bold text-[#1e3a5f] uppercase tracking-wider mb-4">Contact</h4>
              <p className="text-[#6B6560] text-sm font-body mb-2">
                <a href="tel:+19802016705" className="hover:text-[#8B6A45] transition-colors">(980) 201-6705</a>
              </p>
              <p className="text-[#6B6560] text-sm font-body">
                Charlotte, NC 28277
              </p>
            </div>
            <div>
              <h4 className="text-sm font-bold text-[#1e3a5f] uppercase tracking-wider mb-4">Service Hours</h4>
              <p className="text-[#6B6560] text-sm font-body mb-1">Monday — Saturday: 8am — 7pm</p>
              <p className="text-[#6B6560] text-sm font-body">Sunday: By Appointment</p>
            </div>
          </div>
          
          <div className="border-t border-[#E8E0D5] pt-8 flex flex-col md:flex-row justify-between items-center gap-4">
            <p className="text-[#9B9590] text-xs font-sans">
              © 2026 FixCraft VP. All rights reserved.
            </p>
            <p className="text-[#9B9590] text-xs font-sans flex items-center gap-1">
              <MapPin className="w-3 h-3" />
              Serving Ballantyne & Greater Charlotte Area
            </p>
          </div>
        </div>
      </footer>
    </>
  );
}
