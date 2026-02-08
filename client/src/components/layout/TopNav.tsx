import { useState, useRef, useEffect } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import {
  BarChart3,
  LogIn,
  LogOut,
  User,
  Menu,
  X,
  Star,
  Search,
  FileText,
  ChevronDown,
  Shield,
  Settings,
} from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "../ui/Button";

export default function TopNav() {
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [avatarFailed, setAvatarFailed] = useState(false);

  // Make Auth0 optional - gracefully handle if not configured
  let isAuthenticated = false;
  let isLoading = false;
  let loginWithRedirect: any = () => console.warn("Auth0 not configured");
  let logout: any = () => console.warn("Auth0 not configured");
  let user: any = null;

  try {
    const auth0 = useAuth0();
    isAuthenticated = auth0.isAuthenticated;
    isLoading = auth0.isLoading;
    loginWithRedirect = auth0.loginWithRedirect;
    logout = auth0.logout;
    user = auth0.user;
  } catch (error) {
    // Auth0 not configured, use defaults above
    console.log("Auth0 not available, authentication disabled");
  }

  const queryClient = useQueryClient();
  const closeMobileMenu = () => setMobileMenuOpen(false);

  const displayName = user?.name || user?.email || "Account";
  const initials =
    displayName
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part: string) => part[0]?.toUpperCase())
      .join("") || "U";

  // Profile dropdown state
  const [profileOpen, setProfileOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(event.target as Node)
      ) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <nav className="bg-slate-900 border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Logo and Desktop Nav */}
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-2">
              <BarChart3 className="w-8 h-8 text-blue-500" />
              <span className="text-xl font-bold text-white">TickerStats</span>
            </Link>

            {/* Desktop nav items - only show when authenticated */}
            {isAuthenticated && (
              <div className="hidden md:flex items-center space-x-1">
                <Link
                  to="/browse"
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname === "/browse"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname === "/browse" ? "page" : undefined
                  }
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Browse</span>
                </Link>
                <Link
                  to="/saved-searches"
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname === "/saved-searches"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname === "/saved-searches" ? "page" : undefined
                  }
                >
                  <Search className="w-4 h-4" />
                  <span>Saved</span>
                </Link>
                <Link
                  to="/watchlist"
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname === "/watchlist"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname === "/watchlist" ? "page" : undefined
                  }
                >
                  <Star className="w-4 h-4" />
                  <span>Watchlist</span>
                </Link>
                <Link
                  to="/decks"
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname.startsWith("/decks")
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname.startsWith("/decks") ? "page" : undefined
                  }
                >
                  <FileText className="w-4 h-4" />
                  <span>Decks</span>
                </Link>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => navigate("/deck/new")}
                  className="ml-2"
                >
                  <FileText className="w-4 h-4 mr-1" />
                  New Deck
                </Button>
              </div>
            )}
          </div>

          {/* Desktop Auth Section */}
          <div className="hidden md:flex items-center space-x-3">
            {!isLoading && (
              <>
                {isAuthenticated ? (
                  <div className="relative" ref={dropdownRef}>
                    <button
                      onClick={() => setProfileOpen(!profileOpen)}
                      className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800 transition-colors"
                    >
                      {user?.picture && !avatarFailed ? (
                        <img
                          src={user.picture}
                          alt=""
                          className="w-7 h-7 rounded-full border border-slate-600"
                          onError={() => setAvatarFailed(true)}
                        />
                      ) : (
                        <div className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center">
                          <span className="text-xs font-semibold text-slate-200">
                            {initials}
                          </span>
                        </div>
                      )}
                      <span className="text-sm text-slate-300 max-w-[120px] truncate">
                        {displayName}
                      </span>
                      <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
                    </button>

                    {/* Dropdown menu */}
                    {profileOpen && (
                      <div className="absolute right-0 mt-1 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-xl z-50 py-1">
                        <Link
                          to="/profile"
                          onClick={() => setProfileOpen(false)}
                          className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors"
                        >
                          <Settings className="w-4 h-4" />
                          Profile
                        </Link>
                        <button
                          onClick={() => {
                            setProfileOpen(false);
                            queryClient.clear();
                            logout({
                              logoutParams: {
                                returnTo: window.location.origin,
                              },
                            });
                          }}
                          className="flex items-center gap-2 px-4 py-2 text-sm text-slate-300 hover:bg-slate-700 transition-colors w-full text-left"
                        >
                          <LogOut className="w-4 h-4" />
                          Logout
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => loginWithRedirect()}
                      aria-label="Log in"
                    >
                      Log in
                    </Button>
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={() =>
                        loginWithRedirect({
                          authorizationParams: {
                            screen_hint: "signup",
                          },
                        })
                      }
                      aria-label="Sign up"
                    >
                      Sign up
                    </Button>
                  </>
                )}
              </>
            )}
          </div>

          {/* Mobile menu button */}
          <div className="md:hidden">
            <button
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="inline-flex items-center justify-center p-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-blue-500"
              aria-expanded={mobileMenuOpen}
              aria-label="Toggle menu"
            >
              {mobileMenuOpen ? (
                <X className="w-6 h-6" />
              ) : (
                <Menu className="w-6 h-6" />
              )}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-slate-800 bg-slate-900">
          <div className="px-4 pt-2 pb-3 space-y-1">
            {/* Mobile nav items - only show when authenticated */}
            {isAuthenticated && (
              <>
                <Link
                  to="/browse"
                  onClick={closeMobileMenu}
                  className={`flex items-center space-x-2 px-3 py-3 rounded-lg text-base font-medium transition-colors ${
                    location.pathname === "/browse"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname === "/browse" ? "page" : undefined
                  }
                >
                  <BarChart3 className="w-5 h-5" />
                  <span>Browse</span>
                </Link>
                <Link
                  to="/saved-searches"
                  onClick={closeMobileMenu}
                  className={`flex items-center space-x-2 px-3 py-3 rounded-lg text-base font-medium transition-colors ${
                    location.pathname === "/saved-searches"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname === "/saved-searches" ? "page" : undefined
                  }
                >
                  <Search className="w-5 h-5" />
                  <span>Saved Searches</span>
                </Link>
                <Link
                  to="/watchlist"
                  onClick={closeMobileMenu}
                  className={`flex items-center space-x-2 px-3 py-3 rounded-lg text-base font-medium transition-colors ${
                    location.pathname === "/watchlist"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname === "/watchlist" ? "page" : undefined
                  }
                >
                  <Star className="w-5 h-5" />
                  <span>Watchlist</span>
                </Link>
                <Link
                  to="/decks"
                  onClick={closeMobileMenu}
                  className={`flex items-center space-x-2 px-3 py-3 rounded-lg text-base font-medium transition-colors ${
                    location.pathname.startsWith("/decks")
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                  aria-current={
                    location.pathname.startsWith("/decks") ? "page" : undefined
                  }
                >
                  <FileText className="w-5 h-5" />
                  <span>Deck History</span>
                </Link>
                <button
                  onClick={() => {
                    closeMobileMenu();
                    navigate("/deck/new");
                  }}
                  className="flex items-center space-x-2 px-3 py-3 rounded-lg text-base font-medium w-full text-left bg-blue-600 hover:bg-blue-700 text-white transition-colors"
                >
                  <FileText className="w-5 h-5" />
                  <span>New Deck</span>
                </button>
              </>
            )}
          </div>

          {/* Mobile auth section */}
          <div className="pt-4 pb-3 border-t border-slate-800">
            <div className="px-4 space-y-3">
              {!isLoading && (
                <>
                  {isAuthenticated ? (
                    <>
                      <Link
                        to="/profile"
                        onClick={closeMobileMenu}
                        className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-slate-800 transition-colors"
                      >
                        {user?.picture && !avatarFailed ? (
                          <img
                            src={user.picture}
                            alt=""
                            className="w-8 h-8 rounded-full border border-slate-600"
                            onError={() => setAvatarFailed(true)}
                          />
                        ) : (
                          <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center">
                            <span className="text-xs font-semibold text-slate-200">
                              {initials}
                            </span>
                          </div>
                        )}
                        <span className="text-sm text-slate-300">
                          {displayName}
                        </span>
                      </Link>
                      <Button
                        variant="outline"
                        className="w-full justify-center"
                        onClick={() => {
                          closeMobileMenu();
                          queryClient.clear();
                          logout({
                            logoutParams: { returnTo: window.location.origin },
                          });
                        }}
                        aria-label="Log out"
                      >
                        <LogOut className="w-4 h-4 mr-2" />
                        Logout
                      </Button>
                    </>
                  ) : (
                    <>
                      <Button
                        variant="ghost"
                        className="w-full justify-center"
                        onClick={() => {
                          closeMobileMenu();
                          loginWithRedirect();
                        }}
                        aria-label="Log in"
                      >
                        <LogIn className="w-4 h-4 mr-2" />
                        Log in
                      </Button>
                      <Button
                        variant="primary"
                        className="w-full justify-center"
                        onClick={() => {
                          closeMobileMenu();
                          loginWithRedirect({
                            authorizationParams: {
                              screen_hint: "signup",
                            },
                          });
                        }}
                        aria-label="Sign up"
                      >
                        Sign up
                      </Button>
                    </>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
