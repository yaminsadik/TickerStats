/**
 * User profile page showing account info, subscription status, and usage.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import {
  Mail,
  Calendar,
  Crown,
  Shield,
  Star,
  FileText,
  Search,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { Card, Button, Alert } from "../components/ui";
import { useProfileQuery } from "../queries/useProfileQuery";
import { useSubscriptionMutations } from "../queries/useSubscriptionMutations";

export default function ProfilePage() {
  const navigate = useNavigate();
  const { user: auth0User } = useAuth0();
  const { profile, loading, error } = useProfileQuery();
  const {
    createCheckout,
    isCreatingCheckout,
    checkoutError,
    createPortal,
    isCreatingPortal,
    portalError,
  } = useSubscriptionMutations();

  const [avatarFailed, setAvatarFailed] = useState(false);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error || !profile) {
    return (
      <div className="max-w-2xl mx-auto p-6">
        <Alert variant="error">{error || "Failed to load profile"}</Alert>
      </div>
    );
  }

  const avatarUrl = profile.picture || auth0User?.picture || "";
  const displayName = profile.name || auth0User?.name || "Anonymous";
  const displayEmail = profile.email || auth0User?.email || null;
  const initials =
    displayName
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part: string) => part[0]?.toUpperCase())
      .join("") || "U";
  const tierColors: Record<string, string> = {
    free: "bg-slate-600 text-slate-200",
    pro: "bg-yellow-600 text-yellow-100",
    enterprise: "bg-purple-600 text-purple-100",
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-white">Profile</h1>

      {/* Identity Card */}
      <Card className="p-6">
        <div className="flex items-start gap-5">
          {/* Avatar */}
          {avatarUrl && !avatarFailed ? (
            <img
              src={avatarUrl}
              alt="Avatar"
              className="w-20 h-20 rounded-full border-2 border-slate-700 object-cover"
              onError={() => setAvatarFailed(true)}
            />
          ) : (
            <div className="w-20 h-20 rounded-full bg-slate-700 flex items-center justify-center">
              <span className="text-2xl font-semibold text-slate-200">
                {initials}
              </span>
            </div>
          )}

          <div className="flex-1 min-w-0 space-y-2">
            <div className="flex items-center gap-3 flex-wrap">
              <h2 className="text-xl font-semibold text-white">
                {displayName}
              </h2>
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold uppercase ${
                  tierColors[profile.subscription_tier] || tierColors.free
                }`}
              >
                {profile.subscription_tier === "free" ? (
                  <Star className="w-3 h-3" />
                ) : (
                  <Crown className="w-3 h-3" />
                )}
                {profile.subscription_tier}
              </span>
              {profile.is_admin && (
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-red-600 text-red-100">
                  <Shield className="w-3 h-3" />
                  Admin
                </span>
              )}
            </div>

            {displayEmail && (
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <Mail className="w-4 h-4" />
                <span>{displayEmail}</span>
              </div>
            )}

            <div className="flex items-center gap-2 text-slate-400 text-sm">
              <Calendar className="w-4 h-4" />
              <span>
                Member since{" "}
                {new Date(profile.created_at).toLocaleDateString("en-US", {
                  year: "numeric",
                  month: "long",
                  day: "numeric",
                })}
              </span>
            </div>
          </div>
        </div>
      </Card>

      {/* Subscription Card */}
      <Card className="p-6 space-y-4">
        <h3 className="text-lg font-semibold text-white flex items-center gap-2">
          <Crown className="w-5 h-5 text-yellow-500" />
          Subscription
        </h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">
              Current Plan
            </p>
            <p className="text-lg font-semibold text-white capitalize">
              {profile.subscription_tier}
            </p>
          </div>

          {profile.subscription_expires_at && (
            <div className="bg-slate-800/50 rounded-lg p-4">
              <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">
                Expires
              </p>
              <p className="text-lg font-semibold text-white">
                {new Date(profile.subscription_expires_at).toLocaleDateString()}
              </p>
            </div>
          )}
        </div>

        {profile.subscription_tier === "free" && (
          <div className="bg-gradient-to-r from-blue-900/40 to-purple-900/40 border border-blue-800/50 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-white mb-2">
              Upgrade to Pro
            </h4>
            <ul className="text-sm text-slate-300 space-y-1 mb-3">
              <li>
                ✓ Unlimited saved searches (currently limited to{" "}
                {profile.saved_searches_limit})
              </li>
              <li>✓ Export to CSV, Excel, and PDF</li>
              <li>✓ Priority deck generation</li>
            </ul>
            <Button
              variant="primary"
              size="sm"
              onClick={() => createCheckout("pro")}
              disabled={isCreatingCheckout}
            >
              {isCreatingCheckout ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Loading...
                </>
              ) : (
                <>
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Upgrade Now
                </>
              )}
            </Button>
            {checkoutError && (
              <Alert variant="error" className="mt-3">
                {checkoutError}
              </Alert>
            )}
          </div>
        )}
        {profile.subscription_tier !== "free" && (
          <>
            <Button
              variant="outline"
              size="sm"
              onClick={() => createPortal()}
              disabled={isCreatingPortal}
              className="w-full"
            >
              {isCreatingPortal ? (
                <>
                  <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                  Loading...
                </>
              ) : (
                <>
                  <ExternalLink className="w-4 h-4 mr-1" />
                  Manage Subscription
                </>
              )}
            </Button>
            {portalError && (
              <Alert variant="error">
                {portalError}
              </Alert>
            )}
          </>
        )}
      </Card>

      {/* Usage Card */}
      <Card className="p-5 sm:p-6 space-y-5">
        <h3 className="text-lg font-semibold text-white">Usage</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4 sm:gap-5">
          <div className="bg-slate-800/50 rounded-lg p-4 sm:p-5 text-center">
            <Search className="w-5 h-5 text-blue-400 mx-auto mb-1" />
            <p className="text-2xl font-bold text-white">
              {profile.saved_searches_count}
              <span className="text-sm text-slate-400 font-normal">
                {" "}
                /{" "}
                {profile.saved_searches_limit === 999
                  ? "∞"
                  : profile.saved_searches_limit}
              </span>
            </p>
            <p className="text-xs text-slate-400 mt-1">Saved Searches</p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4 sm:p-5 text-center">
            <FileText className="w-5 h-5 text-indigo-400 mx-auto mb-1" />
            <p className="text-2xl font-bold text-white">
              {profile.deck_count_month}
              <span className="text-sm text-slate-400 font-normal">
                {" "}
                / {profile.deck_limit == null ? "∞" : profile.deck_limit}
              </span>
            </p>
            <p className="text-xs text-slate-400 mt-1">Decks / month</p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4 sm:p-5 text-center">
            <Search className="w-5 h-5 text-purple-400 mx-auto mb-1" />
            <p className="text-2xl font-bold text-white">
              {profile.compare_count_month}
              <span className="text-sm text-slate-400 font-normal">
                {" "}
                / {profile.compare_limit == null ? "∞" : profile.compare_limit}
              </span>
            </p>
            <p className="text-xs text-slate-400 mt-1">Compare / month</p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4 sm:p-5 text-center">
            <FileText className="w-5 h-5 text-green-400 mx-auto mb-1" />
            <p className="text-2xl font-bold text-white">
              {profile.can_export ? "✓" : "✗"}
            </p>
            <p className="text-xs text-slate-400 mt-1">Export Access</p>
          </div>

          <div className="bg-slate-800/50 rounded-lg p-4 sm:p-5 text-center">
            <Star className="w-5 h-5 text-yellow-400 mx-auto mb-1" />
            <p className="text-xl font-bold text-white capitalize leading-tight [overflow-wrap:anywhere]">
              {profile.plan_tier || profile.subscription_tier}
            </p>
            <p className="text-xs text-slate-400 mt-1">Plan</p>
          </div>
        </div>
      </Card>

      {/* Admin link */}
      {profile.is_admin && (
        <Card className="p-4">
          <Button
            variant="outline"
            onClick={() => navigate("/admin")}
            className="w-full justify-center"
          >
            <Shield className="w-4 h-4 mr-2" />
            Admin Panel
          </Button>
        </Card>
      )}
    </div>
  );
}
