import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

// Same origin as the page (nginx in production, the Vite proxy in development),
// so the httpOnly auth cookie is sent automatically and never touched by JavaScript.
export const api = createClient<paths>({ credentials: "include" });

type Schemas = components["schemas"];
export type Service = Schemas["ServicePublic"];
export type ServiceAdmin = Schemas["ServiceAdmin"];
export type Provider = Schemas["ProviderPublic"];
export type ProviderAdmin = Schemas["ProviderAdmin"];
export type WindowOut = Schemas["WindowOut"];
export type TimeOffOut = Schemas["TimeOffOut"];
export type Booking = Schemas["BookingOut"];
export type AdminBooking = Schemas["BookingAdminOut"];
export type BookingStatus = Booking["status"];
export type BookingAction = Booking["allowed_actions"][number];
export type User = Schemas["UserOut"];
export type Meta = Schemas["MetaOut"];
