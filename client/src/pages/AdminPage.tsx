/**
 * Admin panel for managing users and viewing platform stats.
 */
import { useState, useEffect, useCallback } from "react";
import {
  Users,
  Crown,
  Shield,
  FileText,
  Star,
  Search,
  Loader2,
  ChevronDown,
  ChevronUp,
  Check,
} from "lucide-react";
import { Card, Button, Alert } from "../components/ui";
import { useAuthenticatedFetch } from "../hooks/useAuthenticatedApi";
import {
  fetchAdminUsers,
  fetchAdminStats,
  updateAdminUser,
  type AdminUser,
  type AdminStats,
} from "../api/profileApi";

export default function AdminPage() {
  const { authenticatedFetch } = useAuthenticatedFetch();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedUser, setExpandedUser] = useState<string | null>(null);
  const [updating, setUpdating] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const [usersData, statsData] = await Promise.all([
        fetchAdminUsers(authenticatedFetch),
        fetchAdminStats(authenticatedFetch),
      ]);
      setUsers(usersData);
      setStats(statsData);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [authenticatedFetch]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTierChange = async (userId: string, newTier: string) => {
    setUpdating(userId);
    try {
      const updated = await updateAdminUser(authenticatedFetch, userId, {
        subscription_tier: newTier,
      });
      setUsers((prev) =>
        prev.map((u) => (u.auth0_user_id === userId ? updated : u)),
      );
      setSuccessMsg(`Updated tier to ${newTier}`);
      setTimeout(() => setSuccessMsg(null), 3000);
      // Refresh stats
      const newStats = await fetchAdminStats(authenticatedFetch);
      setStats(newStats);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUpdating(null);
    }
  };

  const handleToggleAdmin = async (userId: string, currentAdmin: boolean) => {
    setUpdating(userId);
    try {
      const updated = await updateAdminUser(authenticatedFetch, userId, {
        is_admin: !currentAdmin,
      });
      setUsers((prev) =>
        prev.map((u) => (u.auth0_user_id === userId ? updated : u)),
      );
      setSuccessMsg(`Admin status ${!currentAdmin ? "granted" : "revoked"}`);
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setUpdating(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto p-6">
        <Alert variant="error">{error}</Alert>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white flex items-center gap-2">
          <Shield className="w-6 h-6 text-red-400" />
          Admin Panel
        </h1>
      </div>

      {successMsg && <Alert variant="success">{successMsg}</Alert>}

      {/* Stats Grid */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          {[
            {
              label: "Total Users",
              value: stats.total_users,
              icon: Users,
              color: "text-blue-400",
            },
            {
              label: "Paid Users",
              value: stats.paid_users,
              icon: Crown,
              color: "text-yellow-400",
            },
            {
              label: "Free Users",
              value: stats.free_users,
              icon: Star,
              color: "text-slate-400",
            },
            {
              label: "Saved Analyses",
              value: stats.total_saved_analyses,
              icon: Search,
              color: "text-green-400",
            },
            {
              label: "Decks",
              value: stats.total_decks,
              icon: FileText,
              color: "text-purple-400",
            },
            {
              label: "Watchlist Items",
              value: stats.total_watchlist_items,
              icon: Star,
              color: "text-orange-400",
            },
          ].map((stat) => (
            <Card key={stat.label} className="p-3 text-center">
              <stat.icon className={`w-5 h-5 mx-auto mb-1 ${stat.color}`} />
              <p className="text-xl font-bold text-white">{stat.value}</p>
              <p className="text-xs text-slate-400">{stat.label}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Users Table */}
      <Card className="overflow-hidden">
        <div className="p-4 border-b border-slate-700">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Users className="w-5 h-5" />
            Users ({users.length})
          </h2>
        </div>

        <div className="divide-y divide-slate-700">
          {users.map((u) => {
            const isExpanded = expandedUser === u.auth0_user_id;
            const isUpdating = updating === u.auth0_user_id;

            return (
              <div key={u.auth0_user_id}>
                {/* User row */}
                <button
                  onClick={() =>
                    setExpandedUser(isExpanded ? null : u.auth0_user_id)
                  }
                  className="w-full px-4 py-3 flex items-center gap-3 hover:bg-slate-800/50 transition-colors text-left"
                >
                  {/* Avatar */}
                  {u.picture ? (
                    <img
                      src={u.picture}
                      alt=""
                      className="w-8 h-8 rounded-full border border-slate-700"
                    />
                  ) : (
                    <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center">
                      <Users className="w-4 h-4 text-slate-400" />
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-white truncate">
                      {u.name || u.email || u.auth0_user_id}
                    </p>
                    {u.email && (
                      <p className="text-xs text-slate-400 truncate">
                        {u.email}
                      </p>
                    )}
                  </div>

                  {/* Badges */}
                  <div className="flex items-center gap-2">
                    {u.is_admin && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-red-900/50 text-red-300">
                        Admin
                      </span>
                    )}
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full capitalize ${
                        u.subscription_tier === "free"
                          ? "bg-slate-700 text-slate-300"
                          : u.subscription_tier === "pro"
                            ? "bg-yellow-900/50 text-yellow-300"
                            : "bg-purple-900/50 text-purple-300"
                      }`}
                    >
                      {u.subscription_tier}
                    </span>
                  </div>

                  {isExpanded ? (
                    <ChevronUp className="w-4 h-4 text-slate-400" />
                  ) : (
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  )}
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="px-4 pb-4 pt-2 bg-slate-800/30 space-y-3">
                    <div className="grid grid-cols-2 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-slate-400">Auth0 ID</p>
                        <p className="text-slate-300 font-mono text-xs break-all">
                          {u.auth0_user_id}
                        </p>
                      </div>
                      <div>
                        <p className="text-xs text-slate-400">Joined</p>
                        <p className="text-slate-300">
                          {new Date(u.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      {u.stripe_customer_id && (
                        <div>
                          <p className="text-xs text-slate-400">
                            Stripe Customer
                          </p>
                          <p className="text-slate-300 font-mono text-xs">
                            {u.stripe_customer_id}
                          </p>
                        </div>
                      )}
                      {u.subscription_expires_at && (
                        <div>
                          <p className="text-xs text-slate-400">
                            Subscription Expires
                          </p>
                          <p className="text-slate-300">
                            {new Date(
                              u.subscription_expires_at,
                            ).toLocaleDateString()}
                          </p>
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-700">
                      <p className="text-xs text-slate-400 w-full mb-1">
                        Change tier:
                      </p>
                      {["free", "pro", "enterprise"].map((tier) => (
                        <Button
                          key={tier}
                          size="sm"
                          variant={
                            u.subscription_tier === tier ? "primary" : "outline"
                          }
                          disabled={isUpdating || u.subscription_tier === tier}
                          onClick={() =>
                            handleTierChange(u.auth0_user_id, tier)
                          }
                        >
                          {isUpdating ? (
                            <Loader2 className="w-3 h-3 animate-spin mr-1" />
                          ) : u.subscription_tier === tier ? (
                            <Check className="w-3 h-3 mr-1" />
                          ) : null}
                          {tier}
                        </Button>
                      ))}

                      <div className="ml-auto">
                        <Button
                          size="sm"
                          variant={u.is_admin ? "danger" : "outline"}
                          disabled={isUpdating}
                          onClick={() =>
                            handleToggleAdmin(u.auth0_user_id, u.is_admin)
                          }
                        >
                          <Shield className="w-3 h-3 mr-1" />
                          {u.is_admin ? "Remove Admin" : "Make Admin"}
                        </Button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
