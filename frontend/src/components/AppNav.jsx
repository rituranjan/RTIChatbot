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
          <button type="button" className={menu.items.some((item) => item.id === section) ? "nav-link active" : "nav-link"}>
            {menu.label}
          </button>
          <div className="nav-sub">
            {menu.items.map((item) => (
              <button
                type="button"
                key={item.id}
                className={section === item.id ? "active" : ""}
                onClick={() => onNavigate(item.id)}
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
