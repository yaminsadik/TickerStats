import { Link, useLocation } from "react-router-dom";
import { BarChart3, LogIn, LogOut, User } from "lucide-react";
import { useAuth0 } from "@auth0/auth0-react";
import { Button } from "../ui/Button";

export default function TopNav() {
  const location = useLocation();

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

  return (
    <nav className="bg-slate-900 border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-8">
            <Link to="/" className="flex items-center space-x-2">
              <BarChart3 className="w-8 h-8 text-blue-500" />
              <span className="text-xl font-bold text-white">TickerStats</span>
            </Link>

            {/* Only show nav items when authenticated */}
            {isAuthenticated && (
              <div className="hidden md:flex items-center space-x-1">
                <Link
                  to="/browse"
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    location.pathname === "/browse"
                      ? "bg-blue-600 text-white"
                      : "text-slate-300 hover:bg-slate-800 hover:text-white"
                  }`}
                >
                  <BarChart3 className="w-4 h-4" />
                  <span>Browse</span>
                </Link>
              </div>
            )}
          </div>

          {/* Auth Section */}
          <div className="flex items-center space-x-3">
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
    </nav>
  );
}
