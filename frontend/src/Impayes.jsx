import { useEffect, useState } from "react";
import FiltrePeriode from "./FiltrePeriode";

const API = "http://localhost:8000/api";
const ANNEE_PAR_DEFAUT = 2021;

const COULEUR_STATUT = {
  "Payée": { fond: "var(--vert-clair)", texte: "var(--vert-succes)" },
  "Partielle": { fond: "var(--orange-clair)", texte: "var(--orange-alerte)" },
  "Impayée": { fond: "var(--rouge-clair)", texte: "var(--rouge-accent)" },
};

const COULEUR_NIVEAU = {
  Faible: { fond: "var(--vert-clair)", texte: "var(--vert-succes)" },
  Moyen: { fond: "var(--orange-clair)", texte: "var(--orange-alerte)" },
  "Élevé": { fond: "var(--rouge-clair)", texte: "var(--rouge-accent)" },
};

function Impayes() {
  const [reconciliation, setReconciliation] = useState(null);
  const [factures, setFactures] = useState([]);
  const [clientsRisque, setClientsRisque] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);

  const chargerDonnees = (filtres) => {
    setChargement(true);
    const params = new URLSearchParams();
    if (filtres.annee) params.append("annee", filtres.annee);
    if (filtres.mois) params.append("mois", filtres.mois);
    if (filtres.dateDebut) params.append("date_debut", filtres.dateDebut);
    if (filtres.dateFin) params.append("date_fin", filtres.dateFin);

    Promise.all([
      fetch(`${API}/reconciliation-impayes?${params}`).then((r) => r.json()),
      fetch(`${API}/grand-livre?${params}&limit=50`).then((r) => r.json()),
      fetch(`${API}/clients-risque`).then((r) => r.json()),
    ])
      .then(([reconciliationData, facturesData, clientsData]) => {
        setReconciliation(reconciliationData);
        setFactures(facturesData);
        setClientsRisque(clientsData.slice(0, 8));
        setErreur(null);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };

  useEffect(() => {
    chargerDonnees({ annee: ANNEE_PAR_DEFAUT, mois: null, dateDebut: null, dateFin: null });
  }, []);

  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;

  return (
    <>
      <FiltrePeriode onAppliquer={chargerDonnees} />

      {chargement && !reconciliation ? (
        <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>
      ) : (
        <>
          <div className="grille-kpi">
            <CarteKPI label="Impayé listé (période)" valeur={`${reconciliation.total_impaye_snapshot.toLocaleString()} DH`} />
            <CarteKPI label="Solde réel (grand livre)" valeur={`${reconciliation.total_solde_reel.toLocaleString()} DH`} accent="var(--rouge-accent)" />
            <CarteKPI label="Réglé" valeur={`${reconciliation.montant_regularise.toLocaleString()} DH`} accent="var(--vert-succes)" />
            <CarteKPI label="Taux de rapprochement" valeur={`${reconciliation.taux_rapprochement_pct}%`} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: "1rem" }}>
            <div className="carte">
              <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Factures — période sélectionnée</h3>
              {factures.length === 0 ? (
                <p style={{ color: "var(--gris-texte)" }}>Aucune facture sur cette période.</p>
              ) : (
                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                  <thead>
                    <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
                      <th style={{ padding: "8px 4px" }}>N° facture</th>
                      <th style={{ padding: "8px 4px" }}>Client</th>
                      <th style={{ padding: "8px 4px" }}>Date</th>
                      <th style={{ padding: "8px 4px" }}>Montant</th>
                      <th style={{ padding: "8px 4px" }}>Solde</th>
                      <th style={{ padding: "8px 4px" }}>Statut</th>
                    </tr>
                  </thead>
                  <tbody>
                    {factures.map((f, i) => {
                      const couleur = COULEUR_STATUT[f.statut] || { fond: "#eee", texte: "#666" };
                      return (
                        <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                          <td style={{ padding: "8px 4px" }}>{f.numero_facture}</td>
                          <td style={{ padding: "8px 4px" }}>{f.client}</td>
                          <td style={{ padding: "8px 4px" }}>{f.date_facture ?? "—"}</td>
                          <td style={{ padding: "8px 4px" }}>{f.montant_facture?.toLocaleString()} DH</td>
                          <td style={{ padding: "8px 4px" }}>{f.solde?.toLocaleString() ?? "—"} DH</td>
                          <td style={{ padding: "8px 4px" }}>
                            <span style={{
                              padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600,
                              background: couleur.fond, color: couleur.texte,
                            }}>
                              {f.statut ?? "Inconnu"}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              )}
            </div>

            <div className="carte">
              <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Clients à risque</h3>
              <p style={{ fontSize: 12, color: "var(--gris-texte)", marginTop: -8 }}>
                Basé sur l'historique complet, indépendant de la période sélectionnée.
              </p>
              {clientsRisque.map((c, i) => {
                const couleur = COULEUR_NIVEAU[c.niveau_risque] || { fond: "#eee", texte: "#666" };
                return (
                  <div key={i} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "center",
                    padding: "8px 0", borderBottom: "1px solid #f5f5f5", fontSize: 13,
                  }}>
                    <div>
                      <div style={{ fontWeight: 600 }}>{c.client}</div>
                      <div style={{ fontSize: 11, color: "var(--gris-texte)" }}>
                        {c.montant_total_impaye?.toLocaleString()} DH dus
                      </div>
                    </div>
                    <span style={{
                      padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600,
                      background: couleur.fond, color: couleur.texte, whiteSpace: "nowrap",
                    }}>
                      {c.niveau_risque}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </>
      )}
    </>
  );
}

function CarteKPI({ label, valeur, accent = "var(--bleu-marine)" }) {
  return (
    <div className="carte">
      <p style={{ fontSize: 12, color: "var(--gris-texte)", margin: "0 0 6px" }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 700, margin: 0, color: accent }}>{valeur}</p>
    </div>
  );
}

export default Impayes;