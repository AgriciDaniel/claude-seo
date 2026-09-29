# Prompt Adaptation, Mistakes and Safety Rephrasing: Claude Banana

> Split from `prompt-engineering.md`. Load it when adapting a prompt to a model, reviewing a weak prompt, or handling an `IMAGE_SAFETY` block.

## Prompt Adaptation Rules

When adapting prompts from the claude-prompts database (Midjourney/DALL-E/etc.)
to Gemini's natural language format:

| Source Syntax | Gemini Equivalent |
|---------------|-------------------|
| `--ar 16:9` | Call `set_aspect_ratio("16:9")` separately |
| `--v 6`, `--style raw` | Remove - Gemini has no version/style flags |
| `--chaos 50` | Describe variety: "unexpected, surreal composition" |
| `--no trees` | Positive framing: "open clearing with no vegetation" |
| `(word:1.5)` weight | Descriptive emphasis: "prominently featuring [word]" |
| `8K, masterpiece, ultra-detailed` | Keep only "ultra-realistic, high resolution"; remove the rest |
| Comma-separated tags | Expand into descriptive narrative paragraphs |
| `shot on Hasselblad` | Keep - camera specs work well in Gemini |

## Common Prompt Mistakes

1. **Keyword stuffing**:stacking generic quality terms ("8K, masterpiece, best quality") adds nothing. Use only "ultra-realistic, high resolution" at the end
2. **Tag lists**:Gemini wants prose, not "red car, sunset, mountain, cinematic"
3. **Missing lighting**:The single biggest quality differentiator
4. **No composition direction**:Results in generic centered framing
5. **Vague style**:"make it look cool" vs specific art direction
6. **Ignoring aspect ratio**:Always set before generating
7. **Overlong prompts**:Diminishing returns past ~200 words; be precise, not verbose
8. **Text longer than ~25 characters**:Rendering degrades rapidly past this limit
9. **Burying key details at the end**:In long prompts, details placed last may be deprioritized; put critical specifics (exact text, key constraints) in the first third of the prompt
10. **Not iterating with follow-up prompts**:Use `gemini_chat` for progressive refinement instead of trying to get everything right in one generation

## Safety Filter Rephrase Strategies

Gemini's safety filters (Layer 2: server-side output filter) cannot be disabled.
When a prompt is blocked, the only path forward is rephrasing.

### Common Trigger Categories

| Category | Triggers on | Rephrase approach |
|----------|------------|-------------------|
| Violence/weapons | Combat, blood, injuries, firearms | Use metaphor or aftermath: "battle-worn" → "weathered veteran" |
| Medical/gore | Surgery, wounds, anatomical detail | Abstract or clinical: "open wound" → "medical illustration" |
| Real public figures | Named celebrities, politicians | Use archetypes: "Elon Musk" → "a tech entrepreneur in a minimalist office" |
| Children + risk | Minors in any ambiguous context | Add safety context: specify educational, family, or playful framing |
| NSFW/suggestive | Revealing clothing, intimate poses | Use artistic framing: "fashion editorial, fully clothed, editorial pose" |

### Rephrase Patterns

1. **Abstraction**:Replace specific dangerous elements with abstract concepts
2. **Artistic framing**:Frame content as art, editorial, or documentary
3. **Metaphor**:Use symbolic language instead of literal descriptions
4. **Positive emphasis**:Describe what IS present, not what's dangerous
5. **Context shift**:Move from threatening to educational/professional context

### Example Rephrases

| Blocked prompt | Successful rephrase |
|----------------|---------------------|
| "a soldier in combat firing a rifle" | "a determined soldier standing guard at dawn, rifle slung over shoulder, morning mist over the outpost" |
| "a scary horror monster" | "a fantastical creature from a dark fairy tale, intricate organic textures, bioluminescent accents, concept art style" |
| "dog in a fight" | "a friendly golden retriever playing energetically in a sunny park, action shot, joyful expression" |
| "medical surgery scene" | "a clean modern operating room viewed from the observation gallery, soft blue surgical lights, professional documentary style" |
| "celebrity portrait of [name]" | "a distinguished middle-aged man in a tailored navy suit, warm studio lighting, editorial portrait style" |

### Key Principle

Layer 2 (output filter) analyzes the generated image, not just the prompt.
Even well-phrased prompts can be blocked if the model's interpretation triggers
the output filter. When this happens, try shifting the visual concept further
from the trigger rather than just changing words.
