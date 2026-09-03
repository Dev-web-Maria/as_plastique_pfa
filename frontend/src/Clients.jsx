import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import FiltrePeriode from "./FiltrePeriode";

const API = "http://localhost:8000/api";
const ANNEE_PAR_DEFAUT = 2021;

function Clients() {
  const [clients, setClients] = useState([]);
  const [recherche, setRecherche] = useState("");
  const [chargement, setChargement] = useState(true);
  const [erreur, setErreur] = useState(null);
  const navigate = useNavigate();

  const chargerDonnees = (filtres) => {
    setChargement(true);
    const params = new URLSearchParams();
    if (filtres.annee) params.append("annee", filtres.annee);
    if (filtres.mois) params.append("mois", filtres.mois);
    if (filtres.dateDebut) params.append("date_debut", filtres.dateDebut);
    if (filtres.dateFin) params.append("date_fin", filtres.dateFin);

    fetch(`${API}/clients?${params}`)
      .then((r) => r.json())
      .then((data) => {
        setClients(data);
        setErreur(null);
      })
      .catch((err) => setErreur(err.message))
      .finally(() => setChargement(false));
  };

  useEffect(() => {
    chargerDonnees({ annee: ANNEE_PAR_DEFAUT, mois: null, dateDebut: null, dateFin: null });
  }, []);

  const clientsFiltres = clients.filter((c) =>
    c.client.toLowerCase().includes(recherche.toLowerCase())
  );

  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;

  return (
    <>
      <FiltrePeriode onAppliquer={chargerDonnees} />

      <div className="carte">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem" }}>
          <h3 style={{ margin: 0, color: "var(--bleu-marine)" }}>
            Clients ({clientsFiltres.length})
          </h3>
          <input
            type="text"
            placeholder="Rechercher un client..."
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
            style={{ padding: "8px 12px", borderRadius: 8, border: "1px solid var(--gris-bordure)", width: 240, fontSize: 13 }}
          />
        </div>

        {chargement ? (
          <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>
        ) : clientsFiltres.length === 0 ? (
          <p style={{ color: "var(--gris-texte)" }}>Aucun client trouvé.</p>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
                <th style={{ padding: "8px 4px" }}>Client</th>
                <th style={{ padding: "8px 4px" }}>CA (période)</th>
                <th style={{ padding: "8px 4px" }}>Commandes</th>
                <th style={{ padding: "8px 4px" }}>Dernière commande</th>
              </tr>
            </thead>
            <tbody>
              {clientsFiltres.map((c) => (
                <tr
                  key={c.client_id}
                  onClick={() => navigate(`/clients/${c.client_id}`)}
                  style={{ borderBottom: "1px solid #f5f5f5", cursor: "pointer" }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "#f8f9fb")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
                >
                  <td style={{ padding: "10px 4px", fontWeight: 600, color: "var(--bleu-marine)" }}>{c.client}</td>
                  <td style={{ padding: "10px 4px" }}>{c.ca_total.toLocaleString()} DH</td>
                  <td style={{ padding: "10px 4px" }}>{c.nb_commandes}</td>
                  <td style={{ padding: "10px 4px" }}>{c.derniere_commande ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

export default Clients;