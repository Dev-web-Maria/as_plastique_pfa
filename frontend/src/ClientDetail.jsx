import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft } from "lucide-react";

const API = "http://localhost:8000/api";

const COULEUR_STATUT = {
  "Payée": { fond: "var(--vert-clair)", texte: "var(--vert-succes)" },
  "Partielle": { fond: "var(--orange-clair)", texte: "var(--orange-alerte)" },
  "Impayée": { fond: "var(--rouge-clair)", texte: "var(--rouge-accent)" },
};

function ClientDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [client, setClient] = useState(null);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    fetch(`${API}/clients/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("Client introuvable");
        return r.json();
      })
      .then(setClient)
      .catch((err) => setErreur(err.message));
  }, [id]);

  if (erreur) return <p style={{ color: "var(--rouge-accent)" }}>Erreur : {erreur}</p>;
  if (!client) return <p style={{ color: "var(--gris-texte)" }}>Chargement...</p>;

  return (
    <>
      <button
        onClick={() => navigate("/clients")}
        style={{
          display: "flex", alignItems: "center", gap: 6, background: "none", border: "none",
          color: "var(--bleu-marine)", cursor: "pointer", fontSize: 13, marginBottom: "1rem", padding: 0,
        }}
      >
        <ArrowLeft size={16} /> Retour à la liste des clients
      </button>

      <h2 style={{ color: "var(--bleu-marine)", marginTop: 0 }}>{client.nom}</h2>

      <div className="grille-kpi">
        <CarteKPI label="CA total (historique)" valeur={`${client.ca_total.toLocaleString()} DH`} />
        <CarteKPI label="Nombre de commandes" valeur={client.nb_commandes} />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
        <div className="carte">
          <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Historique des documents</h3>
          {client.documents.length === 0 ? (
            <p style={{ color: "var(--gris-texte)" }}>Aucun document.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
                  <th style={{ padding: "6px 4px" }}>Date</th>
                  <th style={{ padding: "6px 4px" }}>Type</th>
                  <th style={{ padding: "6px 4px" }}>N°</th>
                  <th style={{ padding: "6px 4px" }}>Montant</th>
                </tr>
              </thead>
              <tbody>
                {client.documents.map((d, i) => (
                  <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                    <td style={{ padding: "6px 4px" }}>{d.date ?? "—"}</td>
                    <td style={{ padding: "6px 4px", textTransform: "capitalize" }}>{d.type_document.replace("_", " ")}</td>
                    <td style={{ padding: "6px 4px" }}>{d.doc_number ?? "—"}</td>
                    <td style={{ padding: "6px 4px" }}>{(d.net_a_payer ?? d.total_ht)?.toLocaleString() ?? "—"} DH</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="carte">
          <h3 style={{ marginTop: 0, color: "var(--bleu-marine)" }}>Statut de paiement (grand livre)</h3>
          {client.grand_livre.length === 0 ? (
            <p style={{ color: "var(--gris-texte)" }}>Aucune donnée de rapprochement pour ce client.</p>
          ) : (
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ textAlign: "left", borderBottom: "2px solid var(--gris-bordure)" }}>
                  <th style={{ padding: "6px 4px" }}>N° facture</th>
                  <th style={{ padding: "6px 4px" }}>Date</th>
                  <th style={{ padding: "6px 4px" }}>Solde</th>
                  <th style={{ padding: "6px 4px" }}>Statut</th>
                </tr>
              </thead>
              <tbody>
                {client.grand_livre.map((g, i) => {
                  const couleur = COULEUR_STATUT[g.statut] || { fond: "#eee", texte: "#666" };
                  return (
                    <tr key={i} style={{ borderBottom: "1px solid #f5f5f5" }}>
                      <td style={{ padding: "6px 4px" }}>{g.numero_facture}</td>
                      <td style={{ padding: "6px 4px" }}>{g.date_facture ?? "—"}</td>
                      <td style={{ padding: "6px 4px" }}>{g.solde?.toLocaleString() ?? "—"} DH</td>
                      <td style={{ padding: "6px 4px" }}>
                        <span style={{
                          padding: "3px 10px", borderRadius: 12, fontSize: 11, fontWeight: 600,
                          background: couleur.fond, color: couleur.texte,
                        }}>
                          {g.statut ?? "Inconnu"}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </>
  );
}

function CarteKPI({ label, valeur }) {
  return (
    <div className="carte">
      <p style={{ fontSize: 12, color: "var(--gris-texte)", margin: "0 0 6px" }}>{label}</p>
      <p style={{ fontSize: 22, fontWeight: 700, margin: 0, color: "var(--bleu-marine)" }}>{valeur}</p>
    </div>
  );
}

export default ClientDetail;