import { Link, useLocation } from "react-router-dom";
import { BarChart3, FileText } from "lucide-react";

const navItems = [
  { path: "/browse", label: "Browse", icon: BarChart3 },
  { path: "/deck/new", label: "New Deck", icon: FileText },
];

export default function TopNav() {
  const location = useLocation();

  return (
    <nav className="bg-slate-900 border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-2">
              <BarChart3 className="w-8 h-8 text-blue-500" />
              <span className="text-xl font-bold text-white">TicketStats</span>
            </Link>
            <div className="hidden md:flex items-center space-x-1">
              {navItems.map(({ path, label, icon: Icon }) => {
                const isActive =
                  location.pathname === path ||
                  (path === "/deck/new" &&
                    location.pathname.startsWith("/deck/"));
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-600 text-white"
                        : "text-slate-300 hover:bg-slate-800 hover:text-white"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    <span>{label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
