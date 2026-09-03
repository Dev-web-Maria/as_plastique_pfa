function Topbar({ titre }) {
  const dateAujourdhui = new Date().toLocaleDateString("fr-FR", {
    weekday: "long",
    day: "numeric",
    month: "long",
    year: "numeric",
  });

  return (
    <header style={styles.topbar}>
      <h1 style={styles.titre}>{titre}</h1>

      <div style={styles.droite}>
        <input
          type="text"
          placeholder="Rechercher un client, une facture..."
          style={styles.recherche}
        />
        <span style={styles.date}>{dateAujourdhui}</span>
        <div style={styles.avatar}>AP</div>
      </div>
    </header>
  );
}

const styles = {
  topbar: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "1rem 2rem",
    background: "#fff",
    borderBottom: "1px solid var(--gris-bordure)",
  },
  titre: {
    fontSize: "1.3rem",
    fontWeight: 700,
    margin: 0,
    color: "var(--bleu-marine)",
  },
  droite: {
    display: "flex",
    alignItems: "center",
    gap: "1rem",
  },
  recherche: {
    padding: "8px 14px",
    borderRadius: 8,
    border: "1px solid var(--gris-bordure)",
    width: 260,
    fontSize: 13,
  },
  date: {
    fontSize: 13,
    color: "var(--gris-texte)",
    whiteSpace: "nowrap",
  },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: "50%",
    background: "var(--bleu-marine)",
    color: "#fff",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    fontSize: 13,
    fontWeight: 700,
  },
};

export default Topbar;