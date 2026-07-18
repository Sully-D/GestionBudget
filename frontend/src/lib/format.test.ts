import { describe, expect, it } from 'vitest'
import { calculerBudgetCoupleSimule, calculerDisponibleSimule, formatMontant, sortTagsByCategoryAndName } from './format'

interface TestTag {
  tag_id: number
  name: string
  parent_id: number | null
}

// NOTE: aucun test runner n'est configuré dans ce projet frontend (pas de
// script "test" dans package.json, ni vitest/@testing-library/react en
// devDependencies) au moment de l'écriture de ce fichier. Ce test suit la
// même convention que src/hooks/useTheme.test.ts (vitest, idiomatique pour
// un projet Vite) mais ne peut pas être exécuté via `npm test` tant que ces
// dépendances ne sont pas installées et qu'un script "test" n'est pas ajouté.

describe('calculerDisponibleSimule', () => {
  it('calcule un Disponible positif (scénario par défaut de la page Simulation)', () => {
    expect(calculerDisponibleSimule(3000, 1200, 400, 700)).toBe(700)
  })

  it('calcule un Disponible négatif (scénario déficitaire)', () => {
    expect(calculerDisponibleSimule(2000, 1500, 300, 500)).toBe(-300)
  })

  it('renvoie 0 quand toutes les valeurs sont nulles', () => {
    expect(calculerDisponibleSimule(0, 0, 0, 0)).toBe(0)
  })

  it('renvoie exactement 0 comme cas limite (Disponible ni positif ni négatif)', () => {
    expect(calculerDisponibleSimule(1000, 500, 300, 200)).toBe(0)
  })
})

describe('calculerBudgetCoupleSimule', () => {
  // Solde de référence=300 (et non 0 comme dans l'exemple original de la
  // matrice I/O) : seule valeur mathématiquement atteignable avec Revenus/
  // Charges Lui/Elle et % de la spec — cf. spec-budget-couple-page-simulation.md
  // Spec Change Log (2026-07-17) pour le détail du calcul.
  it('calcule un scénario Budget Couple happy path (Revenus/Charges Lui/Elle et % de la spec, Solde ajusté à 300)', () => {
    const result = calculerBudgetCoupleSimule(1800, 1200, 400, 300, 300, 50)
    expect(result).toEqual({
      revenusCouple: 3000,
      budgetChargesConvenu: 1500,
      resteDisponible: 1500,
      virementLui: 200,
      virementElle: 100,
      virementError: null,
      resteAVivreLui: 1200,
      resteAVivreElle: 800,
    })
  })

  it('renvoie un Budget convenu et un Reste disponible nuls, et un message d\'erreur, quand Revenus Couple = 0', () => {
    const result = calculerBudgetCoupleSimule(0, 0, 0, 0, 0, 0)
    expect(result.revenusCouple).toBe(0)
    expect(result.budgetChargesConvenu).toBe(0)
    expect(result.resteDisponible).toBe(0)
    expect(result.virementLui).toBeNull()
    expect(result.virementElle).toBeNull()
    expect(result.virementError).toBe(
      `Virement non calculable : Revenus du Couple nuls (Lui ${formatMontant(0)}, Elle ${formatMontant(0)}). ` +
        'Renseignez au moins un revenu pour permettre le calcul.',
    )
    expect(result.resteAVivreLui).toBeNull()
    expect(result.resteAVivreElle).toBeNull()
  })

  it('signale un message dédié quand Revenus du Couple est négatif', () => {
    const result = calculerBudgetCoupleSimule(-2000, 500, 0, 0, 0, 50)
    expect(result.revenusCouple).toBe(-1500)
    expect(result.virementLui).toBeNull()
    expect(result.virementElle).toBeNull()
    expect(result.virementError).toBe(
      `Virement non calculable : Revenus du Couple négatifs (${formatMontant(-1500)}). ` +
        `Vérifiez les Revenus Lui (${formatMontant(-2000)}) et Elle (${formatMontant(500)}) saisis : ` +
        'au moins un des deux doit être corrigé pour obtenir un total positif ou nul.',
    )
    expect(result.resteAVivreLui).toBeNull()
    expect(result.resteAVivreElle).toBeNull()
  })

  it('signale un virement négatif en détaillant "Lui" quand ses charges déjà payées dépassent sa part théorique', () => {
    const result = calculerBudgetCoupleSimule(1000, 1000, 900, 100, 0, 50)
    expect(result.virementLui).toBeNull()
    expect(result.virementElle).toBeNull()
    expect(result.virementError).toBe(
      `Virement non calculable : Lui a déjà payé ${formatMontant(900)} de Charges pour une part théorique de ` +
        `${formatMontant(500)}, soit ${formatMontant(400)} de trop (réduisez ses Charges déjà payées de ce ` +
        'montant, ou augmentez le Solde de référence du Compte Commun).',
    )
    expect(result.resteAVivreLui).toBeNull()
    expect(result.resteAVivreElle).toBeNull()
  })

  it('signale un virement négatif en détaillant "Elle" quand ses charges déjà payées dépassent sa part théorique', () => {
    const result = calculerBudgetCoupleSimule(1000, 1000, 100, 900, 0, 50)
    expect(result.virementLui).toBeNull()
    expect(result.virementElle).toBeNull()
    expect(result.virementError).toBe(
      `Virement non calculable : Elle a déjà payé ${formatMontant(900)} de Charges pour une part théorique de ` +
        `${formatMontant(500)}, soit ${formatMontant(400)} de trop (réduisez ses Charges déjà payées de ce ` +
        'montant, ou augmentez le Solde de référence du Compte Commun).',
    )
    expect(result.resteAVivreLui).toBeNull()
    expect(result.resteAVivreElle).toBeNull()
  })

  it('signale un besoin total négatif (Solde de référence très bas) sans jamais afficher de part théorique négative', () => {
    const result = calculerBudgetCoupleSimule(1000, 1000, 0, 0, -5000, 0)
    expect(result.virementLui).toBeNull()
    expect(result.virementElle).toBeNull()
    expect(result.virementError).toBe(
      'Virement non calculable : le besoin total à répartir (Charges du Couple + Solde de référence) est ' +
        `négatif (${formatMontant(-5000)}). Augmentez le Solde de référence d'au moins ${formatMontant(5000)} ` +
        'pour repasser à un besoin total nul ou positif, ou vérifiez les Charges du Couple saisies.',
    )
    expect(result.resteAVivreLui).toBeNull()
    expect(result.resteAVivreElle).toBeNull()
  })

  it('détaille Lui ET Elle sans ambiguïté quand les deux ont un virement négatif simultanément', () => {
    const result = calculerBudgetCoupleSimule(100, 1900, 500, 1000, -1000, 0)
    expect(result.virementLui).toBeNull()
    expect(result.virementElle).toBeNull()
    expect(result.virementError).toBe(
      `Virement non calculable : Lui a déjà payé ${formatMontant(500)} de Charges pour une part théorique de ` +
        `${formatMontant(25)}, soit ${formatMontant(475)} de trop (réduisez ses Charges déjà payées de ce ` +
        `montant, ou augmentez le Solde de référence du Compte Commun) ; Elle a déjà payé ${formatMontant(1000)} ` +
        `de Charges pour une part théorique de ${formatMontant(475)}, soit ${formatMontant(525)} de trop ` +
        '(réduisez ses Charges déjà payées de ce montant, ou augmentez le Solde de référence du Compte Commun).',
    )
    expect(result.resteAVivreLui).toBeNull()
    expect(result.resteAVivreElle).toBeNull()
  })

  it('ne signale pas à tort un virement négatif quand la formule donne un résultat mathématiquement nul', () => {
    // 333/667 (revenusCouple=1000) et Charges Lui=99,9€/Solde=200,1€ donnent
    // virementLui = 0,333 × 300 − 99,9 = 0 exact mathématiquement, mais la
    // division binaire (333/1000) laisse un résidu flottant (ex. -1.4e-14)
    // sans l'arrondi au centime : sans lui, ce résidu déclencherait à tort
    // virementError (cf. revue adversarielle, finding "faux positif flottant").
    const result = calculerBudgetCoupleSimule(333, 667, 99.9, 0, 200.1, 0)
    expect(result.virementError).toBeNull()
    expect(result.virementLui).toBe(0)
    expect(result.resteAVivreLui).toBe(233.1)
  })

  it('traite un % Charges convenues vide (converti en 0 par l\'appelant) comme 0 %, Reste disponible = Revenus Couple', () => {
    const result = calculerBudgetCoupleSimule(1000, 500, 0, 0, 0, 0)
    expect(result.revenusCouple).toBe(1500)
    expect(result.budgetChargesConvenu).toBe(0)
    expect(result.resteDisponible).toBe(1500)
    expect(result.virementError).toBeNull()
  })

  it('traite un champ non numérique (ex. "abc" saisi dans Revenus Lui, converti en 0 par l\'appelant) comme 0', () => {
    const result = calculerBudgetCoupleSimule(0, 1200, 0, 300, 0, 50)
    expect(result.revenusCouple).toBe(1200)
    expect(result.virementError).toBeNull()
    expect(result.virementLui).toBe(0)
    expect(result.virementElle).toBe(0)
    expect(result.resteAVivreLui).toBe(0)
    expect(result.resteAVivreElle).toBe(900)
  })
})

describe('sortTagsByCategoryAndName', () => {
  // Alimentation (racine) > Courses / Restaurant ; Loisirs (racine) > Cinéma
  const tags: TestTag[] = [
    { tag_id: 1, name: 'Alimentation', parent_id: null },
    { tag_id: 2, name: 'Loisirs', parent_id: null },
    { tag_id: 3, name: 'Restaurant', parent_id: 1 },
    { tag_id: 4, name: 'Courses', parent_id: 1 },
    { tag_id: 5, name: 'Cinéma', parent_id: 2 },
  ]
  const byId = new Map(tags.map((t) => [t.tag_id, t]))

  it('trie par nom de catégorie racine puis par nom de tag, ordre alphabétique fr', () => {
    const sorted = sortTagsByCategoryAndName(tags, byId)
    expect(sorted.map((t) => t.name)).toEqual(['Alimentation', 'Courses', 'Restaurant', 'Cinéma', 'Loisirs'])
  })

  it("ne modifie ni l'ordre ni le contenu du tableau d'entrée (retourne une copie triée)", () => {
    const input = tags.map((t) => ({ ...t }))
    const snapshot = input.map((t) => ({ ...t }))
    sortTagsByCategoryAndName(input, byId)
    expect(input).toEqual(snapshot)
  })

  it('renvoie un tableau vide pour une entrée vide', () => {
    expect(sortTagsByCategoryAndName([], byId)).toEqual([])
  })

  it('remonte jusqu\'à la racine sur une hiérarchie à 3 niveaux (level 1/2/3)', () => {
    const deep: TestTag[] = [
      { tag_id: 10, name: 'Transport', parent_id: null },
      { tag_id: 11, name: 'Voiture', parent_id: 10 },
      { tag_id: 12, name: 'Essence', parent_id: 11 },
      { tag_id: 13, name: 'Assurance', parent_id: null },
    ]
    const deepById = new Map(deep.map((t) => [t.tag_id, t]))
    const sorted = sortTagsByCategoryAndName(deep, deepById)
    // "Essence" (catégorie racine "Transport") doit passer après "Assurance"
    // (catégorie racine "Assurance") malgré son propre nom alphabétiquement
    // antérieur, car le tri se fait par catégorie racine d'abord.
    expect(sorted.map((t) => t.name)).toEqual(['Assurance', 'Essence', 'Voiture', 'Transport'])
  })

  it('traite un Tag avec un parent_id orphelin (absent de byId) comme sa propre racine', () => {
    const orphan: TestTag[] = [{ tag_id: 20, name: 'Fantome', parent_id: 999 }]
    const orphanById = new Map(orphan.map((t) => [t.tag_id, t]))
    expect(sortTagsByCategoryAndName(orphan, orphanById).map((t) => t.name)).toEqual(['Fantome'])
  })

  it('ne boucle pas indéfiniment sur une chaîne de parent_id cyclique', () => {
    const cyclic: TestTag[] = [
      { tag_id: 30, name: 'A', parent_id: 31 },
      { tag_id: 31, name: 'B', parent_id: 30 },
    ]
    const cyclicById = new Map(cyclic.map((t) => [t.tag_id, t]))
    expect(() => sortTagsByCategoryAndName(cyclic, cyclicById)).not.toThrow()
  })

  it('départage par tag_id quand catégorie ET nom de Tag sont identiques (aucune contrainte unique en base)', () => {
    const duplicateNames: TestTag[] = [
      { tag_id: 41, name: 'Divers', parent_id: null },
      { tag_id: 40, name: 'Divers', parent_id: null },
    ]
    const duplicateById = new Map(duplicateNames.map((t) => [t.tag_id, t]))
    expect(sortTagsByCategoryAndName(duplicateNames, duplicateById).map((t) => t.tag_id)).toEqual([40, 41])
  })
})
