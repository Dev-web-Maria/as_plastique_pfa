import { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import FiltrePeriode from "./FiltrePeriode";

const API = "http://localhost:8000/api";
const ANNEE_PAR_DEFAUT = 2021;

function Ventes() {
  const [kpis, setKpis] = useState(null);
  const [serieVentes, setSerieVentes] = useState([]);
  const [topProduits, setTopProduits] = useState([]);
  const [dernieresVentes, setDernieresVentes] = useState([]);
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
      fetch(`${API}/kpis-ventes?${params}`).then((r) => r.json()),
      fetch(`${API}/ventes-mensuelles?${params}`).then((r) => r.json()),
      fetch(`${API}/top-produits?${params}&limit=5`).then((r) => r.json()),
      fetch(`${API}/dernieres-ventes?${params}&limit=15`).then((r) => r.json()),
    ])
      .then(([kpisData, serieData, produitsData, ventesData]) => {
        setKpis(kpisData);
        setSerieVentes(serieData);
        setTopProduits(produitsData);
        setDernieresVentes(ventesData);
        setErreur(null);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };


  useEffect(() => {
    chargerDonnees({ annee: ANNEE_PAR_DEFAUT, mois: null, dateDebut: null, dateFin: null });
  }, []);

  const donneesGraphique = serieVentes.map((p) => ({
    mois: `${p.annee}-${String(p.mois).padStart(2, "0")}`,
    montant: Math.round(p.montant_total),
  }));

  const maxQuantite = topProduits.length ? Math.max(...topProduits.map((p) => p.quantite_totale)) : 1;

  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;

  return (
    <>
      <FiltrePeriode onAppliquer={chargerDonnees} />

      {chargement && !kpis ? (
        <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>
      ) : (
        <>
          <div className="grille-kpi">
            <CarteKPI label="CA HT total" valeur={`${kpis.ca_total_dh.toLocaleString()} DH`} />
            <CarteKPI label="Volume total" valeur={`${kpis.volume_total.toLocaleString()} KG`} />
            <CarteKPI label="Produits distincts" valeur={kpis.produits_distincts} />
            <CarteKPI label="Clients actifs" valeur={kpis.clients_actifs} />
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
            <div className="carte">
              <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Évolution mensuelle du CA</h3>
              {donneesGraphique.length === 0 ? (
                <p style={{ color: "var(--gris-texte)" }}>Aucune donnée pour cette période.</p>
              ) : (
                <ResponsiveContainer width="100%" height={280}>
                  <BarChart data={donneesGraphique}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="mois" tick={{ fontSize: 11 }} />
                    <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                    <Tooltip formatter={(v) => v.toLocaleString() + " DH"} />
                    <Bar dataKey="montant" fill="var(--bleu-marine)" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div className="carte">
              <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Top 5 produits</h3>
              {topProduits.length === 0 ? (
                <p style={{ color: "var(--gris-texte)" }}>Aucune donnée pour cette période.</p>
              ) : (
                topProduits.map((p, i) => (
                  <div key={i} style={{ marginBottom: 10 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 3 }}>
                      <span style={{ fontWeight: 600 }}>{p.designation.slice(0, 35)}</span>
                      <span style={{ color: "var(--gris-texte)" }}>{p.quantite_totale.toLocaleString()} {p.unite}</span>
                    </div>
                    <div style={{ background: "#eee", borderRadius: 4, height: 8 }}>
                      <div style={{
                        width: `${(p.quantite_totale / maxQuantite) * 100}%`,
                        background: "var(--bleu-marine)", height: 8, borderRadius: 4,
                      }} />
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="carte">
            <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Dernières ventes</h3>
            <p style={{ fontSize: 12, color: "var(--gris-texte)", marginTop: -8 }}>
              Colonnes "Fichier"/"Onglet" : traçabilité vers le document Excel source.
            </p>
            {dernieresVentes.length === 0 ? (
              <p style={{ color: "var(--gris-texte)" }}>Aucune vente pour cette période.</p>
            ) : (
              <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
                    <th style={{ padding: "8px 4px" }}>Date</th>
                    <th style={{ padding: "8px 4px" }}>Client</th>
                    <th style={{ padding: "8px 4px" }}>Type</th>
                    <th style={{ padding: "8px 4px" }}>N°</th>
                    <th style={{ padding: "8px 4px" }}>Montant</th>
                    <th style={{ padding: "8px 4px" }}>Fichier</th>
                    <th style={{ padding: "8px 4px" }}>Onglet</th>
                  </tr>
                </thead>
                <tbody>
                  {dernieresVentes.map((v, i) => (
                    <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                      <td style={{ padding: "8px 4px" }}>{v.date ?? "—"}</td>
                      <td style={{ padding: "8px 4px", fontWeight: 600 }}>{v.client ?? "—"}</td>
                      <td style={{ padding: "8px 4px", textTransform: "capitalize" }}>{v.type_document.replace("_", " ")}</td>
                      <td style={{ padding: "8px 4px" }}>{v.doc_number ?? "—"}</td>
                      <td style={{ padding: "8px 4px" }}>{(v.net_a_payer ?? v.total_ht)?.toLocaleString() ?? "—"} DH</td>
                      <td style={{ padding: "8px 4px", fontSize: 11, color: "var(--gris-texte)" }}>{v.fichier}</td>
                      <td style={{ padding: "8px 4px", fontSize: 11, color: "var(--gris-texte)" }}>{v.onglet}</td>
                    </tr>
                  ))}
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

export default Ventes;