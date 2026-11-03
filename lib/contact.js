import { site } from "@/data/site";

// All email links are built from the ONE email in data/site.js.
const { email, emailSubject } = site.contact;

export const mailtoHref = `mailto:${email}?subject=${encodeURIComponent(emailSubject)}`;
export const gmailHref = `https://mail.google.com/mail/?view=cm&to=${encodeURIComponent(email)}&su=${encodeURIComponent(emailSubject)}`;
