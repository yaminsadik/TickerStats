import { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { BarChart3, LogIn, LogOut, User, Menu, X } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import { Button } from "../ui/Button";

export default function TopNav() {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

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

  const closeMobileMenu = () => setMobileMenuOpen(false);

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
                  aria-current={location.pathname === "/browse" ? "page" : undefined}
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Browse</span>
                </Link>
              </div>
            )}
          </div>

          {/* Desktop Auth Section */}
          <div className="hidden md:flex items-center space-x-3">
            {!isLoading && (
              <>
                {isAuthenticated ? (
                  <>
                    <div className="flex items-center space-x-2 text-slate-300">
                      <User className="w-4 h-4" />
                      <span className="text-sm">
                        {user?.name || user?.email}
                      </span>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() =>
                        logout({
                          logoutParams: { returnTo: window.location.origin },
                        })
                      }
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
              <Link
                to="/browse"
                onClick={closeMobileMenu}
                className={`flex items-center space-x-2 px-3 py-3 rounded-lg text-base font-medium transition-colors ${
                  location.pathname === "/browse"
                    ? "bg-blue-600 text-white"
                    : "text-slate-300 hover:bg-slate-800 hover:text-white"
                }`}
                aria-current={location.pathname === "/browse" ? "page" : undefined}
              >
                <BarChart3 className="w-5 h-5" />
                <span>Browse</span>
              </Link>
            )}
          </div>

          {/* Mobile auth section */}
          <div className="pt-4 pb-3 border-t border-slate-800">
            <div className="px-4 space-y-3">
              {!isLoading && (
                <>
                  {isAuthenticated ? (
                    <>
                      <div className="flex items-center space-x-3 px-3 py-2">
                        <User className="w-5 h-5 text-slate-400" />
                        <span className="text-sm text-slate-300">
                          {user?.name || user?.email}
                        </span>
                      </div>
                      <Button
                        variant="outline"
                        className="w-full justify-center"
                        onClick={() => {
                          closeMobileMenu();
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
