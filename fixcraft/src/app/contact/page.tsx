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
    // TODO: connect to backend/email service
    setSubmitted(true);
  }

  if (submitted) {
    return (
      <>
        <Navbar />
        <main className="min-h-screen flex items-center justify-center px-4">
          <div className="text-center max-w-md">
            <div className="text-6xl mb-6">✅</div>
            <h1 className="text-3xl font-bold mb-4">We Got It!</h1>
            <p className="text-gray-400 text-lg">
              Thanks, {form.name}! We&apos;ll call you back within 1 hour to confirm your booking.
            </p>
            <p className="text-amber-400 font-semibold mt-6">(786) 566-0753</p>
          </div>
        </main>
      </>
    );
  }

  return (
    <>
      <Navbar />

      <main className="pt-28 pb-24 px-4 max-w-2xl mx-auto">
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold mb-4">Book a Service</h1>
          <p className="text-gray-400 text-lg">We&apos;ll call you back within 1 hour to confirm.</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-gray-900 rounded-2xl p-8 border border-white/10 space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Name *
              </label>
              <input
                name="name"
                required
                value={form.name}
                onChange={handleChange}
                className="w-full bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-400/50 transition-colors"
                placeholder="Your name"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Phone *
              </label>
              <input
                name="phone"
                type="tel"
                required
                value={form.phone}
                onChange={handleChange}
                className="w-full bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-400/50 transition-colors"
                placeholder="(704) 000-0000"
              />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Email
            </label>
            <input
              name="email"
              type="email"
              value={form.email}
              onChange={handleChange}
              className="w-full bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-400/50 transition-colors"
              placeholder="your@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Service Needed *
            </label>
            <select
              name="service"
              required
              value={form.service}
              onChange={handleChange}
              className="w-full bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-amber-400/50 transition-colors"
            >
              <option value="">Select a service...</option>
              {services.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Preferred Date *
            </label>
            <input
              name="date"
              type="date"
              required
              value={form.date}
              onChange={handleChange}
              min={new Date().toISOString().split("T")[0]}
              className="w-full bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white focus:outline-none focus:border-amber-400/50 transition-colors"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-300 mb-3">
              Preferred Time *
            </label>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {timeSlots.map((slot) => (
                <label
                  key={slot}
                  className={`flex items-center justify-center px-4 py-3 rounded-xl border cursor-pointer transition-colors text-sm font-medium ${
                    form.time === slot
                      ? "border-amber-400 bg-amber-400/10 text-amber-400"
                      : "border-white/10 text-gray-400 hover:border-white/30"
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
            <label className="block text-sm font-medium text-gray-300 mb-2">
              Additional Details
            </label>
            <textarea
              name="message"
              value={form.message}
              onChange={handleChange}
              rows={4}
              className="w-full bg-gray-800 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-amber-400/50 transition-colors resize-none"
              placeholder="Describe what you need — brand, model, number of items..."
            />
          </div>

          <button
            type="submit"
            className="w-full bg-amber-400 text-gray-950 py-4 rounded-xl text-lg font-bold hover:bg-amber-300 transition-all hover:scale-[1.02]"
          >
            Request Booking
          </button>

          <p className="text-center text-gray-500 text-sm">
            Or call directly:{" "}
            <a href="tel:7865660753" className="text-amber-400 hover:text-amber-300">
              (786) 566-0753
            </a>
          </p>
        </form>
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
