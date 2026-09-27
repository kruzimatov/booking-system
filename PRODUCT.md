# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are clients booking an appointment on a mobile device, often with limited time and attention. Administrators manage bookings during a busy workday.

## Product Purpose

Booking is an appointment system for a small service business such as a barbershop. Clients choose a service, provider, date, and available time, then track or cancel their bookings. The business manages the catalog, providers, schedules, time off, and booking lifecycle.

## Positioning

The product makes appointment booking dependable under real contention: availability is computed by the server and database constraints prevent double booking, even when multiple people choose the same slot.

## Operating Context

Clients use the booking flow from a phone and need to make a confident choice quickly. Administrators use a bookings dashboard to confirm, complete, cancel, and review appointments.

## Capabilities and Constraints

The current booking flow, routes, API behavior, server-side rules, and existing product copy must remain intact during the visual redesign. The frontend uses React, TypeScript, Mantine, TanStack Query, and generated OpenAPI types. The interface must remain accessible, responsive at 375px, keyboard usable, and clear about Tashkent time.

## Brand Commitments

The user selected a warm, editorial, human direction: tactile surfaces, confident typography, and a calm accent. The interface should feel trustworthy and local rather than generic or overly playful.

## Evidence on Hand

The implemented product and API are in this repository. No external brand assets, testimonials, or marketing claims were provided; future UI must not invent them.

## Product Principles

- Make the next booking decision obvious.
- Reassure clients that availability and booking state are current.
- Preserve useful context without overwhelming a small screen.
- Make operational states legible for both clients and administrators.
