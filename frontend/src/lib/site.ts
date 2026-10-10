/**
 * The website's own identity. The clinic's contact details, hours and prices are NOT
 * here - they come from the backend, so there is one place to change them.
 */
export const site = {
  name: "Bright Smile Dental",
  tagline: "Gentle, modern dentistry on the High Street",
  nav: [
    { href: "/services", label: "Treatments" },
    { href: "/dentists", label: "Our team" },
    { href: "/faq", label: "FAQ" },
    { href: "/contact", label: "Contact" },
  ],
} as const;
