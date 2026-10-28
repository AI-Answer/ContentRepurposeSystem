# Pixel-Pal Carousel — Design System (source of truth)

Reverse-engineered from the reference deck. Everything below is LOCKED — reproduce it
exactly so slides stay consistent.

## 1. Color palette (use these hex values verbatim in prompts)

| Role | Hex | Where |
|---|---|---|
| Signature orange | `#FF5C1F` | one emphasis word per headline, mascot body, chip number, tip-box icon, arrow/underline on dark slide |
| Near-black bg | `#0A0A0A` | HOOK slide background only |
| Cream text | `#F5F2ED` | HOOK slide headline + body, hand-drawn accents on dark |
| Pure white bg | `#FFFFFF` | ALL interior + CTA slides |
| Ink black text | `#111111` | interior headlines + bold body |
| Warm gray body | `#5A5A5A` | interior secondary paragraph text |
| Pale peach | `#FFF3E9` | section chip pill + tip-box background |
| Accent blue (rare) | `#1A73E8` | ONLY when contrasting two concepts (e.g. "pictures" vs "words"); otherwise never used |

Orange is the ONE hero accent. Do not introduce other colors except the rare blue.

## 2. The mascot (identity — keep byte-stable)

> A chunky, cute **8-bit pixel-art blob character**, solid **orange `#FF5C1F`** body
> with darker-orange pixel shading on the lower-left edges, two simple **square black
> pixel eyes**, stubby little pixel arms and feet, no mouth. Retro video-game sprite
> look, crisp hard pixel edges, no gradients, no anti-aliasing on the character.

Per-slide props/costumes (mix to fit the beat — this is what gives each slide life):
- big black **headphones** + red-and-white striped **popcorn bucket**, lounging in a beanbag facing a pixel laptop (chill/watching)
- yellow **hard hat** + black **wrench**, one angry eyebrow (frustrated/problem)
- blue headphones + a pixel **heart** thought-bubble (in love / delighted)
- blonde pixel wig + pink **tutu** + magic **wand**, teacher/fairy pose (explaining/showing off)
- pixel **cape** + confident arms-up pose (hero / win)
- holding a glowing pixel **lightbulb** or pixel **trophy** / pixel **rocket** (idea / result / launch)
Invent new props in the same 8-bit style as the topic needs. Always the SAME orange blob underneath.

## 3. Two slide archetypes

### A) HOOK slide (slide 1 ONLY)
- Background: near-black `#0A0A0A`, with a subtle low-opacity pixel-art night scene
  faintly visible (e.g. cozy room, window with pixel moon + city lights) — dark and moody.
- Headline: **SERIF** font (Charter / Source Serif vibe), 3 lines. First + third line
  in cream `#F5F2ED`; the middle emphasis line ONE big word in orange `#FF5C1F`
  ~1.6x larger. Top-left aligned, starts ~8% from top.
- A hand-drawn **cream double-underline scribble** under the last headline line.
- A small handwritten cream sub-line ("here's how →" / "here's the deal.") with a
  curved hand-drawn **cream arrow** pointing to the mascot.
- Mascot: bottom-right, lit warmly, in a "chill/watching" pose.
- Right-edge: a small white **`>` chevron inside a faint circle**, vertically centered on the right margin (carousel nav cue).

### B) INTERIOR / CTA slide (slides 2..N)
- Background: pure white `#FFFFFF`.
- Top-left: **section chip** — a pale-peach `#FFF3E9` rounded pill containing the
  orange `#FF5C1F` two-digit number (e.g. "02") + a short dark-gray label
  ("The problem", "How it works", "What you can do"). Small caps, ~top 6%.
- Headline: **BOLD SANS** (Inter / Helvetica-Now vibe), heavy weight, ink black
  `#111111`, 1-3 lines, top-left, with ONE key word in orange `#FF5C1F`.
- Body: 1-2 short sentences, warm gray `#5A5A5A`, medium weight, can bold or
  orange-highlight a single key phrase.
- Illustration: mascot (+ optional pixel prop/object/machine/diagram) anchored in the
  LOWER portion of the slide, leaving airy whitespace above.
- Optional **speech bubble**: rounded white bubble with a tail, ink text, one orange word.
- Footer: pale-peach `#FFF3E9` rounded **tip-box** spanning near-full width, with a
  small orange icon (lightbulb / 8-pointed asterisk-spark) on the left and one short
  punchy line, a key word bold or orange. Use on most teaching slides.
- Right-edge (and optionally left-edge): small gray `>` / `<` chevron nav dots,
  vertically centered (carousel cue).

## 4. Layout grid (both archetypes)
- Canvas 1080x1350 (4:5). Side margins ~8%. Generous whitespace.
- Reading order top→bottom: chip → headline → body → illustration → tip-box.
- Illustration always anchors the bottom third; text lives in the top two-thirds.

## 5. LOCKED prompt template

Fill placeholders in `{{ }}`. Keep the STYLE BLOCK identical on every slide of a deck.
Everything the slide must display goes in "double quotes" + "spelled exactly, verbatim".

```
Instagram carousel slide, portrait 4:5 (1080x1350), flat editorial graphic-design layout — {{HOOK or INTERIOR}} slide.

STYLE BLOCK (keep identical across the deck):
Design system: clean modern educational carousel. Signature orange #FF5C1F is the single hero accent. Cute chunky 8-bit PIXEL-ART blob mascot — solid orange #FF5C1F body, darker-orange pixel shading on lower-left edges, two square black pixel eyes, stubby pixel arms/feet, no mouth, crisp hard pixel edges, no gradients on the character, retro game-sprite look. Same mascot identity on every slide.

{{FOR HOOK}}
Background: near-black #0A0A0A with a faint low-opacity pixel-art night room (window, pixel moon, distant city lights), moody.
Headline in a warm SERIF, top-left, 3 lines: line1 "{{L1}}" in cream #F5F2ED, line2 "{{ORANGE WORD}}" in orange #FF5C1F about 1.6x larger, line3 "{{L3}}" in cream #F5F2ED — all spelled exactly, verbatim. A hand-drawn cream double-underline scribble beneath line3.
Small handwritten cream sub-line "{{SUBLINE}}" with a curved hand-drawn cream arrow pointing toward the mascot.
Mascot bottom-right, {{MASCOT POSE/PROPS}}, warmly lit.
A small white ">" chevron in a faint circle centered on the right edge (carousel nav).

{{FOR INTERIOR/CTA}}
Background: pure white #FFFFFF.
Top-left section chip: pale-peach #FFF3E9 rounded pill with orange #FF5C1F "{{NN}}" then dark-gray "{{CHIP LABEL}}" — spelled exactly, verbatim.
Headline in HEAVY BOLD SANS, ink black #111111, top-left: "{{HEADLINE}}" with the word "{{ORANGE WORD}}" in orange #FF5C1F — spelled exactly, verbatim.
Body, warm gray #5A5A5A, medium weight: "{{BODY}}" — spelled exactly, verbatim{{, with "KEYPHRASE" bold}}.
Illustration anchored lower-center/side: the orange pixel blob mascot {{MASCOT POSE/PROPS + any pixel object/machine/diagram}}.
{{optional}} Rounded white speech bubble with a tail: "{{BUBBLE TEXT}}" (one word "{{ORANGE}}" in orange), spelled exactly, verbatim.
{{optional}} Bottom pale-peach #FFF3E9 rounded tip-box, full width, small orange {{lightbulb/8-point spark}} icon at left, text "{{TIP TEXT}}" with "{{BOLD WORD}}" bold — spelled exactly, verbatim.
Small gray ">" chevron nav dot centered on the right edge.

Typography crisp and legible, high contrast, no watermark, no gibberish text, no extra UI, professional graphic design.
```

## 6. QC checklist (run image_analyze on the finished set)
1. Every visible word spelled correctly (GPT Image loves to typo long copy).
2. The ORANGE word is the intended emphasis word.
3. Mascot is the same orange 8-bit blob on every slide.
4. Section chip numbers are sequential (01/02/03…).
5. No cropped/cut-off text; margins respected.
6. Tip-box and chevron present where planned.
Regenerate failures: retry same prompt once → simplify copy → last resort re-word.

