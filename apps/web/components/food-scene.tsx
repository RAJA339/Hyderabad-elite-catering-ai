"use client";

import Image from "next/image";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Pause, Play } from "lucide-react";

/** Small, GPU-composited depth effects; no animation loop or WebGL download. */
export function DepthCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const frame = useRef(0);
  useEffect(() => () => cancelAnimationFrame(frame.current), []);
  return <div ref={ref} className={`depth-card ${className}`} onPointerMove={(event) => {
    if (event.pointerType !== "mouse" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - bounds.left) / bounds.width;
    const y = (event.clientY - bounds.top) / bounds.height;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      ref.current?.style.setProperty("--rx", `${(0.5 - y) * 7}deg`);
      ref.current?.style.setProperty("--ry", `${(x - 0.5) * 9}deg`);
    });
  }} onPointerLeave={() => {
    cancelAnimationFrame(frame.current);
    ref.current?.style.setProperty("--rx", "0deg");
    ref.current?.style.setProperty("--ry", "0deg");
  }}>{children}</div>;
}

export function FoodScene() {
  const [paused, setPaused] = useState(false);
  return <div className={`food-scene ${paused ? "motion-paused" : ""}`}>
    <div className="scene-orbit" aria-hidden="true" />
    <DepthCard className="hero-depth">
      <div className="hero-photo-wrap">
        <Image src="/food/biryani.jpg" alt="Fragrant biryani with golden basmati rice and aromatic spices" fill priority sizes="(min-width: 1024px) 56vw, 100vw" className="hero-photo" />
        <div className="hero-photo-shade" />
        <div className="photo-caption"><span>THE HYDERABAD TABLE</span><strong>A little spice.<br />A lot of soul.</strong></div>
      </div>
      <div className="floating-note"><span className="note-mark">HEC</span><div><span>Made for your gathering</span><strong>From 25 to 500 guests</strong></div></div>
      <div className="scene-index" aria-hidden="true">01 / THE SIGNATURE</div>
    </DepthCard>
    <button className="motion-control" aria-label={paused ? "Play ambient motion" : "Pause ambient motion"} aria-pressed={paused} onClick={() => setPaused(!paused)}>{paused ? <Play size={14} /> : <Pause size={14} />}<span>{paused ? "Play motion" : "Pause motion"}</span></button>
  </div>;
}
