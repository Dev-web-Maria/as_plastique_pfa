import { useEffect, useState } from "react";
import FiltrePeriode from "./FiltrePeriode";

const API = "http://localhost:8000/api";
const ANNEE_PAR_DEFAUT = 2021;

const COULEUR_STATUT_EXTRACTION = {
  ok: { fond: "var(--vert-clair)", texte: "var(--vert-succes)" },
  extraction_incomplete: { fond: "var(--orange-clair)", texte: "var(--orange-alerte)" },
  erreur_extraction: { fond: "var(--rouge-clair)", texte: "var(--rouge-accent)" },
};

function PageDocuments({ typeDocument, libelle }) {
  const [kpis, setKpis] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);

  const chargerDonnees = (filtres) => {
    setChargement(true);
    const params = new URLSearchParams({ type_document: typeDocument });
    if (filtres.annee) params.append("annee", filtres.annee);
    if (filtres.mois) params.append("mois", filtres.mois);
    if (filtres.dateDebut) params.append("date_debut", filtres.dateDebut);
    if (filtres.dateFin) params.append("date_fin", filtres.dateFin);

    Promise.all([
      fetch(`${API}/kpis-documents?${params}`).then((r) => r.json()),
      fetch(`${API}/documents-detail?${params}&limit=50`).then((r) => r.json()),
    ])
      .then(([kpisData, docsData]) => {
        setKpis(kpisData);
        setDocuments(docsData);
        setErreur(null);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };

  useEffect(() => {
    chargerDonnees({ annee: ANNEE_PAR_DEFAUT, mois: null, dateDebut: null, dateFin: null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeDocument]);

  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;

  return (
    <>
      <FiltrePeriode onAppliquer={chargerDonnees} />

      {chargement && !kpis ? (
        <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>
      ) : (
        <>
          <div className="grille-kpi">
            <CarteKPI label={`${libelle} (total)`} valeur={kpis.n_total} />
            <CarteKPI label="Montant total" valeur={`${kpis.montant_total_dh.toLocaleString()} DH`} />
            <CarteKPI label="Bien extraits" valeur={kpis.n_ok} accent="var(--vert-succes)" />
            <CarteKPI label="Taux d'extraction" valeur={`${kpis.taux_extraction_pct}%`} />
          </div>

          <div className="carte">
            <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Liste des {libelle.toLowerCase()}</h3>
            <p style={{ fontSize: 12, color: "var(--gris-texte)", marginTop: -8 }}>
              Colonnes "Fichier"/"Onglet" : traçabilité vers le document Excel source.
            </p>
            {documents.length === 0 ? (
              <p style={{ color: "var(--gris-texte)" }}>Aucun document pour cette période.</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
                    <th style={{ padding: "8px 4px" }}>N°</th>
                    <th style={{ padding: "8px 4px" }}>Date</th>
                    <th style={{ padding: "8px 4px" }}>Client</th>
                    <th style={{ padding: "8px 4px" }}>Montant</th>
                    <th style={{ padding: "8px 4px" }}>Statut extraction</th>
                    <th style={{ padding: "8px 4px" }}>Fichier</th>
                    <th style={{ padding: "8px 4px" }}>Onglet</th>
                  </tr>
                </thead>
                <tbody>
                  {documents.map((d, i) => {
                    const couleur = COULEUR_STATUT_EXTRACTION[d.statut_extraction] || { fond: "#eee", texte: "#666" };
                    return (
                      <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                        <td style={{ padding: "8px 4px" }}>{d.doc_number ?? "—"}</td>
                        <td style={{ padding: "8px 4px" }}>{d.date ?? "—"}</td>
                        <td style={{ padding: "8px 4px", fontWeight: 600 }}>{d.client ?? "—"}</td>
                        <td style={{ padding: "8px 4px" }}>{(d.net_a_payer ?? d.total_ht)?.toLocaleString() ?? "—"} DH</td>
                        <td style={{ padding: "8px 4px" }}>
                          <span style={{
                            padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600,
                            background: couleur.fond, color: couleur.texte,
                          }}>
                            {d.statut_extraction}
                          </span>
                        </td>
                        <td style={{ padding: "8px 4px", fontSize: 11, color: "var(--gris-texte)" }}>{d.fichier}</td>
                        <td style={{ padding: "8px 4px", fontSize: 11, color: "var(--gris-texte)" }}>{d.onglet}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
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

export default PageDocuments;