# Proven Prompt Templates: Claude Banana

> Split from `prompt-engineering.md`. Load it when you need a ready-made template for a use case.

## Proven Prompt Templates

> Extracted from 2,500+ tested prompts. These patterns consistently produce
> high-quality results. Use them as starting points and adapt to the request.

### The Winning Formula (Weight Distribution)

| Component | Weight | What to include |
|-----------|--------|-----------------|
| **Subject** | 40% | Age, skin tone, hair color/style, eye color, body type, expression |
| **Styling** | 25% | Brand names, textures, fit, accessories, colors |
| **Environment** | 15% | Location + time of day + context details |
| **Camera** | 10% | Camera model + lens + focal length + shot type |
| **Lighting** | 10% | Quality, direction, color temperature, shadows |

### Instagram Ad / Social Media

**Pattern:** `[Subject with age/appearance] + [outfit with brand/texture] + [action verb] + [setting] + [camera spec] + [lighting] + [platform aesthetic]`

**Example (Product Placement):**
```
Hyper-realistic gym selfie of athletic 24yo influencer with glowing olive
skin, wearing crinkle-textured athleisure set in mauve. iPhone 16 Pro Max
front-facing portrait mode capturing sweat droplets on collarbones, hazel
eyes enhanced by gym LED lighting. Mirror reflection shows perfect form,
golden morning light through floor-to-ceiling windows. Frayed chestnut
ponytail with baby hairs, ultra-detailed skin texture, trending aesthetic.
```

**Example (Lifestyle Ad):**
```
A 24-year-old blonde fitness model in a high-energy sports drink
advertisement. Mid-run on a beach, wearing a vibrant orange sports bra
and black shorts, playful smile and sparkling blue eyes exuding vitality.
Bottle of the drink held in hand, waves crashing in background. Shot on
Nikon D850 with 70-200mm f/2.8 lens, natural light, fast shutter speed
capturing motion. Ultra-realistic skin texture, water droplets, product
label clearly visible.
```

**Example (Luxury Lifestyle):**
```
Gorgeous Instagram model wearing a designer silk gown, luxury rooftop
restaurant, golden hour lighting, champagne in hand, luxurious aspirational
lifestyle. Captured with Sony A7R IV, 85mm f/1.4 lens, shallow depth of
field, warm color grading.
```

### Product / Commercial Photography

**Pattern:** `[Product with brand/detail] + [dynamic elements] + [surface/setting] + "commercial photography for advertising campaign" + [lighting] + "high resolution"`

**Example (Beverage):**
```
Gatorade bottle with condensation dripping down the sides, surrounded by
lightning bolts and a burst of vibrant blue and orange light rays. The
Gatorade logo is prominently displayed on the bottle, with splashes of
water frozen in mid-air. Commercial food photography for an advertising
campaign, high resolution, high level of detail, vibrant complementary
colors.
```

**Example (Food):**
```
In and Out burger with layers of fresh lettuce, melted cheese, and pretzel
bun, placed on a white surface with the In and Out logo subtly glowing in
the background. Falling french fries and golden light, warm scene.
Commercial food photography for an advertising campaign, high resolution,
high level of detail, vibrant complementary colors.
```

### Fashion / Editorial

**Pattern:** `[Subject with ethnicity/age/features] + [outfit with texture/brand/cut] + [location] + [pose/action] + [camera + lens] + [lighting quality]`

**Example (Street Style):**
```
A 24-year-old female AI influencer posing confidently in an urban cityscape
during golden hour. Flawless sun-kissed skin, long wavy brown hair, deep
green eyes. Wearing a chic streetwear outfit: oversized beige blazer,
white top, high-waisted jeans. Captured with Sony A7R IV at 85mm f/1.4,
shallow depth of field with warm golden bokeh.
```

**Example (High Fashion):**
```
Stunning 24-year-old woman, long platinum blonde hair, radiant skin,
piercing blue eyes, dressed in a chic pastel blazer with a modern
minimalist aesthetic, soft sunlight glow, high-end fashion appeal.
Shot on Canon EOS R5, 85mm f/1.2 lens.
```

**Example (Avant-Garde):**
```
A blonde fitness model transformed into a runway-ready fashion icon,
wearing a bold avant-garde outfit: cropped leather jacket with neon pink
accents, paired with high-waisted athletic shorts and knee-high boots.
Captured mid-stride on a minimalist white runway, playful twinkle in her
eye, dramatic studio lighting from above.
```

### SaaS / Tech Marketing

**Pattern:** `[UI mockup or abstract visual] + "on [dark/light] background" + [specific colors with hex] + [typography description] + "clean, premium SaaS aesthetic" + [glassmorphism/gradient/glow effects]`

**Example (Dashboard Hero):**
```
A floating glassmorphism UI card on a deep charcoal background showing a
content analytics dashboard with a rising line graph in teal (#14B8A6),
bar charts in coral (#F97316), and a circular progress indicator at 94%.
Subtle grid lines, frosted glass effect with 20% opacity, teal glow
bleeding from the card edges. Clean premium SaaS aesthetic, no text
smaller than headline size.
```

**Example (Feature Highlight):**
```
An isometric 3D illustration of interconnected data nodes on a dark navy
background. Each node is a glowing teal sphere connected by thin luminous
lines, forming a constellation pattern. One central node pulses brighter
with radiating rings. Modern tech illustration style with subtle depth
of field, volumetric lighting from below.
```

**Example (Comparison/Before-After):**
```
Split-screen image: left side shows a cluttered, dim workspace with
scattered papers, red error indicators, and a frustrated expression
conveyed through a cracked coffee mug and tangled cables. Right side
shows a clean, organized dashboard interface glowing in teal and white
on a dark background, with smooth flowing lines and checkmarks. A sharp
vertical dividing line separates chaos from clarity.
```

### Logo / Branding

**Pattern:** `[Product/bottle/item] + "with [brand element] prominently displayed" + [dynamic visual elements] + "commercial photography" + [lighting style] + "high resolution, vibrant complementary colors"`

**Example:**
```
A sleek matte black bottle with a minimal white logo mark centered on the
label, surrounded by swirling gradient ribbons of teal and coral light.
The bottle sits on a reflective dark surface, sharp studio rim lighting
separating it from the background. Product photography for luxury
branding, high resolution, dramatic contrast.
```

### Key Tactics That Make Prompts Work

1. **Name real cameras**:"Sony A7R IV", "Canon EOS R5", "iPhone 16 Pro Max" anchor realism
2. **Specify exact lens**:"85mm f/1.4" gives the model precise depth-of-field information
3. **Use age + ethnicity + features**:"24yo with olive skin, hazel eyes" beats "a person"
4. **Name brands for styling**:"Lululemon mat", "Tom Ford suit" triggers specific visual associations
5. **Include micro-details**:"sweat droplets on collarbones", "baby hairs stuck to neck"
6. **Add platform context**:"Instagram aesthetic", "commercial photography for advertising"
7. **Describe textures**:"crinkle-textured", "metallic silver", "frosted glass"
8. **Use action verbs**:"mid-run", "posing confidently", "captured mid-stride"
9. **End with "ultra-realistic, high resolution"**:these two specific anchors help on Gemini. Avoid generic stacking like "8K, masterpiece, best quality" which adds no value
10. **For products, say "prominently displayed"**:ensures the product/logo isn't hidden

### Anti-Patterns (What NOT to Do)

- **"A dark-themed Instagram ad showing..."**:too meta, describes the concept not the image
- **"A sleek SaaS dashboard visualization..."**:abstract, no visual anchors
- **"Modern, clean, professional..."**:vague adjectives that mean nothing to the model
- **"A bold call to action with..."**:describes marketing intent, not visual content
- **Describing what the viewer should feel**:instead, describe what creates that feeling
