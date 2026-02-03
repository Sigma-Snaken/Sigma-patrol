## 2026-02-03 - Accessibility Pattern: Icon-Only Buttons
**Learning:** This app uses visual D-pads and icon buttons (like Emergency Stop) extensively without text labels, relying on tooltips (`title`). This is a common pattern here that excludes screen reader users.
**Action:** Systematically check all new icon-only controls for `aria-label` matching or improving upon the `title` attribute.
