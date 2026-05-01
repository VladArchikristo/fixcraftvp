import Navbar from "@/components/Navbar";
import Image from "next/image";
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
    title: "Outdoor TV Mount",
    desc: "75\" TV mounted on covered patio with weatherproof bracket and hidden cables.",
    tags: ["TV Mounting", "Outdoor"],
    img: "/images/outdoor-tv-mount.jpg",
    alt: "Outdoor TV mount installation",
    local: true,
  },
];

export default function GalleryPage() {
  return (
    <>
      <Navbar />

      <main className="pt-28 pb-24 px-4 max-w-6xl mx-auto">
        <div className="text-center mb-16">
          <h1 className="text-5xl font-bold mb-4">Our Work</h1>
          <p className="text-gray-400 text-lg">Real projects. Real results.</p>
        </div>

        <div className="flex flex-wrap justify-center gap-8">
          {works.map((w) => (
            <div
              key={w.id}
              className="bg-gray-900 rounded-2xl overflow-hidden border border-white/10 hover:border-amber-400/40 transition-colors w-full max-w-sm"
            >
              <div className="relative h-64 w-full bg-gray-800">
                {w.local ? (
                  <div className="absolute inset-0 flex items-center justify-center text-gray-600 text-sm">
                    Photo coming soon
                  </div>
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={w.img}
                    alt={w.alt}
                    className="w-full h-full object-cover"
                  />
                )}
              </div>
              <div className="p-6">
                <div className="flex flex-wrap gap-2 mb-3">
                  {w.tags.map((t) => (
                    <span key={t} className="text-xs bg-amber-400/10 text-amber-400 px-2 py-1 rounded-full">
                      {t}
                    </span>
                  ))}
                </div>
                <h3 className="text-xl font-semibold mb-2">{w.title}</h3>
                <p className="text-gray-400 text-sm">{w.desc}</p>
              </div>
            </div>
          ))}
        </div>

        <div className="text-center mt-16">
          <p className="text-gray-400 mb-6">Like what you see?</p>
          <Link
            href="/contact"
            className="bg-amber-400 text-gray-950 px-8 py-4 rounded-full text-lg font-bold hover:bg-amber-300 transition-all hover:scale-105"
          >
            Book a Service
          </Link>
        </div>
      </main>

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
