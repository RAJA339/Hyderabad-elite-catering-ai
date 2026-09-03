-- HEC-AI seed: one tenant, admin user, ingredients + 7-day price history, menu catalog with recipes,
-- package templates, discount rules, WhatsApp templates, upsell rules, venues, demo lead.
-- Apply after schema.sql:  psql "$DATABASE_URL" -f db/seed/seed.sql

BEGIN;

INSERT INTO tenants (id, slug, name, target_margin_pct, min_margin_pct, max_guests, daily_guest_capacity)
VALUES ('11111111-1111-1111-1111-111111111111', 'hec', 'Hyderabad Elite Catering', 40, 32, 500, 500)
ON CONFLICT (slug) DO NOTHING;

-- password: Admin@12345  (bcrypt) — change immediately in production
INSERT INTO users (tenant_id, email, full_name, role, password_hash) VALUES
('11111111-1111-1111-1111-111111111111', 'owner@hec.example', 'Owner', 'owner', '$2b$12$3F2FQmQ1r3xk1rY8VZk1JeMCTQSPCx1Yp8gYLtMGhuNwzM2p0OY8m'),
('11111111-1111-1111-1111-111111111111', 'sales@hec.example', 'Sales Desk', 'sales', '$2b$12$3F2FQmQ1r3xk1rY8VZk1JeMCTQSPCx1Yp8gYLtMGhuNwzM2p0OY8m')
ON CONFLICT DO NOTHING;

-- ── Ingredients ─────────────────────────────────────────────────────────────
INSERT INTO ingredients (tenant_id, key, name, unit, category, is_volatile, alert_threshold_pct) VALUES
('11111111-1111-1111-1111-111111111111','chicken','Chicken (dressed)','kg','meat',true,10),
('11111111-1111-1111-1111-111111111111','mutton','Mutton','kg','meat',true,8),
('11111111-1111-1111-1111-111111111111','fish','Fish (murrel/rohu)','kg','meat',true,12),
('11111111-1111-1111-1111-111111111111','prawns','Prawns','kg','meat',true,12),
('11111111-1111-1111-1111-111111111111','egg','Eggs','dozen','meat',true,15),
('11111111-1111-1111-1111-111111111111','paneer','Paneer','kg','dairy',false,15),
('11111111-1111-1111-1111-111111111111','milk','Milk','l','dairy',false,15),
('11111111-1111-1111-1111-111111111111','curd','Curd','kg','dairy',false,15),
('11111111-1111-1111-1111-111111111111','ghee','Ghee','kg','dairy',false,15),
('11111111-1111-1111-1111-111111111111','butter','Butter','kg','dairy',false,15),
('11111111-1111-1111-1111-111111111111','cream','Fresh cream','l','dairy',false,15),
('11111111-1111-1111-1111-111111111111','rice','Basmati rice','kg','grain',false,15),
('11111111-1111-1111-1111-111111111111','sona_rice','Sona masoori rice','kg','grain',false,15),
('11111111-1111-1111-1111-111111111111','wheat_flour','Wheat flour / maida','kg','grain',false,15),
('11111111-1111-1111-1111-111111111111','urad_dal','Urad dal','kg','grain',false,15),
('11111111-1111-1111-1111-111111111111','toor_dal','Toor dal','kg','grain',false,15),
('11111111-1111-1111-1111-111111111111','oil','Refined oil','l','oil',true,12),
('11111111-1111-1111-1111-111111111111','onion','Onion','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','tomato','Tomato','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','potato','Potato','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','green_chilli','Green chilli','kg','vegetable',true,25),
('11111111-1111-1111-1111-111111111111','ginger_garlic','Ginger-garlic','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','brinjal','Brinjal','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','raw_banana','Raw banana','kg','vegetable',false,20),
('11111111-1111-1111-1111-111111111111','mixed_veg','Mixed vegetables','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','coconut','Coconut','pc','vegetable',false,20),
('11111111-1111-1111-1111-111111111111','coriander_mint','Coriander & mint','kg','vegetable',true,25),
('11111111-1111-1111-1111-111111111111','lemon','Lemon','kg','vegetable',true,25),
('11111111-1111-1111-1111-111111111111','spices','Whole & ground spices','kg','spice',false,15),
('11111111-1111-1111-1111-111111111111','sugar','Sugar','kg','other',false,15),
('11111111-1111-1111-1111-111111111111','dry_fruits','Cashew, almond, raisins','kg','other',false,15),
('11111111-1111-1111-1111-111111111111','bread','Bread (double ka meetha)','kg','other',false,15),
('11111111-1111-1111-1111-111111111111','fruits','Seasonal fruits','kg','vegetable',true,20),
('11111111-1111-1111-1111-111111111111','tamarind','Tamarind','kg','other',false,15),
('11111111-1111-1111-1111-111111111111','pasta','Pasta','kg','grain',false,15),
('11111111-1111-1111-1111-111111111111','soda_syrups','Soda & syrups','l','other',false,15),
('11111111-1111-1111-1111-111111111111','tea_coffee','Tea/coffee','kg','other',false,15)
ON CONFLICT (tenant_id, key) DO NOTHING;

-- Prices: 8 days of wholesale history (Bowenpally / Rythu Bazar style) with a chicken + onion spike, plus retail today.
DO $$
DECLARE
  base jsonb := '{"chicken":200,"mutton":760,"fish":320,"prawns":520,"egg":78,"paneer":360,"milk":56,"curd":70,"ghee":620,"butter":480,"cream":220,
                  "rice":95,"sona_rice":58,"wheat_flour":42,"urad_dal":130,"toor_dal":150,"oil":128,"onion":26,"tomato":30,"potato":26,"green_chilli":60,
                  "ginger_garlic":140,"brinjal":34,"raw_banana":40,"mixed_veg":45,"coconut":28,"coriander_mint":80,"lemon":70,"spices":600,"sugar":44,
                  "dry_fruits":900,"bread":90,"fruits":80,"tamarind":160,"pasta":140,"soda_syrups":120,"tea_coffee":700}'::jsonb;
  k text; d int; p numeric; factor numeric; ing_id uuid;
BEGIN
  FOR k IN SELECT jsonb_object_keys(base) LOOP
    SELECT id INTO ing_id FROM ingredients WHERE tenant_id='11111111-1111-1111-1111-111111111111' AND key=k;
    FOR d IN 0..8 LOOP
      factor := 1;
      IF k = 'chicken' AND d <= 2 THEN factor := 1.16; END IF;   -- chicken spiked 16% in the last 3 days
      IF k = 'onion' AND d <= 3 THEN factor := 1.25; END IF;     -- onion spiked 25%
      IF k = 'tomato' AND d <= 1 THEN factor := 0.93; END IF;    -- tomato softened
      -- the jitter is float8, so cast the whole product back to numeric before round(numeric, int)
      p := round(((base->>k)::numeric * factor * (1 + (random()-0.5)*0.02)::numeric), 2);
      INSERT INTO ingredient_prices (tenant_id, ingredient_id, source, market, price_per_unit, observed_at)
      VALUES ('11111111-1111-1111-1111-111111111111', ing_id, 'bowenpally_wholesale', 'wholesale', p, now() - (d || ' days')::interval);
    END LOOP;
    INSERT INTO ingredient_prices (tenant_id, ingredient_id, source, market, price_per_unit, observed_at)
    VALUES ('11111111-1111-1111-1111-111111111111', ing_id, 'rythu_bazar_retail', 'retail', round((base->>k)::numeric * 1.28, 2), now());
  END LOOP;
END $$;

-- ── Menu categories ─────────────────────────────────────────────────────────
INSERT INTO menu_categories (tenant_id, key, name, sort_order) VALUES
('11111111-1111-1111-1111-111111111111','welcome_drinks','Welcome Drinks',1),
('11111111-1111-1111-1111-111111111111','starters','Starters',2),
('11111111-1111-1111-1111-111111111111','main_veg','Main Course · Veg',3),
('11111111-1111-1111-1111-111111111111','main_nonveg','Main Course · Non-Veg',4),
('11111111-1111-1111-1111-111111111111','rice_breads','Rice & Breads',5),
('11111111-1111-1111-1111-111111111111','live_counters','Live Counters',6),
('11111111-1111-1111-1111-111111111111','desserts','Desserts',7)
ON CONFLICT (tenant_id, key) DO NOTHING;

-- ── Menu items (recipes are per-guest quantities) ───────────────────────────
CREATE TEMP TABLE seed_items (slug text, cat text, name text, name_te text, descr text, diet diet_pref, jain bool, live bool, contains text[], labour numeric, setup numeric, tags text[], pop int, recipe jsonb);
INSERT INTO seed_items VALUES
('buttermilk','welcome_drinks','Spiced Buttermilk','మజ్జిగ','Chilled majjiga with curry leaf and ginger','veg',false,false,'{dairy,ginger}',1.5,0,'{traditional}',80,'{"curd":0.08,"spices":0.001,"coriander_mint":0.003,"ginger_garlic":0.002}'),
('nannari_sharbat','welcome_drinks','Nannari Sharbat','నన్నారి షర్బత్','Hyderabad summer classic with lemon','veg',true,false,'{}',1.5,0,'{traditional,summer}',70,'{"soda_syrups":0.03,"lemon":0.01,"sugar":0.01}'),
('watermelon_juice','welcome_drinks','Watermelon Cooler','','Fresh pressed, no added sugar','veg',true,false,'{}',2,0,'{healthy}',65,'{"fruits":0.15}'),
('virgin_mojito','welcome_drinks','Virgin Mojito','','Mint, lime, soda','veg',true,false,'{}',2.5,0,'{premium,party}',75,'{"soda_syrups":0.06,"lemon":0.02,"coriander_mint":0.01,"sugar":0.01}'),
('rose_milk','welcome_drinks','Rose Milk','రోజ్ మిల్క్','Chilled rose milk with sabja','veg',true,false,'{dairy}',1.5,0,'{traditional,kids}',60,'{"milk":0.12,"soda_syrups":0.015,"sugar":0.01}'),
('paneer_tikka','starters','Paneer Tikka','','Smoky tandoor paneer with mint chutney','veg',false,false,'{dairy,onion,garlic}',6,0,'{tandoor,premium}',90,'{"paneer":0.05,"curd":0.01,"onion":0.015,"spices":0.004,"oil":0.005}'),
('corn_cheese_balls','starters','Corn Cheese Balls','','Crispy, creamy, kids favourite','veg',true,false,'{dairy}',4,0,'{kids}',70,'{"paneer":0.02,"potato":0.03,"wheat_flour":0.01,"oil":0.02}'),
('veg_spring_roll','starters','Veg Spring Rolls','','Crunchy rolls with schezwan dip','veg',false,false,'{onion,garlic}',4,0,'{indo_chinese,kids}',60,'{"mixed_veg":0.04,"wheat_flour":0.015,"oil":0.02}'),
('mirchi_bajji','starters','Mirchi Bajji','మిర్చి బజ్జి','Hyderabadi street classic, stuffed','veg',true,false,'{}',3,0,'{traditional,hyderabadi}',75,'{"green_chilli":0.03,"wheat_flour":0.02,"oil":0.02,"tamarind":0.005}'),
('chicken_65','starters','Chicken 65','చికెన్ 65','Hyderabad favourite, halal, curry leaf tempered','non_veg',false,false,'{meat,garlic}',6,0,'{hyderabadi,spicy}',100,'{"chicken":0.08,"curd":0.01,"spices":0.005,"oil":0.02,"ginger_garlic":0.005}'),
('apollo_fish','starters','Apollo Fish','','Boneless fish tossed in spicy sauce','non_veg',false,false,'{meat,garlic}',7,0,'{hyderabadi,premium}',80,'{"fish":0.07,"wheat_flour":0.01,"spices":0.004,"oil":0.02,"ginger_garlic":0.004}'),
('mutton_seekh','starters','Mutton Seekh Kebab','','Tandoor seekh, halal','non_veg',false,false,'{meat,onion,garlic}',8,0,'{tandoor,premium}',75,'{"mutton":0.06,"onion":0.01,"spices":0.004,"oil":0.005,"ginger_garlic":0.003}'),
('chicken_malai_tikka','starters','Chicken Malai Tikka','','Creamy mild tandoor tikka','non_veg',false,false,'{meat,dairy,garlic}',7,0,'{tandoor,mild}',85,'{"chicken":0.07,"cream":0.01,"curd":0.01,"spices":0.003,"oil":0.005}'),
('paneer_butter_masala','main_veg','Paneer Butter Masala','','Rich tomato-cashew gravy','veg',false,false,'{dairy,onion,garlic,nuts}',6,0,'{north_indian,crowd_pleaser}',95,'{"paneer":0.06,"tomato":0.05,"onion":0.02,"butter":0.01,"cream":0.01,"dry_fruits":0.005,"spices":0.003}'),
('gutti_vankaya','main_veg','Gutti Vankaya Kura','గుత్తి వంకాయ','Stuffed brinjal in peanut-sesame gravy','veg',false,false,'{onion,garlic,nuts}',6,0,'{telugu,traditional}',85,'{"brinjal":0.08,"onion":0.02,"tamarind":0.005,"spices":0.005,"oil":0.012,"dry_fruits":0.004}'),
('dal_tadka','main_veg','Dal Tadka','పప్పు','Toor dal with ghee tempering','veg',false,false,'{onion,garlic}',3,0,'{staple}',80,'{"toor_dal":0.035,"tomato":0.02,"onion":0.01,"ghee":0.004,"spices":0.002}'),
('aratikaya_vepudu','main_veg','Aratikaya Vepudu','అరటికాయ వేపుడు','Raw banana fry, Jain friendly','veg',true,false,'{}',4,0,'{telugu,jain}',60,'{"raw_banana":0.07,"oil":0.012,"spices":0.004}'),
('kobbari_pachadi','main_veg','Kobbari Pachadi','కొబ్బరి పచ్చడి','Coconut chutney, Jain friendly','veg',true,false,'{}',2,0,'{telugu,jain}',55,'{"coconut":0.1,"green_chilli":0.003,"tamarind":0.002,"spices":0.001}'),
('mixed_veg_kurma','main_veg','Mixed Veg Kurma','','Coconut-based mild kurma','veg',false,false,'{onion,garlic,potato}',4,0,'{south_indian}',70,'{"mixed_veg":0.07,"coconut":0.05,"onion":0.015,"spices":0.003,"oil":0.01}'),
('chicken_biryani','main_nonveg','Chicken Dum Biryani','చికెన్ దమ్ బిర్యానీ','Authentic Hyderabadi kacchi dum, halal','non_veg',false,false,'{meat,onion,garlic,dairy}',12,0,'{hyderabadi,signature}',100,'{"chicken":0.18,"rice":0.12,"onion":0.05,"curd":0.02,"oil":0.02,"ghee":0.005,"spices":0.008,"coriander_mint":0.01,"ginger_garlic":0.006}'),
('mutton_biryani','main_nonveg','Mutton Dum Biryani','మటన్ దమ్ బిర్యానీ','Slow dum with tender mutton, halal','non_veg',false,false,'{meat,onion,garlic,dairy}',14,0,'{hyderabadi,premium,mutton}',90,'{"mutton":0.16,"rice":0.12,"onion":0.05,"curd":0.02,"oil":0.02,"ghee":0.005,"spices":0.008,"coriander_mint":0.01,"ginger_garlic":0.006}'),
('chicken_curry','main_nonveg','Andhra Chicken Curry','కోడి కూర','Spicy home-style curry','non_veg',false,false,'{meat,onion,garlic}',7,0,'{telugu,spicy}',85,'{"chicken":0.14,"onion":0.04,"tomato":0.03,"oil":0.015,"spices":0.006,"ginger_garlic":0.005}'),
('mutton_curry','main_nonveg','Mutton Masala','మటన్ కూర','Slow-cooked mutton masala','non_veg',false,false,'{meat,onion,garlic}',8,0,'{telugu,premium,mutton}',80,'{"mutton":0.12,"onion":0.04,"tomato":0.03,"oil":0.015,"spices":0.006,"ginger_garlic":0.005}'),
('fish_pulusu','main_nonveg','Chepala Pulusu','చేపల పులుసు','Tangy tamarind fish curry','non_veg',false,false,'{meat,onion,garlic}',7,0,'{telugu}',65,'{"fish":0.12,"onion":0.03,"tamarind":0.01,"tomato":0.02,"oil":0.015,"spices":0.005}'),
('egg_masala','main_nonveg','Egg Masala','గుడ్డు కూర','Boiled eggs in onion-tomato masala','non_veg',false,false,'{egg,onion,garlic}',4,0,'{budget}',60,'{"egg":0.17,"onion":0.03,"tomato":0.03,"oil":0.01,"spices":0.004}'),
('pulihora','rice_breads','Pulihora','పులిహోర','Tamarind rice, temple style','veg',true,false,'{}',3,0,'{telugu,traditional,jain}',80,'{"sona_rice":0.08,"tamarind":0.008,"oil":0.01,"spices":0.004,"dry_fruits":0.003}'),
('veg_biryani','rice_breads','Veg Dum Biryani','','Aromatic dum biryani with vegetables','veg',false,false,'{onion,garlic,dairy}',8,0,'{hyderabadi}',75,'{"rice":0.11,"mixed_veg":0.06,"onion":0.04,"curd":0.02,"oil":0.02,"spices":0.006,"coriander_mint":0.01}'),
('steamed_rice','rice_breads','Steamed Rice & Sambar','అన్నం సాంబార్','Sona masoori with drumstick sambar','veg',false,false,'{onion}',3,0,'{staple}',85,'{"sona_rice":0.1,"toor_dal":0.025,"mixed_veg":0.03,"tamarind":0.005,"spices":0.003}'),
('rumali_roti','rice_breads','Rumali Roti','','Paper-thin, made fresh','veg',true,false,'{}',4,0,'{tandoor}',70,'{"wheat_flour":0.06,"oil":0.005}'),
('live_dosa','live_counters','Live Dosa Counter','దోశ కౌంటర్','Crispy dosas made to order with 3 chutneys','veg',false,true,'{potato,onion}',6,2500,'{live,crowd_pleaser}',90,'{"sona_rice":0.05,"urad_dal":0.02,"potato":0.03,"onion":0.01,"oil":0.012,"coconut":0.03}'),
('live_chaat','live_counters','Live Chaat Station','','Pani puri, dahi puri, bhel — made fresh','veg',false,true,'{potato,onion,dairy}',6,3000,'{live,party,upsell}',85,'{"potato":0.04,"curd":0.02,"wheat_flour":0.02,"tamarind":0.005,"onion":0.01,"spices":0.003,"oil":0.01}'),
('live_pasta','live_counters','Live Pasta Counter','','Penne and fusilli in white/red sauce','veg',false,true,'{dairy,garlic}',7,3500,'{live,premium,kids}',70,'{"pasta":0.06,"cream":0.02,"tomato":0.03,"butter":0.005,"mixed_veg":0.02}'),
('live_mocktail','live_counters','Live Mocktail Bar','','Bartender-style mocktails, 6 flavours','veg',true,true,'{}',8,4000,'{live,premium,party,upsell}',75,'{"soda_syrups":0.12,"fruits":0.04,"lemon":0.02,"coriander_mint":0.005}'),
('live_tandoor','live_counters','Live Tandoor','','Kebabs and rotis straight from the tandoor','non_veg',false,true,'{meat,dairy,garlic}',10,5000,'{live,premium}',80,'{"chicken":0.07,"paneer":0.02,"wheat_flour":0.04,"curd":0.01,"spices":0.004,"oil":0.008}'),
('irani_chai','live_counters','Irani Chai & Osmania Biscuits','ఇరానీ చాయ్','Hyderabad ritual, served hot','veg',true,true,'{dairy}',3,1200,'{live,hyderabadi,traditional}',80,'{"milk":0.08,"tea_coffee":0.004,"sugar":0.01,"wheat_flour":0.02,"butter":0.005}'),
('gulab_jamun','desserts','Gulab Jamun','గులాబ్ జామూన్','Soft, warm, in cardamom syrup','veg',true,false,'{dairy}',2,0,'{classic}',95,'{"milk":0.05,"sugar":0.03,"wheat_flour":0.01,"oil":0.006}'),
('double_ka_meetha','desserts','Double ka Meetha','డబుల్ కా మీఠా','Hyderabadi bread pudding with saffron','veg',true,false,'{dairy,nuts}',3,0,'{hyderabadi,traditional}',85,'{"bread":0.04,"milk":0.06,"sugar":0.025,"ghee":0.008,"dry_fruits":0.006}'),
('qubani_ka_meetha','desserts','Qubani ka Meetha','ఖుబానీ కా మీఠా','Apricot dessert with cream','veg',true,false,'{nuts,dairy}',3,0,'{hyderabadi,premium}',75,'{"dry_fruits":0.03,"sugar":0.02,"cream":0.02}'),
('rasmalai','desserts','Rasmalai','','Chilled, saffron-kissed','veg',true,false,'{dairy,nuts}',3,0,'{premium}',80,'{"milk":0.12,"sugar":0.025,"dry_fruits":0.003}'),
('ice_cream','desserts','Ice Cream (2 flavours)','','Vanilla & butterscotch','veg',true,false,'{dairy}',1.5,0,'{kids}',70,'{"milk":0.06,"sugar":0.02,"cream":0.02}'),
('kaddu_kheer','desserts','Kaddu ki Kheer','గుమ్మడికాయ పాయసం','Bottle-gourd kheer, Hyderabadi','veg',true,false,'{dairy,nuts}',2.5,0,'{hyderabadi,traditional}',60,'{"mixed_veg":0.05,"milk":0.08,"sugar":0.02,"dry_fruits":0.004}');

INSERT INTO menu_items (tenant_id, category_id, slug, name, name_te, description, diet, is_jain_ok, is_live_counter, contains, labour_cost_per_guest, fixed_setup_cost, tags, popularity, min_guests)
SELECT '11111111-1111-1111-1111-111111111111', c.id, s.slug, s.name, NULLIF(s.name_te,''), s.descr, s.diet, s.jain, s.live, s.contains, s.labour, s.setup, s.tags, s.pop,
       CASE WHEN s.live THEN 50 ELSE 25 END
FROM seed_items s JOIN menu_categories c ON c.key = s.cat AND c.tenant_id='11111111-1111-1111-1111-111111111111'
ON CONFLICT (tenant_id, slug) DO NOTHING;

INSERT INTO menu_item_ingredients (menu_item_id, ingredient_id, qty_per_guest, waste_pct)
SELECT mi.id, i.id, (r.value)::numeric, 5
FROM seed_items s JOIN menu_items mi ON mi.slug = s.slug AND mi.tenant_id='11111111-1111-1111-1111-111111111111'
CROSS JOIN LATERAL jsonb_each_text(s.recipe) r
JOIN ingredients i ON i.key = r.key AND i.tenant_id='11111111-1111-1111-1111-111111111111'
ON CONFLICT DO NOTHING;

-- ── Package templates ────────────────────────────────────────────────────────
CREATE TEMP TABLE seed_pkgs (key text, tier text, name text, diet diet_pref, occasions text[], descr text, items text[]);
INSERT INTO seed_pkgs VALUES
('classic_veg','classic','Classic Veg','veg','{housewarming,pooja,birthday,naming_ceremony}','Honest, generous Telugu-style veg spread.','{buttermilk,mirchi_bajji,corn_cheese_balls,dal_tadka,mixed_veg_kurma,gutti_vankaya,steamed_rice,pulihora,gulab_jamun}'),
('signature_veg','signature','Signature Veg','veg','{housewarming,pooja,birthday,half_saree,anniversary}','Our most-booked veg package — adds paneer and a live dosa counter.','{buttermilk,nannari_sharbat,paneer_tikka,mirchi_bajji,corn_cheese_balls,paneer_butter_masala,gutti_vankaya,dal_tadka,steamed_rice,pulihora,live_dosa,gulab_jamun,double_ka_meetha}'),
('royal_veg','royal','Royal Veg','veg','{wedding,half_saree,corporate,anniversary}','Lavish veg with two live counters and Hyderabadi desserts.','{virgin_mojito,nannari_sharbat,paneer_tikka,veg_spring_roll,mirchi_bajji,paneer_butter_masala,gutti_vankaya,mixed_veg_kurma,dal_tadka,veg_biryani,rumali_roti,pulihora,live_dosa,live_chaat,gulab_jamun,qubani_ka_meetha,rasmalai}'),
('classic_nonveg','classic','Classic Non-Veg','non_veg','{birthday,corporate,festival_party}','Biryani-led classic with one veg main.','{buttermilk,chicken_65,mirchi_bajji,chicken_biryani,paneer_butter_masala,dal_tadka,steamed_rice,gulab_jamun}'),
('signature_nonveg','signature','Signature Non-Veg','non_veg','{wedding,birthday,corporate,anniversary,festival_party}','Chicken and mutton biryanis, tandoor starters, live tandoor.','{buttermilk,virgin_mojito,chicken_65,chicken_malai_tikka,paneer_tikka,chicken_biryani,mutton_curry,paneer_butter_masala,dal_tadka,steamed_rice,live_tandoor,gulab_jamun,double_ka_meetha}'),
('royal_nonveg','royal','Royal Non-Veg','non_veg','{wedding,corporate,festival_party}','Full Hyderabadi royal spread with three live counters.','{virgin_mojito,rose_milk,chicken_65,apollo_fish,mutton_seekh,paneer_tikka,chicken_biryani,mutton_biryani,fish_pulusu,paneer_butter_masala,gutti_vankaya,rumali_roti,live_tandoor,live_chaat,live_mocktail,gulab_jamun,qubani_ka_meetha,rasmalai,irani_chai}');

INSERT INTO package_templates (tenant_id, key, tier, name, diet, occasions, description)
SELECT '11111111-1111-1111-1111-111111111111', key, tier, name, diet, occasions, descr FROM seed_pkgs
ON CONFLICT (tenant_id, key) DO NOTHING;

INSERT INTO package_template_items (package_template_id, menu_item_id)
SELECT pt.id, mi.id FROM seed_pkgs s JOIN package_templates pt ON pt.key = s.key AND pt.tenant_id='11111111-1111-1111-1111-111111111111'
CROSS JOIN LATERAL unnest(s.items) it JOIN menu_items mi ON mi.slug = it AND mi.tenant_id='11111111-1111-1111-1111-111111111111'
ON CONFLICT DO NOTHING;

-- ── Discount rules ───────────────────────────────────────────────────────────
INSERT INTO discount_rules (tenant_id, key, name, kind, value, festival_key, booking_window_days_before_festival, guest_min, diet, stackable, priority, explanation_template, min_margin_pct) VALUES
('11111111-1111-1111-1111-111111111111','diwali_early_bird','Diwali Early Bird','percent',8,'diwali',14,NULL,NULL,false,10,'Book {days} days before {festival} and save {pct}% (₹{amount})',34),
('11111111-1111-1111-1111-111111111111','dasara_early_bird','Dasara Early Bird','percent',6,'dasara',10,NULL,NULL,false,12,'Confirm this week for {festival} and save {pct}% (₹{amount})',34),
('11111111-1111-1111-1111-111111111111','ganesh_veg_special','Vinayaka Chavithi Veg Special','percent',5,'ganesh_chaturthi',7,NULL,'veg',false,15,'{pct}% off pure-veg menus around {festival}',33),
('11111111-1111-1111-1111-111111111111','bathukamma_women','Bathukamma Celebration Offer','free_item',0,'bathukamma',5,100,'veg',true,20,'Complimentary {item} for {festival} celebrations',33),
('11111111-1111-1111-1111-111111111111','ramzan_iftar','Ramzan Iftar Offer','per_plate_off',20,'ramzan',7,100,'non_veg',false,15,'₹20 off per plate on iftar menus for {festival}',34),
('11111111-1111-1111-1111-111111111111','sankranti_family','Sankranti Family Offer','percent',5,'sankranti',10,NULL,NULL,false,18,'{pct}% off for {festival} family gatherings booked early',33),
('11111111-1111-1111-1111-111111111111','ugadi_pachadi','Ugadi Offer','free_item',0,'ugadi',5,50,'veg',true,25,'Free {item} for every guest this {festival}',33),
('11111111-1111-1111-1111-111111111111','newyear_party','New Year Party Offer','percent',5,'new_year',15,150,NULL,false,18,'{pct}% off party menus with live counters for {festival}',34),
('11111111-1111-1111-1111-111111111111','volume_300','Volume 300+','per_plate_off',15,NULL,NULL,300,NULL,true,50,'₹15 off per plate for {guests} guests',32),
('11111111-1111-1111-1111-111111111111','volume_450','Volume 450+','per_plate_off',25,NULL,NULL,450,NULL,true,49,'₹25 off per plate for {guests} guests',32),
('11111111-1111-1111-1111-111111111111','early_bird_30','Plan-Ahead 30 Days','percent',4,NULL,NULL,NULL,NULL,false,60,'Book 30+ days ahead and save {pct}%',34)
ON CONFLICT (tenant_id, key) DO NOTHING;
UPDATE discount_rules SET free_item_slug='irani_chai' WHERE key='bathukamma_women';
UPDATE discount_rules SET free_item_slug='buttermilk' WHERE key='ugadi_pachadi';

-- ── WhatsApp templates (names as approved in Meta Business Manager) ──────────
INSERT INTO whatsapp_templates (tenant_id, key, meta_name, language, category, params_schema) VALUES
('11111111-1111-1111-1111-111111111111','quote_ready','hec_quote_ready','en','UTILITY','["quote_number","per_plate","total","portal_url"]'),
('11111111-1111-1111-1111-111111111111','menu_change_update','hec_menu_change','en','UTILITY','["quote_number","change_summary","per_plate","total","portal_url"]'),
('11111111-1111-1111-1111-111111111111','price_lock_confirmation','hec_price_lock','en','UTILITY','["quote_number","per_plate","valid_until","certificate","portal_url"]'),
('11111111-1111-1111-1111-111111111111','payment_reminder','hec_payment_reminder','en','UTILITY','["quote_number","amount","link"]'),
('11111111-1111-1111-1111-111111111111','post_event_thankyou','hec_post_event','en','UTILITY','["occasion","review_url","next_offer"]'),
('11111111-1111-1111-1111-111111111111','festival_offer_alert','hec_festival_offer','en','MARKETING','["quote_number","offer","valid_until"]'),
('11111111-1111-1111-1111-111111111111','reengagement_festival','hec_reengage','en','MARKETING','["festival_name","date"]')
ON CONFLICT (tenant_id, key) DO NOTHING;

-- ── Upsell rules (seeded attach rates; learned later from quote_events) ───────
INSERT INTO upsell_rules (tenant_id, guest_min, guest_max, occasion, diet, suggest_item_slug, attach_rate, message) VALUES
('11111111-1111-1111-1111-111111111111',300,NULL,NULL,NULL,'live_mocktail',0.62,'Clients booking 300+ guests usually add a live mocktail bar — it keeps the crowd happy while food is served.'),
('11111111-1111-1111-1111-111111111111',150,NULL,NULL,NULL,'live_chaat',0.58,'Most 150+ guest events add a live chaat station; it is the most photographed counter.'),
('11111111-1111-1111-1111-111111111111',NULL,NULL,'birthday',NULL,'live_pasta',0.44,'Birthday parties love the live pasta counter — kids and adults both.'),
('11111111-1111-1111-1111-111111111111',NULL,NULL,NULL,'non_veg','live_tandoor',0.51,'Non-veg menus with a live tandoor get the best reviews for freshness.'),
('11111111-1111-1111-1111-111111111111',NULL,NULL,'corporate',NULL,'irani_chai',0.47,'Corporate evenings usually end with Irani chai and Osmania biscuits.'),
('11111111-1111-1111-1111-111111111111',NULL,NULL,'wedding',NULL,'qubani_ka_meetha',0.55,'Weddings in Hyderabad almost always add qubani ka meetha.'),
('11111111-1111-1111-1111-111111111111',80,NULL,NULL,NULL,'irani_chai',0.41,'Most functions end with Irani chai and Osmania biscuits — it is what guests remember.');

-- ── Partner venues ───────────────────────────────────────────────────────────
INSERT INTO venues (tenant_id, name, area, capacity, preferred_rate, tags) VALUES
('11111111-1111-1111-1111-111111111111','Sitara Grand Gardens','Kompally',500,85000,'{lawn,parking,power}'),
('11111111-1111-1111-1111-111111111111','Palm Meadows Lawn','Gachibowli',400,120000,'{lawn,indoor,corporate}'),
('11111111-1111-1111-1111-111111111111','Aakriti Convention','Kokapet',500,150000,'{indoor,two_halls}'),
('11111111-1111-1111-1111-111111111111','Vintage Palace','Secunderabad',250,60000,'{heritage,indoor}'),
('11111111-1111-1111-1111-111111111111','Rock Garden Terrace','Jubilee Hills',150,70000,'{rooftop,premium}');

-- ── Global festival calendar (mirrors app/festivals/calendar.py) ─────────────
INSERT INTO festivals (tenant_id, key, name, starts_on, ends_on, demand_multiplier, tags) VALUES
(NULL,'sankranti_2026','Sankranti / Pongal','2026-01-13','2026-01-16',1.25,'{veg_heavy,sweets,family}'),
(NULL,'ramzan_2026','Ramzan / Eid-ul-Fitr','2026-02-18','2026-03-20',1.30,'{non_veg,haleem,iftar,hyderabadi}'),
(NULL,'ugadi_2026','Ugadi','2026-03-19','2026-03-19',1.30,'{veg_heavy,telugu_new_year}'),
(NULL,'wedding_season_summer_2026','Wedding Season (Summer)','2026-04-15','2026-06-15',1.40,'{wedding,peak}'),
(NULL,'bakrid_2026','Bakrid','2026-05-27','2026-05-28',1.25,'{non_veg,mutton}'),
(NULL,'bonalu_2026','Bonalu','2026-07-12','2026-08-02',1.15,'{hyderabadi,telangana}'),
(NULL,'ganesh_chaturthi_2026','Ganesh Chaturthi','2026-09-14','2026-09-24',1.35,'{veg_heavy,sweets,community}'),
(NULL,'bathukamma_2026','Bathukamma','2026-10-09','2026-10-17',1.30,'{telangana,veg_heavy,women}'),
(NULL,'dasara_2026','Dasara','2026-10-11','2026-10-20',1.35,'{family,sweets}'),
(NULL,'diwali_2026','Diwali','2026-11-06','2026-11-10',1.40,'{sweets,corporate,family,peak}'),
(NULL,'wedding_season_winter_2026','Wedding Season (Winter)','2026-11-15','2027-02-28',1.45,'{wedding,peak}'),
(NULL,'christmas_2026','Christmas','2026-12-24','2026-12-26',1.20,'{corporate,cake}'),
(NULL,'new_year_2027','New Year''s Eve','2026-12-30','2027-01-01',1.35,'{corporate,party,peak}'),
(NULL,'sankranti_2027','Sankranti / Pongal','2027-01-13','2027-01-16',1.25,'{veg_heavy,sweets,family}'),
(NULL,'ramzan_2027','Ramzan / Eid-ul-Fitr','2027-02-08','2027-03-10',1.30,'{non_veg,haleem,iftar}'),
(NULL,'ugadi_2027','Ugadi','2027-04-07','2027-04-07',1.30,'{veg_heavy,telugu_new_year}')
ON CONFLICT (tenant_id, key) DO NOTHING;

-- ── Demo customer + lead (for dashboards) ────────────────────────────────────
INSERT INTO customers (id, tenant_id, wa_id, phone, full_name, area) VALUES
('22222222-2222-2222-2222-222222222222','11111111-1111-1111-1111-111111111111','919876543210','+919876543210','Lakshmi Prasanna','Kompally')
ON CONFLICT DO NOTHING;
INSERT INTO consents (tenant_id, customer_id, purpose, granted, evidence) VALUES
('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222','communication',true,'{"via":"seed"}'),
('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222','data_storage',true,'{"via":"seed"}')
ON CONFLICT DO NOTHING;
INSERT INTO leads (tenant_id, customer_id, source, stage, occasion, event_date, guest_count, diet, venue_area, budget_min_per_plate, budget_max_per_plate)
VALUES ('11111111-1111-1111-1111-111111111111','22222222-2222-2222-2222-222222222222','whatsapp','qualified','housewarming', current_date + 41, 120, 'veg', 'Kompally', 500, 600);

COMMIT;

-- After seeding, compute cached costs and build the RAG index:
--   python -m app.cli refresh-costs && python -m app.cli reindex
