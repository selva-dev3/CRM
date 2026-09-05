import type { Metadata } from "next";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui";
import { Badge } from "@/components/ui";
import { Button } from "@/components/ui";
import { Input } from "@/components/ui";

export const metadata: Metadata = {
  title: "Typography Style Guide",
  description:
    "Enterprise typography system: type scale, hierarchy, WCAG AA contrast verification, and font pairing rationale.",
};

const scaleRows = [
  { token: "--text-3xl", rem: "2.75rem", px: "44px", leading: "3.25rem", use: "Hero / display", sample: "Aa" },
  { token: "--text-2xl", rem: "2rem", px: "32px", leading: "2.5rem", use: "H1 / page titles", sample: "Aa" },
  { token: "--text-xl", rem: "1.5rem", px: "24px", leading: "2rem", use: "H2 / section heads", sample: "Aa" },
  { token: "--text-lg", rem: "1.125rem", px: "18px", leading: "1.75rem", use: "H3 / card titles", sample: "Aa" },
  { token: "--text-base", rem: "1rem", px: "16px", leading: "1.5rem", use: "Body copy", sample: "Aa" },
  { token: "--text-sm", rem: "0.875rem", px: "14px", leading: "1.25rem", use: "Dense UI: tables, inputs, buttons", sample: "Aa" },
  { token: "--text-xs", rem: "0.75rem", px: "12px", leading: "1rem", use: "Captions, labels, badges", sample: "Aa" },
];

const contrastRows = [
  {
    token: "--color-text-primary",
    hex: "#111827",
    onWhite: "17.74",
    onSurface: "16.98",
    status: "AAA",
    note: "Headings & highest-emphasis text",
  },
  {
    token: "--color-text-secondary",
    hex: "#374151",
    onWhite: "10.31",
    onSurface: "9.86",
    status: "AAA",
    note: "Body copy",
  },
  {
    token: "--color-text-muted",
    hex: "#6B7280",
    onWhite: "4.83",
    onSurface: "4.63",
    status: "AA",
    note: "Captions / secondary UI text — do not go lighter",
  },
  {
    token: "--color-text-inverse",
    hex: "#FFFFFF",
    onWhite: "—",
    onSurface: "17.74 on #111827",
    status: "AAA",
    note: "Text on dark/primary surfaces",
  },
  {
    token: "--color-text-placeholder",
    hex: "#9CA3AF",
    onWhite: "2.54",
    onSurface: "2.43",
    status: "Fail",
    note: "Placeholder / disabled content ONLY — never real content",
  },
  {
    token: "brand link",
    hex: "#2563EB",
    onWhite: "5.17",
    onSurface: "—",
    status: "AA",
    note: "Inline links & primary actions",
  },
];

const statusVariant: Record<string, "default" | "secondary" | "warning" | "success" | "danger"> = {
  AAA: "success",
  AA: "success",
  Fail: "danger",
};

export default function TypographyStyleGuidePage() {
  return (
    <div className="space-y-6 text-text-secondary">
      <div>
        <h1 className="text-page-title">Typography Style Guide</h1>
        <p className="text-body text-text-muted mt-1">
          Token-driven enterprise type system. All sizes/weights/colors map to tokens in{" "}
          <code className="font-mono text-xs bg-slate-100 rounded px-1 py-0.5">src/styles/typography.css</code> — no
          one-off sizes in components.
        </p>
      </div>

      {/* ─── Type scale ─────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Type scale</CardTitle>
          <CardDescription>Modular ≈1.25 ratio — legibility over drama. Line-heights live alongside each size.</CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-table font-semibold">Token</TableHead>
                <TableHead className="text-table font-semibold">Size</TableHead>
                <TableHead className="text-table font-semibold">Leading</TableHead>
                <TableHead className="text-table font-semibold">Use</TableHead>
                <TableHead className="text-table font-semibold">Sample</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {scaleRows.map((row) => (
                <TableRow key={row.token} className="text-table">
                  <TableCell className="font-mono text-xs">{row.token}</TableCell>
                  <TableCell>
                    {row.rem} <span className="text-text-muted">({row.px})</span>
                  </TableCell>
                  <TableCell className="text-text-muted">{row.leading}</TableCell>
                  <TableCell>{row.use}</TableCell>
                  <TableCell className="text-2xl font-semibold leading-tight">{row.sample}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ─── Hierarchy ─────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Hierarchy</CardTitle>
          <CardDescription>
            One H1 per page. Headings follow document structure; the visual weight/size contrast between adjacent
            levels is deliberate, never a 2px nudge.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-slate-200 pb-3">
            <h1 className="text-page-title">Page title (H1 · .text-page-title)</h1>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-slate-200 pb-3">
            <h2 className="text-section-title">Section title (H2 · .text-section-title)</h2>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-slate-200 pb-3">
            <h3 className="text-card-title">Card title (H3 · .text-card-title)</h3>
          </div>
          <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 border-b border-slate-200 pb-3">
            <h4 className="text-subheading">Subheading (H4 · .text-subheading)</h4>
          </div>
        </CardContent>
      </Card>

      {/* ─── Body & supporting variants ────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Body &amp; supporting text</CardTitle>
          <CardDescription>
            Body is 16px minimum (1.5 leading). 14px is a documented exception for dense data tables, inputs, and
            buttons. Keep paragraphs ≤ 65ch.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-body text-measure">
            <span className="text-caption font-semibold uppercase tracking-wide mr-2">.text-body · 16px/1.5</span>
            Enterprise content is often dense; unconstrained line length kills readability. This paragraph is clamped to
            65ch and reads comfortably at default body size with secondary contrast (10.31:1 — AAA).
          </p>
          <p className="text-caption">
            <span className="font-semibold uppercase tracking-wide mr-2">.text-caption · 12px</span>
            Muted helper text, legal notes, and secondary labels.
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-label">.text-label</span>
            <Button size="sm">.text-button (sm)</Button>
            <Button size="lg">.text-button (lg)</Button>
            <Badge variant="secondary">.text-badge</Badge>
          </div>
          <div className="flex flex-col gap-2 max-w-md">
            <span className="text-caption font-semibold uppercase tracking-wide">.text-field</span>
            <Input
              className="flex h-10 w-full rounded-input border border-[#E5E7EB] bg-white px-3 py-2 text-field placeholder:text-text-placeholder focus:outline-none focus:border-[#2563EB] focus:ring-2 focus:ring-[#2563EB]/20 transition duration-150 shadow-saas-sm"
              placeholder="Placeholder text (2.54:1 — placeholder only)"
            />
          </div>
        </CardContent>
      </Card>

      {/* ─── Links ─────────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Links</CardTitle>
          <CardDescription>
            Inline links use brand blue (5.17:1 AA) and keep a visible focus ring. Meaning is never conveyed by color
            alone — underlines always present on links.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-body text-measure">
            Default{" "}
            <a
              href="#"
              className="font-medium text-text-primary underline decoration-text-primary/40 underline-offset-4 transition-colors hover:decoration-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-text-primary"
            >
              inline link
            </a>{" "}
            · Hover{" "}
            <a
              href="#"
              className="font-medium text-text-primary underline decoration-text-primary underline-offset-4"
            >
              link hover
            </a>{" "}
            · Focus (Tab to this){" "}
            <a
              href="#"
              className="font-medium text-text-primary underline decoration-text-primary/40 underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-text-primary"
            >
              link focus
            </a>
            .
          </p>
          <div className="rounded-btn bg-text-primary p-4">
            <p className="text-caption text-text-inverse">
              Inverse: <span className="font-medium">white on #111827 (17.74:1)</span> for dark surfaces.
            </p>
          </div>
        </CardContent>
      </Card>

      {/* ─── Data / numbers ────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Data &amp; tabular values</CardTitle>
          <CardDescription>
            Numbers align with <code className="font-mono text-xs bg-slate-100 rounded px-1 py-0.5">tabular-nums</code>{" "}
            on .text-table so columns line up; mono is reserved for code and raw data.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="font-mono text-xs">
            <span className="text-caption mr-2">mono:</span>
            <code className="text-text-primary">2026-08-14 · 14:03:22 · org_id=9f2c</code>
          </p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-table font-semibold">Invoice</TableHead>
                <TableHead className="text-table font-semibold text-right">Amount</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {[
                ["INV-0001", "1,234.50"],
                ["INV-0002", "99.00"],
                ["INV-0003", "12,040,000.75"],
              ].map(([inv, amt]) => (
                <TableRow key={inv} className="text-table">
                  <TableCell>{inv}</TableCell>
                  <TableCell className="text-right">{amt}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ─── Contrast ──────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Color &amp; WCAG 2.1 AA contrast</CardTitle>
          <CardDescription>
            Verified against both <code className="font-mono text-xs">#FFFFFF</code> (cards) and{" "}
            <code className="font-mono text-xs">#F9FAFB</code> (surface background). Normal text ≥ 4.5:1; large text ≥
            3:1.
          </CardDescription>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-table font-semibold">Token</TableHead>
                <TableHead className="text-table font-semibold">Hex</TableHead>
                <TableHead className="text-table font-semibold">on #FFF</TableHead>
                <TableHead className="text-table font-semibold">on #F9FAFB</TableHead>
                <TableHead className="text-table font-semibold">Status</TableHead>
                <TableHead className="text-table font-semibold">Note</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {contrastRows.map((row) => (
                <TableRow key={row.token} className="text-table">
                  <TableCell className="font-mono text-xs">{row.token}</TableCell>
                  <TableCell>
                    <span className="inline-flex items-center gap-2">
                      <span
                        className="inline-block w-4 h-4 rounded border border-slate-300"
                        style={{ backgroundColor: row.hex }}
                        aria-hidden
                      />
                      <span className="font-mono text-xs">{row.hex}</span>
                    </span>
                  </TableCell>
                  <TableCell>{row.onWhite}</TableCell>
                  <TableCell>{row.onSurface}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant[row.status]}>{row.status}</Badge>
                  </TableCell>
                  <TableCell className="text-text-muted">{row.note}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* ─── Responsive ────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Responsive display type</CardTitle>
          <CardDescription>
            Hero/display sizes clamp fluidly instead of jumping at breakpoints; body copy never shrinks below 16px.
            Verify at 200% browser zoom — text reflows without horizontal scroll (WCAG 1.4.4).
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-hero">Fluid hero heading</p>
          <p className="text-caption mt-1">
            <code className="font-mono text-xs">clamp(2rem, 2.5vw + 1.125rem, 2.75rem)</code> — 32px→44px fluid.
          </p>
        </CardContent>
      </Card>

      {/* ─── Rationale ─────────────────────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle>Pairing rationale (do not “fix” this)</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-body text-measure">
            We ship a single-family system built on <strong>Inter</strong> for both display and body. Enterprise
            evaluators read a neutral, high-x-height humanist grotesque as credible and legible at the small sizes dense
            CRMs demand, where a decorative display face would read as editorial and undercut trust. One family halves
            the font budget versus a two-family pairing while keeping every weight optically consistent — and the UI is
            95% body text, so the body face is the brand. Hierarchy is communicated by size and weight contrast
            (headings 700/600 with tight leading; body 400 with relaxed leading), not by switching typefaces. Geist
            Mono is the single mono family for data, code, and tabular values.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
