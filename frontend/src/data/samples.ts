import type { Conversation } from '../lib/types'

export const EXAMPLE_PROMPTS: { label: string; prompt: string; topic: string }[] = [
  { topic: 'Power rule', label: 'f(x) = x³ + 2x² − 5x + 7', prompt: 'Find the derivative of f(x) = x^3 + 2x^2 - 5x + 7' },
  { topic: 'Chain rule', label: '(x² + 1)⁵', prompt: 'Find the derivative of (x^2 + 1)^5' },
  { topic: 'Product rule', label: 'x² sin(x)', prompt: 'Differentiate x^2 sin(x)' },
  { topic: 'Quotient rule', label: '(x² + 1) / (x − 1)', prompt: 'Differentiate (x^2 + 1)/(x - 1)' },
  { topic: 'Implicit', label: 'x² + y² = 25', prompt: 'Find dy/dx if x^2 + y^2 = 25' },
  { topic: 'Second derivative', label: 'e^(2x) sin(x)', prompt: 'Find the second derivative of e^(2x) sin(x)' },
]

export const FOLLOW_UP_CHIPS = [
  'Why did you use this rule?',
  'Explain it in simpler words',
  'Can you solve this using another method?',
  'Give me a similar problem to practice',
]

const t0 = Date.UTC(2026, 9, 1, 9, 0, 0)

/** A pre-loaded example so the interface isn't empty on first visit. */
export const SAMPLE_CONVERSATION: Conversation = {
  id: 'sample-power-rule',
  title: 'Example: x³ + 2x² − 5x + 7',
  createdAt: t0,
  updatedAt: t0,
  messages: [
    {
      id: 's1',
      role: 'user',
      createdAt: t0,
      content: 'Find the derivative of f(x) = x^3 + 2x^2 - 5x + 7.',
    },
    {
      id: 's2',
      role: 'assistant',
      createdAt: t0 + 1000,
      kind: 'solution',
      source: 'engine',
      verified: true,
      content: `Let's solve this step by step.

### Problem
Find the derivative of

$$ f(x) = x^{3} + 2 x^{2} - 5 x + 7 $$

### Rules we'll use
- **Sum and difference rule** — differentiate each term separately.
- **Power rule** — $\\frac{d}{dx}x^n = nx^{n-1}$.
- **Constant multiple rule** — constants stay in front.
- **Constant rule** — the derivative of a constant is 0.

### Step-by-step solution

**Step 1: Differentiate each term**

$$ \\begin{aligned} \\frac{d}{dx}\\left[x^{3}\\right] &= 3 x^{2} \\\\ \\frac{d}{dx}\\left[2 x^{2}\\right] &= 4 x \\\\ \\frac{d}{dx}\\left[- 5 x\\right] &= -5 \\\\ \\frac{d}{dx}\\left[7\\right] &= 0 \\end{aligned} $$

**Step 2: Combine the results**

$$ f'(x) = 3 x^{2} + 4 x - 5 $$

### Final answer
$$ \\boxed{f'(x) = 3 x^{2} + 4 x - 5} $$

### Verification
**✅ Verified** by the symbolic math engine.`,
      context: {
        original: 'x**3 + 2*x**2 - 5*x + 7',
        original_latex: 'x^{3} + 2 x^{2} - 5 x + 7',
        variable: 'x',
        order: 1,
        implicit: false,
        derivative: '3*x**2 + 4*x - 5',
        derivative_latex: '3 x^{2} + 4 x - 5',
        answer_latex: "f'(x) = 3 x^{2} + 4 x - 5",
        rules: ['Sum and difference rule', 'Power rule', 'Constant multiple rule', 'Constant rule'],
        verified: true,
        verification_method: 'symbolic simplification check + independent numerical differentiation',
      },
    },
  ],
}
