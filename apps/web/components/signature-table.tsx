import Image from "next/image";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { DepthCard } from "@/components/food-scene";

const dishes = [
  { image: "biryani", label: "THE HEART OF HYDERABAD", name: "The biryani collection", alt: "Chicken biryani with basmati rice, mint and spices", copy: "Fragrant rice, layered spices and the comfort of a proper feast. Explore our chicken and mutton dum menus.", position: "50% 65%" },
  { image: "curry", label: "RICH, WARM & GENEROUS", name: "Curries worth gathering for", alt: "Butter chicken served with naan and rice; representative Indian food photography", copy: "From mutton curry to stuffed gutti vankaya, discover the dishes that make a complete Hyderabad table.", position: "65% 85%" },
  { image: "dessert", label: "SAVE ROOM FOR SOMETHING SWEET", name: "The sweetest finish", alt: "A plate of syrup-soaked Indian sweets; representative dessert photography", copy: "Double ka meetha, gulab jamun and more. Choose the sweet ending that feels right for your celebration.", position: "50% 50%" },
];

export function SignatureTable() {
  return <section id="table" className="signature-section" aria-labelledby="table-heading">
    <div className="section-heading"><div><p className="eyebrow">THE SIGNATURE TABLE</p><h2 id="table-heading">Some flavours<br /><em>stay with you.</em></h2></div><p>Recipes with roots. Spices with a story. A generous spread that brings everyone a little closer.</p></div>
    <div className="signature-grid">{dishes.map((dish, i) => <DepthCard key={dish.image}><article><div className="signature-photo"><Image src={`/food/${dish.image}.jpg`} alt={dish.alt} fill sizes="(min-width: 768px) 33vw, 88vw" style={{ objectPosition: dish.position }} /><span className="signature-number" aria-hidden="true">0{i + 1}</span></div><div className="signature-caption"><span>{dish.label}</span><h3>{dish.name}</h3><p>{dish.copy}</p></div></article></DepthCard>)}</div>
    <div className="signature-footnote"><div><p>Complete the spread with Telugu favourites, including majjiga charu, chutneys, karapodi and ghee. Available selections vary by menu.</p><p className="mt-3 !text-xs">Photography illustrates the cuisine; presentation and dishes vary by selected menu.</p></div><Link href="/menu" className="text-button">Find your perfect menu <ArrowUpRight size={17} /></Link></div>
  </section>;
}
