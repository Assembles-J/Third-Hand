# ThirdHand Stabilization Sprint Plan

## Goal

Recover the core daily product path before expanding advanced AI capabilities.

## Priority

```
S0 Stabilization
    ↓
N2 Device Acceptance
    ↓
PUX1 UX Improvement
    ↓
N4 AI Research
```

## S0 Scope

### Portfolio Recovery

Restore:

```
Portfolio
  ↓
Holding Detail
```

Fix:

- transaction flow
- stock identity mapping
- holding data consistency
- profit/loss presentation

### Watchlist Recovery

Restore:

```
Home
 ↓
Watchlist
 ↓
Stock Detail
```

Remove broken 404 paths.

### Holding Detail Reset

Holding Detail owns:

- stock information
- price
- cost
- quantity
- profit/loss
- market value
- K-line entry

Decision Workspace owns:

- AI research
- financial reports
- events
- What Changed

### K-line UX Layers

Layer 1:

- price
- holding
- profit/loss

Layer 2:

- K-line
- timeframe
- volume

Layer 3:

- AI
- research
- events

### AI Navigation

Target:

```
AI Entry
 ↓
Decision Workspace
 ↓
AI Research
```

### Market Data Freshness

Unified states:

- realtime
- close snapshot
- delayed
- unavailable

## Delivery Rule

Every feature follows:

```
Backend → API → Android → Acceptance
```

Backend-only work is not considered complete.

## Paused

Until S0 acceptance:

- N5 AI Trading
- excessive scoring expansion
- non-core automation features
