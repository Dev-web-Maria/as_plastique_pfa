import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from "recharts";
import FiltrePeriode from "./FiltrePeriode";

const API = "http://localhost:8000/api";
const ANNEE_PAR_DEFAUT = 2021; // doit rester cohérent avec le défaut de FiltrePeriode

function VueGlobale() {
  const [kpis, setKpis] = useState(null);
  const [serieVentes, setSerieVentes] = useState([]);
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
      fetch(`${API}/kpis?${params}`).then((r) => r.json()),
      fetch(`${API}/ventes-mensuelles?${params}`).then((r) => r.json()),
    ])
      .then(([kpisData, serieData]) => {
        setKpis(kpisData);
        setSerieVentes(serieData);
        setErreur(null);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };

  // Chargement initial : année par défaut, cohérent avec FiltrePeriode
  useEffect(() => {
    chargerDonnees({ annee: ANNEE_PAR_DEFAUT, mois: null, dateDebut: null, dateFin: null });
  }, []);

  const donneesGraphique = serieVentes.map((p) => ({
    mois: `${p.annee}-${String(p.mois).padStart(2, "0")}`,
    montant: Math.round(p.montant_total),
  }));

  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;

  return (
    <>
      <FiltrePeriode onAppliquer={chargerDonnees} />

      {chargement && !kpis ? (
        <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>
      ) : (
        <>
          <div className="grille-kpi">
            <CarteKPI label="Ventes totales" valeur={`${kpis.total_ventes_dh.toLocaleString()} DH`} />
            <CarteKPI label="Documents extraits" valeur={kpis.nb_documents} />
            <CarteKPI label="Clients" valeur={kpis.nb_clients} />
            <CarteKPI
              label="Impayés"
              valeur={`${kpis.total_impaye_dh.toLocaleString()} DH`}
              accent="var(--rouge-accent)"
            />
          </div>

          <div className="carte">
            <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Évolution des ventes</h3>
            {donneesGraphique.length === 0 ? (
              <p style={{ color: "var(--gris-texte)" }}>Aucune donnée pour cette période.</p>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={donneesGraphique}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="mois" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v) => v.toLocaleString() + " DH"} />
                  <Line type="monotone" dataKey="montant" stroke="var(--bleu-marine)" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
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

export default VueGlobale;