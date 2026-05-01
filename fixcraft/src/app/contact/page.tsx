"use client";

import Navbar from "@/components/Navbar";
import { useState, FormEvent } from "react";

const services = [
  "Furniture Assembly",
  "TV Mounting",
  "Shelves & Organizers",
  "Drywall Repair",
  "Painting",
  "Garbage Disposal",
  "Faucet Replacement",
  "Other",
];

const timeSlots = ["Morning (8am–12pm)", "Afternoon (12pm–4pm)", "Evening (4pm–8pm)"];

export default function ContactPage() {
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    service: "",
    date: "",
    time: "",
    message: "",
  });

  function handleChange(e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) {
    setForm({ ...form, [e.target.name]: e.target.value });
  }

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <>
        <Navbar />
        <main className="min-h-screen flex items-center justify-center px-4 bg-[#FAF7F2]">
          <div className="text-center max-w-md">
            <div className="w-16 h-16 rounded-full bg-[#A67C52]/10 flex items-center justify-center mx-auto mb-8">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8 text-[#A67C52]">
                <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
              </svg>
            </div>
            <h1 className="font-[family-name:var(--font-playfair)] text-3xl font-semibold text-[#2C1B0F] mb-4">
              Thank You, {form.name}
            </h1>
            <p className="text-[#6B6560] text-lg font-[family-name:var(--font-cormorant)] leading-relaxed">
              We received your request. We&apos;ll call you back within 1 hour to confirm your booking.
            </p>
            <p className="text-[#A67C52] font-semibold mt-8 text-lg">(786) 566-0753</p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Navbar />

      <main className="pt-32 pb-28 px-4 max-w-2xl mx-auto bg-[#FAF7F2] min-h-screen">
        <div className="text-center mb-16">
          <p className="text-[#A67C52] text-sm uppercase tracking-[0.25em] mb-4 font-[family-name:var(--font-cormorant)]">Booking</p>
          <h1 className="font-[family-name:var(--font-playfair)] text-4xl md:text-5xl font-semibold text-[#2C1B0F] mb-4">
            Book a Service
          </h1>
          <p className="text-[#6B6560] text-lg font-[family-name:var(--font-cormorant)]">
            We&apos;ll call you back within 1 hour to confirm.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="bg-white border border-[#D4C4A8]/30 p-10 shadow-sm space-y-8">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
                Name *
              </label>
              <input
                name="name"
                required
                value={form.name}
                onChange={handleChange}
                className="w-full bg-[#FAF7F2] border border-[#D4C4A8]/40 px-4 py-3 text-[#1A1918] placeholder-[#A8A098] focus:outline-none focus:border-[#A67C52] transition-colors"
                placeholder="Your name"
              />
            </div>
            <div>
              <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
                Phone *
              </label>
              <input
                name="phone"
                type="tel"
                required
                value={form.phone}
                onChange={handleChange}
                className="w-full bg-[#FAF7F2] border border-[#D4C4A8]/40 px-4 py-3 text-[#1A1918] placeholder-[#A8A098] focus:outline-none focus:border-[#A67C52] transition-colors"
                placeholder="(704) 000-0000"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
              Email
            </label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              className="w-full bg-[#FAF7F2] border border-[#D4C4A8]/40 px-4 py-3 text-[#1A1918] placeholder-[#A8A098] focus:outline-none focus:border-[#A67C52] transition-colors"
              placeholder="your@email.com"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
              Service Needed *
            </label>
            <select
              name="service"
              required
              value={form.service}
              onChange={handleChange}
              className="w-full bg-[#FAF7F2] border border-[#D4C4A8]/40 px-4 py-3 text-[#1A1918] focus:outline-none focus:border-[#A67C52] transition-colors appearance-none cursor-pointer"
            >
              <option value="">Select a service...</option>
              {services.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
              Preferred Date *
            </label>
            <input
              name="date"
              type="date"
              required
              value={form.date}
              onChange={handleChange}
              min={new Date().toISOString().split("T")[0]}
              className="w-full bg-[#FAF7F2] border border-[#D4C4A8]/40 px-4 py-3 text-[#1A1918] focus:outline-none focus:border-[#A67C52] transition-colors"
            />
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
              Preferred Time *
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {timeSlots.map((slot) => (
                <label
                  key={slot}
                  className={`flex items-center justify-center px-4 py-3 border cursor-pointer transition-colors text-sm ${
                    form.time === slot
                      ? "border-[#2C1B0F] bg-[#2C1B0F] text-[#FAF7F2]"
                      : "border-[#D4C4A8]/40 text-[#6B6560] hover:border-[#A67C52]"
                  }`}
                >
                  <input
                    type="radio"
                    name="time"
                    value={slot}
                    checked={form.time === slot}
                    onChange={handleChange}
                    className="sr-only"
                    required
                  />
                  {slot}
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium uppercase tracking-[0.15em] text-[#6B6560] mb-3">
              Additional Details
            </label>
            <textarea
              name="message"
              value={form.message}
              onChange={handleChange}
              rows={4}
              className="w-full bg-[#FAF7F2] border border-[#D4C4A8]/40 px-4 py-3 text-[#1A1918] placeholder-[#A8A098] focus:outline-none focus:border-[#A67C52] transition-colors resize-none"
              placeholder="Describe what you need — brand, model, number of items..."
            />
          </div>

          <button
            type="submit"
            className="w-full bg-[#2C1B0F] text-[#FAF7F2] py-4 text-sm font-medium uppercase tracking-[0.15em] hover:bg-[#A67C52] transition-colors duration-300"
          >
            Request Booking
          </button>

          <p className="text-center text-[#6B6560]/60 text-sm">
            Or call directly:{" "}
            <a href="tel:7865660753" className="text-[#A67C52] hover:text-[#2C1B0F] transition-colors underline underline-offset-4">
              (786) 566-0753
            </a>
          </p>
        </form>
      </main>

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
