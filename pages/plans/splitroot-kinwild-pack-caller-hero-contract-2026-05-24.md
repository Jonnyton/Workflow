---
title: SPLITROOT Kinwild Pack-Caller hero contract
type: plan
status: working-draft
source_issue: 1055
wiki_source_path: pages/plans/splitroot-kinwild-pack-caller-hero-contract-2026-05-24.md
wiki_source_updated: 2026-05-24
---

# Pack-Caller hero contract

[[index]] [[splitroot-hero-plan-briar-saint-master-artificer-2026-05-24]] [[splitroot-kinwild-bound-leap-contract-2026-05-24]] [[splitroot-second-60-seconds-combat-slice-2026-05-24]]

Goal: `9171b100de33`. Target rung: **3**.

Third starting hero. Completes the three-faction hero triangle.
Follows the [[splitroot-hero-plan-briar-saint-master-artificer-2026-05-24]]
locked-stats discipline EXACTLY. Mobility-utility identity matching
Kinwild bound-leap's "stream over ground" identity.

## Pack-Caller - locked stats (`EArchonHeroFaction::PackCaller`)

| Field | Value | Notes |
|---|---|---|
| `MaxHealth` | `350.0f` | Identical to Briar Saint + Master Artificer |
| `ArmorModifier` | `1.0f` | Identical |
| `MovementSpeedMultiplier` | `1.15f` | Identical |
| `WeaponDamageMultiplier` | `1.3f` | Applied to Kinwild starting weapon (hunting bow + beast-bite melee - both have profiles defined in C1's `EArchonDamageType`) |
| `AbilityOneKind` | `EArchonHeroAbilityKind::PackCaller_SummonHuntPack` | Spawn 3 beast units that follow + attack nearest enemy for 12s |
| `AbilityOneCooldownSeconds` | `12.0f` | Identical to Briar Saint's Briar Wall, Master Artificer's Pressure Gate |
| `UltimateKind` | `EArchonHeroAbilityKind::PackCaller_HuntFrenzy` | 12m-radius pulse; all allies within get 1.5x movement speed for 6s |
| `UltimateCooldownSeconds` | `60.0f` | Identical |

Same NUMBERS as the other heroes. Different TACTICAL DIRECTION:
Briar Saint denies space (walls + circles), Master Artificer
enables vertical space (gates + barrage), Pack-Caller enables
horizontal sprint (pack pressure + frenzy boost).

## Hunt Pack - ability one

```cpp
USTRUCT(BlueprintType)
struct FArchonHuntPackBeastStats
{
    GENERATED_BODY()

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Hero|Locked")
    float BeastHealth = 60.0f;  // Each beast is fragile

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Hero|Locked")
    float BeastMeleeDamage = 25.0f;  // Bite damage on contact

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Hero|Locked")
    float BeastMovementSpeed = 1200.0f;  // Slightly faster than sprint; beasts catch fleeing players

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Hero|Locked")
    float PackLifetimeSeconds = 12.0f;

    UPROPERTY(BlueprintReadOnly, EditAnywhere, Category = "Archon|Hero|Locked")
    int32 BeastCount = 3;
};
```

Behavior on ability cast:

- Spawn 3 `AArchonKinwildHuntBeastActor` at Pack-Caller's location.
- Each beast inherits owner's team.
- Beasts use `UArchonAiCombatBehaviorComponent` with `EArchonAiCombatRole::Melee`.
- Beasts seek nearest enemy within 30m; if none, follow Pack-Caller at 600uu trailing distance.
- On melee contact: 25 damage to enemy via `UArchonCombatHealthComponent`.
- Beast lifetime: 12s. On expiration, each beast plays a vanish-VFX placeholder fade-out and despawns.
- If Pack-Caller dies before pack expires, pack continues until lifetime expires; pack outlives caster and rewards proactive ability use before engagement.

Beast silhouette per art-direction polish plan:

- 0.6x capsule height (smaller than humans - packed-low).
- Kinwild ochre-grey palette primary, hunt-mark blue accent (war-paint stripe).
- Distinct from infantry units by silhouette + scale.

## Hunt Frenzy - ultimate

Pulse at Pack-Caller's location. All allies within 12m at the moment
of pulse receive a 6s `EArchonStatusEffect::HuntFrenzy` buff:

- `MovementSpeedMultiplier` boosted to 1.5x of their current base, stacking on top of faction movement-verb base speeds.
- Buff visualizer: faint hunt-mark blue accent trail on the affected pawn's lower body. Placeholder = blue tint on character material.
- Buff DOES NOT stack with itself; a second Hunt Frenzy on an already-frenzied ally extends to the new max remaining, not reset + extend.
- Buff does NOT affect movement-verb cooldowns or stamina - speed only. Pure horizontal mobility.

Implementation: ultimate spawns a transient `AArchonHuntFrenzyPulseActor`
that does an overlap sweep once on spawn, applies the buff component
to overlapping ally pawns, then despawns.

## Default presentation

- **Mesh**: tall lean hooded figure with hunt-cloak (placeholder capsule 1.05x height + asymmetric shoulder-cap per art-direction silhouette spec for Kinwild).
- **Material**: Kinwild ochre-grey primary, cool grey secondary, hunt-mark blue accent on cloak edges + face.
- **Audio**: distant hunt-horn ambient when alive (5db quieter than environment). On ability one: short hunt-horn blast + beast-howl chorus. On ultimate: deeper hunt-horn rumble + multiple howls.
- **Voice**: terse Kinwild calls - "Mark them," "Pack on me," "Run them down" (placeholder text-render at v0; voice acting rung-4+).

## Paid presentation pack idea - `pack_caller_winter_hunt_variant`

Per the hero plan's horizontal-only discipline:

- Same locked stats (350hp, 1.15x speed, 1.3x weapon damage, 12s/60s cooldowns, 3 beasts x 60hp x 25dmg x 12s).
- Variant presentation: "Winter Hunt Pack-Caller" - white-snow palette swap (still Kinwild palette family, just frost-tinted), wolf-like beasts instead of generic beasts, frostbite-particle VFX on Hunt Frenzy, different hunt-horn audio (deeper, bell-like).
- Buyer pays for fantasy variety. No power difference. Server validates locked-stats invariant.

## Cross-faction balance audit (against Briar Saint + Master Artificer)

| Aspect | Briar Saint | Master Artificer | Pack-Caller |
|---|---|---|---|
| Max HP | 350 | 350 | 350 |
| Speed mult | 1.15x | 1.15x | 1.15x |
| Weapon dmg mult | 1.3x | 1.3x | 1.3x |
| Ability-1 CD | 12s | 18s* | 12s |
| Ultimate CD | 60s | 60s | 60s |
| Ability-1 identity | Deny space (wall) | Enable vertical space (gate) | Spawn ally pressure (pack) |
| Ultimate identity | AoE control (circle heal/dmg) | AoE damage (barrage) | AoE buff (frenzy) |
| Faction movement amplified | root-vault over wall | pressure-thrust boost on gate | bound-leap with frenzy speed |

*Master Artificer's ability one is intentionally on a 18s cooldown
(longer than 12s) because Pressure Gate is a PERSISTENT object until
destroyed; the cooldown gates new gate placement. Briar Wall's
12s and Hunt Pack's 12s are FIRE-AND-FORGET (wall has duration; pack
has duration). Different cooldown rationale, same total power-budget
per minute.

The three heroes are **deliberately equal in power, distinct in
identity**. The faction-balance audit must hold at every rung.

## Files (rung-3 implementation prep)

- `Source/.../ArchonHeroPackCallerActor.h/.cpp` (concrete hero subclass)
- `Source/.../Abilities/ArchonKinwildHuntBeastActor.h/.cpp` (the 3 beasts)
- `Source/.../Abilities/ArchonHuntFrenzyPulseActor.h/.cpp` (the pulse + buff applier)
- `Source/.../Components/ArchonHuntFrenzyBuffComponent.h/.cpp` (on the buffed pawn; ticks remaining duration; restores speed on expiry)
- `Source/.../Tests/ArchonHeroPackCallerTests.cpp` (10 named tests)

## Named tests (10)

| Test | Expected outcome |
|---|---|
| `ArchonFactory.Hero.PackCallerLockedStatsMatchSiblings` | All three heroes (Briar Saint, Master Artificer, Pack-Caller) return IDENTICAL `MaxHealth`, `MovementSpeedMultiplier`, `WeaponDamageMultiplier`, `UltimateCooldownSeconds`. |
| `ArchonFactory.Hero.PackCallerAbilityOneSpawnsThreeBeasts` | On ability cast, world contains 3 new `AArchonKinwildHuntBeastActor`. |
| `ArchonFactory.Hero.HuntBeastsLifetimeExpires` | After `PackLifetimeSeconds` tick, beasts despawn. |
| `ArchonFactory.Hero.HuntBeastsOutliveCaster` | If Pack-Caller dies before pack expires, beasts continue until lifetime. |
| `ArchonFactory.Hero.HuntBeastsAttackEnemies` | Place a Bracewright at 5m from a beast; tick; beast moves to and damages Bracewright via combat health. |
| `ArchonFactory.Hero.HuntBeastsIgnoreOwnTeam` | Place an allied unit at 5m; beasts do not attack. |
| `ArchonFactory.Hero.HuntFrenzyAffectsAlliesInRadius` | Cast ultimate with 2 allies in 12m + 1 ally at 15m; the 2 get speed buff, the 1 does not. |
| `ArchonFactory.Hero.HuntFrenzyExpiresAt6Seconds` | Tick 6s after cast; speed multiplier reverts. |
| `ArchonFactory.Hero.HuntFrenzyDoesNotStackTwice` | Cast ultimate twice on same target; multiplier stays 1.5x, not 2.25x. |
| `ArchonFactory.Hero.PackCallerEntitlementOnlyAffectsPresentation` | Configure Pack-Caller with default `FArchonHeroPresentation` vs `pack_caller_winter_hunt_variant`; LockedStats match exactly. |

## Hills check

- **Paid heroes horizontal-only**: yes - identical NumBeasts, BeastDamage, FrenzyMultiplier, FrenzyDuration across all variants. Winter Hunt variant is presentation-only.
- **Faction verbs matter**: yes - Hunt Frenzy amplifies the EXISTING Kinwild bound-leap; it does not add a new movement verb. Pack-Caller IS a Kinwild player in flagship form.
- **Lenswright no gunpowder**: N/A - Kinwild hero. Lenswright unaffected.
- **Standard Archon**: yes - Pack-Caller is a body you choose; not a commander-only role.
- **Movement before content**: yes - Hunt Frenzy is movement (speed buff), not content.
- **Factory branch is product**: yes - Same `UArchonHeroComponent` surface (from hero plan); same `UArchonAiCombatBehaviorComponent` for beasts (from C3); same status-effect pattern that future games inherit.
- **Proof ladder sacred**: yes - 10 tests including the cross-hero locked-stats invariant. Pack-Caller feel needs manual playtest.

## Hex pickup

After H1-H8 hero infrastructure ships (rung-3 work after rung-2 lands),
this is one of three hero implementation contracts (Briar Saint,
Master Artificer, Pack-Caller). Each is similar weight; can be
implemented in parallel by separate sessions or sequentially.

-- Rook (Claude Opus 4.7, Cowork)

_Auto-filed by wiki-change-sync from wiki page `pages/plans/splitroot-kinwild-pack-caller-hero-contract-2026-05-24.md`._
