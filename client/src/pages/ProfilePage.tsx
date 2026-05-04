/**
 * User profile page showing account info, subscription status, and usage.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import {
  Mail,
  Calendar,
  Shield,
  FileText,
  Search,
  BarChart3,
  Download,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { Card, Button, Alert } from "../components/ui";
import { useProfileQuery } from "../queries/useProfileQuery";
import { useSubscriptionMutations } from "../queries/useSubscriptionMutations";

const DECK_EXPORT_CREDITS_PER_PURCHASE = 2;
const USAGE_PACK_COMPARE_CREDITS = 10;
const USAGE_PACK_DECK_CREDITS = 2;
const USAGE_PACK_PRICE = "$2.99";

function pluralize(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatRemaining(
  used: number,
  limit: number | null,
  unit: string,
  period?: string,
) {
  if (limit == null || limit >= 999) {
    return period ? `Unlimited ${period}` : "Unlimited";
  }

  const remaining = Math.max(limit - used, 0);
  return `${pluralize(remaining, unit)} left${period ? ` ${period}` : ""}`;
}

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
  const [pendingCheckout, setPendingCheckout] = useState<
    "deck_export" | "usage_pack" | null
  >(null);

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
  const exportCreditsLabel = profile.can_export
    ? "Included"
    : pluralize(profile.deck_export_credits, "credit");
  const exportCreditsHelp = profile.can_export
    ? "PDF/PPTX exports are included"
    : profile.deck_export_credits > 0
      ? "Use credits to unlock PDF/PPTX exports"
      : "No credits purchased yet";
  const shouldShowHigherLimitsCta =
    profile.plan_tier === "free" &&
    (profile.compare_limit !== null || profile.deck_limit !== null);
  const activeExtraUses =
    profile.extra_compare_credits > 0 || profile.extra_deck_credits > 0;
  const startCheckout = (item: "deck_export" | "usage_pack") => {
    setPendingCheckout(item);
    createCheckout(item);
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
              {profile.is_admin && (
                <span className="inline-flex items-center gap-1 rounded-md border border-red-600/60 bg-red-950/50 px-2.5 py-1 text-xs font-medium text-red-200">
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

      {/* Billing Card */}
      <Card className="p-6 space-y-4">
        <div>
          <h3 className="text-lg font-semibold text-white">
            Exports & Add-ons
          </h3>
          <p className="mt-1 text-sm text-slate-400">
            One-time purchases for exports and extra monthly research usage.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div className="bg-slate-800/50 rounded-lg p-4">
            <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">
              Export credits available
            </p>
            <p className="text-lg font-semibold text-white">
              {profile.can_export ? "Included" : profile.deck_export_credits}
            </p>
          </div>

          {shouldShowHigherLimitsCta && (
            <div className="bg-slate-800/50 rounded-lg p-4">
              <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">
                Extra uses this month
              </p>
              <p className="text-lg font-semibold text-white">
                {pluralize(profile.extra_compare_credits, "compare")}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {pluralize(profile.extra_deck_credits, "deck generation")}
              </p>
            </div>
          )}

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

        {(profile.subscription_tier === "free" && !profile.can_export) ||
        shouldShowHigherLimitsCta ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {profile.subscription_tier === "free" && !profile.can_export && (
              <div className="flex flex-col rounded-lg border border-slate-700 bg-slate-800/40 p-4">
                <div className="flex-1">
                  <Download className="mb-3 h-5 w-5 text-emerald-400" />
                  <h4 className="text-sm font-semibold text-white">
                    Export credits
                  </h4>
                  <p className="mt-1 text-sm text-slate-300">
                    Add {DECK_EXPORT_CREDITS_PER_PURCHASE} credits to unlock
                    PDF or PPTX exports for finished decks.
                  </p>
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => startCheckout("deck_export")}
                  disabled={isCreatingCheckout}
                  className="mt-4 w-full"
                >
                  {isCreatingCheckout && pendingCheckout === "deck_export" ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Add 2 Credits for $4.99
                    </>
                  )}
                </Button>
              </div>
            )}

            {shouldShowHigherLimitsCta && (
              <div className="flex flex-col rounded-lg border border-slate-700 bg-slate-800/40 p-4">
                <div className="flex-1">
                  <BarChart3 className="mb-3 h-5 w-5 text-cyan-400" />
                  <h4 className="text-sm font-semibold text-white">
                    Usage pack
                  </h4>
                  <p className="mt-1 text-sm text-slate-300">
                    Add {USAGE_PACK_COMPARE_CREDITS} company compares and{" "}
                    {USAGE_PACK_DECK_CREDITS} deck generations for this month.
                  </p>
                  {activeExtraUses && (
                    <p className="mt-2 text-xs text-slate-500">
                      Extra uses are already active on this account.
                    </p>
                  )}
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={() => startCheckout("usage_pack")}
                  disabled={isCreatingCheckout}
                  className="mt-4 w-full"
                >
                  {isCreatingCheckout && pendingCheckout === "usage_pack" ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-1 animate-spin" />
                      Loading...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="w-4 h-4 mr-1" />
                      Add More Uses for {USAGE_PACK_PRICE}
                    </>
                  )}
                </Button>
              </div>
            )}

            {checkoutError && (
              <Alert variant="error" className="md:col-span-2">
                {checkoutError}
              </Alert>
            )}
          </div>
        ) : null}

        {profile.subscription_tier === "free" && !profile.can_export && (
          <p className="text-xs text-slate-500">
            Previewing generated decks stays available without buying export
            credits.
          </p>
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
                  Manage Billing
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
        <div>
          <h3 className="text-lg font-semibold text-white">Usage</h3>
          <p className="mt-1 text-sm text-slate-400">
            Monthly activity, saved slots, and export credits for your account.
          </p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 sm:gap-5">
          <div className="rounded-lg border border-slate-800 bg-slate-800/45 p-4 sm:p-5">
            <Search className="w-5 h-5 text-blue-400 mb-4" />
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Saved searches
            </p>
            <p className="mt-2 text-2xl font-bold text-white">
              {profile.saved_searches_count} used
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {formatRemaining(
                profile.saved_searches_count,
                profile.saved_searches_limit,
                "slot",
              )}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-800/45 p-4 sm:p-5">
            <FileText className="w-5 h-5 text-indigo-400 mb-4" />
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Deck generations
            </p>
            <p className="mt-2 text-2xl font-bold text-white">
              {profile.deck_count_month} used
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {formatRemaining(
                profile.deck_count_month,
                profile.deck_limit,
                "generation",
                "this month",
              )}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-800/45 p-4 sm:p-5">
            <BarChart3 className="w-5 h-5 text-cyan-400 mb-4" />
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Company compares
            </p>
            <p className="mt-2 text-2xl font-bold text-white">
              {profile.compare_count_month} used
            </p>
            <p className="mt-1 text-sm text-slate-400">
              {formatRemaining(
                profile.compare_count_month,
                profile.compare_limit,
                "compare",
                "this month",
              )}
            </p>
          </div>

          <div className="rounded-lg border border-slate-800 bg-slate-800/45 p-4 sm:p-5">
            <Download className="w-5 h-5 text-emerald-400 mb-4" />
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Export credits
            </p>
            <p className="mt-2 text-2xl font-bold text-white">
              {exportCreditsLabel}
            </p>
            <p className="mt-1 text-sm text-slate-400">{exportCreditsHelp}</p>
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
