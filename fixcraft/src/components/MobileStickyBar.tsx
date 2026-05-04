import { Phone, MessageSquare } from "lucide-react";

export default function MobileStickyBar() {
  return (
    <div className="md:hidden fixed bottom-0 left-0 right-0 z-50 bg-[#1B2A52] border-t border-white/10 grid grid-cols-2 shadow-[0_-4px_20px_rgba(0,0,0,0.15)]">
      <a
        href="tel:+19802016705"
        className="flex items-center justify-center gap-2 py-4 text-white font-semibold text-sm tracking-wide active:bg-[#152040] transition-colors border-r border-white/10"
        aria-label="Call FixCraft VP"
      >
        <Phone className="w-5 h-5" />
        <span>Call Now</span>
      </a>
      <a
        href="sms:+19802016705"
        className="flex items-center justify-center gap-2 py-4 text-white font-semibold text-sm tracking-wide active:bg-[#152040] transition-colors"
        aria-label="Text FixCraft VP"
      >
        <MessageSquare className="w-5 h-5" />
        <span>Text Us</span>
      </a>
    </div>
  );
}
