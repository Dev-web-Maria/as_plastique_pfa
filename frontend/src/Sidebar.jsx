import { NavLink } from "react-router-dom";
import {
  LayoutDashboard, Wallet, Users, Truck, FileText,
  AlertTriangle, TrendingUp, MessageCircle,
} from "lucide-react";
import logo from "./assets/logo-as-plastique.png";

const PAGES = [
  { path: "/", label: "Vue globale", Icone: LayoutDashboard },
  { path: "/ventes", label: "Ventes", Icone: Wallet },
  { path: "/clients", label: "Clients", Icone: Users },
  { path: "/bons-livraison", label: "Bons de livraison", Icone: Truck },
  { path: "/factures", label: "Factures", Icone: FileText },
  { path: "/impayes", label: "Impayés", Icone: AlertTriangle },
  { path: "/previsions", label: "Prévisions", Icone: TrendingUp },
];

function Sidebar() {
  return (
    <nav style={styles.sidebar}>
      <div style={styles.logoZone}>
        <img src={logo} alt="As Plastique" style={styles.logoImage} />
      </div>

      <div style={styles.liensZone}>
        {PAGES.map(({ path, label, Icone }) => (
          <NavLink
            key={path}
            to={path}
            end={path === "/"}
            style={({ isActive }) => ({
              ...styles.lien,
              ...(isActive ? styles.lienActif : {}),
            })}
          >
            <Icone size={18} strokeWidth={1.75} style={{ marginRight: 12, flexShrink: 0 }} />
            {label}
          </NavLink>
        ))}
      </div>

      <div style={styles.bas}>
        <NavLink
          to="/assistant"
          style={({ isActive }) => ({
            ...styles.lien,
            ...(isActive ? styles.lienActif : {}),
          })}
        >
          <MessageCircle size={18} strokeWidth={1.75} style={{ marginRight: 12, flexShrink: 0 }} />
          Assistant Data
        </NavLink>
      </div>
    </nav>
  );
}

const styles = {
  sidebar: {
    width: 240,
    height: "100vh",
    position: "fixed",
    top: 0,
    left: 0,
    overflowY: "hidden",
    background: "var(--bleu-marine)",
    display: "flex",
    flexDirection: "column",
    flexShrink: 0,
  },
  logoZone: {
    padding: "1.5rem 1.25rem 1.25rem",
    borderBottom: "1px solid rgba(255,255,255,0.1)",
    display: "flex",
    justifyContent: "center",
  },
  logoImage: {
    width: "100%",
    maxWidth: 168,
    height: "auto",
    background: "#fff",
    borderRadius: 6,
    padding: "10px 14px",
    boxShadow: "0 2px 8px rgba(0,0,0,0.25)",
  },
  liensZone: {
    flex: 1,
    padding: "1rem 0.75rem",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  lien: {
    display: "flex",
    alignItems: "center",
    padding: "10px 14px",
    borderRadius: 8,
    color: "rgba(255,255,255,0.75)",
    textDecoration: "none",
    fontSize: 14,
    fontWeight: 500,
    transition: "background 0.15s",
  },
  lienActif: {
    background: "var(--bleu-marine-hover)",
    color: "#fff",
    borderLeft: "3px solid var(--rouge-accent)",
    paddingLeft: 11,
  },
  bas: {
    padding: "0.75rem",
    borderTop: "1px solid rgba(255,255,255,0.1)",
  },
};

export default Sidebar;