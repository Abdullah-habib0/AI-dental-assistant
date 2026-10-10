/**
 * Reading clinic data from the FastAPI backend, on the server.
 *
 * These run in Server Components, at request time. They are deliberately not cached
 * with "use cache": a cached read would be run while the site is being BUILT, so every
 * deploy would need the backend to be up. Fetching per visit means a build never talks
 * to the backend, and a price changed in the database shows immediately - the same price
 * the chat assistant quotes.
 */

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

export type Service = {
  slug: string;
  name: string;
  summary: string;
  duration_minutes: number;
  price_cents: number;
};

export type ServiceDetail = Service & { description: string };

export type Dentist = {
  slug: string;
  name: string;
  qualifications: string;
  speciality: string;
  bio: string;
  photo_url: string;
};

export type Faq = { category: string; question: string; answer: string };

export type ClinicInfo = {
  name: string;
  phone: string;
  email: string;
  address: string;
  timezone: string;
  opening_hour: number;
  closing_hour: number;
  open_weekdays: number[]; // Monday = 0
};

export class NotFoundError extends Error {}

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${API_URL}/api/v1${path}`);
  if (response.status === 404) throw new NotFoundError(path);
  if (!response.ok) throw new Error(`Backend returned ${response.status} for ${path}`);
  return response.json() as Promise<T>;
}

export const getServices = () => get<Service[]>("/services");
export const getService = (slug: string) => get<ServiceDetail>(`/services/${encodeURIComponent(slug)}`);
export const getDentists = () => get<Dentist[]>("/dentists");
export const getFaqs = () => get<Faq[]>("/faqs");
export const getClinicInfo = () => get<ClinicInfo>("/clinic");
