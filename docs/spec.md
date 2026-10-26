# Forever Service Board — Product & Technical Specification

> **Working name:** *Forever Service Board* (placeholder — final name must avoid Blizzard trademarks, see §11.4)
> **Version:** 0.2 (pre-prototype — stack decided: FastAPI + PostgreSQL + Nuxt)
> **Date:** 26 October 2026
> **Target game:** World of Warcraft: Forever (launch: 4 November 2026)

---

## Table of contents

1. [Summary](#1-summary)
2. [The problem](#2-the-problem)
3. [Goals and non-goals](#3-goals-and-non-goals)
4. [Game facts that shape the design](#4-game-facts-that-shape-the-design)
5. [Users and core use cases](#5-users-and-core-use-cases)
6. [Feature specification](#6-feature-specification)
7. [Data sources: what is available and what is not](#7-data-sources-what-is-available-and-what-is-not)
8. [Architecture](#8-architecture)
9. [Data model](#9-data-model)
10. [Key flows](#10-key-flows)
11. [Compliance, rules and privacy](#11-compliance-rules-and-privacy)
12. [Risks and mitigations](#12-risks-and-mitigations)
13. [Open questions to verify at launch](#13-open-questions-to-verify-at-launch)
14. [Roadmap](#14-roadmap)
15. [Success metrics](#15-success-metrics)
16. [Sources](#16-sources)

---

## 1. Summary

A web app where WoW Forever players **list in-game services** they offer — summons, portals, enchants, crafted items and more — and other players **find them with filters** instead of scrolling through chat.

- Players **log in with Battle.net**. Their characters are imported automatically, so nobody types a character name, faction or ruleset by hand, and nobody can list someone else's character.
- A seller picks one of their characters, a **service type**, and fills a short form. For crafts and enchants, they search the item or enchant and the **reagents are filled in automatically** from game data. They choose whether the buyer pays only gold, or gold plus some or all of the materials.
- Buyers see only listings they can actually use: **same region, same ruleset, same faction** as their active character.
- Contact happens **in game**: the buyer copies a ready-made whisper (`/w <name> …`) and pastes it into WoW chat.
- **Web-only first.** No addon is required. An optional addon may come later for live online status (§14, Phase 4).

---

## 2. The problem

Finding a service in WoW Forever today means using chat:

- Trade, General and LookingForGroup channels are noisy, scroll fast, and mix buying, selling, recruiting and conversation.
- There is no structured way to ask "who can craft X right now, and what do I need to bring?".
- Forever has **no summoning stones** at dungeon entrances. The only way to summon is the Warlock's Ritual of Summoning, which needs two other party members present. Its group finder is the Classic-style one, which organizes groups but does not teleport anyone. Travel services are therefore in real demand.
- Forever adds **more than 600 new profession recipes**, so "who can make this?" is harder to answer from memory than in Classic.
- Existing addons (ForeverCodex, CraftBoard, GuildCrafts, EnchantOrders…) solve crafter discovery **inside a guild**. Nothing found so far offers an open, ruleset-wide marketplace for services.

---

## 3. Goals and non-goals

### Goals

| # | Goal |
|---|------|
| G1 | A buyer finds a suitable, available service provider in **under a minute**. |
| G2 | A seller creates a listing in **under 30 seconds** with no manual typing of names, items or reagents. |
| G3 | Listings are **trustworthy**: the character belongs to the lister, and stale listings disappear on their own. |
| G4 | Works on **phone and desktop**, so it can be used on a second screen while playing. |
| G5 | Fully within Blizzard's rules (API terms, game ToS). |

### Non-goals (for now)

- **No real-money transactions** of any kind. Prices are in-game gold only.
- **No in-game automation**: no bots, no injected clients, no automated chat.
- **No in-site chat between users** in the MVP. Contact happens in WoW. (Could be revisited.)
- **No auction-house price tracking** in the MVP.
- **No addon** in the MVP.

---

## 4. Game facts that shape the design

These facts come from Blizzard announcements and press coverage. Each one has a direct effect on the product.

| Fact | Effect on the product |
|------|-----------------------|
| **No realms.** Characters choose a **ruleset**: Normal, PvP, Roleplaying, with Hardcore after launch. Each ruleset works like one very large realm per region. | Filters use **region + ruleset**, not realm. |
| Grouping (and in practice trading face to face) only works **within the same ruleset**. Battlegrounds can mix rulesets, but that doesn't matter for services. | A listing is only shown to buyers on the **same ruleset**. |
| **Factions stay separate.** Horde and Alliance cannot group. | A listing is only shown to buyers on the **same faction**. Faction comes from the character data. |
| **Hardcore** (post-launch) is a fully separate ecosystem. | Hardcore is its own ruleset value. No mixing. |
| On the **PvP ruleset**, an account can only have characters of **one faction**. On the other rulesets both factions are allowed. | Many users will have characters on both factions, so an **active-character switcher** is essential. |
| The new **Skyborne** race can join **either faction**. | Faction must come from the character's faction field, **never inferred from race**. |
| **Two-part names** (first name + surname), **unique across the whole region**, even across rulesets. | A character is identified by **region + full name**. The whisper uses the full name. |
| **Language preference** is an account-wide setting that matches players with others sharing that language. | Add a **language** filter and a language field on the user profile. |
| No summoning stones; Ritual of Summoning needs **3 players** (warlock + 2 helpers). | Summon listings must say where the warlock is and whether helpers are already present. |
| Mages: **Teleport** spells move only the mage. **Portal** spells move the party. | Selling travel means selling **Portals**, not Teleports. The UI uses the word "Portal". |
| **600+ new recipes**, changed reagents, plus **camping** and **profession buffs**. | Recipe data must come from **Forever's own game data**, not Classic. |
| Launch: **4 November 2026**, 3:00 PM PST. | API and data availability can only be confirmed after launch (§13). |

---

## 5. Users and core use cases

### Personas

- **The seller (provider).** A warlock who wants to sell summons in Orgrimmar. An enchanter who sells weapon enchants. A blacksmith who crafts gear. Wants visibility with minimal effort.
- **The buyer (customer).** Needs a summon to a dungeon, a portal home, an enchant, or a crafted item. Wants to know quickly who is available, how much it costs and what to bring.
- **The browser (logged out).** Checks prices or availability before deciding to sign in.

### Core use cases

| ID | As a… | I want to… |
|----|-------|------------|
| UC1 | Seller | sign in with Battle.net and see my Forever characters already imported |
| UC2 | Seller | create a listing ("Summon, from Orgrimmar, 2g") in a few clicks |
| UC3 | Seller | list a craft, search the item, and have its reagents filled in automatically |
| UC4 | Seller | say which reagents I provide and which the buyer must bring |
| UC5 | Seller | mark myself Available / Busy, and refresh a listing with one tap from my phone |
| UC6 | Buyer | see only listings for my region, ruleset and faction |
| UC7 | Buyer | filter by service type, profession, item, location, price, freshness, language |
| UC8 | Buyer | see exactly which materials I need to bring, with icons and quantities |
| UC9 | Buyer | copy a ready-made whisper and paste it into WoW |
| UC10 | Buyer | rate the service afterwards, or report a fake or abusive listing |
| UC11 | Any user | switch my active character and have the whole board re-filter |

---

## 6. Feature specification

### 6.1 Authentication and account

- **Sign in with Battle.net** (OAuth 2.0 authorization code flow, scope `wow.profile`).
- The user chooses their **region** at sign-in (US, EU, KR, TW), because the Battle.net API and character names are per region.
- On every sign-in, re-import the character list (see §7.2 on why: user tokens are short-lived).
- Account page: language preference, linked characters, "Unlink Battle.net and delete my data" (§11.3).
- Logged-out users can browse after choosing region + ruleset + faction manually. Creating listings, rating and reporting require sign-in.

### 6.2 Characters

- Imported from the account profile: name (both parts), faction, race, class, level, ruleset, region, guild (if available), last-logout time.
- Only **WoW Forever** characters are shown (the account endpoint returns characters for one game version per namespace).
- The user can hide characters they don't want to use on the site.
- The **active character** (header switcher) decides the scope of the whole board: region + ruleset + faction. Switching re-filters instantly.

### 6.3 Service types (catalog)

The service-type catalog is **data-driven** (a database table, not hard-coded), so new types can be added without a release.

| Type | Who can offer it | What the seller specifies | Uses item/recipe data? |
|------|------------------|---------------------------|------------------------|
| **Summon** | Warlock | Current location (zone/city), helpers present? (0/1/2), price | No |
| **Portal** | Mage | Destination city(ies) from the list the mage can open, current location, price, reagent (Rune of Portals) included? | No (destination list is data) |
| **Enchant** | Enchanter | One or more enchants, price per enchant, reagent split | **Yes** (recipe → reagents) |
| **Craft** | Any crafting profession | One or more craftable items, quantity, price, reagent split | **Yes** (recipe → item + reagents) |
| **Other** (later) | Varies | Free-form but structured: e.g. lockpicking (rogue), conjured food/water, camping profession buffs | Partly |

Rules:
- The **class/profession filter is enforced**: only a warlock character can create a Summon listing, only a mage a Portal listing. Class is known from the API. Profession knowledge may not be verifiable (§7.4), so Enchant/Craft listings are self-declared at first.
- Portal destinations: the six classic capital cities (Alliance: Stormwind, Ironforge, Darnassus; Horde: Orgrimmar, Undercity, Thunder Bluff), limited to the seller's faction. Stored as data because Forever may add more.

### 6.4 Listing creation (the modal)

A step-by-step modal:

1. **Character** — preselected to the active character; can change.
2. **Service type** — only types that character can offer.
3. **Details** — depends on the type:
   - *Summon / Portal*: location, destination(s), helpers present, price.
   - *Craft / Enchant*:
     1. **Search the item or enchant** (autocomplete with icon, quality color and profession; only craftable entries).
     2. **Quantity** (crafts).
     3. **Payment mode**:
        - **Gold only** — seller provides everything.
        - **Gold + buyer's materials** — all reagents shown, buyer brings them.
        - **Mixed** — full reagent list with a toggle per reagent: *I provide* / *Buyer brings*.
     4. Reagent quantities **multiply automatically** with the quantity.
     5. For enchants: the target slot is shown (from the enchant data); the buyer brings the item to enchant.
     6. Tools the seller always needs (e.g. an enchanting rod) are shown as "seller's tool", not as buyer materials.
4. **Price** — in gold/silver/copper. Optional "tips welcome" flag.
5. **Availability** — Available now / Scheduled (e.g. "today 20:00–22:00 server time").
6. **Note** — short free text (max ~200 characters), filtered for links and profanity.
7. **Preview** — exactly what buyers will see. Publish.

Limits: one active listing per **character × service type** (a crafter can bundle several items into one Craft listing). This prevents spam without blocking real sellers.

### 6.5 The board (browse and filter)

- **Scope (always applied):** region, ruleset, faction of the active character (or the manual choice when logged out).
- **Filters:** service type, profession, item/enchant search, location (zone/city), portal destination, price range, payment mode ("I don't want to bring mats"), freshness ("updated in the last 10 min"), language, seller rating.
- **Sort:** freshest first (default), cheapest, best rated.
- **Listing card:** character name + class icon, service, item icon/enchant, price, materials the buyer brings (icons + quantities), location, freshness badge ("updated 3 min ago"), availability (Available / Busy / Scheduled), rating.
- **Listing detail:** full reagent table, item tooltip, seller profile (other listings, rating), copy-whisper button, report button.
- Real-time updates: new listings and status changes appear without reload (§8).

### 6.6 Contacting the seller

- **Copy whisper** button copies a ready-made line, e.g.:
  `/w <FullName> Hi! I saw your summon listing on <site> (2g). Can you summon me to Orgrimmar?`
- Plain **copy name** button as well.
- The exact whisper syntax for two-part names must be confirmed at launch (§13).
- Optional: buyer clicks "I contacted this seller" — used only for ratings eligibility and stats.

### 6.7 Freshness and expiry

This is the main weakness of a web-only product (the site cannot see the game), so it gets explicit rules:

| Service type | Default lifetime | Refresh |
|--------------|------------------|---------|
| Summon, Portal | **30 minutes** | One-tap "Still here" resets the timer |
| Enchant | **24 hours** | One tap |
| Craft | **7 days** | One tap |

- Sellers can switch **Available ↔ Busy** at any time; Busy listings stay visible but sorted lower.
- **Auto-hide inactive characters**: if the character's last-logout time from the API is older than a threshold (e.g. 14 days), their listings are hidden. Note this field only proves *recent activity*, never *online now* (§7.3).
- Expired listings can be re-published in one click from "My listings".

### 6.8 Trust: ratings and reports

- **Ownership is guaranteed** by Battle.net login: a listing can only be created from a character on the lister's own account.
- **Ratings**: after "I contacted this seller", the buyer can give thumbs up / down and an optional short comment within 72 hours. One rating per buyer per seller per day.
- **Reports**: fake listing, no-show, scam, offensive note. Repeated reports auto-hide a listing pending review.
- **Admin tools** (minimal): review queue, hide listing, suspend user.

### 6.9 Notifications (post-MVP)

- Saved searches: "notify me when a Portal to Undercity appears" (web push / email).
- Seller reminders: "Your summon listing expires in 5 min — still there?"

---

## 7. Data sources: what is available and what is not

### 7.1 Availability matrix

| Need | Source | Status today (22 Oct 2026) | Confidence |
|------|--------|---------------------------|-----------|
| Battle.net login | Battle.net OAuth (`wow.profile` scope) | Available, standard | High |
| User's Forever characters | Profile API `/profile/user/wow` + per-character `/profile/wow/character/{realm}/{name}` | Endpoints exist for Retail/Classic. **Forever namespace not yet documented by Blizzard**; developers are asking on the API forums | **Unknown until launch** |
| Character faction, class, level | Character profile | Available for Retail/Classic | Likely |
| "Is the character online now?" | — | **Not available.** `last_login_timestamp` exists but developers report it reflects the last *logout* and is not live | High (that it's missing) |
| Character professions/recipes known | Retail has a professions endpoint; Classic APIs historically do not | **Probably not available for Forever** | Low |
| Items (name, icon, quality, class, stats) | Game Data API: `/data/wow/item/{id}`, `/data/wow/item-class/…`, `/data/wow/media/item/{id}`, `/data/wow/search/item` | Exists; Forever namespace pending | Likely |
| Recipes → reagents → created item | Blizzard recipe endpoints (Retail); otherwise the game's own data tables (DB2) published by **wago.tools** | Blizzard: uncertain for Forever. wago.tools publishes tables per build; community tools already read Forever beta tables from it | Medium |
| Item tooltips on the site | Build our own from item data; or an embeddable tooltip script if a fan site offers one for Forever | To verify | Medium |
| Wowhead data | No public API; Wowhead tries to prevent scraping | **Do not use** | — |

### 7.2 Battle.net OAuth and the Profile API

- Standard authorization-code flow. After the redirect, exchange the code for a user access token and call `/profile/user/wow` with the Forever profile namespace.
- **User tokens last 24 hours and cannot be renewed automatically.** Consequence: character data is refreshed **at each sign-in**, not in the background. The site's own session can last longer than the Blizzard token; we store the imported data, not the token.
- The **namespace** is a configuration value (`BLIZZARD_PROFILE_NAMESPACE`, `BLIZZARD_STATIC_NAMESPACE`), so it can be switched the day Blizzard publishes the Forever one. Until then, the prototype uses mock data.
- Rate limits: **36,000 requests/hour and 100 requests/second** per client; going over the per-second limit returns HTTP 429, and developers report the hourly cap is strictly enforced. Our usage is small (≈1–N calls per sign-in, plus a periodic catalog import), but the API client must throttle and back off anyway.

### 7.3 Online status

There is **no API for live online status**. The product handles this with:
1. Short expiry + "Still here" refresh for live services (§6.7).
2. Available / Busy toggle.
3. Hiding characters inactive for a long time (last-logout field).
4. Later: an optional addon that reports status (§14, Phase 4).

### 7.4 Item and recipe catalog

**Principle: the app reads only from its own database.** External sources only fill it, through an import job. This makes the source swappable and keeps the site fast and within rate limits.

Import pipeline (per game build):
1. **Items**: from the Blizzard item API (names, icons, quality, class) once the Forever namespace exists; or from the game data tables.
2. **Recipes**: from the game data tables via wago.tools. In WoW's data, a recipe is a spell linked to a profession; the reagent list and the created item come from the spell's data. The exact table names for Forever's build must be validated on the real data before building the importer.
3. **Enchants**: same as recipes, but the result is an effect on a slot, not an item.
4. **Validation**: spot-check a sample of recipes against the in-game profession window after launch.
5. Store the **build version** on every catalog row, so changes between patches can be detected and listings referencing removed recipes can be flagged.

Notes:
- wago.tools is **community-run**. Cache everything locally, never call it at request time, and be polite with downloads.
- Using datamined client tables is common practice among fan sites, but it is a grey area with respect to Blizzard's terms (§11.1). Prefer the official API wherever it covers the need.

### 7.5 Recipe ownership verification

Probably not possible through the API for Forever (§7.1). Plan:
- MVP: self-declared, protected by ratings and reports.
- Later: if Blizzard exposes professions for Forever, show a "verified recipe" badge.
- Later: the optional addon could export the character's known recipes (Phase 4).

---

## 8. Architecture

### 8.1 Overview

Three deployable parts: a **Nuxt** frontend (server-rendered), a **FastAPI** backend, and **PostgreSQL**. Background work runs in a separate worker process that shares the backend's code.

```
 ┌──────────────┐  HTTPS   ┌──────────────────────┐  /api/*   ┌────────────────────────────┐
 │  Browser /   │ ───────▶ │  Nuxt (SSR)          │ ────────▶ │  FastAPI                   │
 │  phone       │ ◀─────── │  - pages, components │ ◀──────── │  - REST API (OpenAPI)      │
 └──────┬───────┘          │  - OG meta for links │           │  - Battle.net OAuth        │
        │                  └──────────────────────┘           │  - session cookies         │
        │   SSE (live board updates)                          │  - SSE endpoint            │
        └────────────────────────────────────────────────────▶│  - Blizzard API client     │
                                                              └─────────────┬──────────────┘
                                                                            │ SQLAlchemy (async)
                                                                            ▼    ▲ LISTEN/NOTIFY
 ┌────────────────────────────┐   writes catalog     ┌──────────────────────────────────────┐
 │  Worker (same codebase)    │ ───────────────────▶ │  PostgreSQL                          │
 │  - expire listings         │                      │  users, characters, listings,        │
 │  - 30-day purge            │                      │  ratings, reports, items, recipes…   │
 │  - catalog import per build│ ◀── Blizzard Game Data API                                  │
 └────────────────────────────┘ ◀── wago.tools game tables  └──────────────────────────────┘
```

**Request routing.** Frontend and API are served under the **same site**, with the API under `/api` (a reverse proxy such as Caddy or Nginx in front, or Nuxt's server proxy in development). This keeps the session cookie first-party, avoids CORS, and makes the OAuth redirect URL simple: `https://<site>/api/auth/battlenet/callback`.

### 8.2 Stack

| Layer | Choice | Why |
|-------|--------|-----|
| **Backend framework** | **FastAPI** (Python 3.12+) | Async, fast to write, automatic **OpenAPI** schema; Python suits the data-heavy catalog import |
| Validation / settings | **Pydantic v2** + `pydantic-settings` | Request/response models; all config (namespaces, regions, secrets) from environment variables |
| Database | **PostgreSQL 16+** | `pg_trgm` for item autocomplete, native enums/arrays/JSONB, partial unique indexes, `LISTEN/NOTIFY` for realtime |
| ORM / migrations | **SQLAlchemy 2.0** (async, `asyncpg`) + **Alembic** | Mature, typed, explicit SQL when needed |
| OAuth | **Authlib** (Starlette integration) | Battle.net authorization-code flow, `state` handling |
| HTTP client | **httpx** (async) + a token-bucket rate limiter | Blizzard API calls with throttling and retry on 429 |
| Sessions | Server-side sessions in Postgres, referenced by an **httpOnly, Secure, SameSite=Lax** cookie | Revocable; Blizzard token never reaches the browser |
| Realtime | **Server-Sent Events** from FastAPI, fed by Postgres `LISTEN/NOTIFY` | One-way updates are all the board needs; no extra infrastructure |
| Background jobs | **APScheduler** in a separate worker process (move to **arq** + Redis only if jobs get heavy) | Expiry, 30-day purge, catalog import |
| Catalog import | Python script/CLI in the worker (`csv`/`polars` for wago.tools tables) | Runs per game build, idempotent upserts |
| **Frontend framework** | **Nuxt 4** (Vue 3, TypeScript), **SSR enabled** | Team knows Vue; SSR gives fast first load on phones and **link previews** (Open Graph) for listings shared on Discord/chat |
| UI components | **Nuxt UI** (Tailwind-based) | Minimal, clean, accessible components; dark mode built in |
| State / data fetching | Nuxt `useFetch` / `$fetch` + **Pinia** for the active character and filters | Simple, SSR-aware |
| API client types | **openapi-typescript** generated from FastAPI's `/openapi.json` | Frontend types always match the backend |
| Testing | **pytest** + `httpx.AsyncClient` (backend), **Vitest** + **Playwright** (frontend, e2e) | |
| Packaging | `uv` (Python), `pnpm` (frontend), **Docker Compose** for local dev | One command to run everything |
| Hosting | Docker images on a VPS (e.g. Hetzner) or a PaaS (Railway, Render, Fly.io) + managed Postgres (Neon, Supabase) or Postgres in Compose | EU region recommended for GDPR (§11.3) |
| Monitoring | **Sentry** (both apps) + privacy-friendly analytics (e.g. Plausible, Umami) | Debugging and metrics without ad trackers |

### 8.3 Repository layout

A monorepo keeps the API schema and the generated frontend types in sync.

```
forever-service-board/
├─ backend/
│  ├─ app/
│  │  ├─ main.py              # FastAPI app, routers, middleware
│  │  ├─ config.py            # pydantic-settings (namespaces, regions, secrets)
│  │  ├─ db/                  # engine, session, base models
│  │  ├─ models/              # SQLAlchemy models (users, characters, listings, catalog…)
│  │  ├─ schemas/             # Pydantic request/response models
│  │  ├─ routers/             # auth, me, characters, listings, catalog, ratings, reports, events (SSE), admin
│  │  ├─ services/            # business logic (listing rules, expiry, scope filtering)
│  │  ├─ blizzard/            # OAuth + API client, rate limiter, mock provider
│  │  └─ worker/              # scheduler entry point, jobs, catalog importer
│  ├─ alembic/                # migrations
│  ├─ seeds/                  # mock data for Phase 0 (characters, items, recipes, cities)
│  ├─ tests/
│  └─ pyproject.toml
├─ frontend/
│  ├─ app/
│  │  ├─ pages/               # index (board), listings/[id], new, me/listings, account, admin
│  │  ├─ components/          # ListingCard, FilterBar, CharacterSwitcher, CreateListingModal…
│  │  ├─ composables/         # useBoardStream (SSE), useActiveCharacter, useMoney
│  │  ├─ stores/              # Pinia: active character, filters
│  │  └─ types/api.d.ts       # generated from OpenAPI
│  ├─ nuxt.config.ts
│  └─ package.json
├─ docker-compose.yml         # postgres, backend, worker, frontend, (caddy)
└─ README.md
```

### 8.4 Main API endpoints

All under `/api`. Responses are JSON; authenticated routes use the session cookie.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/auth/battlenet/login?region=eu` | Start OAuth: generate `state`, redirect to Battle.net |
| GET | `/auth/battlenet/callback` | Exchange code → token, import characters, create session, redirect to site |
| POST | `/auth/logout` | End session |
| GET | `/me` | Current user, characters, active character |
| PUT | `/me/active-character` | Switch active character (changes board scope) |
| POST | `/me/refresh-characters` | Re-import (only while the Blizzard token is still valid) |
| DELETE | `/me` | Unlink Battle.net and delete all data (§10.5) |
| GET | `/service-types` | Catalog of service types and their rules |
| GET | `/locations?portal=true&faction=horde` | Zones/cities, portal destinations |
| GET | `/catalog/search?q=arcan&profession=alchemy` | Craftable item / enchant autocomplete (trigram search) |
| GET | `/catalog/recipes/{id}` | Recipe with reagents, tools, created item |
| GET | `/listings?region=&ruleset=&faction=&type=&…` | The board: scoped, filtered, sorted, paginated |
| GET | `/listings/{id}` | Listing detail |
| POST | `/listings` | Create (validates class rules, one active per character × type) |
| PATCH | `/listings/{id}` | Edit, Available/Busy |
| POST | `/listings/{id}/bump` | "Still here": reset `expires_at` |
| DELETE | `/listings/{id}` | Remove |
| GET | `/me/listings` | Seller's own listings, including expired |
| POST | `/listings/{id}/contact` | "I contacted this seller" |
| POST | `/listings/{id}/ratings` | Rate (only after a contact, within 72 h) |
| POST | `/listings/{id}/reports` | Report |
| GET | `/events/board?region=&ruleset=&faction=` | **SSE stream** of listing created/updated/removed for one scope |
| GET/POST | `/admin/…` | Review queue, hide listing, suspend user |

### 8.5 Key technical decisions

- **Gold stored as integer copper** (1 gold = 100 silver = 10,000 copper). Avoids rounding errors. A shared `useMoney` composable formats it as `2g 50s`.
- **Catalog versioned by game build.**
- **All scope filtering in SQL** (region, ruleset, faction) with composite indexes, so the board stays fast at scale.
- **Expiry enforced in queries** (`WHERE expires_at > now()`), not only by the worker, so an expired listing never appears even if a job is late.
- **One active listing per character × service type** enforced by a **partial unique index** (`WHERE status = 'active'`), not just in code.
- **Configurable namespaces and regions** — no hard-coded Blizzard values (`BLIZZARD_PROFILE_NAMESPACE`, `BLIZZARD_STATIC_NAMESPACE`, `BLIZZARD_REGIONS`).
- **Blizzard client behind an interface** with two implementations: the real API client and a **mock provider** reading `seeds/`. `BLIZZARD_MODE=mock|live` switches between them, so the whole app works before the Forever API exists.
- **Blizzard access token is never sent to the browser.** It's used during the callback to import characters, kept server-side at most until it expires (24 h), then discarded.
- **Realtime design:** after any listing write, the backend runs `NOTIFY listings, '<scope>:<listing_id>:<event>'`. A single listener task in each API process fans the events out to the SSE connections subscribed to that scope. The client re-fetches the changed listing (or removes it) — events carry IDs, not data, so the stream never bypasses permission or expiry checks.
- **Two Battle.net clients** (development with `localhost` redirect, production with the real domain); secrets only in environment variables.
- **SSR caveat:** pages that depend on the session (active character, "My listings") render on the client or forward the cookie during SSR; public pages (board for a chosen scope, listing detail) render fully on the server for speed and link previews.

---

## 9. Data model

Simplified. Types are indicative.

### `users`
| Field | Type | Notes |
|-------|------|-------|
| id | uuid | |
| battlenet_account_id | text | from OAuth; unique per region |
| battletag | text | shown only if the user opts in |
| region | enum(us, eu, kr, tw) | |
| language | text | preferred language |
| created_at, last_sign_in_at | timestamp | |
| status | enum(active, suspended) | |

### `characters`
| Field | Type | Notes |
|-------|------|-------|
| id | uuid | |
| user_id | fk users | |
| blizzard_character_id | bigint | |
| region | enum | |
| ruleset | enum(normal, pvp, rp, hardcore) | |
| first_name, last_name | text | full name unique per region |
| faction | enum(alliance, horde) | from API, never from race |
| race, class | text / fk | |
| level | int | |
| last_logout_at | timestamp | from `last_login_timestamp` |
| hidden | bool | user can hide |
| last_fetched_at | timestamp | for the 30-day refresh/delete rule |

### `service_types`
| Field | Type | Notes |
|-------|------|-------|
| id | text | `summon`, `portal`, `enchant`, `craft`, … |
| label | text | |
| allowed_classes | text[] | e.g. `['warlock']`; empty = any |
| requires_recipe | bool | |
| default_lifetime_minutes | int | 30 / 1440 / 10080 |

### `items`
| Field | Type | Notes |
|-------|------|-------|
| id | int | game item ID |
| name | text | localized names in a separate table if multi-language |
| icon | text | |
| quality | enum | poor…legendary |
| item_class, subclass | int | |
| build | text | game build of the data |

### `recipes`
| Field | Type | Notes |
|-------|------|-------|
| id | int | spell ID |
| profession | text | |
| skill_required | int | |
| creates_item_id | fk items, nullable | null for enchants |
| creates_quantity | int | |
| enchant_slot | text, nullable | for enchants |
| tools | int[] | items the crafter needs (rods, etc.) |
| build | text | |

### `recipe_reagents`
| Field | Type |
|-------|------|
| recipe_id | fk recipes |
| item_id | fk items |
| quantity | int |

### `locations`
| Field | Type | Notes |
|-------|------|-------|
| id | int | zone/area ID |
| name | text | |
| faction | enum, nullable | for portal destinations |
| is_portal_destination | bool | |

### `listings`
| Field | Type | Notes |
|-------|------|-------|
| id | uuid | |
| character_id | fk characters | region/ruleset/faction denormalized for indexes |
| region, ruleset, faction | enums | copied from the character at creation |
| service_type_id | fk service_types | |
| location_id | fk locations, nullable | where the seller is |
| helpers_present | int, nullable | summons |
| price_copper | bigint | |
| payment_mode | enum(gold_only, buyer_mats, mixed) | |
| note | text | ≤200 chars |
| availability | enum(available, busy, scheduled) | |
| scheduled_from, scheduled_to | timestamp, nullable | |
| status | enum(active, expired, removed) | |
| expires_at | timestamp | |
| bumped_at, created_at | timestamp | |

Unique constraint: one `active` listing per (`character_id`, `service_type_id`).

### `listing_items` (crafts/enchants, one row per offered recipe)
| Field | Type |
|-------|------|
| listing_id | fk listings |
| recipe_id | fk recipes |
| quantity | int |
| price_copper | bigint, nullable (per-item price) |

### `listing_reagent_overrides` (who provides what)
| Field | Type |
|-------|------|
| listing_item_id | fk listing_items |
| item_id | fk items |
| provided_by | enum(seller, buyer) |

### `listing_portal_destinations`
| listing_id | location_id |

### `sessions`
| Field | Type | Notes |
|-------|------|-------|
| id | text | random, stored in the httpOnly cookie (hashed in DB) |
| user_id | fk users | |
| active_character_id | fk characters, nullable | drives the board scope |
| blizzard_token_encrypted | text, nullable | only until it expires (24 h), then nulled |
| expires_at, created_at | timestamp | |

### `contacts`, `ratings`, `reports`
- `contacts`: buyer_user_id, listing_id, created_at (for rating eligibility).
- `ratings`: rater_user_id, seller_character_id, listing_id, score (+1/−1), comment, created_at.
- `reports`: reporter_user_id, listing_id, reason, details, status, created_at.

### Indexes (main ones)
- `listings (region, ruleset, faction, status, service_type_id, expires_at)`
- `items` name trigram index for autocomplete
- `recipes (profession)`, `recipe_reagents (recipe_id)`

---

## 10. Key flows

### 10.1 First sign-in
1. User clicks **Sign in with Battle.net**, picks region.
2. Battle.net login and consent (`wow.profile`).
3. Callback: exchange code → user token.
4. Call `/profile/user/wow` (Forever namespace) → list of characters.
5. Optionally fetch each character's profile for faction/class/level/last-logout.
6. Upsert `users` and `characters`; discard the Blizzard token (or keep it only for the 24-hour session).
7. User lands on the board with their highest-level (or last used) character active.

### 10.2 Creating a craft listing
1. Seller clicks **New listing** → character preselected → **Craft**.
2. Types "arcan…" → autocomplete from `items` joined with `recipes` (only craftable results).
3. Picks the item, quantity 10.
4. App loads `recipe_reagents`, multiplies by 10, shows the list.
5. Seller picks **Mixed**, toggles which reagents they provide.
6. Sets price, availability, note → preview → publish.
7. Listing gets `expires_at = now + 7 days`, appears live on matching boards.

### 10.3 Finding a summon
1. Buyer's active character: EU, Normal, Horde.
2. Board scope is applied automatically; buyer filters **Summon**, location **Orgrimmar**, "updated < 10 min".
3. Picks a listing → **Copy whisper** → pastes in WoW.
4. Later, clicks "I contacted this seller" → can rate.

### 10.4 Listing lifecycle
`active` → (bump resets `expires_at`) → `expired` when `expires_at` passes → seller can re-publish. `removed` by seller, by admin, or automatically after enough reports. Characters inactive beyond the threshold hide their listings from the board.

### 10.5 Unlink / delete account
User clicks **Unlink Battle.net and delete my data** → all Blizzard-sourced data (characters, imported fields) and the user's listings, ratings given and contacts are deleted immediately; ratings *received* are anonymized or deleted per the privacy policy.

---

## 11. Compliance, rules and privacy

### 11.1 Blizzard Developer API Terms of Use

The points below are taken from community implementations' summaries of the terms. **They must be verified against the official Blizzard Developer API Terms of Use before launch.**

- **Credit Blizzard** as the data source on pages that display API data.
- **No charging for features that use API data**, no paywalls on API-sourced content, no forced ads alongside it, no selling the data. → The site should be **free**. Any future monetization (donations, cosmetic profile features) must be checked against the terms.
- **Cached data must be refreshed or deleted within 30 days.** → Every Blizzard-sourced row has `last_fetched_at`; a daily job refreshes on next sign-in or deletes after 30 days.
- **If a user unlinks Battle.net or asks for deletion, purge their Blizzard-sourced data immediately.**
- The terms are reported to restrict **data mining** of Blizzard products. Using community-published game tables (wago.tools) is common among fan sites but is a **grey area**; prefer official endpoints when they cover the need, and document the decision.
- API access needs a Battle.net account with an authenticator; each developer account can create a limited number of clients.

### 11.2 Game Terms of Service

- **Gold only.** Never allow, facilitate or display real-money prices or payments for in-game services. Notes are filtered for prices in real currency, payment links and external contact links.
- Gold-for-services between players in game is normal gameplay.
- The site never touches the game client.

### 11.3 Privacy (GDPR and similar)

- Collect the minimum: Battle.net account ID, region, characters, language. **BattleTag hidden by default.**
- Public profile = character name, class, listings, rating. No real names, no emails shown.
- Clear privacy policy, cookie consent only if non-essential cookies are used (aim for none).
- Data export and deletion on request (§10.5).
- EU users are likely a large share of the audience → host data in a region compatible with GDPR obligations or use standard contractual clauses.

### 11.4 Branding

- Do not use Blizzard logos, the WoW logo or official art.
- Choose a name that doesn't suggest an official Blizzard product.
- Footer disclaimer: "Not affiliated with or endorsed by Blizzard Entertainment. World of Warcraft is a trademark of Blizzard Entertainment, Inc."

---

## 12. Risks and mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|-----------|
| Blizzard doesn't publish a Forever API namespace at launch | No auto-import of characters | Medium | Configurable namespace; mock mode; temporary fallback: manual character entry with verification (e.g. code in a guild note or in-game mail), clearly marked "unverified" |
| Recipe data unavailable from Blizzard | No auto-filled reagents | Medium–High | Import from game tables (wago.tools); manual curation for the most popular recipes as a last resort |
| Stale listings (players offline) | Buyers lose trust | **High** | Short expiry, "Still here", Busy toggle, freshness badges, inactive-character hiding, later the addon |
| Not enough sellers at launch (cold start) | Empty board | High | Start with travel services (easy, high demand), seed via guilds and communities, make listing creation extremely fast, shareable listing links for chat/Discord |
| Fake listings / harassment (listing a rival) | Trust | Low (ownership verified) | Battle.net ownership, reports, rate limits on creation |
| Scams (no-show after payment) | Trust | Medium | Ratings, reports; UI advice: "pay after the service" |
| API rate limits / 429 | Sign-in failures | Low | Throttled client, backoff, caching, few calls per user |
| Terms of Use change or interpretation | Feature removal | Low–Medium | Free site, minimal data, compliance checklist, quick kill switch for any feature |
| Whisper format for two-part names differs from assumption | Broken copy-whisper | Medium | Verify at launch; format string is configurable |
| Patches change recipes | Wrong reagents | Medium | Catalog versioned per build; re-import on patch; flag affected listings |

---

## 13. Open questions to verify at launch

1. **Forever API namespaces** (profile and static/game data): names, per region, release date.
2. Does `/profile/user/wow` return **ruleset** for Forever characters? If not, how to derive it (realm-like field? connected-realm ID per ruleset?).
3. How are two-part names represented in the API (one field or two)? What is the **character URL slug**?
4. Exact **whisper syntax** for two-part names (`/w First Second`, `/w First-Second`, other).
5. Does the Forever API expose **professions / known recipes** for a character?
6. Does the Forever game data API expose **recipes and reagents**? If not, which game tables in the Forever build hold recipe → reagents → created item, and do they match the in-game window?
7. **Neutral auction houses** in Forever: do they still allow cross-faction exchange? (Possible future "via neutral AH" option.)
8. Can players **trade face to face across rulesets** in any situation (e.g. shared cities, battlegrounds)? Assumed no.
9. Final **portal destinations** in Forever (new cities? Gilneas?).
10. Official **API Terms of Use** wording on monetization, caching and data mining.
11. Is there an embeddable **item tooltip** script that supports Forever?

---

## 14. Roadmap

### Phase 0 — Clickable prototype (now → launch)
- Mock data: fake account with characters on two factions and rulesets, ~50 items, ~20 recipes, portal cities.
- Screens: sign-in, character switcher, board with filters, listing detail with copy-whisper, creation modal (all four types), "My listings".
- Built directly on the real stack: Nuxt frontend + FastAPI with `BLIZZARD_MODE=mock`, seeded Postgres, Docker Compose. The prototype then becomes the MVP codebase instead of being thrown away.
- Goal: test the flow with real players (guild/Discord) before the Forever API is available.

### Phase 1 — MVP (launch + ~2–4 weeks)
- Real Battle.net login (as soon as the namespace is known; mock or manual fallback otherwise).
- Service types: **Summon, Portal** first (no recipe data needed), then **Craft, Enchant** with a curated catalog.
- Expiry, Still-here, Available/Busy, reports, basic admin.
- Compliance basics: credits, disclaimer, privacy policy, delete account.

### Phase 2 — Real catalog
- Automated import of items and recipes per build; reagent auto-fill for all professions.
- Ratings.
- Shareable listing links (for posting in chat/Discord).

### Phase 3 — Quality of life
- Saved searches and notifications.
- Seller profiles and stats.
- Multi-language UI matching Forever's language preference.
- More service types (lockpicking, camping buffs, conjured food/water).

### Phase 4 — Optional companion addon
- Not required to use the site.
- Reports online status and current zone of the seller's character, and optionally known recipes.
- Addons cannot make network requests, so this needs a **small desktop companion** that reads the addon's saved data (written on logout or `/reload`) and syncs it — the model used by tools like Raider.IO and TSM. Alternatively, a purely in-game addon-to-addon channel for live listings.
- Revisit only if stale listings remain the top complaint.

---

## 15. Success metrics

| Metric | Target (first month) |
|--------|---------------------|
| Time to create a listing | < 30 s median |
| Share of listings refreshed at least once (live services) | > 50 % |
| Buyer "contacted" clicks per active listing per day | Growing week over week |
| Listings reported as fake / no-show | < 2 % |
| Weekly active sellers per region + ruleset + faction | Enough that a summon search usually returns ≥ 3 fresh results in capitals at peak hours |
| Positive rating share | > 85 % |

---

## 16. Sources

Game facts
- [Rulesets Replace Realms in WoW Forever – Icy Veins](https://www.icy-veins.com/wow-forever/news/rulesets-replace-realms-in-wow-forever-heres-how-it-works/) (quotes Blizzard's official ruleset article)
- [World of Warcraft: Forever will be realmless – Blizzard Watch](https://blizzardwatch.com/2026/09/13/world-warcraft-forever-will-realmless/)
- [Create a Name of Your Own in WoW: Forever – Blizzard News](https://news.blizzard.com/en-us/article/24304161)
- [Choosing Your Character Name and Ruleset in WoW Forever – Method](https://www.method.gg/wow-forever/choosing-your-character-name-and-ruleset-in-wow-forever)
- [No Group Finder or Summoning Stones in WoW Forever – Warcraft Tavern](https://www.warcrafttavern.com/forever/news/no-group-finder-or-summoning-stones-in-wow-forever/)
- [What to Expect in WoW Forever – wowforevertalents.com](https://wowforevertalents.com/what-to-expect/)
- [WoW Forever: release date, price and everything we know – The Forever Era](https://theforeverera.com/en/guides/wow-forever/)

Existing addons
- [ForeverCodex](https://www.curseforge.com/wow/addons/forevercodex), [Allemano CraftBoard](https://www.curseforge.com/wow/addons/allemano-craftboard), [GuildCrafts](https://www.curseforge.com/wow/addons/guildcrafts), [EnchantOrders](https://www.curseforge.com/wow/addons/enchantorders), [BloomChat](https://www.curseforge.com/wow/addons/bloomchat) – CurseForge

Blizzard API
- [WoW Profile APIs – Battle.net Developer Portal](https://community.developer.battle.net/documentation/world-of-warcraft/profile-apis)
- [World of Warcraft: Forever API Namespace? – Blizzard Forums](https://us.forums.blizzard.com/en/blizzard/t/world-of-warcraft-forever-api-namespace/59774)
- [homeassistant-wow-blizzard (Forever namespace status, 24 h tokens) – GitHub](https://github.com/yourdawi/homeassistant-wow-blizzard)
- [WoW Last Login Timestamp and API Performance – Blizzard Forums](https://us.forums.blizzard.com/en/blizzard/t/wow-last-login-timestamp-and-api-performance/9028)
- [WoW API Limits and 429 errors – Blizzard Forums](https://us.forums.blizzard.com/en/blizzard/t/wow-api-limits-and-429-errors/18526)
- [Blizzard API coverage – Drupal WoW module docs](https://project.pages.drupalcode.org/wow/reference/apis/)
- [Blizzard API compliance summary – Drupal WoW module docs](https://project.pages.drupalcode.org/wow/development/api-compliance/)
- [Questions about Blizzard Developer API Terms Of Use – Blizzard Forums](https://us.forums.blizzard.com/en/blizzard/t/questions-about-blizzard-developer-api-terms-of-use/57897)

Game data tables
- [wowlab – Game Data (wago.tools tables for the Forever build) – GitHub](https://github.com/sandgraal/wowlab/wiki/Game-Data)
- [WoWDBDefs – database definitions – GitHub](https://www.github.com/wowdev/WoWDBDefs)