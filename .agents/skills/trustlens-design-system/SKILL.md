# TrustLens AI Design System

## Purpose

This skill defines the reusable visual language of TrustLens AI.

All frontend pages and components should follow this system.

The goal is a cohesive premium AI/security product experience.

---

## Brand

Product:

TrustLens AI

Core concept:

"Multiple signals → one trust assessment"

Tone:

- Professional
- Intelligent
- Trustworthy
- Technical
- Modern
- Clear

Avoid a playful/social-media aesthetic.

---

## Visual Language

Primary style:

Dark premium SaaS + AI/security interface.

Use:

- deep dark backgrounds
- subtle borders
- elevated surfaces
- restrained gradients
- blue/cyan accents
- green/amber/red status colors
- rounded components
- clean typography
- subtle motion

Avoid:

- excessive glassmorphism
- excessive neon
- excessive gradients
- excessive shadows
- cartoon-style graphics
- generic Bootstrap styling
- unnecessary decorative elements

---

## Status System

Success:

Use green.

Meaning:
- Authentic
- Completed
- Successful

Review:

Use amber.

Meaning:
- Needs Review
- Attention
- Additional inspection

Suspicious:

Use red.

Meaning:
- Potentially Suspicious
- Failed validation
- High-risk signal

Neutral:

Use blue/gray.

Meaning:
- Processing
- Information
- General status

Never communicate important status through color alone.

Use icons and text as well.

---

## Cards

Cards should use:

- subtle border
- consistent radius
- restrained shadow
- clear internal spacing

Cards should not become nested endlessly.

Use cards to group meaningful information.

---

## Buttons

Primary button:

Used for the main action.

Examples:

- Analyze Image
- Get Started
- Generate Report

Secondary button:

Used for supporting actions.

Examples:

- How It Works
- View Details

Destructive:

Used only for destructive actions.

Examples:

- Delete Account
- Delete Analysis

Icon-only buttons must have accessible labels/tooltips.

---

## Trust Score

Trust Score is a primary visual element.

Use:

- large numerical value
- category
- visual progress/ring
- supporting explanation

Do not use random decorative gauges.

The visualization must represent the real score.

---

## Evidence

Evidence should use a consistent visual pattern.

Each evidence item should contain:

- icon
- title
- result
- confidence/value
- explanation

Examples:

Tampering Detection

AI-Generated Detection

OCR

Image Quality

ELA

---

## Spacing

Use consistent spacing tokens.

Avoid arbitrary margins.

Major sections should have more spacing than internal elements.

---

## Responsive Behavior

Desktop:

Use multi-column layouts where useful.

Tablet:

Reduce columns.

Mobile:

Stack important information vertically.

Results page should prioritize:

1. Trust Score
2. Summary
3. Detection results
4. Evidence
5. ELA
6. Report actions

---

## Motion

Motion must communicate state or improve usability.

Good examples:

- score count-up
- card entrance
- hover elevation
- upload drag feedback
- progress transitions
- toast entrance

Keep transitions subtle.

Respect prefers-reduced-motion.

---

## Consistency Rule

A component should not introduce a new visual pattern if an existing
TrustLens component already solves the same problem.

Extend reusable components instead.

---

## Data Integrity Rule

The design system must never encourage fake visual data.

Charts, scores, metrics and analysis states must use actual backend data.

When real data does not exist, use an honest empty/loading state.