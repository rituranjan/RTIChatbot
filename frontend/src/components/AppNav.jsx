import { useState } from "react";

const MENUS = [
  {
    id: "knowledge",
    label: "Knowledge",
    items: [
      { id: "websites", label: "Website RAG" },
      { id: "files", label: "Files" },
      { id: "databases", label: "Databases" },
      { id: "sql", label: "SQL keywords" },
    ],
  },
  {
    id: "setup",
    label: "Setup",
    items: [
      { id: "questions", label: "Questions before chat" },
      { id: "embed", label: "Website embed" },
    ],
  },
  {
    id: "user",
    label: "User settings",
    items: [{ id: "model", label: "Model" }],
  },
  {
    id: "admin",
    label: "Admin",
    items: [{ id: "settings", label: "Settings" }],
  },
  {
    id: "insights",
    label: "Insights",
    items: [
      { id: "visitors", label: "Visitor answers" },
      { id: "chats", label: "Stored chats" },
    ],
  },
];

const ADMIN_MENUS = new Set(["knowledge", "admin"]);
const ADMIN_ITEMS = new Set(["embed"]);

export default function AppNav({ section, onNavigate, admin }) {
  const [openMenu, setOpenMenu] = useState("");
  const menus = MENUS.map((menu) => ({
    ...menu,
    items: menu.items.filter((item) => admin || !ADMIN_ITEMS.has(item.id)),
  })).filter((menu) => (admin || !ADMIN_MENUS.has(menu.id)) && menu.items.length > 0);

  return (
    <nav className="app-nav" aria-label="Main">
      <button
        type="button"
        className={section === "chat" ? "nav-link active" : "nav-link"}
        onClick={() => onNavigate("chat")}
      >
        Chat
      </button>
      {menus.map((menu) => (
        <div className="nav-menu" key={menu.id}>
          <button
            type="button"
            className={menu.items.some((item) => item.id === section) || openMenu === menu.id ? "nav-link active" : "nav-link"}
            aria-expanded={openMenu === menu.id}
            onClick={() => setOpenMenu((current) => (current === menu.id ? "" : menu.id))}
          >
            {menu.label}
          </button>
          <div className={openMenu === menu.id ? "nav-sub open" : "nav-sub"}>
            {menu.items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={section === item.id ? "active" : ""}
                onClick={() => {
                  setOpenMenu("");
                  onNavigate(item.id);
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </nav>
  );
}
