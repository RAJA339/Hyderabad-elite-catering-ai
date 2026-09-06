"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";

export function SiteHeader() {
  const [open, setOpen] = useState(false);
  return <header className="elite-header">
    <a href="#main-content" className="skip-link">Skip to content</a>
    <div className="elite-nav">
      <Link href="/" className="elite-brand" aria-label="Hyderabad Elite Catering home"><span className="brand-monogram">H<span>E</span></span><span>HYDERABAD ELITE<small>C A T E R I N G</small></span></Link>
      <nav className="desktop-nav" aria-label="Main navigation"><Link href="/menu">Our menus</Link><Link href="/#table">The signature table</Link><Link href="/portal">Client portal</Link></nav>
      <div className="nav-actions"><ThemeToggle /><Link href="/#enquire" className="nav-book">Plan your event <ArrowUpRight size={16} /></Link><button className="mobile-menu-button" aria-expanded={open} aria-controls="mobile-navigation" aria-label={open ? "Close navigation" : "Open navigation"} onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button></div>
    </div>
    {open && <nav id="mobile-navigation" className="mobile-navigation" aria-label="Mobile navigation" onKeyDown={(e) => { if (e.key === "Escape") setOpen(false); }}><Link onClick={() => setOpen(false)} href="/menu">Our menus</Link><Link onClick={() => setOpen(false)} href="/#table">The signature table</Link><Link onClick={() => setOpen(false)} href="/portal">Client portal</Link><Link onClick={() => setOpen(false)} href="/#enquire">Plan your event</Link><Link onClick={() => setOpen(false)} href="/admin">Admin</Link></nav>}
  </header>;
}
