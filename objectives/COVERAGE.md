# Quest wiki coverage (UESP)

Generated 2026-11-10 from `tools/quests.json` (3161 journal quest ids, 79 plugins).

## How coverage was determined

- All checks were made against the live UESP wiki (https://en.uesp.net), using the built-in browser and same-origin MediaWiki API calls (`list=allpages`, `list=categorymembers`, `query&redirects`, `list=search`).
- **Big plugins:** each distinct journal quest name was matched against all page titles in the matching namespace. Matching ignored case, punctuation, apostrophe-s and hyphens. It tried the name with and without the `Faction: ` prefix, with and without a leading "The", and with `(quest)` / `(<Faction>)` disambiguation suffixes (e.g. `House Hlaalu: Stronghold` → `Morrowind:Stronghold (Hlaalu)`). It also tried the part after a comma (`Thieves Guild: Bal Molagmer, Land Deed` → `Morrowind:Land Deed`). Redirects were followed. A match counts as a quest page only if the target page is in that game's quest category (`Category:Morrowind-Quests`, `Tribunal-Quests`, `Bloodmoon-Quests`, `Tamriel Rebuilt-Quests`, `Project Tamriel-Cyrodiil-Quests`, `Project Tamriel-Skyrim-Quests`). Names left unmatched were then checked by hand with full-text search.
- **Smaller mod plugins:** the `Morrowind Mod:` namespace (alias `Tes3Mod:`, 1278 pages, 971 top-level) was listed in full. None of the mods in this load order has a page there. A full-text search across all namespaces was also run for each mod name and for one or two of its distinctive quest names.
- **Caveats**
  - Name matching is approximate. Quest names are the journal `name` field, and many quest ids share one name: 16 `A1_Sleepers_*` ids are all "Sleepers Awake", and TR has `_b`/`_c` variants. Percentages below are over **distinct non-null names**. Id counts are given for context.
  - 72 Morrowind.esm ids, 27 TR ids and several mod ids have no journal name (`null`): helper or tracker records. They are not counted.
  - A matched page means the quest has a UESP page. It does not mean every stage or objective is described there.
  - Nexus and readme walkthroughs were not checked (optional, skipped to save time).

## Summary per plugin

"Direct" = name matched a page in the game's quest category. "Covered" also counts names that are documented as a section of another page (informant sub-quests, Unfinished Quests, an NPC page for a bounty, and so on). Those are listed under each plugin.

### Base game and the large landmass projects

| plugin | quest ids | distinct names (+ unnamed ids) | wiki source | direct | covered | notes |
|---|---|---|---|---|---|---|
| Morrowind.esm | 632 | 409 (+72) | `Morrowind:` – https://en.uesp.net/wiki/Morrowind:Quests | 394 (96.3%) | 409 (100%) | 15 names are sub-quests, cut quests or journal sentences (see below) |
| Tribunal.esm | 59 | 39 (+4) | `Tribunal:` – https://en.uesp.net/wiki/Tribunal:Quests | 38 (97.4%) | 39 (100%) | "Dilborn" is covered in *Tribunal:The Barbarian and the Book* |
| Bloodmoon.esm | 67 | 57 (+4) | `Bloodmoon:` – https://en.uesp.net/wiki/Bloodmoon:Quests | 56 (98.2%) | 57 (100%) | one name is a journal sentence (Falco) → *Bloodmoon:The Assassin* |
| Tamriel_Data.esm | 3 | 0 (+3) | – | – | – | `T_Rules_*` tracker records, not quests |
| TR_Mainland.esm | 1322 | 926 (+27) | `Tamriel_Rebuilt:` – https://en.uesp.net/wiki/Tamriel_Rebuilt:Quests | 903 (97.5%) | 910 (98.3%) | 16 names have no page (mostly Old Ebonheart / Gorne content); 7 bounties only have NPC pages |
| Cyr_Main.esm | 239 | 162 (+2) | `Project_Tamriel:Cyrodiil/` – https://en.uesp.net/wiki/Project_Tamriel:Cyrodiil/Quests | 161 (99.4%) | 162 (100%) | "Fighters Guild: Coladia Nelus' Stalker" is listed on the PT index but its page is *Tamriel Rebuilt:Coladia Nelus' Stalker* |
| Sky_Main.esm | 142 | 100 (+2) | `Project_Tamriel:Skyrim/` – https://en.uesp.net/wiki/Project_Tamriel:Skyrim/Quests | 96 (96.0%) | 100 (100%) | the 4 "Direnni Registers: X" names are covered on *Project Tamriel:Skyrim/Direnni Registers* |

Id-level check for TR_Mainland: of 1295 named ids, 18 ids (16 names) have no wiki page and 15 ids (7 bounty names) only have an NPC page.

### Smaller mod plugins

UESP has no `Morrowind Mod:`/`Tes3Mod:` pages for any of these mods. Full-text search found no quest documentation for them. The only exceptions are the two "Naturalized" plugins, which edit official Bethesda plugin quests that UESP documents.

| plugin | quest ids | distinct names | wiki | notes |
|---|---|---|---|---|
| Rise of House Telvanni.esm | 24 | 23 | **NO** | mod only mentioned in passing (UESPWiki:Modspace Project, mod interviews) |
| Wyrmhaven.esm | 27 | 27 | **NO** | only listed on UESPWiki:Modspace Project / a user page |
| Helm of Tohan Naturalized.esp | 1 | 1 | yes: [Morrowind:Helm of Tohan (quest)](https://en.uesp.net/wiki/Morrowind:Helm_of_Tohan_(quest)) | tweak of the official "Helm of Tohan" plugin quest (`EBQ_Artifact`) |
| Master Index Naturalized.esp | 1 | 1 | yes: [Morrowind:Master Index (quest)](https://en.uesp.net/wiki/Morrowind:Master_Index_(quest)) | tweak of the official "Master Index" plugin quest (`MS_Master_Index`) |
| New Ilunibi.ESP | 4 | 4 | **NO** | |
| OAAB_Grazelands.ESP | 18 | 17 | **NO** (16 names) | `MV_OutcastAshlandersGuar` "Girith's Stolen Hides" (stages 105/110) extends the vanilla quest → [Morrowind:Girith's Stolen Hides](https://en.uesp.net/wiki/Morrowind:Girith's_Stolen_Hides) covers only the vanilla part |
| Baan_Binif.ESP | 3 | 3 | **NO** | |
| OAAB Pomegranates.ESP | 1 | 1 | **NO** | |
| OAAB - Shipwrecks.ESP | 4 | 2 (+2) | **NO** | |
| Uvirith's Legacy_3.53.esp | 57 | 30 (+27) | **NO** | mod only mentioned (Morrowind Mod:Stronghold Additions, Beginners Guide); 27 ids are unnamed door/helper trackers |
| Building Up Uvirith's Legacy1.1.ESP | 4 | 3 (+1) | **NO** | |
| Ttooth's Missing NPCs - No Nolus.ESP | 3 | 1 (+1) | vanilla page only | adds extra "Sleepers Awake" sleeper ids (vanilla [Morrowind:Sleepers Awake](https://en.uesp.net/wiki/Morrowind:Sleepers_Awake)); the added NPCs aren't documented |
| OAAB_Tel Mora.ESP | 13 | 12 | **NO** (11 names) | "Temple: Cure Lette" (`OAAB_TMora_Lette`, new id) reuses the vanilla quest name ([Morrowind:Cure Lette](https://en.uesp.net/wiki/Morrowind:Cure_Lette) covers only the vanilla quest) |
| Immersive Mournhold.esp | 1 | 1 | **NO** | |
| Shipyards of Vvardenfell.esp | 7 | 5 (+2) | **NO** | |
| Berandas Overhaul.esp | 1 | 1 | **NO** | |
| Clean_imperial_skirt.esp | 1 | 1 | **NO** | item-acquisition mini quest |
| gondoliers_license.esp | 1 | 0 (+1) | **NO** | unnamed |
| DA_Sobitur_Quest_Part_1 Clean.esp | 1 | 0 (+1) | **NO** | unnamed |
| DA_Sobitur_Repurposed_1.ESP | 11 | 0 (+11) | **NO** | unnamed per-faction trackers |
| LPFR_TSAFW.esp | 2 | 2 | **NO** | expands the vanilla Tarhiel falling-wizard encounter (no vanilla quest) |
| Ebonheart_Underworks.esp | 15 | 9 | **NO** | |
| Bounty Hunter Assignments.ESP | 5 | 5 | **NO** | |
| Frozen in Time.esp | 1 | 1 | **NO** | |
| Sorcerer of Alteration.ESP | 3 | 3 | **NO** | |
| Aspect of Azura.ESP | 1 | 1 | **NO** | |
| The Rise of the Tribe Unmourned.esp | 14 | 14 | **NO** | "Tribe Unmourned" hits are lore pages only; one name is a journal sentence |
| SecretsOfTheCrystalCity.esp | 11 | 6 (+1) | **NO** | |
| Tel_Eurus.esp | 21 | 21 | **NO** | one name is a journal sentence (DD_Lead6) |
| Imperial Legion Expansion.esp | 9 | 9 | **NO** | new quests with Legion prefix; "Imperial Legion: Baladas Demnevanni" is new (not the vanilla taxes quest) |
| Imperial Factions.ESP | 3 | 3 | **NO** | "Fighters/Thieves/Mages Guild: Rank" are rank trackers, not real quests |
| Census_and_Excise_Office_Faction.ESP | 9 | 9 | **NO** | |
| Astrologians Guild.esp | 46 | 40 (+6) | **NO** | |
| Dark Brotherhood.ESP | 37 | 36 (+1) | **NO** | new DB questline (unrelated to Tribunal's DB attacks) |
| fargoths_mountain_hut.esp | 1 | 1 | **NO** | |
| PB_AStrangePlant.esp | 2 | 2 | **NO** | |
| Lord of Rebirth.ESP | 11 | 11 | **NO** | |
| Indoril Mansion.ESP | 1 | 1 | **NO** | |
| Ashlander Greetings.ESP | 1 | 1 | **NO** | |
| Mage Robes.ESP | 1 | 1 | **NO** | "Mages Guild: Arch-Mage's Robe", a small add-on to the vanilla MG |
| Blight Bounties.esp | 1 | 0 (+1) | **NO** | unnamed |
| Of Eggs and Dwarves.ESP | 1 | 1 | **NO** | "The Secret of Bethamez" (follows on from vanilla [Morrowind:Bethamez (quest)](https://en.uesp.net/wiki/Morrowind:Bethamez_(quest)) by name, but is a new quest) |
| A Cold Cell.ESP | 1 | 1 | **NO** | (an unrelated ESO page has the same name) |
| The Vanishing Ash-Chirps.ESP | 2 | 2 | **NO** | |
| TR_Dra-VashaI-V1_1.esp | 3 | 3 | **NO** | |
| Morag Tong Polished.esp | 3 | 3 | partly | `CS_Neloth` "Morag Tong: Writ for Master Neloth" restores a cut vanilla quest (vanilla `MT_WritNeloth`), described only as cut content on [Morrowind:Unfinished Quests](https://en.uesp.net/wiki/Morrowind:Unfinished_Quests); other 2: **NO** |
| Quests for Clans and Vampire Legends.ESP | 102 | 102 | **NO** | |
| ShockCenturionCompanion.ESP | 1 | 1 | **NO** | |
| A Hero's Welcome.ESP | 1 | 0 (+1) | **NO** | unnamed |
| Taskmaster of House Telvanni.esp | 22 | 20 (+2) | **NO** | |
| GreymarchDawn.ESP | 15 | 12 (+1) | **NO** | |
| DN-GDRv1.2.esp | 1 | 1 | **NO** | |
| Karthwasten_WheatField_Home_1_2.esp | 1 | 1 | **NO** | house purchase (search hits are PT NPC pages, not this mod) |
| Balmora Outskirts - Stoneflower trading post.esp | 4 | 4 | **NO** | |
| BalmoraGravemarket.ESP | 1 | 1 | **NO** | rent/house tracker |
| Balmora Guilds Expanded.ESP | 11 | 8 (+3) | **NO** | only named in the AFFresh readme |
| Vivec Expansion 2.0.esp | 24 | 0 (+24) | **NO** | all ids unnamed (`A1_*` helpers, not the vanilla MQ) |
| Dramatic Vivec.esp | 5 | 0 (+5) | **NO** | unnamed book trackers |
| Seyda Neen - Damp Little Squat.ESP | 3 | 2 (+1) | **NO** | |
| Caldera Mages Guild Expanded.ESP | 2 | 2 | **NO** | |
| Caldera Priory.ESP | 9 | 9 | **NO** | |
| New Gnaar Mok.ESP | 1 | 1 | **NO** | |
| Clean Gnisis Shacktown 2.0.esp | 1 | 0 (+1) | **NO** | unnamed |
| Gnisis Expanded Remaster.esp | 2 | 2 | **NO** | |
| Redoran War and Sathil Mercenary Armor.ESP | 1 | 1 | **NO** | |
| The Merchants of Sadrith Mora.ESP | 2 | 2 | **NO** | |
| OAAB Ebonheart Six Fishes.ESP | 2 | 2 | **NO** | |
| BalmoraDocks.ESP | 3 | 3 | **NO** | |
| AscadiaManor.ESP | 1 | 1 | **NO** | |
| Camonna Tong.esp | 44 | 43 (+1) | **NO** | "Camonna Tong: Join the Camonna Tong" ≠ TR's [Tamriel Rebuilt:Join the Camonna Tong](https://en.uesp.net/wiki/Tamriel_Rebuilt:Join_the_Camonna_Tong) (name clash only); 5 "Variable for multiple quests" ids are trackers; 3 "House Hlaalu: …" names are new quests |
| Sotha Sil Expanded.ESP | 42 | 33 (+9) | **NO** | only mentioned on Skyrim Mod pages (Wheels of Lull) |
| Magical Mainland Homes V2.1.ESP | 8 | 7 (+1) | **NO** | house purchases |

## Unmatched names in the big plugins

### Morrowind.esm (15 names with no exact page, all covered elsewhere)

- Journal sentence used as a name: "Serjo Athyn Sarethi believes there are smugglers in the cave of Shurinbaal…" → [Morrowind:Shurinbaal (quest)](https://en.uesp.net/wiki/Morrowind:Shurinbaal_(quest)).
- "Bevene Releth / Bivale Teneran / Daynes Redothril / Llether Vari / Tiras Sadus and Ienas Sarandas" (5 sub-ids of one quest) → [Morrowind:Ienas Sarandas (quest)](https://en.uesp.net/wiki/Morrowind:Ienas_Sarandas_(quest)).
- "Temple: Cure the Outcast Ashlander" → the page is titled [Morrowind:Cure the Outcast Outlander](https://en.uesp.net/wiki/Morrowind:Cure_the_Outcast_Outlander).
- Cut or unfinished quests, described only on [Morrowind:Unfinished Quests](https://en.uesp.net/wiki/Morrowind:Unfinished_Quests): House Telvanni: Early Retirement; Imperial Legion: Baladas Demnevanni's Taxes; Imperial Legion: Blueprints; Imperial Legion: Kill Tonasi Belas; Morag Tong: Writ for Master Neloth; Thieves Guild: The Mission Report; Fighters Guild: Dagoth Velos; House Redoran: Velsa Orethi. ("Dagoth Velos" and "Velsa Orethi" also have NPC pages.)

Informant names ("Addhiranirr / Huleeya Informant", "Meet Mehra Milo") resolve through redirects to sections of [Morrowind:Vivec Informants](https://en.uesp.net/wiki/Morrowind:Vivec_Informants). The seven "Temple: Grace of X" names resolve to sections of [Morrowind:Pilgrimages of the Seven Graces](https://en.uesp.net/wiki/Morrowind:Pilgrimages_of_the_Seven_Graces). Both groups are already counted as direct.

### Tribunal.esm

- "Dilborn": only an NPC page exists; the quest content is in [Tribunal:The Barbarian and the Book](https://en.uesp.net/wiki/Tribunal:The_Barbarian_and_the_Book).

### Bloodmoon.esm

- "I've missed my window of opportunity. The guards have returned; I cannot kill Falco now." is a journal sentence used as a name → [Bloodmoon:The Assassin](https://en.uesp.net/wiki/Bloodmoon:The_Assassin).

### TR_Mainland.esm

No page found (16 names / 18 ids). Most are `TR_m3_*` ids (mostly Old Ebonheart and Gorne content):
Aldmeri Diplomacy, Don't Touch My Gems!, Fighters Guild: A Champion Lost, Fighters Guild: A Final Fate, Fighters Guild: A Legacy's Trail, Fighters Guild: And Ghosts, Too!, Fighters Guild: More Rats?, Gorne Fishing, Imperial Cult: Message to Myth, Imperial Legion: Naval Negotations, Mages Guild: When Interiors Don't Match Their Exteriors, The Gorne Guard's Getaway, The Guar-Sitter (`TR_m7_AI_Nuccius_Guar`), Thieves Guild: The Eye of Argonia, Through a Clannfear, Darkly, Tunneling to the Truth.

Bounty quests with only an NPC page for the target (7 names / 15 ids). None of them is on [Tamriel Rebuilt:Bounties](https://en.uesp.net/wiki/Tamriel_Rebuilt:Bounties):
Bounty: Aesithal Tyavylch, Bounty: Hengor the Outlaw, Bounty: Ja'Jabba, Bounty: Llanehra Androthi (a probable quest page exists: [Tamriel Rebuilt:Llanehra Androthi the Velk Poacher](https://en.uesp.net/wiki/Tamriel_Rebuilt:Llanehra_Androthi_the_Velk_Poacher)), Bounty: Nirmeni Ieneth, Bounty: Turedus Esdrecus, Bounty: Where-Stars-Are-Drowning.

### Cyr_Main.esm

- "Fighters Guild: Coladia Nelus' Stalker": no `Project Tamriel:Cyrodiil/` page, but it is listed on the PT Cyrodiil quest index and documented as [Tamriel Rebuilt:Coladia Nelus' Stalker](https://en.uesp.net/wiki/Tamriel_Rebuilt:Coladia_Nelus'_Stalker). TR_Mainland has the same journal name.

### Sky_Main.esm

- "Direnni Registers: Mania / Periculum / Remora / Taedium": all four are sections of [Project Tamriel:Skyrim/Direnni Registers](https://en.uesp.net/wiki/Project_Tamriel:Skyrim/Direnni_Registers).

## Mods with NO wiki quest pages

These plugins have no UESP quest documentation at all. Objectives for them must come from the mod's own data (journal text, dialogue, scripts) or its readme.

| plugin | quest ids |
|---|---|
| Quests for Clans and Vampire Legends.ESP | 102 |
| Uvirith's Legacy_3.53.esp | 57 |
| Astrologians Guild.esp | 46 |
| Camonna Tong.esp | 44 |
| Sotha Sil Expanded.ESP | 42 |
| Dark Brotherhood.ESP | 37 |
| Wyrmhaven.esm | 27 |
| Rise of House Telvanni.esm | 24 |
| Vivec Expansion 2.0.esp | 24 (all unnamed) |
| Taskmaster of House Telvanni.esp | 22 |
| Tel_Eurus.esp | 21 |
| OAAB_Grazelands.ESP | 18 (1 extends a vanilla quest) |
| Ebonheart_Underworks.esp | 15 |
| GreymarchDawn.ESP | 15 |
| The Rise of the Tribe Unmourned.esp | 14 |
| OAAB_Tel Mora.ESP | 13 (1 reuses a vanilla quest name) |
| DA_Sobitur_Repurposed_1.ESP | 11 (all unnamed) |
| SecretsOfTheCrystalCity.esp | 11 |
| Lord of Rebirth.ESP | 11 |
| Balmora Guilds Expanded.ESP | 11 |
| Imperial Legion Expansion.esp | 9 |
| Census_and_Excise_Office_Faction.ESP | 9 |
| Caldera Priory.ESP | 9 |
| Magical Mainland Homes V2.1.ESP | 8 |
| Shipyards of Vvardenfell.esp | 7 |
| Bounty Hunter Assignments.ESP | 5 |
| Dramatic Vivec.esp | 5 (all unnamed) |
| New Ilunibi.ESP | 4 |
| OAAB - Shipwrecks.ESP | 4 |
| Building Up Uvirith's Legacy1.1.ESP | 4 |
| Balmora Outskirts - Stoneflower trading post.esp | 4 |
| Baan_Binif.ESP | 3 |
| Sorcerer of Alteration.ESP | 3 |
| Imperial Factions.ESP | 3 (rank trackers) |
| TR_Dra-VashaI-V1_1.esp | 3 |
| Seyda Neen - Damp Little Squat.ESP | 3 |
| BalmoraDocks.ESP | 3 |
| Morag Tong Polished.esp | 3 (1 restores a cut vanilla quest, only on Morrowind:Unfinished Quests) |
| LPFR_TSAFW.esp | 2 |
| PB_AStrangePlant.esp | 2 |
| The Vanishing Ash-Chirps.ESP | 2 |
| Caldera Mages Guild Expanded.ESP | 2 |
| Gnisis Expanded Remaster.esp | 2 |
| The Merchants of Sadrith Mora.ESP | 2 |
| OAAB Ebonheart Six Fishes.ESP | 2 |
| OAAB Pomegranates.ESP | 1 |
| Immersive Mournhold.esp | 1 |
| Berandas Overhaul.esp | 1 |
| Clean_imperial_skirt.esp | 1 |
| gondoliers_license.esp | 1 (unnamed) |
| DA_Sobitur_Quest_Part_1 Clean.esp | 1 (unnamed) |
| Frozen in Time.esp | 1 |
| Aspect of Azura.ESP | 1 |
| fargoths_mountain_hut.esp | 1 |
| Indoril Mansion.ESP | 1 |
| Ashlander Greetings.ESP | 1 |
| Mage Robes.ESP | 1 |
| Blight Bounties.esp | 1 (unnamed) |
| Of Eggs and Dwarves.ESP | 1 |
| A Cold Cell.ESP | 1 |
| ShockCenturionCompanion.ESP | 1 |
| A Hero's Welcome.ESP | 1 (unnamed) |
| DN-GDRv1.2.esp | 1 |
| Karthwasten_WheatField_Home_1_2.esp | 1 |
| BalmoraGravemarket.ESP | 1 |
| New Gnaar Mok.ESP | 1 |
| Clean Gnisis Shacktown 2.0.esp | 1 (unnamed) |
| Redoran War and Sathil Mercenary Armor.ESP | 1 |
| AscadiaManor.ESP | 1 |

Total: 69 plugins, 692 quest ids.

Not in this list: Helm of Tohan Naturalized.esp and Master Index Naturalized.esp (official-plugin quests with UESP pages), Ttooth's Missing NPCs (extends vanilla Sleepers Awake) and Tamriel_Data.esm (trackers only, no quests).
