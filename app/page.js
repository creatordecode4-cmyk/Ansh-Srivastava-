import Navbar from "@/components/Navbar";
import Hero from "@/components/Hero";
import Stats from "@/components/Stats";
import Work from "@/components/Work";
import WebProjects from "@/components/WebProjects";
import Capabilities from "@/components/Capabilities";
import Process from "@/components/Process";
import About from "@/components/About";
import Contact from "@/components/Contact";
import Footer from "@/components/Footer";

export default function Home() {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[100] focus:rounded focus:bg-white focus:px-4 focus:py-2 focus:text-black"
      >
        Skip to content
      </a>
      <Navbar />
      <main id="main" className="mx-auto max-w-6xl px-4 sm:px-6">
        <Hero />
        <Stats />
        <Work />
        <WebProjects />
        <Capabilities />
        <Process />
        <About />
        <Contact />
      </main>
      <Footer />
    </>
  );
}
