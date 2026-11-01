import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/Hero";
import Agents from "@/components/landing/Agents";
import Workspace from "@/components/landing/Workspace";
import Features from "@/components/landing/Features";
import UseCases from "@/components/landing/UseCases";
import Roadmap from "@/components/landing/Roadmap";
import Trust from "@/components/landing/Trust";
import CTA from "@/components/landing/CTA";
import Footer from "@/components/landing/Footer";

export default function LandingPage() {
  return (
    <main className="min-h-screen overflow-x-hidden bg-ink-950 text-text">
      <Navbar />

      <Hero />

      <Agents />

      <Workspace />

      <Features />

      <UseCases />

      <Roadmap />

      <Trust />

      <CTA />

      <Footer />
    </main>
  );
}