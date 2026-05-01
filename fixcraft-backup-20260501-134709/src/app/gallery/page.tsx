import Navbar from "@/components/Navbar";
import Link from "next/link";

const works = [
  {
    id: 1,
    title: "Pottery Barn Bedroom Set",
    desc: "Full bedroom assembly: bed frame, dresser, nightstands, and wardrobe.",
    tags: ["Furniture Assembly", "Bedroom"],
    img: "https://images.unsplash.com/photo-1616594039964-ae9021a400a0?w=800&q=80",
    alt: "Assembled Pottery Barn bedroom set",
  },
  {
    id: 2,
    title: "IKEA PAX Wardrobe",
    desc: "Full PAX wardrobe system with drawers and internal organizers.",
    tags: ["Furniture Assembly", "IKEA"],
    img: "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800&q=80",
    alt: "IKEA PAX wardrobe assembly",
  },
  {
    id: 3,
    title: "Living Room Setup",
    desc: "Sectional sofa, coffee table, and entertainment center assembled in one visit.",
    tags: ["Furniture Assembly", "Living Room"],
    img: "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800&q=80",
    alt: "Living room furniture assembly",
  },
  {
    id: 4,
    title: "Floating Shelves",
    desc: "Custom floating shelves installed with hidden brackets and precise leveling.",
    tags: ["Shelves", "Installation"],
    img: "https://images.unsplash.com/photo-1595428774223-ef52624120d2?w=800&q=80",
    alt: "Floating shelves installation",
  },
  {
    id: 5,
    title: "TV Wall Mount",
    desc: "65\" TV wall-mounted with full-motion bracket and cable concealment.",
    tags: ["TV Mounting", "Cables"],
    img: "https://images.unsplash.com/photo-1580927752452-89d86da3fa0a?w=800&q=80",
    alt: "TV wall mount installation",
  },
  {
    id: 6,
    title: "Closet Organizer",
    desc: "Complete closet system with rods, shelves, and drawer units.",
    tags: ["Organizers", "Closet"],
    img: "https://images.unsplash.com/photo-1595515106969-1ce29566ff1c?w=800&q=80",
    alt: "Closet organizer installation",
  },
];

export default function GalleryPage() {
  return (
    <>
      <Navbar />

      <main className="pt-32 pb-28 px-4 max-w-6xl mx-auto bg-[#FAF7F2] min-h-screen">
        <div className="text-center mb-20">
          <p className="text-[#A67C52] text-sm uppercase tracking-[0.25em] mb-4 font-[family-name:var(--font-cormorant)]">
            Portfolio
          </p>
          <h1 className="font-[family-name:var(--font-playfair)] text-4xl md:text-5xl font-semibold text-[#2C1B0F] mb-6">
            Our Work
          </h1>
          <p className="text-[#6B6560] text-lg font-[family-name:var(--font-cormorant)]">
            Real projects. Real results.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {works.map((w) => (
            <div
              key={w.id}
              className="bg-white border border-[#D4C4A8]/30 overflow-hidden hover:shadow-2xl hover:shadow-[#A67C52]/5 hover:border-[#A67C52]/20 transition-all duration-500 group"
            >
              <div className="relative h-56 w-full bg-[#F5EFE6] overflow-hidden">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={w.img}
                  alt={w.alt}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                />
              </div>
              <div className="p-6">
                <div className="flex flex-wrap gap-2 mb-3">
                  {w.tags.map((t) => (
                    <span key={t} className="text-[10px] uppercase tracking-[0.15em] bg-[#F5EFE6] text-[#A67C52] px-3 py-1 font-medium">
                      {t}
                    </span>
                  ))}
                </div>
                <h3 className="font-[family-name:var(--font-playfair)] text-lg font-semibold mb-2 text-[#2C1B0F]">
                  {w.title}
                </h3>
                <p className="text-[#6B6560] text-sm leading-relaxed">
                  {w.desc}
                </p>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center mt-20">
          <p className="text-[#6B6560] text-lg font-[family-name:var(--font-cormorant)] mb-8">
            Like what you see?
          </p>
          <Link
            href="/contact"
            className="bg-[#2C1B0F] text-[#FAF7F2] px-10 py-4 text-sm font-medium uppercase tracking-[0.15em] hover:bg-[#A67C52] transition-colors duration-300 shadow-xl shadow-[#2C1B0F]/10"
          >
            Book a Service
          </Link>
        </div>
      </main>

      <footer className="bg-[#FAF7F2] border-t border-[#D4C4A8]/30 py-12 px-4">
        <div className="max-w-6xl mx-auto text-center">
          <p className="text-[#6B6560] text-sm">
            © 2026 FixCraft VP — Charlotte, NC
          </p>
        </div>
      </footer>
    </>
  );
}
